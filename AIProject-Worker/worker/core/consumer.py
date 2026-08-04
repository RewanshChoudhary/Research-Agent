"""
Redis Stream consumer — concurrent job processing.

Key change from the original: jobs are no longer processed serially.
Instead, each incoming message is dispatched to an asyncio.Task and the
consumer continues reading from the stream immediately.

A bounded semaphore (MAX_CONCURRENT_JOBS, default 3) prevents unbounded
memory growth when many messages arrive at once, while still keeping
multiple jobs in-flight to hide inter-stage I/O latency.

Acknowledgement happens inside the per-job wrapper so that a crash in one
job does not block the stream.
"""
import asyncio
import os
from uuid import UUID

import redis.asyncio as aioredis
import structlog
from dotenv import load_dotenv

from worker.core.orchestrator import run

load_dotenv()
log = structlog.get_logger()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_CONSUMER_GROUP = (
    os.getenv("REDIS_JOB_GROUP")
    or os.getenv("REDIS_CONSUMER_GROUP")
    or "research:workers"
)
REDIS_STREAM = (
    os.getenv("REDIS_JOB_STREAM")
    or os.getenv("REDIS_STREAM_NAME")
    or "research:jobs:stream"
)
# Maximum number of jobs running concurrently in this worker process.
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "3"))


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def extract_job_id(job_data: dict) -> str | None:
    raw_job_id = job_data.get("jobId")
    if isinstance(raw_job_id, bytes):
        raw_job_id = raw_job_id.decode()
    if not isinstance(raw_job_id, str) or not raw_job_id.strip():
        return None

    job_id = raw_job_id.strip()
    try:
        UUID(job_id)
    except ValueError:
        return None
    return job_id


async def _run_and_ack(
    r: aioredis.Redis,
    msg_id: str,
    job_id: str,
    sem: asyncio.Semaphore,
) -> None:
    """Run one job under the concurrency semaphore, then acknowledge."""
    async with sem:
        log.info("job_started", job_id=job_id, msg_id=msg_id)
        await run(job_id, redis_client=r)
    await r.xack(REDIS_STREAM, REDIS_CONSUMER_GROUP, msg_id)
    log.info("job_acknowledged", job_id=job_id, msg_id=msg_id)


async def consume(consumer_name: str) -> None:
    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    sem = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

    try:
        await r.xgroup_create(REDIS_STREAM, REDIS_CONSUMER_GROUP, id="0", mkstream=True)
    except aioredis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise

    while True:
        try:
            results = await r.xreadgroup(
                groupname=REDIS_CONSUMER_GROUP,
                consumername=consumer_name,
                streams={REDIS_STREAM: ">"},
                count=10,
                block=2000,
            )
        except Exception as e:
            if "Timeout" in str(type(e).__name__):
                log.debug("redis_read_timeout_ignoring")
                continue
            raise
        if not results:
            continue
        for stream_name, messages in results:
            for msg_id, job_data in messages:
                job_id = extract_job_id(job_data)
                if job_id is None:
                    log.warning(
                        "redis_message_missing_job_id",
                        stream=stream_name,
                        message_id=msg_id,
                        fields=job_data,
                    )
                    await r.xack(REDIS_STREAM, REDIS_CONSUMER_GROUP, msg_id)
                    continue

                # Fire-and-forget: consumer loop stays unblocked.
                asyncio.create_task(
                    _run_and_ack(r, msg_id, job_id, sem),
                    name=f"job-{job_id}",
                )


if __name__ == "__main__":
    asyncio.run(consume("worker-1"))
