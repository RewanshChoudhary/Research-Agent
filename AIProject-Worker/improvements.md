# Research-Agent Worker — Performance Optimisation Log

This document describes every optimisation applied to reduce time-to-result
for the Research-Agent worker pipeline, the rationale behind each change, and
the accuracy safeguards that accompany it.

---

## Priority ranking

| Priority | Change | Expected impact |
|---|---|---|
| P0 | Per-stage latency & token instrumentation | Enables                   job_id=e25ed484-1d7c-4d60-87eb-187f79da0836 stage=summarizingevidence-based tuning |
| P1 | Concurrent job processing | Hides queue-wait for concurrent users |
| P1 | Parallelise search (HYDE + decomposition + DDG) | Saves ≥ 1 LLM round-trip on critical path |
| P1 | Model-context alignment | Eliminates expensive retry storms |
| P1 | Global LLM rate limiter | Prevents provider 429s and 4-60 s back-off |
| P1 | In-process summary cache | Eliminates repeat LLM work for repeat URLs |
| P2 | Reuse HTTP client | Eliminates per-callback TCP/TLS setup |
| P2 | Remove redundant status PATCH | Saves one HTTP round-trip per job |
| P2 | Faster frontend polling + single report fetch | Reduces perceived latency by up to 2.5 s |

---

## P0 — Per-stage latency instrumentation

**File changed:** `worker/core/orchestrator.py`

**What:** Every pipeline stage now records wall-clock duration (`duration_ms`),
LLM call count (`llm_calls_made`), and token consumption (`tokens_used`) into
`ctx.agent_metrics[stage.value]`.  The `AgentMetric` dataclass existed before
this change but was never populated.

**Why it reduces time-to-result:** Instrumentation itself does not save time,
but it is the prerequisite for evidence-based tuning.  Without stage-level
data it is impossible to know which stage dominates latency or whether a
change actually improved p50/p95.

**Accuracy safeguard:** Pure observation; no research logic changed.

---

## P1 — Concurrent job processing

**File changed:** `worker/core/consumer.py`

**What:** The consumer loop previously awaited `process_job()` inline, so each
job had to complete the entire pipeline before the next message was even read
from the stream.  Now each message is dispatched as an `asyncio.Task` and the
loop continues reading immediately.  A `asyncio.Semaphore(MAX_CONCURRENT_JOBS,
default 3)` bounds the number of jobs executing simultaneously so memory and
LLM budget do not grow without limit.

**Why it reduces time-to-result:** Users who submit jobs while another is
running previously waited for the full pipeline of the earlier job before
their job even started.  With concurrent dispatch, multiple pipelines overlap
their I/O-heavy stages (scraping, LLM calls) instead of queuing.

**Tuning:** Set `MAX_CONCURRENT_JOBS` in `.env`.  Start at 3 and lower if
you observe LLM rate-limit errors; raise if the LLM provider allows higher
throughput.

**Accuracy safeguard:** Each job's `ResearchContext` is fully isolated; there
is no shared mutable state between jobs.

---

## P1 — Parallelise search-stage operations

**File changed:** `worker/agents/search.py`

**What (three sub-changes):**

1. **HYDE + query decomposition run concurrently.**  Previously `search_by_hyde`
   completed before the LLM decomposition call even started.  Now both are
   launched with `asyncio.create_task` and collected with `asyncio.gather`,
   saving one sequential LLM round-trip from the critical path.

2. **All DDG sub-queries run concurrently.**  The original loop `for phrase in
   phrases: await _search_ddg(phrase)` searched DuckDuckGo serially.  Now all
   phrases are gathered in parallel, reducing search-stage wall time by roughly
   `(N-1) × DDG_latency`.

3. **HYDE ranking boost reduced from +80 to +20.**  The fixed +80 boost meant
   that any HYDE result automatically outranked every fresh web result regardless
   of relevance.  This could make the system *faster* at the cost of accuracy
   by reusing stale previously scraped content.  The reduced +20 boost lets
   HYDE results participate in ranking without displacing genuinely more relevant
   fresh pages.

**Accuracy safeguards:**
- The full candidate pool (HYDE + all DDG sub-queries) is retained.
- Ranking still uses keyword-in-title (+3), keyword-in-snippet (+1), and snippet
  length bonuses alongside the reduced HYDE signal.
- HYDE results that are genuinely topically close will still rank highly through
  keyword overlap.

---

## P1 — Model-context alignment

**File changed:** `worker/core/prompt_chunker.py`

**What:** `MAX_CONTEXT_TOKENS` previously defaulted to `128 000`.  The Compose
default model is `llama3-groq-8b-8192-tool-use-preview` which has an 8 192-token
context window.  Sending 128 k-sized prompts to an 8 k model causes the provider
to truncate the prompt silently *or* raise a context-exceeded error — triggering
the tenacity retry loop with 4-60 s exponential waits per attempt, up to five
times.  The new default is `8 192` with `RESERVED_OUTPUT_TOKENS` lowered from
`4 000` to `1 024` (appropriate for the short outputs this model produces), giving
`7 168` usable prompt tokens.

**Tuning:** Set `MAX_CONTEXT_TOKENS=128000` and `RESERVED_OUTPUT_TOKENS=4000` in
`.env` when using a large-context model (llama-3.3-70b-versatile, Nemotron-70b).

**Accuracy safeguard:** The `chunk_content` function correctly splits oversized
prompts, so no content is silently dropped; chunked summarisation is already
implemented for all stages.

---

## P1 — Process-wide LLM rate limiter

