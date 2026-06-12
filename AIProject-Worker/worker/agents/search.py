import asyncio
import json
from urllib.parse import urlparse

from worker.agent_output import ResearchContext


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
    phrases = await _query_phrases(query, config, llm)

    all_results: list[dict[str, str]] = []
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


async def _query_phrases(query: str, config: dict, llm: callable) -> list[str]:
    if not _should_optimize_query(query):
        return [query]

    try:
        result = await llm(
            prompt=(
                "Convert this research question into 2 or 3 specific web search keyword phrases. "
                "Return only a JSON array of strings.\n\n"
                f"Question: {query}"
            ),
            system=config.get("system_prompt", ""),
        )
        phrases = json.loads(result.content)
        if isinstance(phrases, list):
            clean = [str(item).strip() for item in phrases if str(item).strip()]
            return clean[:5] or [query]
# Only in case of exception (Just to hint that exception is possible)
    except Exception:
        return [query]
    return [query]


def _should_optimize_query(query: str) -> bool:
    lowered = query.strip().lower()
    return (
        len(query) > 140
        or "," in query
        or lowered.endswith("?")
        or lowered.startswith((
            "what ",
            "why ",
            "how ",
            "when ",
            "where ",
            "is ",
            "are ",
            "compare ",
            "analyze ",
            "evaluate ",
            "research ",
        ))
    )


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
