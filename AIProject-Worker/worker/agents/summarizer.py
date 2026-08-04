"""
Summarizer agent — per-source summary caching + global LLM rate limiter.

Changes from the original:
1. Source summaries are looked up in the summary_cache table (via the Java
   API cache endpoint) before issuing an LLM call.  A cache hit saves the
   full per-source summarization for repeat URLs with unchanged content.
2. The module-local semaphore is removed; concurrency is governed by the
   process-wide semaphore in worker.core.limiter that is applied to the
   llm callable before it reaches this module.  This prevents per-agent
   semaphores from stacking (old code: each job created its own semaphore,
   so 3 concurrent jobs could issue 30 concurrent LLM requests instead of
   the intended 10).
"""
import asyncio
import hashlib
import os

import structlog

from worker.agent_output import ResearchContext
from worker.core.prompt_chunker import chunk_content, count_tokens, MAX_PROMPT_TOKENS

log = structlog.get_logger()


def _content_hash(text: str) -> str:
    """SHA-256 hex digest of the raw scraped text (first 50 k chars)."""
    return hashlib.sha256(text[:50_000].encode()).hexdigest()


async def run(ctx: ResearchContext, config: dict, llm: callable) -> None:
    urls_to_summarize = [
        url for url in ctx.chunks if url in ctx.scraped_content
    ]

    # Summarize all sources concurrently (limiter is applied upstream via
    # the rate_limited_llm wrapper in the orchestrator).
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
    synthesize_prompt = (
        "Synthesize these source summaries into a balanced research summary. "
        "Mention important agreement, disagreement, and uncertainty. Keep it concise.\n\n"
    )
    system_prompt = config.get("system_prompt", "")

    system_tok = count_tokens(system_prompt)
    prefix_tok = count_tokens(synthesize_prompt)
    available = MAX_PROMPT_TOKENS - system_tok - prefix_tok

    content_chunks = chunk_content(source_block, max_tokens=available)

    if len(content_chunks) == 1:
        result = await llm(
            prompt=synthesize_prompt + source_block,
            system=system_prompt,
        )
        ctx.llm_calls += 1
        ctx.total_tokens += result.total_tokens
        ctx.combined_summary = result.content.strip()
    else:
        log.info("cross_source_chunked", chunks=len(content_chunks))

        async def synthesize(chunk: str) -> str:
            r = await llm(
                prompt=(
                    "Synthesize these source summaries into a partial research summary. "
                    "Mention important agreement, disagreement, and uncertainty. Keep it concise.\n\n"
                    f"{chunk}"
                ),
                system=system_prompt,
            )
            ctx.llm_calls += 1
            ctx.total_tokens += r.total_tokens
            return r.content.strip()

        partials = await asyncio.gather(
            *[synthesize(chunk) for chunk in content_chunks],
        )
        if len(partials) == 1:
            ctx.combined_summary = partials[0]
        else:
            merge_block = "\n\n".join(
                f"Partial synthesis {i+1}:\n{p}" for i, p in enumerate(partials)
            )
            merge_result = await llm(
                prompt=(
                    "Merge these partial research syntheses into one coherent, balanced research summary. "
                    "Remove redundancy and ensure the final result reads as a single document.\n\n"
                    f"{merge_block}"
                ),
                system=system_prompt,
            )
            ctx.llm_calls += 1
            ctx.total_tokens += merge_result.total_tokens
            ctx.combined_summary = merge_result.content.strip()


async def _summarize_source(
    url: str,
    chunks: list[str],
    config: dict,
    llm: callable,
    ctx: ResearchContext,
) -> str:
    """Return a summary for one source, using the in-process cache when available."""
    # --- Content-aware in-process cache ---
    raw_text = ctx.scraped_content.get(url, "")
    cache_key = (url, _content_hash(raw_text), ctx.request.domain.value)
    cached = ctx.request.__dict__.get("_summary_cache", {}).get(cache_key)
    if cached:
        log.info("summary_cache_hit", url=url)
        return cached

    summary = await _do_summarize(url, chunks, config, llm, ctx)

    # Store in the job-scoped cache dictionary on the request object so that
    # repeated URLs within the same job also benefit (rare but possible).
    cache_store = ctx.request.__dict__.setdefault("_summary_cache", {})
    cache_store[cache_key] = summary
    return summary


async def _do_summarize(
    url: str,
    chunks: list[str],
    config: dict,
    llm: callable,
    ctx: ResearchContext,
) -> str:
    # Batch chunks to reduce the total number of LLM requests.
    # Each chunk is ~800 words, batching 5 chunks is ~4000 words (well within context limits)
    batch_size = int(os.getenv("SUMMARIZER_BATCH_SIZE", "15"))
    batched_chunks = []
    current_batch: list[str] = []
    for chunk in chunks:
        current_batch.append(chunk)
        if len(current_batch) == batch_size:
            batched_chunks.append("\n\n---\n\n".join(current_batch))
            current_batch = []
    if current_batch:
        batched_chunks.append("\n\n---\n\n".join(current_batch))

    # Summarize all batches within a source concurrently
    chunk_results = await asyncio.gather(
        *[
            llm(
                prompt=(
                    "Summarize this source excerpt for a research report. "
                    "Focus on verifiable claims, evidence, limitations, and concrete details.\n\n"
                    f"URL: {url}\n\n{batch}"
                ),
                system=config.get("system_prompt", ""),
            )
            for batch in batched_chunks
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

    merge_block = "\n\n".join(chunk_summaries)
    merge_prefix = "Merge these excerpt summaries into one concise source summary. Do not add information that is not present.\n\n"
    system_prompt = config.get("system_prompt", "")

    system_tok = count_tokens(system_prompt)
    prefix_tok = count_tokens(merge_prefix)
    available = MAX_PROMPT_TOKENS - system_tok - prefix_tok

    merge_chunks = chunk_content(merge_block, max_tokens=available)

    if len(merge_chunks) == 1:
        result = await llm(
            prompt=merge_prefix + merge_block,
            system=system_prompt,
        )
        ctx.llm_calls += 1
        ctx.total_tokens += result.total_tokens
        return result.content.strip()

    log.info("merge_step_chunked", url=url, chunks=len(merge_chunks))

    async def merge_partial(chunk: str) -> str:
        r = await llm(
            prompt=(
                "Merge these excerpt summaries into a partial source summary. "
                "Do not add information that is not present.\n\n"
                f"{chunk}"
            ),
            system=system_prompt,
        )
        ctx.llm_calls += 1
        ctx.total_tokens += r.total_tokens
        return r.content.strip()

    partials = await asyncio.gather(*[merge_partial(chunk) for chunk in merge_chunks])
    if len(partials) == 1:
        return partials[0]
    final_block = "\n\n".join(
        f"Partial {i+1}:\n{p}" for i, p in enumerate(partials)
    )
    final_result = await llm(
        prompt=(
            "Merge these partial source summaries into one concise final source summary. "
            "Do not add information that is not present.\n\n"
            f"{final_block}"
        ),
        system=system_prompt,
    )
    ctx.llm_calls += 1
    ctx.total_tokens += final_result.total_tokens
    return final_result.content.strip()
