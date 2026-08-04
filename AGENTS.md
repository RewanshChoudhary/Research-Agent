# Research-Agent — Project Context

## What It Is

A multi-agent AI-powered research assistant. User submits a natural-language query → system orchestrates a pipeline of agents that search the web, scrape content, summarize, fact-check, analyze, and produce a structured, cited report.

## System Architecture (6 Docker Services)

```
Frontend (nginx) → Spring Boot API (Java 25) → Redis Stream → Python Worker (asyncio)
                    ↕ PostgreSQL                    ↕ Weaviate (vector DB)
```

| Service | Tech | Role |
|---|---|---|
| `frontend` | nginx + vanilla HTML/CSS/JS | Query form, polls API for results |
| `api` | Spring Boot 4.0.3 / Java 25 | REST endpoints, JPA persistence, Redis stream publisher |
| `worker` | Python 3.14+ / asyncio | Consumes Redis stream, runs agent pipeline, reports back via HTTP |
| `postgres` | PostgreSQL 16 | Job/report/source/user persistence |
| `redis` | Redis 7 | Job queue via streams + consumer groups |
| `weaviate` | Weaviate 1.38.2 | Vector DB for HYDE (no vectorizer module — Python-side embedding) |

## Pipeline Stages (depth-dependent)

| Depth | Stages |
|---|---|
| QUICK | SEARCH → SCRAPE → SUMMARIZE → BUILD |
| STANDARD | SEARCH → SCRAPE → SUMMARIZE → FACT_CHECK → BUILD |
| DEEP | SEARCH → SCRAPE → SUMMARIZE → FACT_CHECK → ANALYZE → BUILD |

### SEARCH (`worker/agents/search.py`)
- Runs HYDE search (generate 3 hypothetical docs via LLM → embed with `all-MiniLM-L6-v2` → `nearVector` in Weaviate → deduplicate by URL → inject with +80 ranking boost)
- Decomposes query into sub-queries via LLM
- Searches DuckDuckGo for each sub-query
- Ranks results by: HYDE boost (+80), keyword matches in title (+3) / snippet (+1), snippet length bonus
- Stores ranked URL list in `ctx.urls`

### SCRAPE (`worker/agents/scraper.py`)
- Concurrent HTTP fetches via httpx (8s timeout)
- BeautifulSoup parsing: prefers `<article>`, falls back to `<main>`, then largest `<div>`
- Chunks text (configurable: 800 words, 100 overlap)
- Fire-and-forget Weaviate indexing via `asyncio.create_task(index_chunks(ctx))` — does not block pipeline
- Minimum 2 successful scrapes required (or 1 if maxSources < 2)

### SUMMARIZE (`worker/agents/summarizer.py`)
- Per-source: summarizes each chunk via LLM, merges into per-source summary
- Cross-source: synthesizes all source summaries into one balanced research summary

### FACT_CHECK (`worker/agents/fact_checker.py`)
- LLM extracts up to 12 factual claims from summary
- Each claim verified via token overlap against source texts
- Threshold: 0.70 GENERAL, 0.85 MEDICAL/LEGAL, 0.75 TECHNICAL
- Confidence = (verified / total) − (conflicts × 0.05)
- LLM generates human-readable verdict

### ANALYZE (`worker/agents/analyst.py`) — DEEP only
- LLM identifies patterns, differing perspectives (with source URLs), knowledge gaps, further reading

### BUILD (`worker/agents/report_builder.py`)
- LLM extracts 3–7 key findings
- Assembles `WorkerCompleteRequest` with all sources, metadata, fact-check, analysis

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | Spring Boot 4.0.3, Java 25, Maven |
| Worker | Python 3.14+, asyncio, Poetry (pyproject.toml) |
| Database | PostgreSQL 16 (JPA/Hibernate, ddl-auto=update) |
| Queue | Redis 7 streams + consumer groups |
| Vector DB | Weaviate 1.38.2 (no vectorizer module) |
| Embedding | `sentence-transformers/all-MiniLM-L6-v2` (384-dim, CPU) |
| LLM | OpenAI-compatible — NVIDIA NIM (llama-3.1-nemotron-70b-instruct) or Groq (llama-3.3-70b-versatile) |
| Search | DuckDuckGo via `duckduckgo_search` |
| Scraping | httpx + BeautifulSoup4 |
| Frontend | Vanilla HTML5/CSS3/JS, nginx reverse proxy |

