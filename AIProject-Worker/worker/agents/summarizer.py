from worker.agent_output import ResearchContext


async def run(ctx: ResearchContext, config: dict, llm: callable) -> None:
    for url, chunks in ctx.chunks.items():
        if url not in ctx.scraped_content:
            continue
        try:
            ctx.source_summaries[url] = await _summarize_source(url, chunks, config, llm, ctx)
        except Exception:
            continue

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
    chunk_summaries: list[str] = []
    for chunk in chunks:
        result = await llm(
            prompt=(
                "Summarize this source excerpt for a research report. "
                "Focus on verifiable claims, evidence, limitations, and concrete details.\n\n"
                f"URL: {url}\n\n{chunk}"
            ),
            system=config.get("system_prompt", ""),
        )
        ctx.llm_calls += 1
        ctx.total_tokens += result.total_tokens
        if result.content.strip():
            chunk_summaries.append(result.content.strip())

    if not chunk_summaries:
        raise RuntimeError(f"Failed to summarize source: {url}")
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
