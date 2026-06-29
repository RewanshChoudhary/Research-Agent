# Project Context

## HYDE (Hypothetical Document Embeddings) — Architecture

### Status
- `weaviate-client` declared and wired.
- `worker/db/collections.py` — schema defined, `ensure_collection()` written, `ChunkPayload` model matches schema.
- `worker/core/hyde.py` — complete: `generate_hypothetical_docs()`, `get_embed_model()`, `search_by_hyde()`, `index_chunks()`.
- `worker/agents/search.py` — calls `search_by_hyde()` pre-web-search, injects results with ranking boost.
- `worker/agents/scraper.py` — calls `index_chunks()` fire-and-forget after scrape completes.
- Weaviate service not yet added to `docker-compose.yml` (blocker — pipeline will fail without it).

### Vector Database
- **Weaviate** (local, no vectorizer module — `DEFAULT_VECTORIZER_MODULE: none`).
- Single collection `ResearchChunk` holds all embedded chunks across all domains. Domain stored as a property for optional filtering.

### Embedding Model
- **`sentence-transformers/all-MiniLM-L6-v2`** — 384-dim, runs on CPU, ~50 chunks/sec.
- Loaded lazily via `get_embed_model()` singleton in `hyde.py`.
- Python-side encoding (Option A): we generate vectors locally, Weaviate only stores + searches.

### Two Separate Paths

#### Path 1: Indexing (called from scraper.py after scrape completes)
- Real scraped chunks → embed → store in Weaviate.
- Fire-and-forget via `asyncio.create_task()`, does not block pipeline.
- Called once per URL after successful scrape + chunking.
- Function: `index_chunks(ctx: ResearchContext)` in `hyde.py`.

#### Path 2: HYDE Search (called from search.py, pre-web-search enrichment)
- User query → LLM generates 3-5 hypothetical documents → embed → `nearVector` search in Weaviate.
- Retrieved real chunks are aggregated, deduplicated by `sourceUrl`, and injected as enriched search results.
- Hypothetical docs are **ephemeral** — generated per-query, never stored.
- Function: `search_by_hyde(ctx, n)` in `hyde.py` — returns `list[dict[str, str]]` compatible with `rank_and_filter_results()`.

### Fixed Gotchas (as of 2026-06-29)
- `collections.py` `load_dotenv("COLLECTION_NAME")` → `os.getenv("COLLECTION_NAME", "ResearchChunk")`. `load_dotenv` returns `bool`, not a string.
- `collections.py` — global `client` renamed to `_client`, lazy-init via `get_weaviate_client()`, no crash on import.
- `hyde.py` — `create_hyde_embedddings()` split into `search_by_hyde()` and `index_chunks()`.
- `hyde.py` — `domain=ctx.request.domain` was enum, now `.value` to get string.
- `hyde.py` — `for idx,chunk_text in chunks` missing `enumerate()`, now fixed.
- `hyde.py` — `index_chunks()` was building payloads but never inserting, now calls `col.data.insert_many()`.
- `search.py` — `rank_and_filter_results()` gives HYDE results (`from_hyde == "true"`) an 80-point boost.
- `scraper.py` — `index_chunks()` runs fire-and-forget via `asyncio.create_task()` after scraping.

### Dependencies
- `sentence-transformers` (already declared)
- `weaviate-client` (already declared)
- All vectorization in Python, not via Weaviate modules.

### Configuration (needed in .env / docker-compose)
- `WEAVIATE_URL=http://weaviate:8080`
- `HYDE_TOP_K=5`
- `HYDE_N_DOCS=3`
- `HYDE_MIN_SIMILARITY=0.70`