## Project Structure

```
Research-Agent/
├── docker-compose.yml           # 6 services (postgres, redis, weaviate, api, worker, frontend)
├── .env.example                 # Template for all env vars
├── .env                         # Active config (git-ignored)
├── AGENTS.md                    # This file
│
├── AIproject/                   # === Spring Boot API ===
│   ├── pom.xml                  # Maven with spring-ai BOM 2.0.0-M2, langchain4j
│   ├── Dockerfile               # Multi-stage: eclipse-temurin:25-jdk → jre
│   └── src/main/java/com/ResearchAgent/AIproject/
│       ├── AIprojectApplication.java
│       ├── auth/WorkerInterceptor.java          # X-Worker-Token validation
│       ├── config/RedisStreamsConfig.java        # Stream + consumer group init
│       ├── controller/
│       │   ├── ClientResearchController.java    # POST /api/research/send, GET /jobs/{id}
│       │   └── WorkerJobController.java         # Internal worker callbacks
│       ├── persistence/
│       │   ├── entity/                          # JPA entities (job, report, source, user, etc.)
│       │   ├── dto/                             # Request/response DTOs
│       │   └── repository/                      # Spring Data repos
│       └── service/
│           ├── ResearchRequestService.java      # Client request logic
│           ├── WorkerJobService.java            # Worker callback handlers (transactional)
│           └── RedisJobPublisherService.java    # Publishes to Redis stream
│
├── AIProject-Worker/            # === Python Worker ===
│   ├── pyproject.toml           # Dependencies + uv.lock
│   ├── main.py                  # Entry point: asyncio.run(consume())
│   └── worker/
│       ├── enums.py             # Domain, Depth, OutputFormat, JobStatus, PipelineStage, etc.
│       ├── schemas.py           # Pydantic models for API communication
│       ├── agent_output.py      # Dataclasses: ResearchContext, FactCheckResult, etc.
│       ├── agents/
│       │   ├── search.py        # HYDE + DDGS + ranking
│       │   ├── scraper.py       # HTTP scraping + chunking + fire-and-forget indexing
│       │   ├── summarizer.py    # Chunk + per-source + merged LLM summarization
│       │   ├── fact_checker.py  # Claim extraction + token-overlap verification
│       │   ├── analyst.py       # Patterns/perspectives/gaps (DEEP only)
│       │   └── report_builder.py
│       ├── core/
│       │   ├── consumer.py      # Redis xreadgroup consumer
│       │   ├── orchestrator.py  # Stage sequencing + PATCH status
│       │   ├── llm.py           # OpenAI-compatible client (tenacity retry, 5 attempts)
│       │   ├── java_api.py      # HTTP client for API callbacks
│       │   ├── hyde.py          # Generate hypothetical docs → embed → Weaviate
│       │   └── config/domain.py # Domain-specific prompts/prefixes/thresholds
│       └── db/
│           └── collections.py   # Weaviate client + ResearchChunk schema + ChunkPayload
│
└── frontend/                    # === Static Frontend ===
    ├── index.html               # Research query form
    ├── app.js                   # Submission + polling logic
    ├── styles.css               # Dark theme
    ├── nginx.conf               # Reverse proxy /api/ → api:8080
    └── Dockerfile               # nginx:1.27-alpine
```

## Key Environment Variables

