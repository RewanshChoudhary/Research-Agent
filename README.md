# Research-Agent

> Multi-agent AI-powered research assistant — submit a natural-language query and get a structured, cited report with fact-checking and analyst insights.

## What Is It?

Research-Agent automates the end-to-end research workflow. Instead of manually searching, reading, and synthesizing information from dozens of web pages, you submit a question and it orchestrates a pipeline of AI agents to produce a comprehensive, sourced report.

The system is built around a **Spring Boot API** that receives requests, persists state in **PostgreSQL**, and queues work via **Redis Streams**. A **Python async worker** consumes jobs, runs a configurable agent pipeline, and reports results back. A **Weaviate** vector database enables semantic search via **HYDE** (Hypothetical Document Embedding), and a dark-theme **vanilla frontend** lets you submit queries and track progress in real time.

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐     ┌──────────────────┐
│  Frontend   │────▶│  Spring Boot API  │────▶│  Redis Queue │────▶│  Python Worker   │
│  (nginx)    │     │  (Java 25)        │     │  (Streams)   │     │  (asyncio)       │
│             │◀────│                   │◀────│              │◀────│                  │
└─────────────┘     └────────┬─────────┘     └──────────────┘     └────────┬─────────┘
                            │                                              │
                      ┌─────▼──────┐                                 Internal HTTP
                      │ PostgreSQL │                               callbacks (auth'd)
                      │ (jobs,     │                               PATCH /status
                      │  reports,  │                               POST /complete
                      │  sources)  │                               POST /fail
                      └────────────┘
                                                    ┌──────────────────────────┐
                                                    │        Weaviate          │
                                                    │  (vector DB, no native   │
                                                    │   vectorizer — Python-   │
                                                    │   side embeddings with   │
                                                    │   all-MiniLM-L6-v2)      │
                                                    └──────────────────────────┘
```

### Services

| Service | Tech | Role |
|---|---|---|
| `frontend` | nginx 1.27 + vanilla HTML/CSS/JS | Query form, polls API for results |
| `api` | Spring Boot 4.0.3 / Java 25 | REST endpoints, JPA persistence, Redis stream publisher |
| `worker` | Python 3.14+ / asyncio | Consumes Redis stream, runs agent pipeline, reports back via HTTP |
| `postgres` | PostgreSQL 16 | Job, report, source, and user persistence |
| `redis` | Redis 7 | Job queue via streams + consumer groups + dead-letter stream |
| `weaviate` | Weaviate 1.38.2 | Vector DB for HYDE search (no native vectorizer — Python generates embeddings) |

### Flow

1. User submits a query via the frontend or API
2. API persists the job in PostgreSQL, publishes `{jobId}` to a Redis stream
3. Worker consumes the message via `xreadgroup`, fetches full job details from the API
4. Worker runs the agent pipeline (varies by depth), patching status after each stage
5. On completion, worker POSTs the full report to the API, which atomically saves job + report + sources in a single transaction
6. Frontend polls `GET /api/research/jobs/{id}` every 2.5s and renders the result

## Agent Pipeline

| Depth | Pipeline |
|---|---|
| QUICK | Search → Scrape → Summarize → Build |
| STANDARD | Search → Scrape → Summarize → FactCheck → Build |
| DEEP | Search → Scrape → Summarize → FactCheck → Analyze → Build |

### 1. SEARCH (`agents/search.py`)
- **Query decomposition** — LLM splits the user question into retrieval sub-queries with specific purposes
- **HYDE search** — LLM generates 3 hypothetical answer docs → embedded with `all-MiniLM-L6-v2` → `nearVector` query in Weaviate → results deduplicated by URL
- **DuckDuckGo search** — Each sub-query searches DDGS for up to 10 results
- **Ranking** — HYDE results get an +80 boost; keyword matches in title (+3) and snippet (+1) add points; snippet length bonus (`min(len,240)//40`); top `maxSources` URLs selected
- **Fallback** — If search finds nothing, extracts keywords by removing stop words and retries

### 2. SCRAPE (`agents/scraper.py`)
- **Concurrent fetching** — httpx `AsyncClient` with 8s timeout, all URLs fetched in parallel via `asyncio.gather`
- **Content extraction** — BeautifulSoup: prefers `<article>`, falls back to `<main>`, then largest `<div>`; strips script/style/nav/footer/aside
- **Chunking** — Configurable word-based chunks (default: 800 words, 100 overlap)
- **Fire-and-forget indexing** — `asyncio.create_task(_index_chunks_background(ctx))` sends chunks to Weaviate without blocking the pipeline
- **Minimum threshold** — Requires at least 2 successful scrapes (or 1 if `maxSources < 2`)

### 3. SUMMARIZE (`agents/summarizer.py`)
- **Per-source** — Chunks batched in groups of 5, summarized concurrently via LLM with a semaphore (default 10 concurrent), then merged into a single per-source summary
- **Cross-source synthesis** — All source summaries concatenated; if the combined content exceeds the LLM context window it is split, partial syntheses run concurrently, then merged via a final LLM call
- **Concurrent by default** — All source summarization happens in parallel; configurable via `CONCURRENT_LLM_REQUESTS` env var

### 4. FACT CHECK (`agents/fact_checker.py`)
- **Claim extraction** — LLM extracts up to 12 specific factual claims from the combined summary; falls back to sentence splitting if LLM output is unparseable
- **Token-overlap verification** — Each claim is checked against all source texts: terms (len > 3, non-stopwords) are extracted and overlap ratio computed
- **Domain-aware thresholds** — GENERAL/OTHER: 0.70, TECHNICAL: 0.75, MEDICAL/LEGAL: 0.85
- **Confidence score** — `(verified / total) − (conflicts × 0.05)`, clamped to [0.0, 1.0]; labelled HIGH (≥0.8), MEDIUM (≥0.5), or LOW
- **Verdict** — LLM generates a 2-sentence human-readable verdict summarising verification results

### 5. ANALYZE (`agents/analyst.py`) — DEEP only
- Identifies patterns across sources, differing perspectives (with supporting source URLs), knowledge gaps, and further reading suggestions
- If source summaries exceed context window, content is chunked, analyzed in parallel, and results deduplicated via `_merge_insights`

### 6. BUILD (`agents/report_builder.py`)
- LLM extracts 3-7 key findings from the combined summary; falls back to sentence extraction
- Assembles the final `WorkerCompleteRequest` with all sources (URL, title, domain, scrape status, content length, per-source summary), metadata (total found/processed, elapsed time), fact-check results, and analyst insights

## Key Concepts

### HYDE (Hypothetical Document Embedding)
Before consulting DuckDuckGo, the search agent generates 3 hypothetical answer documents via LLM — one per distinct aspect of the query. These are embedded with `sentence-transformers/all-MiniLM-L6-v2` (384-dim, CPU) and used as `nearVector` queries in Weaviate. Retrieved results get an **+80 ranking boost**, making them surface above standard web results regardless of DDGS ranking.

### Domain-Aware Configuration
Each domain (**GENERAL**, **MEDICAL**, **LEGAL**, **TECHNICAL**, **OTHER**) has a tailored system prompt, search prefix (e.g. `"clinical study peer reviewed"` for MEDICAL), fact-check threshold (0.70/0.85/0.85/0.75/0.70), and cache TTL configured in `core/config/domain.py`.

### Redis Streams with Consumer Groups
The API publishes job IDs to a Redis stream (`research:jobs:stream`). The Python worker consumes via `xreadgroup` with a consumer group (`research:workers`), enabling multiple worker instances to process jobs concurrently without duplication. A dead-letter stream (`research:jobs:dead`) captures failed messages.

### Python-Side Vectorization
Weaviate is configured with `DEFAULT_VECTORIZER_MODULE: none`. All embeddings are generated locally in Python using `SentenceTransformer` (`all-MiniLM-L6-v2`). The `ResearchChunk` collection stores the 384-dim vector alongside chunk text, source URL, domain, original query, title, and chunk index.

### Fire-and-Forget Weaviate Indexing
After scraping, chunks are sent to Weaviate via `asyncio.create_task()` — this runs in the background and never blocks the pipeline. Future queries on similar topics benefit from previously indexed content via HYDE search.

### Chunked LLM Processing
When content exceeds the LLM context window (~7,000 tokens for the default model), it is split using `chunk_content()`. Each chunk is processed concurrently, and partial results are merged via a final LLM pass. This is used in the summarizer (cross-source), analyst, and per-source merge steps.

### LLM Retry with Tenacity
All LLM calls are wrapped with `@tenacity.retry`: exponential backoff (1× multiplier, min 4s, max 60s), 5 attempts, retrying on `RateLimitError`, `APITimeoutError`, and `APIConnectionError`.

### Atomic Completion
The Java API's `completeJob()` method is annotated with `@Transactional`. The job status update, report creation, and source persistence commit atomically — if any write fails, the entire completion is rolled back. The worker is fire-and-forget and receives no response body beyond the HTTP status code.

### Token-Based Worker Authentication
All `/internal/worker/*` endpoints are protected by `WorkerInterceptor`, which validates the `X-Worker-Token` header against a shared secret. Invalid or missing tokens receive a `401 Unauthorized` response.

### Structured Logging
The Python worker uses `structlog` throughout, with stage-level context (job ID, pipeline stage, duration) attached to every log line for traceability.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | Spring Boot 4.0.3, Java 25, Maven, Lombok |
| Worker | Python 3.14+, asyncio, uv |
| Database | PostgreSQL 16 (JPA/Hibernate, `ddl-auto=update`) |
| Queue | Redis 7 (streams + consumer groups + dead-letter) |
| Vector DB | Weaviate 1.38.2 (no native vectorizer module) |
| Embedding | `sentence-transformers/all-MiniLM-L6-v2` (384-dim, CPU) |
| LLM | OpenAI-compatible — Groq (llama-3.3-70b / llama3-groq-8b) or NVIDIA NIM |
| Search | DuckDuckGo via `duckduckgo_search` |
| Scraping | httpx + BeautifulSoup4 |
| Frontend | Vanilla HTML5/CSS3/JS, nginx 1.27-alpine |
| Container | Docker + Docker Compose |
| Observability | Spring Actuator + Prometheus, structlog (Python) |

## Quick Start

### Docker (production-like)
```bash
cp .env.example .env
# Edit .env: set GROQ_API_KEY or LLM_API_KEY
docker compose up --build
```

### Local Development (no image rebuild)
```bash
./run-local.sh          # start everything
./run-local.sh stop     # stop infra + local processes
./run-local.sh infra-only  # only postgres/redis/weaviate
```

### Services

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API | http://localhost:8080 |
| Postgres | localhost:5432 |
| Redis | localhost:6379 |
| Weaviate HTTP | localhost:8081 |
| Weaviate gRPC | localhost:50051 |

## Configuration

Key environment variables (full list in `.env.example`):

### LLM
| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | _(required)_ | Groq API key (uses llama-3.3-70b) |
| `LLM_API_KEY` | `$GROQ_API_KEY` | Fallback LLM API key |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | OpenAI-compatible base URL |
| `LLM_MODEL` | `llama3-groq-8b-8192-tool-use-preview` | Model name |
| `LLM_TIMEOUT` | `60.0` | Request timeout in seconds |

### Redis
| Variable | Default | Description |
|---|---|---|
| `REDIS_JOB_STREAM` | `research:jobs:stream` | Stream for job dispatch |
| `REDIS_JOB_GROUP` | `research:workers` | Consumer group name |
| `REDIS_DEAD_STREAM` | `research:jobs:dead` | Dead-letter stream |
| `REDIS_CONSUMER_NAME` | `worker-1` | Unique consumer ID |

### Weaviate / HYDE
| Variable | Default | Description |
|---|---|---|
| `WEAVIATE_URL` | `http://localhost:8080` | Weaviate HTTP endpoint |
| `WEAVIATE_GRPC_PORT` | `50051` | Weaviate gRPC port |
| `COLLECTION_NAME` | `ResearchChunk` | Weaviate collection name |
| `HYDE_TOP_K` | `5` | Results per vector query |
| `HYDE_N_DOCS` | `3` | Hypothetical docs to generate |
| `HYDE_MIN_SIMILARITY` | `0.70` | Minimum cosine similarity |

### Chunking
| Variable | Default | Description |
|---|---|---|
| `CHUNK_SIZE` | `800` | Words per chunk |
| `CHUNK_OVERLAP` | `100` | Overlap words between chunks |
| `CONCURRENT_LLM_REQUESTS` | `10` | Max parallel LLM calls |
| `SUMMARIZER_BATCH_SIZE` | `5` | Chunks per LLM batch |

### Auth
| Variable | Default | Description |
|---|---|---|
| `WORKER_TOKEN` | `dev-worker-secret` | Shared secret for worker→API auth |

## API Endpoints

### Client-facing

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/research/send` | Submit research query → `202 Accepted` with `jobId` and `pollUrl` |
| `GET` | `/api/research/jobs/{jobId}` | Poll job status, progress, and completed report |
| `GET` | `/api/research/jobs/{jobId}/report` | Get completed report only |

**`POST /api/research/send`** accepts:
```json
{
  "query": "string (1-500 chars)",
  "domain": "GENERAL | MEDICAL | LEGAL | TECHNICAL | OTHER",
  "depth": "QUICK | STANDARD | DEEP",
  "factCheck": true,
  "maxSources": 5,
  "outputFormat": "JSON | MARKDOWN | PLAIN"
}
```

### Internal (worker → API, requires `X-Worker-Token` header)

| Method | Path | Description |
|---|---|---|
| `GET` | `/internal/worker/jobs/{jobId}` | Fetch job details (query, domain, depth, maxSources, factCheckEnabled) |
| `PATCH` | `/internal/worker/jobs/{jobId}/status` | Update job status, current stage, progress percent |
| `POST` | `/internal/worker/jobs/{jobId}/complete` | Submit completed report with sources, fact-check, analyst data |
| `POST` | `/internal/worker/jobs/{jobId}/fail` | Report failure with error message |

## Project Structure

```
Research-Agent/
├── docker-compose.yml              # 6-service Docker Compose
├── .env.example                    # Template for all env vars
├── AGENTS.md                       # Agent context (for AI coding assistants)
├── DOCKER.md                       # Docker quick-reference
├── run-local.sh                    # Local dev launcher (no image rebuild)
│
├── AIproject/                      # === Spring Boot API ===
│   ├── pom.xml                     # Maven build (Spring Boot 4.0.3, Java 25)
│   ├── Dockerfile                  # Multi-stage: jdk → jre
│   └── src/main/java/com/ResearchAgent/AIproject/
│       ├── AIprojectApplication.java
│       ├── auth/WorkerInterceptor.java         # X-Worker-Token validation
│       ├── config/
│       │   ├── RedisStreamsConfig.java         # Stream + consumer group init
│       │   └── WebMvcConfig.java               # CORS config
│       ├── controller/
│       │   ├── ClientResearchController.java   # POST /api/research/send, GET /jobs/{id}
│       │   └── WorkerJobController.java        # Internal worker callbacks
│       ├── exception/GlobalExceptionHandler.java
│       ├── persistence/
│       │   ├── dto/                            # Request/response DTOs
│       │   │   └── enums/                     # AgentNameType, ConfidenceLabelType, etc.
│       │   ├── entity/                        # JPA entities
│       │   │   └── enums/                     # JobStatus, ResearchDepth, ResearchDomain, etc.
│       │   └── repository/                    # Spring Data repos
│       ├── service/
│       │   ├── ResearchRequestService.java    # Client request logic
│       │   ├── WorkerJobService.java          # Worker callbacks (transactional)
│       │   ├── RedisJobPublisherService.java  # Publishes to Redis stream
│       │   ├── ResearchReportMapper.java      # Entity → response DTO
│       │   ├── LocalUserService.java          # Auto-creates local user
│       │   └── RequestResponseService.java    # Helper
│       └── utils/ParsingUtils.java
│
├── AIProject-Worker/               # === Python Worker ===
│   ├── pyproject.toml              # Dependencies (uv)
│   ├── Dockerfile                  # python:3.14-slim
│   ├── main.py                     # Entry: asyncio.run(consume())
│   └── worker/
│       ├── enums.py                # Domain, Depth, JobStatus, PipelineStage, etc.
│       ├── schemas.py              # Pydantic models for API communication
│       ├── agent_output.py         # ResearchContext, FactCheckResult, AnalystInsights
│       ├── agents/
│       │   ├── search.py           # HYDE + DDGS + ranking
│       │   ├── scraper.py          # HTTP scraping + chunking + fire-and-forget indexing
│       │   ├── summarizer.py       # Chunk + per-source + merged LLM summarization
│       │   ├── fact_checker.py     # Claim extraction + token-overlap verification
│       │   ├── analyst.py          # Patterns/perspectives/gaps (DEEP only)
│       │   └── report_builder.py   # Final payload assembly
│       ├── core/
│       │   ├── consumer.py         # Redis xreadgroup consumer
│       │   ├── orchestrator.py     # Stage sequencing + PATCH status
│       │   ├── llm.py              # OpenAI-compatible client (tenacity retry, 5 attempts)
│       │   ├── java_api.py         # HTTP client for API callbacks
│       │   ├── hyde.py             # Generate hypothetical docs → embed → Weaviate
│       │   ├── json_utils.py       # JSON parsing utilities
│       │   ├── prompt_chunker.py   # Token counting + content chunking
│       │   └── config/domain.py    # Domain-specific prompts/thresholds
│       └── db/collections.py       # Weaviate client + schema + insert
│
├── frontend/                       # === Static Frontend ===
│   ├── index.html                  # Research query form
│   ├── app.js                      # Submission + polling logic (2.5s interval)
│   ├── styles.css                  # Dark theme with Inter font
│   ├── serve.js                    # Zero-dependency dev server
│   ├── nginx.conf                  # Reverse proxy /api/ → api:8080
│   └── Dockerfile                  # nginx:1.27-alpine
```

## Use Cases

- **Literature reviews** — Quickly gather and summarize information on any topic with cited sources
- **Technical research** — Compare tools, frameworks, or technologies with domain-specific prompts
- **Medical/legal research** — Stricter fact-checking thresholds and domain-tuned search prefixes
- **Competitive analysis** — Focus on authoritative sources with configurable source limits
- **Learning & exploration** — Ask open-ended questions and get structured summaries with multiple perspectives
