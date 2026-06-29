import asyncio
import json
from urllib.parse import urlparse

import structlog

from worker.agent_output import ResearchContext
from worker.core.hyde import search_by_hyde

log = structlog.get_logger()

template="""You are a query decomposition model.

Given a user's question:
question= {query}
1. Identify the final objective.
2. Determine which information must be retrieved.
3. Split retrieval into independent search queries.
4. Split reasoning into separate tasks.
5. Keep retrieval and reasoning separate.
6. Do not answer the question.

Output:

{
  "goal": "...",
  "retrieval_tasks": [
      {
         "query": "...",
         "purpose": "...",
         "expected_information": "..."
      }
  ],
  "reasoning_tasks":[
      ...
  ]
}"""
def domain_for(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def domain_matches(domain: str, patterns: list[str]) -> bool:
    domain = domain.lower()
    return any(domain == pattern.lower() or domain.endswith("." + pattern.lower()) for pattern in patterns)


def rank_and_filter_results(
    results: list[dict[str, str]],
    query: str,
    config: dict,
    trusted_domains: list[str],
    excluded_domains: list[str],
    max_sources: int,
) -> list[dict[str, str]]:
    trusted = [*config.get("trusted_sources", []), *trusted_domains]
    excluded = [*config.get("excluded_sources", []), *excluded_domains]
    query_words = {word.lower() for word in query.split() if len(word) > 3}
    seen: set[str] = set()
    scored: list[tuple[int, dict[str, str]]] = []

    for item in results:
        url = item.get("url", "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        domain = domain_for(url)
        if domain_matches(domain, excluded):
            continue

        title = item.get("title", "")
        snippet = item.get("snippet", "")
        haystack = f"{title} {snippet}".lower()
        score = 0
        if item.get("from_hyde") == "true":
            score += 80
        if domain_matches(domain, trusted):
            score += 100
        score += sum(3 for word in query_words if word in title.lower())
        score += sum(1 for word in query_words if word in haystack)
        score += min(len(snippet), 240) // 40
        if domain_matches(domain, ["reddit.com", "quora.com"]) and config.get("fact_check_threshold", 0.7) >= 0.85:
            score -= 50

        enriched = {**item, "domain": domain, "trusted": str(domain_matches(domain, trusted)).lower()}
        scored.append((score, enriched))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:max_sources]]


async def run(ctx: ResearchContext, config: dict, llm: callable) -> None:
    query = f"{config.get('search_prefix', '')} {ctx.request.query}".strip()

    all_results: list[dict[str, str]] = []
    try:
        hyde_results = await search_by_hyde(ctx, n=5)
        all_results.extend(hyde_results)
        log.info("hyde_retrieved", count=len(hyde_results))
    except Exception:
        log.warning("hyde_search_failed", exc_info=True)

    phrases = await _query_phrases(query, config, llm)
    for phrase in phrases:
        all_results.extend(await _search_ddg(phrase))
    if not all_results:
        for phrase in _fallback_search_phrases(query):
            all_results.extend(await _search_ddg(phrase))
            if all_results:
                break

    ranked = rank_and_filter_results(
        all_results,
        query,
        config,
        ctx.request.trustedDomains,
        ctx.request.excludeDomains,
        ctx.request.maxSources,
    )
    if not ranked:
        raise RuntimeError("No search results found")

    ctx.urls = [item["url"] for item in ranked]
    ctx.search_results = {item["url"]: item for item in ranked}

# Uses decomposition method to capture query intent
async def _query_phrases(query: str, config: dict, llm: callable) -> list[str]:
    try:
        decompose_prompt = template.format(query=query)
        result = await llm(prompt=decompose_prompt)
        parsed = json.loads(result.content)
        tasks = parsed.get("retrieval_tasks", [])
        queries = [t["query"] for t in tasks if t.get("query")]
        return queries[:5] or [query]
    except Exception:
        return [query]





def _fallback_search_phrases(query: str) -> list[str]:
    words = [word.strip(".,:;()[]{}").lower() for word in query.split()]
    stop_words = {
        "about",
        "after",
        "against",
        "also",
        "and",
        "between",
        "compare",
        "current",
        "during",
        "focusing",
        "from",
        "include",
        "including",
        "into",
        "such",
        "that",
        "the",
        "their",
        "these",
        "this",
        "with",
    }
    keywords = [word for word in words if len(word) > 3 and word not in stop_words]
    compact = " ".join(dict.fromkeys(keywords[:10]))
    return [compact] if compact else [query[:140]]


async def _search_ddg(query: str) -> list[dict[str, str]]:
    loop = asyncio.get_running_loop()

    def _sync_search() -> list[dict]:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=10))

    results = await loop.run_in_executor(None, _sync_search)
    return [
        {"url": r.get("href", ""), "title": r.get("title", ""), "snippet": r.get("body", "")}
        for r in results
    ]
