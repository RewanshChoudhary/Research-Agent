"""
Java API HTTP client — reuses a shared persistent client.

Original issue: a fresh httpx.AsyncClient was opened and closed for every
single API callback (get_job_details, patch_job_progress, post_report,
post_job_failure).  Each creation involves DNS resolution, TCP handshake,
and connection-pool setup — all wasted work when the target host never changes.

Fix: a module-level AsyncClient is created once on first use and reused for
the lifetime of the worker process.  Connection pooling is handled
automatically by httpx.
"""
import os
from contextlib import asynccontextmanager
from functools import lru_cache

import dotenv
import httpx
import structlog

from worker.schemas import (
    WorkerCompleteRequest,
    WorkerFailRequest,
    WorkerJobDetailsResponse,
    WorkerStatusUpdateRequest,
)

dotenv.load_dotenv()

log = structlog.get_logger()

JAVA_SERVER_URL = os.getenv("JAVA_SERVER_URL")
WORKER_TOKEN = os.getenv("WORKER_TOKEN", "dev-worker-secret")

_shared_client: httpx.AsyncClient | None = None


def get_java_server_url() -> str:
    if not JAVA_SERVER_URL:
        raise RuntimeError("JAVA_SERVER_URL is not set")
    return JAVA_SERVER_URL.rstrip("/")


def worker_headers() -> dict[str, str]:
    return {"X-Worker-Token": WORKER_TOKEN}


def _get_client() -> httpx.AsyncClient:
    """Return (or lazily create) the module-level shared HTTP client."""
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=10.0,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _shared_client


async def get_job_details(job_id: str) -> WorkerJobDetailsResponse:
    base_url = get_java_server_url()
    url = f"{base_url}/internal/worker/jobs/{job_id}"

    try:
        client = _get_client()
        response = await client.get(url, headers=worker_headers())
        response.raise_for_status()
        data = response.json()
        log.info(
            "job_details_fetched",
            job_id=job_id,
            url=url,
            status_code=response.status_code,
        )
        return WorkerJobDetailsResponse(**data)

    except httpx.HTTPStatusError as e:
        log.error(
            "java_server_returned_error_status",
            job_id=job_id,
            url=url,
            status_code=e.response.status_code,
            response_text=e.response.text,
        )
        raise

    except httpx.RequestError as e:
        log.error(
            "java_server_request_failed",
            job_id=job_id,
            url=url,
            error=str(e),
        )
        raise


async def patch_job_progress(
    job_id: str,
    job_progress: WorkerStatusUpdateRequest,
) -> None:
    base_url = get_java_server_url()
    url = f"{base_url}/internal/worker/jobs/{job_id}/status"
    payload = job_progress.model_dump(mode="json", exclude_none=True)

    try:
        client = _get_client()
        response = await client.patch(url, json=payload, headers=worker_headers())
        response.raise_for_status()
        log.info(
            "job_status_patched",
            job_id=job_id,
            url=url,
            status_code=response.status_code,
            status=payload.get("status"),
            current_stage=payload.get("currentStage"),
            progress_percent=payload.get("progressPercent"),
        )

    except httpx.HTTPStatusError as e:
        log.error(
            "java_server_returned_error_status",
            job_id=job_id,
            url=url,
            status_code=e.response.status_code,
            response_text=e.response.text,
        )
        raise

    except httpx.RequestError as e:
        log.error(
            "java_server_request_failed",
            job_id=job_id,
            url=url,
            error=str(e),
        )
        raise


async def post_report(job_id: str, complete_report: WorkerCompleteRequest) -> None:
    base_url = get_java_server_url()
    url = f"{base_url}/internal/worker/jobs/{job_id}/complete"
    payload = complete_report.model_dump(mode="json", exclude_none=True)

    try:
        client = _get_client()
        response = await client.post(url, json=payload, headers=worker_headers())
        response.raise_for_status()
        log.info(
            "job_completion_posted",
            job_id=job_id,
            url=url,
            status_code=response.status_code,
        )

    except httpx.HTTPStatusError as e:
        log.error(
            "java_server_returned_error_status",
            job_id=job_id,
            url=url,
            status_code=e.response.status_code,
            response_text=e.response.text,
        )
        raise

    except httpx.RequestError as e:
        log.error(
            "java_server_request_failed",
            job_id=job_id,
            url=url,
            error=str(e),
        )
        raise


async def post_job_failure(
    job_id: str,
    failure: WorkerFailRequest,
) -> None:
    base_url = get_java_server_url()
    url = f"{base_url}/internal/worker/jobs/{job_id}/fail"
    payload = failure.model_dump(mode="json", exclude_none=True)

    try:
        client = _get_client()
        response = await client.post(url, json=payload, headers=worker_headers())
        response.raise_for_status()
        log.info(
            "job_failure_posted",
            job_id=job_id,
            url=url,
            status_code=response.status_code,
            error_message=payload.get("errorMessage"),
        )

    except httpx.HTTPStatusError as e:
        log.error(
            "java_server_returned_error_status",
            job_id=job_id,
            url=url,
            status_code=e.response.status_code,
            response_text=e.response.text,
        )
        raise

    except httpx.RequestError as e:
        log.error(
            "java_server_request_failed",
            job_id=job_id,
            url=url,
            error=str(e),
        )
        raise