| Variable | Default | Where Used |
|---|---|---|
| `LLM_API_KEY` / `GROQ_API_KEY` | (required) | Worker LLM client |
| `LLM_BASE_URL` | `https://integrate.api.nvidia.com/v1` | Worker |
| `LLM_MODEL` | `nvidia/llama-3.1-nemotron-70b-instruct` | Worker |
| `WORKER_TOKEN` | `dev-worker-secret` | Shared auth (API validates, worker sends) |
| `WEAVIATE_URL` | `http://weaviate:8080` | Worker `collections.py` |
| `HYDE_TOP_K` | 5 | Worker `search_by_hyde()` |
| `HYDE_N_DOCS` | 3 | Worker `generate_hypothetical_docs()` |
| `HYDE_MIN_SIMILARITY` | 0.70 | Worker Weaviate search |
| `CHUNK_SIZE` | 800 | Worker scraper chunking (words) |
| `CHUNK_OVERLAP` | 100 | Worker scraper chunking |
| `REDIS_JOB_STREAM` | `research:jobs:stream` | Both worker + API |
| `REDIS_JOB_GROUP` | `research:workers` | Both |

## Key Architectural Decisions

- **Project name: Research-Agent** — Display name is `Research-Agent`. Identifiers that cannot contain hyphens use: Java/Maven `com.ResearchAgent`, Docker containers `research-agent-*`, DB credentials `researchagent`, local user email `local@research-agent.dev`.
- **Async worker**: All I/O in Python is asyncio (HTTP, Redis, LLM, embeddings)
- **Fire-and-forget Weaviate indexing**: Scraped chunks indexed in background via `asyncio.create_task()`, never blocks pipeline
- **HYDE + hybrid search**: LLM generates hypothetical answer docs → embed → `nearVector` in Weaviate → results get +80 ranking boost over DDGS results
- **Domain-aware**: Each domain (GENERAL/MEDICAL/LEGAL/TECHNICAL) has tailored system prompts, search prefixes, and fact-check thresholds configured in `config/domain.py`
- **Token-based worker auth**: `X-Worker-Token` header validated by Spring interceptor; API endpoints are internal-only (no client access)
- **Redis streams**: Reliable job queue with consumer groups + dead-letter stream
- **LLM retry**: tenacity with exponential backoff (5 attempts, 4-60s wait) for rate limits/timeouts
- **Structured logging**: structlog throughout Python worker
- **Atomic completion**: Java API uses `@Transactional` to atomically update job status + create report + save sources
- **Python-side vectorization**: Weaviate configured with `DEFAULT_VECTORIZER_MODULE: none` — embeddings generated locally with sentence-transformers

## API Endpoints

### Client-facing
| Method | Path | Returns |
|---|---|---|
| POST | `/api/research/send` | `202 Accepted` with `jobId` |
| GET | `/api/research/jobs/{jobId}` | Job status + report (if complete) |
| GET | `/api/research/jobs/{jobId}/report` | Completed report |

### Internal (worker → API, requires `X-Worker-Token`)
| Method | Path | Purpose |
|---|---|---|
| GET | `/internal/worker/jobs/{jobId}` | Fetch job details |
| PATCH | `/internal/worker/jobs/{jobId}/status` | Update progress/stage |
| POST | `/internal/worker/jobs/{jobId}/complete` | Submit completed report |
| POST | `/internal/worker/jobs/{jobId}/fail` | Report failure |

## Database Tables (PostgreSQL)

| Table | Key Columns |
|---|---|
| `users` | id (UUID), email, api_key, plan (FREE/PRO) |
| `research_jobs` | id (UUID), user_id (FK), query, domain, depth, status, current_stage, max_sources |
| `research_reports` | id (UUID), job_id (FK, UNIQUE), summary, key_findings (JSONB), confidence_score, analyst_insights (JSONB) |
| `sources` | id (UUID), job_id (FK), url, title, scrape_status, content_length, summary |
| `summary_cache` | id (UUID), url_hash (UNIQUE), url, summary, content_hash, hit_count |
| `agent_metrics` | id (UUID), job_id (FK), agent_name, duration_ms, llm_calls_made, tokens_used, success |

