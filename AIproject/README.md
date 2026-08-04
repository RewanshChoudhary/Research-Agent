# Multi-Agent Research Assistant

An AI-powered research API that accepts research queries, orchestrates a multi-agent pipeline (Search → Scrape → Summarize → FactCheck → Analyze → Build), and returns structured reports with cited sources, confidence scores, and analyst insights.

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   Client     │────▶│  Spring Boot API  │────▶│   Redis Stream      │
│  (cURL/App)  │◀────│  (Phase 1,9,10)   │     │  (job queue)        │
└──────────────┘     └──────────────────┘     └──────────┬──────────┘
                                                         │
                                                         ▼
                                              ┌─────────────────────┐
                                              │  Python Worker       │
                                              │  (Phases 3-8)        │
                                              │  Agents Pipeline     │
                                              └──────────┬──────────┘
                                                         │
                                              ┌──────────▼──────────┐
                                              │  /internal/worker   │
                                              │  (status/completion) │
                                              └─────────────────────┘
```

**Spring Boot API** handles intake, auth, rate limiting, persistence, and polling.  
**Python Worker** reads jobs from Redis, runs the agent pipeline, and calls back into Spring to report results.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Spring Boot 4.0.3 (Java 25) |
| Database | PostgreSQL |
| Cache / Queue | Redis (streams + rate limiting) |
| Search | Google Custom Search API / SerpAPI |
| LLM | LangChain4j (OpenAI, Gemini) |
| Scraping | Jsoup (HTML → clean text) |
| Worker Orchestration | Python (separate service) |
| Metrics | Prometheus + Micrometer |

## Workflow

```
ResearchRequest
  → [Search Agent]     produces: List of URLs
  → [Scraper Agent]    produces: Map of URL → CleanText
  → [Summarizer Agent] produces: Map of URL → Summary + CombinedSummary
  → [FactCheck Agent]  produces: ClaimMap + ConfidenceScore + Verdict
  → [Analyst Agent]    produces: Patterns + Perspectives + Gaps (DEEP only)
  → [ReportBuilder]    produces: Final ResearchReport
  → Saved to DB
  → Returned to Client
```

### Pipeline by Depth

| Depth | Agents |
|-------|--------|
| QUICK | Search → Scrape → Summarize → BuildReport |
| STANDARD | Search → Scrape → Summarize → FactCheck → BuildReport |
| DEEP | Search → Scrape → Summarize → FactCheck → Analyze → BuildReport |

## Getting Started

### Prerequisites

- JDK 25+
- Docker (PostgreSQL + Redis)
- Python 3.12+ (worker service)

### 1. Start Infrastructure

```bash
docker run -d --name postgres -e POSTGRES_DB=research -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:17
docker run -d --name redis -p 6379:6379 redis:7
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your service credentials:
# GROQ_API_KEY, SEARCH_API_KEY, WORKER_TOKEN, etc.
```

### 3. Run Spring Boot API

```bash
./mvnw spring-boot:run
```

### 4. Run Python Worker

```bash
cd worker/
pip install -r requirements.txt
python main.py
```

## API Reference

### Client Endpoints

Client endpoints do not require an API key. The server stores jobs under a local internal user and the Python worker uses your `GROQ_API_KEY` for LLM calls.

#### Submit Research

```
POST /api/research/send

{
  "query": "effectiveness of semaglutide for weight loss",
  "domain": "MEDICAL",
  "depth": "STANDARD",
  "factCheck": true,
  "maxSources": 5,
  "outputFormat": "JSON",
  "trustedDomains": ["pubmed.ncbi.nlm.nih.gov"],
  "excludeDomains": ["reddit.com"]
}
```

Response `202 Accepted`:
```json
{
  "jobId": "uuid",
  "status": "PENDING",
  "estimatedTimeSeconds": 30,
  "pollUrl": "/api/research/jobs/uuid"
}
```

#### Poll Job Status

```
GET /api/research/jobs/{jobId}
```

Response `200 OK` (while processing):
```json
{
  "jobId": "uuid",
  "status": "PROCESSING",
  "currentStage": "SEARCHING",
  "progressPercent": 20
}
```

Response `200 OK` (when complete — includes full report):
```json
{
  "jobId": "uuid",
  "status": "COMPLETED",
  "report": {
    "reportId": "uuid",
    "summary": "...",
    "keyFindings": ["..."],
    "sources": [...],
    "factCheck": { ... },
    "analystInsights": { ... },
    "metadata": { ... }
  }
}
```

#### Get Report

```
GET /api/research/jobs/{jobId}/report
```

Returns the full report object directly (no status wrapper).

### Internal Worker Endpoints (require `X-Worker-Token` header)

Called by the Python worker — not exposed to clients.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/internal/worker/jobs/{jobId}` | Fetch job details |
| PATCH | `/internal/worker/jobs/{jobId}/status` | Update progress |
| POST | `/internal/worker/jobs/{jobId}/complete` | Submit completed report |
| POST | `/internal/worker/jobs/{jobId}/fail` | Report failure |

## Job State Machine

```
PENDING
  │ orchestrator picks it up
  ▼
PROCESSING
  │ stage: SEARCHING → SCRAPING → SUMMARIZING → FACT_CHECKING → ANALYZING → BUILDING
  │ report written successfully
  ▼
COMPLETED

  (or at any point)
  ▼
FAILED
```

## Failure Handling

| Failure Point | Behavior |
|--------------|----------|
| Search API down | Retry once, then FAILED |
| All URLs blocked by scraper | FAILED — insufficient sources |
| < 2 URLs scraped | FAILED — insufficient sources |
| LLM rate limit hit | Exponential backoff, up to 3 retries |
| LLM API down | FAILED with message |
| Single URL scrape fails | Skip URL, continue |
| Single chunk LLM fails | Skip chunk, note in report |
| FactCheck claim extraction fails | Skip FactCheck, continue with null confidence |
| Database write fails | Log error, retry once |
| Job timeout (120s) | Force FAILED, release resources |

## Project Structure

```
src/main/java/com/ResearchAgent/AIproject/
├── AIprojectApplication.java
├── auth/              # Worker token interceptor
├── config/            # WebMVC, Redis streams
├── controller/        # Client + Worker controllers
├── exception/         # Global error handling
├── persistence/
│   ├── dto/           # Request/response objects
│   ├── entity/        # JPA entities
│   └── repository/    # Spring Data repositories
├── service/           # Business logic
└── utils/             # Parsing utilities
```

## Configuration

All environment variables with defaults:

| Variable | Default | Purpose |
|----------|---------|---------|
| `WORKER_TOKEN` | `dev-worker-secret` | Shared secret for worker API |
| `REDIS_JOB_STREAM` | `research:jobs:stream` | Redis stream for job queue |
| `REDIS_JOB_GROUP` | `research:workers` | Consumer group name |
| `REDIS_DEAD_STREAM` | `research:jobs:dead` | Dead letter queue |

## License

MIT
