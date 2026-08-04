"""
Search agent — parallelised retrieval.

Changes from the original:
1. HYDE search and query-decomposition LLM call run concurrently via
   asyncio.gather instead of sequentially (saves one full LLM round-trip
   from the critical path).
2. All DuckDuckGo sub-queries are dispatched concurrently with asyncio.gather
   instead of being awaited one-by-one.
3. HYDE results are no longer given a blind +80 ranking boost.  They receive
   a smaller +20 boost and must still pass the same keyword/snippet scoring
   as web results.  This prevents stale cached content from displacing fresh
   high-quality web results when the Weaviate index is populated from prior
   queries.
"""
import asyncio
from urllib.parse import urlparse

import structlog

from worker.agent_output import ResearchContext
from worker.core.cache_service import get_cached_search, set_cached_search
from worker.core.hyde import search_by_hyde
from worker.core.json_utils import parse_json_from_llm

log = structlog.get_logger()

template = """You are a query decomposition model.

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
    max_sources: int,
) -> list[dict[str, str]]:
    query_words = {word.lower() for word in query.split() if len(word) > 3}
    seen: set[str] = set()
    scored: list[tuple[int, dict[str, str]]] = []

    for item in results:
        url = item.get("url", "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        domain = domain_for(url)

        title = item.get("title", "")
        snippet = item.get("snippet", "")
        haystack = f"{title} {snippet}".lower()
        score = 0
        # Reduced HYDE boost: results must still earn keyword relevance.
        # Previously +80; now +20 so fresh web results can outrank stale
        # cached content when they are more relevant.
        if item.get("from_hyde") == "true":
            score += 20
        score += sum(3 for word in query_words if word in title.lower())
        score += sum(1 for word in query_words if word in haystack)
        score += min(len(snippet), 240) // 40

        enriched = {**item, "domain": domain}
        scored.append((score, enriched))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:max_sources]]


async def run(ctx: ResearchContext, config: dict, llm: callable) -> None:
    query = f"{config.get('search_prefix', '')} {ctx.request.query}".strip()

    # --- P1: Parallelise HYDE search and query decomposition ---
    # Both are independent LLM/IO operations; start them simultaneously.
    if ctx.request.depth.value == "QUICK":
        async def _empty_hyde(): return []
        hyde_task = asyncio.create_task(_empty_hyde())
    else:
        hyde_task = asyncio.create_task(_safe_hyde(ctx))
    phrases_task = asyncio.create_task(_query_phrases(query, config, llm))

    hyde_results, phrases = await asyncio.gather(hyde_task, phrases_task)

    all_results: list[dict[str, str]] = list(hyde_results)
    log.info("hyde_retrieved", count=len(hyde_results))

    # --- P1: Parallelise all DuckDuckGo sub-queries ---
    # Limit sub-queries for QUICK mode to reduce LLM calls on free-tier APIs
    is_quick = ctx.request.depth.value == "QUICK"

    if phrases:
        max_phrases = 2 if is_quick else len(phrases)
        ddg_results_list = await asyncio.gather(
            *[_search_ddg(phrase, ctx.redis_client) for phrase in phrases[:max_phrases]],
            return_exceptions=True,
        )
        for res in ddg_results_list:
            if isinstance(res, Exception):
                log.warning("ddg_search_failed", error=str(res))
            else:
                all_results.extend(res)

    if not all_results:
        for phrase in _fallback_search_phrases(query):
            all_results.extend(await _search_ddg(phrase, ctx.redis_client))
            if all_results:
                break

    ranked = rank_and_filter_results(
        all_results,
        query,
        ctx.request.maxSources,
    )
    if not ranked:
        raise RuntimeError("No search results found")

    ctx.urls = [item["url"] for item in ranked]
    ctx.search_results = {item["url"]: item for item in ranked}


async def _safe_hyde(ctx: ResearchContext) -> list[dict[str, str]]:
    """Run HYDE search, returning an empty list on any failure."""
    try:
        return await search_by_hyde(ctx, n=5)
    except Exception:
        log.warning("hyde_search_failed", exc_info=True)
        return []


# Uses decomposition method to capture query intent
async def _query_phrases(query: str, config: dict, llm: callable) -> list[str]:
    try:
        decompose_prompt = template.format(query=query)
        result = await llm(prompt=decompose_prompt)
        parsed = parse_json_from_llm(result.content)
        tasks = parsed.get("retrieval_tasks", [])
        queries = [t["query"] for t in tasks if t.get("query")]
        return queries[:5] or [query]
    except Exception:
        return [query]


def _fallback_search_phrases(query: str) -> list[str]:
    words = [word.strip(".,:;()[]{}", ).lower() for word in query.split()]
    stop_words = {
        "about", "after", "against", "also", "and", "between", "compare",
        "current", "during", "focusing", "from", "include", "including",
        "into", "such", "that", "the", "their", "these", "this", "with",
    }
    keywords = [word for word in words if len(word) > 3 and word not in stop_words]
    compact = " ".join(dict.fromkeys(keywords[:10]))
    return [compact] if compact else [query[:140]]


async def _search_ddg(query: str, redis_client=None) -> list[dict[str, str]]:
    # Check Redis cache first
    cached = await get_cached_search(redis_client, query)
    if cached is not None:
        return cached

    loop = asyncio.get_running_loop()

    def _sync_search() -> list[dict]:
        from ddgs import DDGS

        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=10))

    results = await loop.run_in_executor(None, _sync_search)
    formatted = [
        {"url": r.get("href", ""), "title": r.get("title", ""), "snippet": r.get("body", "")}
        for r in results
    ]
    await set_cached_search(redis_client, query, formatted)
    return formatted
