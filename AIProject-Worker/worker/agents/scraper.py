import asyncio
import re

import httpx
import structlog
from bs4 import BeautifulSoup

from worker.agent_output import ResearchContext
from worker.core.hyde import index_chunks
from worker.enums import SourceStatus

log = structlog.get_logger()

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)


async def run(ctx: ResearchContext, config: dict, llm: callable) -> None:  # pyright: ignore[reportGeneralTypeIssues]
    del config, llm
    async with httpx.AsyncClient(
        timeout=8.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    ) as client:
        results = await asyncio.gather(
            *[_scrape_url(client, url) for url in ctx.urls], return_exceptions=True
        )

    for url, result in zip(ctx.urls, results, strict=False):
        if isinstance(result, Exception):
            ctx.scrape_status[url] = SourceStatus.FAILED.value
            continue
        text, title = result
        if len(text) < 200:
            ctx.scrape_status[url] = SourceStatus.BLOCKED.value
            continue
        ctx.scraped_content[url] = text
        ctx.scrape_status[url] = SourceStatus.SUCCESS.value
        ctx.chunks[url] = chunk_text(text)
        if title and url in ctx.search_results:
            ctx.search_results[url]["title"] = title

    asyncio.create_task(_index_chunks_background(ctx))

    minimum = 2 if ctx.request.maxSources >= 2 else 1
    if len(ctx.scraped_content) < minimum:
        raise RuntimeError("Insufficient source content")


async def _index_chunks_background(ctx: ResearchContext) -> None:
    try:
        index_chunks(ctx)
        log.info("chunks_indexed", chunk_count=sum(len(v) for v in ctx.chunks.values()))
    except Exception:
        log.warning("chunk_indexing_failed", exc_info=True)


async def _scrape_url(client: httpx.AsyncClient, url: str) -> tuple[str, str | None]:
    response = await client.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else None
    text = extract_main_text(soup)
    return text, title


def extract_main_text(soup: BeautifulSoup) -> str:
    for tag in soup(
        ["script", "style", "nav", "header", "footer", "aside", "noscript"]
    ):
        tag.decompose()

    main = soup.find("article") or soup.find("main") or _largest_text_div(soup)
    text = main.get_text(" ", strip=True) if main else soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def _largest_text_div(soup: BeautifulSoup):
    divs = soup.find_all("div")
    if not divs:
        return None
    return max(divs, key=lambda tag: len(tag.get_text(" ", strip=True)))


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    words = text.split()
    if not words:
        return []
    if len(words) <= chunk_size:
        return [" ".join(words)]

    chunks: list[str] = []
    start = 0
    step = max(1, chunk_size - overlap)
    while start < len(words):
        chunks.append(" ".join(words[start : start + chunk_size]))
        start += step
    return chunks
