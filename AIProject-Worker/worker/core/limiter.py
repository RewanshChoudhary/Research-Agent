"""
Process-wide LLM rate limiter — free-tier aware.

Combines two guards:
1. A concurrency semaphore (LLM_GLOBAL_CONCURRENCY, default 2) — prevents
   bursting more than N simultaneous in-flight requests.
2. A token-bucket RPM limiter (LLM_MAX_RPM, default 25) — proactively sleeps
   for sub-second intervals rather than hammering the provider into a 429 and
   waiting 4-60 s for tenacity exponential back-off.

Defaults are tuned for free-tier Groq / NVIDIA NIM:
  - llama-3.3-70b-versatile: 30 RPM / 6 000 TPM (free)
  - llama-3.1-nemotron-70b:  10 RPM on NIM free tier
Set LLM_MAX_RPM=0 to disable the RPM guard (e.g. paid tier).
"""

import asyncio
import collections
import os
import time

import structlog

log = structlog.get_logger()

_global_llm_sem: asyncio.Semaphore | None = None

# Ring-buffer of request timestamps for sliding-window RPM tracking.
_request_times: collections.deque[float] = collections.deque()
_rpm_lock: asyncio.Lock | None = None


def get_llm_semaphore() -> asyncio.Semaphore:
    """Return (or lazily create) the process-wide concurrency semaphore."""
    global _global_llm_sem
    if _global_llm_sem is None:
        limit = int(os.getenv("LLM_GLOBAL_CONCURRENCY", "2"))
        _global_llm_sem = asyncio.Semaphore(limit)
    return _global_llm_sem


def _get_rpm_lock() -> asyncio.Lock:
    global _rpm_lock
    if _rpm_lock is None:
        _rpm_lock = asyncio.Lock()
    return _rpm_lock


async def _wait_for_rpm_slot() -> None:
    """Block until we are under the configured RPM cap using a sliding 60s window."""
    max_rpm = int(os.getenv("LLM_MAX_RPM", "25"))
    if max_rpm <= 0:
        return  # disabled

    async with _get_rpm_lock():
        now = time.monotonic()
        # Evict timestamps older than 60 s.
        while _request_times and now - _request_times[0] >= 60.0:
            _request_times.popleft()

        if len(_request_times) >= max_rpm:
            # Oldest request in the window; sleep until it falls out.
            sleep_for = 60.0 - (now - _request_times[0]) + 0.05
            log.debug(
                "rpm_limit_sleeping",
                current_rpm=len(_request_times),
                max_rpm=max_rpm,
                sleep_s=round(sleep_for, 2),
            )
            await asyncio.sleep(max(sleep_for, 0.05))

        _request_times.append(time.monotonic())


async def limited_llm_call(llm_fn, *args, **kwargs):
    """Wrap any llm callable with the global concurrency + RPM rate limiter."""
    await _wait_for_rpm_slot()
    async with get_llm_semaphore():
        return await llm_fn(*args, **kwargs)
