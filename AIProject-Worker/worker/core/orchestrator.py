"""
Orchestrator — per-stage latency instrumentation + global LLM rate limiter.

Changes from the original:
1. Each stage's wall-clock duration is measured and stored in ctx.agent_metrics.
   This populates the AgentMetric dataclass that previously existed but was
   never written to.
2. The llm callable passed to every agent is wrapped by the process-wide
   semaphore from worker.core.limiter, so all in-flight jobs share one
   rate budget and never pile up concurrent LLM requests that trigger
   provider-side 429s and the expensive tenacity backoff.
3. The redundant final PATCH (status=COMPLETED) that was issued after
   post_report is removed — the Java API's completeJob() already sets
   the job status atomically, so the extra round-trip was a no-op at best
   and a race at worst.
"""
import asyncio
import time
from collections.abc import Awaitable, Callable

import structlog

from worker.agent_output import AgentMetric, ResearchContext
from worker.agents import analyst, fact_checker, report_builder, scraper, search, summarizer
from worker.core.config.domain import resolve_config
from worker.core.java_api import get_job_details, patch_job_progress, post_job_failure, post_report
from worker.core.limiter import limited_llm_call
from worker.core.llm import llm_complete
from worker.enums import Depth, JobStatus, PipelineStage
from worker.schemas import WorkerFailRequest, WorkerStatusUpdateRequest, WorkerJobDetailsResponse

log = structlog.get_logger()
Agent = Callable[[ResearchContext, dict, callable], Awaitable[None]]


def build_pipeline(depth: Depth, fact_check_enabled: bool) -> list[tuple[PipelineStage, Agent, int]]:
    pipeline: list[tuple[PipelineStage, Agent, int]] = [
        (PipelineStage.SEARCHING, search.run, 10),
        (PipelineStage.SCRAPING, scraper.run, 25),
        (PipelineStage.SUMMARIZING, summarizer.run, 55),
    ]
    # QUICK mode skips fact-check entirely to save 2 LLM calls on free-tier APIs.
    if depth == Depth.QUICK:
        log.debug("pipeline_fact_check_skipped", reason="QUICK depth")
    elif fact_check_enabled:
        pipeline.append((PipelineStage.FACT_CHECKING, fact_checker.run, 75))
    if depth == Depth.DEEP:
        pipeline.append((PipelineStage.ANALYZING, analyst.run, 88))
    pipeline.append((PipelineStage.BUILDING, report_builder.run, 95))
    return pipeline


async def run_job(job_id: str, redis_client=None) -> None:
    start = time.monotonic()
    log.info("orchestrator_started", job_id=job_id)

    request: WorkerJobDetailsResponse = await get_job_details(job_id)
    config = resolve_config(request.domain)
    pipeline = build_pipeline(request.depth, request.factCheckEnabled)
    ctx = ResearchContext(request=request, redis_client=redis_client)

    # Wrap the LLM function with the process-wide rate limiter so that
    # concurrent jobs share one concurrency budget.
    async def rate_limited_llm(*args, **kwargs):
        return await limited_llm_call(llm_complete, *args, **kwargs)

    llm_start_tokens = ctx.total_tokens

    for stage, agent, progress in pipeline:
        await patch_job_progress(
            job_id,
            WorkerStatusUpdateRequest(
                status=JobStatus.PROCESSING,
                currentStage=stage,
                progressPercent=progress,
            ),
        )
        log.info("stage_started", job_id=job_id, stage=stage.value)
        stage_start = time.monotonic()
        llm_calls_before = ctx.llm_calls
        tokens_before = ctx.total_tokens
        stage_success = True
        try:
            await agent(ctx, config, rate_limited_llm)
        except Exception:
            stage_success = False
            raise
        finally:
            stage_ms = int((time.monotonic() - stage_start) * 1000)
            ctx.agent_metrics[stage.value] = AgentMetric(
                duration_ms=stage_ms,
                llm_calls_made=ctx.llm_calls - llm_calls_before,
                tokens_used=ctx.total_tokens - tokens_before,
                success=stage_success,
            )
            log.info(
                "stage_finished",
                job_id=job_id,
                stage=stage.value,
                duration_ms=stage_ms,
                llm_calls=ctx.llm_calls - llm_calls_before,
                tokens=ctx.total_tokens - tokens_before,
            )

    elapsed_ms = int((time.monotonic() - start) * 1000)
    report = report_builder.build_worker_request(ctx, elapsed_ms)
    # post_report atomically marks the job COMPLETED inside the Java API —
    # no follow-up PATCH needed.
    await post_report(job_id, report)
    log.info("job_completed", job_id=job_id, elapsed_ms=elapsed_ms)


async def run(job_id: str, redis_client=None) -> None:
    try:
        await run_job(job_id, redis_client)
    except Exception as exc:
        log.exception("job_failed", job_id=job_id)
        await post_job_failure(job_id, WorkerFailRequest(errorMessage=str(exc)))
