import os

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


def get_java_server_url() -> str:
    if not JAVA_SERVER_URL:
        raise RuntimeError("JAVA_SERVER_URL is not set")

    return JAVA_SERVER_URL.rstrip("/")


def worker_headers() -> dict[str, str]:
    return {"X-Worker-Token": WORKER_TOKEN}


async def get_job_details(job_id: str) -> WorkerJobDetailsResponse:
    base_url = get_java_server_url()
    url = f"{base_url}/internal/worker/jobs/{job_id}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
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
        async with httpx.AsyncClient(timeout=10.0) as client:
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
        async with httpx.AsyncClient(timeout=10.0) as client:
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
        async with httpx.AsyncClient(timeout=10.0) as client:
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