## Weaviate Collection

- **Name**: `ResearchChunk`
- **Vectorizer**: none (Python-side embeddings, 384-dim)
- **Properties**: chunkText, sourceUrl, domain, originalQuery, title, chunkIndex, createdAt
- **Usage**: HYDE search (pre-web-search) + background indexing from scraper

## Fixed Gotchas (dev history)

- `collections.py` `load_dotenv("COLLECTION_NAME")` → use `os.getenv("COLLECTION_NAME", "ResearchChunk")`. `load_dotenv` returns `bool`, not a string.
- `collections.py` — global `client` renamed to `_client`, lazy-init via `get_weaviate_client()`, no crash on import.
- `hyde.py` — `domain=ctx.request.domain` was enum, now `.value` to get string.
- `hyde.py` — `for idx,chunk_text in chunks` missing `enumerate()`, now fixed.
- `hyde.py` — `index_chunks()` was building payloads but never inserting, now calls `col.data.insert_many()`.
- `search.py` — `rank_and_filter_results()` gives HYDE results (`from_hyde == "true"`) an 80-point boost.
- `scraper.py` — `index_chunks()` runs fire-and-forget via `asyncio.create_task()` after scraping.
- **`ResearchRequest.java` — `@Builder.Default` has no effect when Jackson deserializes via no-args constructor + setters.** Field initializers like `= Boolean.TRUE` are applied by the no-args constructor, but `@Builder.Default` only affects Lombok's builder, not Jackson. If a field is omitted from the JSON, Jackson's setter is not called and the field retains its initializer value — UNLESS Jackson uses builder-based deserialization (which it doesn't by default here). **Fix**: For `factCheck`, made `ResearchRequestService` null-safe via `Boolean.TRUE.equals(request.getFactCheck())` instead of calling `.booleanValue()` on a potentially null `Boolean`.
- **`SourceEntity.java` — DB column `is_trusted_source` has NOT NULL constraint but entity lacked the field.** The database table `sources` has `is_trusted_source boolean NOT NULL` from a prior schema state, but `SourceEntity` had no mapping for it. When `WorkerJobService.completeJob()` inserts sources via `sourceRepository.saveAll()`, Hibernate omits the unmapped column from INSERT, causing a `PSQLException: null value in column "is_trusted_source" violates not-null constraint`. **Fix**: Added `@Builder.Default private Boolean isTrustedSource = true` field to `SourceEntity.java` with `@Column(name = "is_trusted_source", nullable = false)`.
- **Both Jackson 2.x (`com.fasterxml.jackson`) and 3.x (`tools.jackson`) on classpath.** Spring Boot 4.0.3's `spring-boot-starter-json` pulls in Jackson 3.x (`tools.jackson`), but some transitive dependencies (langchain4j, spring-ai) pull in Jackson 2.x (`com.fasterxml.jackson`). DTO imports use `com.fasterxml.jackson.annotation.JsonInclude` from Jackson 2.x, but `ResearchReportMapper` uses `tools.jackson.databind.ObjectMapper` from Jackson 3.x. Spring Boot auto-configuration resolves to Jackson 3.x for ObjectMapper, but annotations from `com.fasterxml.jackson` may work via backward-compat JARs. Potential issue if annotation behavior differs between versions.
- **Fire-and-forget Weaviate indexing uses wrong object format.** In `collections.py` when `index_chunks()` inserts data with `col.data.insert_many()`, the payload structure puts `id` and `vector` at the wrong nesting level. Weaviate warns: `id is totally forbidden as it is reserved and vector is forbidden at this level. You should use the DataObject class`. This is fire-and-forget so it doesn't block the pipeline, but chunks are never actually indexed into Weaviate, rendering HYDE search useless for follow-up queries.
