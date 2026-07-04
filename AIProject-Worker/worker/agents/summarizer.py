import asyncio

import structlog

from worker.agent_output import ResearchContext

log = structlog.get_logger()


async def run(ctx: ResearchContext, config: dict, llm: callable) -> None:
    urls_to_summarize = [
        url for url in ctx.chunks if url in ctx.scraped_content
    ]

    # Summarize all sources concurrently instead of sequentially
    results = await asyncio.gather(
        *[_summarize_source(url, ctx.chunks[url], config, llm, ctx) for url in urls_to_summarize],
        return_exceptions=True,
    )

    for url, result in zip(urls_to_summarize, results, strict=False):
        if isinstance(result, Exception):
            log.warning("source_summary_failed", url=url, error=str(result))
            continue
        ctx.source_summaries[url] = result

    if not ctx.source_summaries:
        raise RuntimeError("No source summaries could be generated")

    source_block = "\n\n".join(
        f"Source: {url}\nSummary: {summary}" for url, summary in ctx.source_summaries.items()
    )
    result = await llm(
        prompt=(
            "Synthesize these source summaries into a balanced research summary. "
            "Mention important agreement, disagreement, and uncertainty. Keep it concise.\n\n"
            f"{source_block}"
        ),
        system=config.get("system_prompt", ""),
    )
    ctx.combined_summary = result.content.strip()
    ctx.llm_calls += 1
    ctx.total_tokens += result.total_tokens


async def _summarize_source(
    url: str,
    chunks: list[str],
    config: dict,
    llm: callable,
    ctx: ResearchContext,
) -> str:
    # Summarize all chunks within a source concurrently
    chunk_results = await asyncio.gather(
        *[
            llm(
                prompt=(
                    "Summarize this source excerpt for a research report. "
                    "Focus on verifiable claims, evidence, limitations, and concrete details.\n\n"
                    f"URL: {url}\n\n{chunk}"
                ),
                system=config.get("system_prompt", ""),
            )
            for chunk in chunks
        ],
        return_exceptions=True,
    )

    chunk_summaries: list[str] = []
    for res in chunk_results:
        if isinstance(res, Exception):
            log.warning("chunk_summary_failed", url=url, error=str(res))
            continue
        ctx.llm_calls += 1
        ctx.total_tokens += res.total_tokens
        if res.content.strip():
            chunk_summaries.append(res.content.strip())

    if not chunk_summaries:
        raise RuntimeError(f"Failed to summarize any chunks for source: {url}")
    if len(chunk_summaries) == 1:
        return chunk_summaries[0]

    result = await llm(
        prompt=(
            "Merge these excerpt summaries into one concise source summary. "
            "Do not add information that is not present.\n\n"
            + "\n\n".join(chunk_summaries)
        ),
        system=config.get("system_prompt", ""),
    )
    ctx.llm_calls += 1
    ctx.total_tokens += result.total_tokens
    return result.content.strip()
