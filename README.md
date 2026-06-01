# ResearchBuddy

<!--toc:start-->

- [ResearchBuddy](#researchbuddy)
  - [Why ResearchBuddy?](#why-researchbuddy)
  - [Architecture](#architecture)
  - [Agent Pipeline](#agent-pipeline)
  - [Use Cases](#use-cases)
  - [Tech Stack](#tech-stack)
  - [Quick Start](#quick-start)
  - [Configuration](#configuration)
  - [API Endpoints](#api-endpoints)
  - [Project Structure](#project-structure)
  <!--toc:end-->

A multi-agent AI-powered research assistant that accepts natural-language queries and produces structured, cited reports with fact-checking and analyst insights. Instead of manually searching, reading, and synthesizing information from dozens of web pages, you submit a question and ResearchBuddy orchestrates a pipeline of AI agents to do the work for you.

## Why ResearchBuddy?

- **Save hours of manual research** — Automates the entire research workflow: web search, content scraping, summarization, fact-checking, and analysis.
- **Structured, cited reports** — Every source is tracked and linked. No more lost bookmarks or forgotten where you read something.
- **Configurable depth** — Choose between QUICK (summary only), STANDARD (with fact-checking), or DEEP (with analytical insights including patterns, perspectives, and knowledge gaps).
- **Domain-aware** — Tailored prompts and trust thresholds for GENERAL, MEDICAL, LEGAL, and TECHNICAL domains.
- **Source control** — Whitelist trusted domains and blacklist unreliable ones to improve result quality.

## Architecture

```
┌──────────┐     ┌──────────────────┐     ┌──────────────┐     ┌───────────────┐
│          │     │                  │     │              │     │               │
│ Frontend │────▶│  Spring Boot API │────▶│  Redis Queue │────▶│ Python Worker │
│ (nginx)  │     │  (Java 25)       │     │  (Streams)   │     │ (asyncio)     │
│          │◀────│                  │◀────│              │◀────│               │
└──────────┘     └─────────┬────────┘     └──────────────┘     └───────────────┘
                           │                                              │
                           │                                              │
                     ┌─────▼──────┐                                Internal HTTP
                     │ PostgreSQL │                              callbacks (auth'd)
                     │  (Job/Report│                              ────────────────
                     │   storage)  │                              PATCH /status
                     └────────────┘                              POST /complete
                                                                  POST /fail
```

The system is composed of four services orchestrated via Docker Compose:

- **Spring Boot API** — Receives research requests, persists job/report state in PostgreSQL, queues work via Redis streams, and exposes internal callbacks for the worker.
- **Python Worker** — Consumes jobs from Redis, runs an async agent pipeline, and reports results back to the API via authenticated HTTP callbacks.
- **Frontend** — Static HTML/CSS/JS served by nginx, proxies API calls, and polls for job completion.
- **PostgreSQL + Redis** — Database for job/report storage and Redis streams for async job dispatch.

## Agent Pipeline

| Depth    | Pipeline                                                   |
| -------- | ---------------------------------------------------------- |
| QUICK    | Search → Scrape → Summarize → Report                       |
| STANDARD | Search → Scrape → Summarize → FactCheck → Report           |
| DEEP     | Search → Scrape → Summarize → FactCheck → Analyze → Report |

Each stage:

1. **SEARCH** — Optionally decomposes the query into keyword phrases via LLM, searches DuckDuckGo, ranks results by domain trust and relevance, deduplicates by URL.
2. **SCRAPE** — Concurrently fetches and parses HTML via httpx + BeautifulSoup, extracts main content, chunks into overlapping segments.
3. **SUMMARIZE** — Summarizes each chunk per-source via LLM, merges chunk summaries per source, then synthesizes a balanced research summary noting agreements and disagreements.
4. **FACT CHECK** — Extracts factual claims from the summary, verifies each via token overlap against source texts, computes a confidence score, and generates a verdict.
5. **ANALYZE** (DEEP only) — Identifies patterns, differing perspectives (with supporting source URLs), knowledge gaps, and further reading suggestions.
6. **BUILD** — Extracts key findings and assembles the final report payload with all sources, metadata, and optional fact-check / analyst sections.

## Use Cases

- **Literature reviews** — Quickly gather and summarize information on any topic.
- **Technical research** — Compare tools, frameworks, or technologies with cited sources.
- **Medical/legal research** — Domain-specific prompts and stricter fact-checking thresholds.
- **Competitive analysis** — Use trusted/excluded domain lists to focus on authoritative sources.
- **Learning & exploration** — Ask open-ended questions and get structured summaries with multiple perspectives.

## Tech Stack

| Layer       | Technology                                                      |
| ----------- | --------------------------------------------------------------- |
| Backend API | Spring Boot 4.0.3, Java 25, Maven                               |
| Worker      | Python 3.14+, asyncio, Poetry                                   |
| Database    | PostgreSQL 16                                                   |
| Queue/Cache | Redis 7 (streams + consumer groups)                             |
| LLM         | OpenAI-compatible API (default: Groq / llama-3.3-70b-versatile) |
| Search      | DuckDuckGo                                                      |
| Scraping    | httpx + BeautifulSoup4                                          |
| Frontend    | Vanilla HTML5, CSS3, JavaScript, nginx                          |
| Container   | Docker, Docker Compose                                          |

## Quick Start

```bash
cp .env.example .env
# Edit .env and set GROQ_API_KEY
docker compose up --build
```

| Service  | URL                   |
| -------- | --------------------- |
| Frontend | <http://localhost:3000> |
| API      | <http://localhost:8080> |

Open the frontend, enter a research question, configure options (domain, depth, max sources, output format, fact-check toggle, trusted/excluded domains), and submit. The UI polls for completion and displays the full report.

## Configuration

Key environment variables (see `.env.example` for full list):

| Variable           | Default                   | Description                |
| ------------------ | ------------------------- | -------------------------- |
| `GROQ_API_KEY`     | _(required)_              | LLM API key                |
| `LLM_MODEL`        | `llama-3.3-70b-versatile` | LLM model name             |
| `WORKER_TOKEN`     | `dev-worker-secret`       | Shared auth for worker→API |
| `DB_NAME`          | `researchbuddy`           | PostgreSQL database        |
| `REDIS_PORT`       | `6379`                    | Redis port                 |
| `REDIS_JOB_STREAM` | `research:jobs:stream`    | Redis stream name          |

## API Endpoints

**Client-facing:**

- `POST /api/research/send` — Submit a research query (returns `202 Accepted` with `jobId`)
- `GET /api/research/jobs/{jobId}` — Poll job status and report
- `GET /api/research/jobs/{jobId}/report` — Get completed report

**Internal (worker → API, requires `X-Worker-Token`):**

- `GET /internal/worker/jobs/{jobId}` — Fetch job details
- `PATCH /internal/worker/jobs/{jobId}/status` — Update progress
- `POST /internal/worker/jobs/{jobId}/complete` — Submit report
- `POST /internal/worker/jobs/{jobId}/fail` — Report failure

## Project Structure

```
ResearchBuddy/
├── docker-compose.yml              # 4-service orchestration
├── .env.example                    # Environment variable template
├── DOCKER.md                       # Docker setup notes
│
├── AIproject/                      # Spring Boot backend (Java 25)
│   ├── pom.xml                     # Maven build config
│   ├── Dockerfile
│   └── src/
│       ├── main/java/com/ResearchBuddy/AIproject/
│       │   ├── AIprojectApplication.java
│       │   ├── auth/               # X-Worker-Token validation
│       │   ├── config/             # Redis streams + web MVC config
│       │   ├── controller/         # Client + worker REST controllers
│       │   ├── exception/          # Global error handling
│       │   ├── persistence/
│       │   │   ├── dto/            # Request/response DTOs
│       │   │   ├── entity/         # JPA entities (job, report, source, etc.)
│       │   │   └── repository/     # Spring Data repositories
│       │   ├── service/            # Business logic
│       │   └── utils/
│       └── test/
│
├── AIProject-Worker/               # Python async worker
│   ├── pyproject.toml              # Poetry project config
│   ├── Dockerfile
│   ├── main.py                     # Entry point
│   └── worker/
│       ├── enums.py                # Shared enums
│       ├── schemas.py              # Pydantic models
│       ├── agent_output.py         # Data classes
│       ├── agents/
│       │   ├── search.py           # DuckDuckGo + ranking
│       │   ├── scraper.py          # HTTP scraping + parsing
│       │   ├── summarizer.py       # Chunked LLM summarization
│       │   ├── fact_checker.py     # Claim verification
│       │   ├── analyst.py          # Pattern/perspective analysis
│       │   └── report_builder.py   # Final payload assembly
│       ├── core/
│       │   ├── consumer.py         # Redis stream consumer
│       │   ├── orchestrator.py     # Pipeline runner
│       │   ├── llm.py              # LLM client (retry logic)
│       │   ├── java_api.py         # Java API HTTP client
│       │   └── config/
│       │       └── domain.py       # Domain-specific prompts/thresholds
│       └── tests/
│
├── frontend/                       # Static frontend (nginx)
│   ├── index.html                  # Research query form
│   ├── app.js                      # Submission + polling logic
│   ├── styles.css                  # UI styles
│   ├── nginx.conf                  # Reverse proxy config
│   └── Dockerfile
│
└── target/                         # Maven build output
```
