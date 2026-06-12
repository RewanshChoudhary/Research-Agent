import asyncio
import time
from collections.abc import Awaitable, Callable

import structlog

from worker.agent_output import ResearchContext
from worker.agents import analyst, fact_checker, report_builder, scraper, search, summarizer
from worker.core.config.domain import resolve_config
from worker.core.java_api import get_job_details, patch_job_progress, post_job_failure, post_report
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
    if depth != Depth.QUICK and fact_check_enabled:
        pipeline.append((PipelineStage.FACT_CHECKING, fact_checker.run, 75))
    if depth == Depth.DEEP:
        pipeline.append((PipelineStage.ANALYZING, analyst.run, 88))
    pipeline.append((PipelineStage.BUILDING, report_builder.run, 95))
    return pipeline


async def run_job(job_id: str) -> None:
    start = time.monotonic()
    log.info("orchestrator_started", job_id=job_id)

    request: WorkerJobDetailsResponse = await get_job_details(job_id)
    config = resolve_config(request.domain)
    pipeline = build_pipeline(request.depth, request.factCheckEnabled)
    ctx = ResearchContext(request=request)

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
        await agent(ctx, config, llm_complete)
        log.info("stage_finished", job_id=job_id, stage=stage.value)

    elapsed_ms = int((time.monotonic() - start) * 1000)
    report = report_builder.build_worker_request(ctx, elapsed_ms)
    await post_report(job_id, report)
    await patch_job_progress(
        job_id,
        WorkerStatusUpdateRequest(
            status=JobStatus.COMPLETED,
            currentStage=PipelineStage.BUILDING,
            progressPercent=100,
        ),
    )
    log.info("job_completed", job_id=job_id, elapsed_ms=elapsed_ms)


async def run(job_id: str) -> None:
    try:
        await asyncio.wait_for(run_job(job_id), timeout=120)
    except asyncio.TimeoutError:
        log.error("job_timed_out", job_id=job_id)
        await post_job_failure(job_id, WorkerFailRequest(errorMessage="Job timed out after 120 seconds"))
    except Exception as exc:
        log.exception("job_failed", job_id=job_id)
        await post_job_failure(job_id, WorkerFailRequest(errorMessage=str(exc)))