**Files changed:** `worker/core/limiter.py` (new), `worker/core/orchestrator.py`

**What:** A new module `worker/core/limiter.py` provides a single
`asyncio.Semaphore` shared across every agent in every concurrent job.  The
orchestrator wraps `llm_complete` in `limited_llm_call()` before passing it
to each agent.  The summarizer's own per-agent semaphore was removed because
it stacked multiplicatively with the global one (3 jobs × 10 per-job = 30
concurrent requests instead of the intended limit).

**Why it reduces time-to-result:** Uncontrolled concurrency causes provider-side
429 rate-limit responses, which trigger the tenacity retry with 4-60 s
exponential back-off per attempt (up to 5 attempts = up to 5 minutes of wasted
wall time in the worst case).  A shared limiter keeps in-flight LLM requests
below the threshold.

**Tuning:** Set `LLM_GLOBAL_CONCURRENCY` in `.env`.  Start at 5 (Groq free tier),
raise to 15-20 for paid tiers or NVIDIA NIM.

---

## P1 — In-process summary cache

**File changed:** `worker/agents/summarizer.py`

**What:** Before issuing LLM calls for a source URL, the summarizer checks an
in-process dict keyed on `(url, sha256(scraped_text[:50k]), domain)`.  A cache
hit returns the existing summary without any LLM interaction.

**Why it reduces time-to-result:** Repeat queries that land on the same popular
source URLs (e.g., Wikipedia, major news outlets) previously triggered identical
LLM summarisation work for every job.  A cache hit saves the entire per-source
summarisation cost — typically 1-4 LLM calls and several seconds.

**Accuracy safeguards:**
- The cache key includes a content hash of the scraped text, so a changed page
  automatically gets a fresh summary.
- The cache key includes domain (research domain — GENERAL/MEDICAL/etc.) so
  domain-specific system prompts do not bleed across.
- The cache is in-process (not persisted), so a worker restart always starts
  with a fresh cache.

> **Note:** The `summary_cache` PostgreSQL table and Spring repositories exist
> but are not wired from the Python side.  The in-process cache provides
> meaningful benefit within a long-running worker session without requiring
> additional API endpoints.  Wiring the DB-backed cache is a future improvement.

---

## P2 — Reuse HTTP client across callbacks

**File changed:** `worker/core/java_api.py`

**What:** The original code opened a new `httpx.AsyncClient(...)` context
manager for every API callback (get_job_details, patch_job_progress,
post_report, post_job_failure), closing and discarding it immediately after.
A module-level `_shared_client` is now created once on first use and reused
for the lifetime of the process.  Connection pooling is handled automatically
by httpx.

**Why it reduces time-to-result:** Each `AsyncClient` creation involves at
minimum a new connection establishment (TCP + TLS handshake to the Java API),
adding 5-50 ms per callback.  With 5+ callbacks per job this accumulates to
25-250 ms of wasted network setup per pipeline run.

**Accuracy safeguard:** HTTP semantics are unchanged; only the connection
lifecycle is affected.

---

## P2 — Remove redundant completion PATCH

**File changed:** `worker/core/orchestrator.py`

**What:** After calling `post_report()` the original orchestrator issued a
follow-up `patch_job_progress(status=COMPLETED, ...)`.  The Java API's
`completeJob()` method is `@Transactional` and already sets the job status to
`COMPLETED` atomically as part of persisting the report.  The extra PATCH was
therefore a redundant no-op at best and a race condition at worst.

**Why it reduces time-to-result:** Saves one HTTP round-trip (≈ 5-50 ms) at
the end of every pipeline.

---

## P2 — Faster frontend polling + single report fetch

**File changed:** `frontend/app.js`

**What (two sub-changes):**

1. **Polling interval reduced from 2 500 ms to 1 000 ms.**  The previous
   interval meant up to 2.5 seconds elapsed between job completion and the
   user seeing the result.  At 1 000 ms the average wait is 500 ms.

2. **Report fetched only once.**  When `status.status === "COMPLETED"`, the
   status response from `/api/research/jobs/{jobId}` already includes the full
   report object in `status.report` (if the Java API embeds it).  When the
   field is present the result is rendered immediately without a second request
   to `/api/research/jobs/{jobId}/report`.  If the field is absent the existing
   fallback fetch is preserved.

**Accuracy safeguard:** If the Java API does not embed the report in the status
response the code falls back to the original explicit `/report` fetch, so there
is no regression if the Spring side is not updated.

---

## New environment variables

These can be set in `.env` or overridden per-environment:

| Variable | Default | Description |
|---|---|---|
| `MAX_CONTEXT_TOKENS` | `8192` | Context window of deployed LLM model |
| `RESERVED_OUTPUT_TOKENS` | `1024` | Tokens reserved for model output |
| `LLM_GLOBAL_CONCURRENCY` | `5` | Max in-flight LLM requests process-wide |
| `MAX_CONCURRENT_JOBS` | `3` | Max research jobs running simultaneously |

---

## What was deliberately NOT changed

| Area | Reason |
|---|---|
| Scraper concurrency | Already concurrent via `asyncio.gather`; bounded by URL count |
| Summarizer `asyncio.gather` per source | Correctly parallel; kept as-is |
| Fact-checker claim verification | CPU-only token overlap; not a bottleneck |
| HYDE hypothetical doc generation | Single LLM call; parallel to decomposition now |
| Weaviate fire-and-forget indexing | Background; does not affect pipeline latency |
| PostgreSQL `summary_cache` table wiring | Left as future work to avoid adding new API endpoints |
