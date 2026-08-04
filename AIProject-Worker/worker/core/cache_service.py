"""
Redis search result cache.

Caches DuckDuckGo results per query string with a configurable TTL
(default 1 hour). This is especially important on free-tier APIs where
repeated test runs of the same query waste time and can trip provider limits.

Set DDG_CACHE_TTL=0 to disable caching entirely.
"""
import hashlib
import json
import os

import structlog

log = structlog.get_logger()

DDG_CACHE_TTL = int(os.getenv("DDG_CACHE_TTL", "3600"))  # seconds; 0 = disabled
_CACHE_PREFIX = "ddg:query:"


def _cache_key(query: str) -> str:
    digest = hashlib.sha256(query.lower().strip().encode()).hexdigest()[:24]
    return f"{_CACHE_PREFIX}{digest}"


async def get_cached_search(redis_client, query: str) -> list[dict] | None:
    """Return cached results for *query*, or None on cache miss / disabled."""
    if DDG_CACHE_TTL <= 0 or redis_client is None:
        return None
    try:
        raw = await redis_client.get(_cache_key(query))
        if raw:
            log.debug("ddg_cache_hit", query=query[:60])
            return json.loads(raw)
    except Exception:
        log.warning("ddg_cache_get_failed", query=query[:60], exc_info=True)
    return None


async def set_cached_search(redis_client, query: str, results: list[dict]) -> None:
    """Store *results* for *query* with the configured TTL."""
    if DDG_CACHE_TTL <= 0 or redis_client is None or not results:
        return
    try:
        await redis_client.setex(_cache_key(query), DDG_CACHE_TTL, json.dumps(results))
        log.debug("ddg_cache_set", query=query[:60], count=len(results), ttl=DDG_CACHE_TTL)
    except Exception:
        log.warning("ddg_cache_set_failed", query=query[:60], exc_info=True)
