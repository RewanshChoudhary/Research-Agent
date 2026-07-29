# ResearchBuddy: Architectural & Codebase Improvements Analysis

Based on an audit of the Python worker and the overall architecture, here are prioritized suggestions to improve performance, enhance agent behaviors, and adopt optimal strategies for a mid-size project. These suggestions are aimed at avoiding over-engineering while significantly boosting reliability and speed.

---

## 1. Performance Improvements (High Priority)

> [!TIP]
> **Summary**: Reduce concurrent I/O bottlenecks and leverage large context windows to cut down LLM roundtrips.

### A. Leverage Large Context Windows to Reduce LLM Calls (`summarizer.py`)
Currently, `summarizer.py` heavily chunks scraped text (800 words/chunk) and batches them. This creates a massive fan-out of concurrent LLM requests (e.g., 5 sources × 10 chunks = 50 concurrent requests). This quickly exhausts your `asyncio.Semaphore` and hits LLM provider rate limits.
**Suggestion**: Both LLaMA 3.1 70B and Groq support massive context windows (up to 128k). Stop aggressively chunking text for summarization. Feed the entire cleaned source text into a single prompt for summarization. This transforms 50 LLM calls into just 5, drastically reducing latency, avoiding rate limits, and improving summary coherence.

### B. Replace Synchronous DuckDuckGo Search (`search.py`)
The search agent relies on the `duckduckgo_search` library running in a `ThreadPoolExecutor`. DDG heavily throttles programmatic searches, leading to timeouts and IP blocks, which introduces severe tail latency.
**Suggestion**: Migrate to a dedicated async search API (e.g., **Tavily**, **Serper**, or **Brave Search**). These APIs provide much faster, rate-limit-friendly async searches and often return better snippets without the risk of silent blocking.

### C. Eliminate Threading for Database Operations (`scraper.py`)
`_index_chunks_background` uses `asyncio.to_thread(index_chunks, ctx)` for Weaviate ingestion. Under heavy load, this can lead to thread pool exhaustion, stalling the `asyncio` event loop.
**Suggestion**: Ensure you are using the Weaviate v4 Python client's native `async` methods (e.g., asynchronous `insert_many`). This keeps your worker entirely non-blocking and memory-efficient.

---

## 2. Agent Behaviors & LLM Reliability (Medium Priority)

> [!IMPORTANT]
> **Summary**: Make agent outputs deterministic and improve fact-checking semantic accuracy.

### A. Enforce Structured Outputs via Native JSON Mode
In `search.py`, `fact_checker.py`, and `report_builder.py`, agents prompt the LLM to return JSON but rely on brittle regex parsers (`parse_json_from_llm`) to extract it. If the LLM wraps the JSON in markdown or adds conversational text, the pipeline risks falling back to less effective heuristics.
**Suggestion**: Both Groq and NVIDIA NIM (OpenAI-compatible) support native JSON mode. Add `response_format={"type": "json_object"}` to your `AsyncOpenAI` client calls in `llm.py` when expecting JSON. This guarantees valid, parseable JSON and eliminates the need for complex string manipulation.

### B. Upgrade Fact-Checking from Token Overlap to Embeddings (`fact_checker.py`)
The current fact-checker uses token overlap (`_token_overlap`) to verify claims against source texts. This is a very weak mechanism because it fails on synonyms and phrasing changes (e.g., "fasting" vs. "did not eat").
**Suggestion**: You are already using `sentence-transformers/all-MiniLM-L6-v2` for HYDE search. Reuse it here! Convert the extracted claims into embeddings and perform a cosine similarity match against the chunk embeddings. This provides robust semantic fact-checking without requiring additional LLM calls or external dependencies.

### C. Improve Web Scraping Fidelity (`scraper.py`)
Using BeautifulSoup to extract the `<article>`, `<main>`, or largest `<div>` often captures unwanted navbar text, cookie banners, or misses content in complex page structures.
**Suggestion**: Swap the custom heuristic out for a specialized extraction library like `readability-lxml` or `trafilatura`. They are heavily optimized for extracting main article content accurately and will dramatically increase the signal-to-noise ratio of the text sent to your agents.

---

## 3. Optimal Strategies for a Mid-Size Project (Strategic)

> [!NOTE]
> **Summary**: Implement resilience and observability without introducing heavy infrastructural dependencies.

### A. Add Resilience to the Java API Communication (`java_api.py`)
Your worker communicates with the Spring Boot API via HTTP calls (`patch_job_progress`, `post_report`). Currently, if the Spring Boot API drops a single connection or restarts, the worker will throw an exception and the entire multi-minute research job will fail.
**Suggestion**: Use the `tenacity` library (which you are already using in `llm.py`) to add exponential backoff retries to the `httpx` calls in `java_api.py`. This ensures your worker is resilient to brief network hiccups or backend deployments.

### B. Adopt Lightweight LLM Observability
With a pipeline this complex (HYDE -> Search -> Scrape -> Summarize -> Fact-Check -> Analyze -> Build), it becomes nearly impossible to debug *why* a final report is bad just from standard logs.
**Suggestion**: Integrate a lightweight, open-source LLM observability tool like **Langfuse** or **Phoenix**. By simply adding a decorator to `llm_complete`, you can visualize the exact prompt chains, latencies, and token usages per job. This is vital for a multi-agent system and is easy to implement without over-engineering.

### C. Remove Hardcoded Stop Words (`search.py`, `fact_checker.py`)
You are manually filtering out stop words. Modern LLMs and dense retrieval systems (like Weaviate and your sentence-transformer) actually benefit from the context provided by stop words. Removing them can distort the semantic meaning of claims and search queries.
**Suggestion**: Let the embedding models and modern search engines handle natural language directly. Remove the stop-word filtering step for a cleaner, more semantic pipeline.
