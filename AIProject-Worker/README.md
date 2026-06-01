# Multi-Agent Research Assistant — Complete Workflow Design

---

## Bird's Eye View

```
Client
  ↓  HTTP POST /api/research
API Layer
  ↓  validates and creates job
Orchestrator
  ↓  reads config, builds pipeline
Agent Pipeline
  ↓  Search → Scrape → Summarize → FactCheck → Analyze → Build
Persistence
  ↓  saves report
Client
  ↑  HTTP response with structured report
```

Every step below expands exactly what happens inside each of these arrows.

---

## Phase 1 — Request Intake & Validation

**Trigger:** Client sends POST /api/research

**Step 1.1 — Request Arrival** The controller receives the raw HTTP request body. Before anything else happens, the request goes through validation. The query field must not be empty. The domain must be one of the accepted enum values. The depth must be valid. Max sources must be between 1 and 20. If any validation fails, the controller immediately returns a 400 Bad Request with a descriptive error message. The orchestrator is never touched.

**Step 1.2 — Local Request Ownership** Client requests do not need an API key. The API creates jobs under an internal local user so the persistence model keeps a stable owner while the Python worker uses the server-side `GROQ_API_KEY` for LLM calls.

**Step 1.3 — Rate Limit Check** Before creating any job, check how many jobs this user has run in the last hour. FREE plan users get 10 requests per hour. PRO plan users get 100. If the user is over their limit, return 429 Too Many Requests. This check happens against Redis — it is a fast counter lookup, not a database query.

**Step 1.4 — Duplicate Detection** Check if this exact user submitted this exact query with this exact domain and depth in the last 30 minutes. If yes, return the existing cached report immediately instead of running the pipeline again. This saves API quota and improves response time significantly. The lookup key is a hash of userid + query + domain + depth.

**Step 1.5 — Job Creation** If all checks pass, create a new record in the research_jobs table with status PENDING, store all request parameters, record the created_at timestamp, and generate a job ID. Return the job ID to the client immediately with status 202 Accepted. The client now has a job ID they can use to poll for results.

**Decision point:** Synchronous or Asynchronous? For QUICK depth, run synchronously and return the result directly in the same HTTP response. For STANDARD and DEEP depth, run asynchronously and ask the client to poll. This is an important design decision because DEEP research can take 30-60 seconds.

---

## Phase 2 — Orchestrator Planning

**Trigger:** Job record created, orchestrator receives job ID

**Step 2.1 — Job Pickup** The orchestrator reads the job from the database. Updates job status from PENDING to PROCESSING. Records started_at timestamp.

**Step 2.2 — Domain Config Resolution** The orchestrator asks the DomainConfigRegistry for the config matching the request's domain. This config object now travels with every agent call for the rest of the pipeline. It carries the system prompt, trusted sources list, excluded sources list, search prefix, and strictness settings.

**Step 2.3 — Pipeline Blueprint Construction** Based on depth and domain config, the orchestrator decides exactly which agents will run and in what order:

```
QUICK pipeline:
Search → Scrape → Summarize → BuildReport

STANDARD pipeline:
Search → Scrape → Summarize → FactCheck → BuildReport

DEEP pipeline:
Search → Scrape → Summarize → FactCheck → Analyze → BuildReport
```

The orchestrator also decides at this point whether Summarize and Scrape can run with partial parallelism — multiple URLs can be scraped and summarized concurrently. This decision is recorded internally.

**Step 2.4 — Context Object Initialization** The orchestrator creates a ResearchContext object that will accumulate results as agents run. It starts empty and gets populated after each agent completes. This context object is what gets passed between agents — agents do not call each other directly. Only the orchestrator passes data between them.

---

## Phase 3 — Search Agent Execution

**Trigger:** Orchestrator calls Search Agent with query and domain config

**Step 3.1 — Query Enrichment** The raw user query is examined. If the domain config has a search prefix, it is prepended. For example a MEDICAL domain query for "metformin effectiveness" becomes "clinical study peer reviewed metformin effectiveness". This happens via a simple string operation, no LLM needed.

**Step 3.2 — LLM Query Optimization (optional)** If the query is vague or conversational (detected by checking if it is a full sentence or question), make one LLM call to convert it into 2-3 optimized search keyword phrases. For example "what do people think about remote work these days" becomes ["remote work productivity research 2024", "remote work employee satisfaction studies", "remote work policy trends companies"]. This produces significantly better search results.

**Step 3.3 — Search API Call** Each optimized query phrase is sent to the Search API. Results come back as a list of URLs with titles and snippets. Collect all results across all query variants. Remove duplicates by URL. You now have a raw list of potentially 10-30 URLs.

**Step 3.4 — URL Filtering** Apply three filters in order: First, remove any URL from the excluded domains list in the domain config. Second, if the domain config has a trusted sources list, score each URL — URLs from trusted sources go to the top. Third, apply a quality heuristic — prefer URLs that have the query keywords in the title, prefer longer snippet text, deprioritize forum sites for MEDICAL and LEGAL domains.

**Step 3.5 — URL Ranking and Trimming** After filtering, rank by the quality score computed in the previous step. Trim to max_sources count from the request (default 5, maximum 20). Create a source record in the database for each URL with status PENDING.

**Step 3.6 — Output to Context** The orchestrator receives a ranked list of URLs. Updates the research_jobs table with current_stage = SCRAPING. Passes URL list to the next agent.

**Failure handling:** If the Search API call fails, retry once after 2 seconds. If it fails again, mark the job as FAILED with error message "Search service unavailable" and stop the pipeline.

---

## Phase 4 — Scraper Agent Execution

**Trigger:** Orchestrator calls Scraper Agent with list of URLs

**Step 4.1 — Parallel Scraping** All URLs are scraped concurrently using async execution. You do not wait for one URL to finish before starting the next. All scrape requests fire at the same time.

**Step 4.2 — Per URL Scraping Flow** For each URL individually: Make HTTP GET request with a browser-like User-Agent header to avoid basic bot detection. Set a timeout of 8 seconds — if the page doesn't load in time, mark as FAILED and move on. Receive the HTML response. Use Jsoup to parse the HTML. Remove all script tags, style tags, nav elements, header elements, footer elements, and aside elements. Extract the main content — look for article tags, main tags, or the largest div block by text content. Strip all remaining HTML tags, leaving only plain text. Normalize whitespace — collapse multiple spaces and newlines. Count the character length of the resulting text.

**Step 4.3 — Content Quality Check** If extracted text is under 200 characters, the scrape is considered a failure — likely a login wall, paywall, or JavaScript-rendered page that Jsoup cannot handle. Mark the source record as BLOCKED and skip it. If extracted text is over 200 characters, mark the source record as SUCCESS and store the content length.

**Step 4.4 — Content Chunking** LLMs have token limits. Content over approximately 3000 words needs to be chunked. Split content into overlapping chunks of 800 words with a 100 word overlap between chunks. The overlap ensures context is not lost at chunk boundaries. Store the number of chunks alongside the content.

**Step 4.5 — Output to Context** Collect all successfully scraped content. If fewer than 2 URLs were successfully scraped, the job does not have enough information to continue — mark it FAILED with error "Insufficient source content". Otherwise pass content map to the next agent. Update source records in database with final scrape status.

**Failure handling:** Individual URL failures are normal and expected. The agent continues as long as at least 2 URLs succeed. Only a complete failure of all URLs stops the pipeline.

---

## Phase 5 — Summarizer Agent Execution

**Trigger:** Orchestrator calls Summarizer Agent with content map and domain config

**Step 5.1 — Cache Check** Before making any LLM calls, check the summary_cache table for each URL. The cache lookup key is the SHA-256 hash of the URL combined with the domain name. If a cache entry exists and has not expired (expires_at is in the future), use the cached summary and skip the LLM call entirely for that URL. Increment the hit_count on the cache record. Record this as a cache hit in agent metrics.

**Step 5.2 — Per Source Summarization** For each URL that was not in cache: Build the prompt using the domain config's system prompt as the base instruction. Add the source content (or each chunk if content was chunked). If content was chunked, make one LLM call per chunk to get a chunk-level summary, then make one final LLM call to merge chunk summaries into a source-level summary. If content was not chunked, make a single LLM call. Record the number of LLM calls and tokens used in agent_metrics.

**Step 5.3 — Cache Population** For every fresh summary generated, write a new entry to summary_cache with an expiry of 24 hours for GENERAL domain, 72 hours for MEDICAL and LEGAL domains (these change less frequently).

**Step 5.4 — Cross-Source Synthesis** Once all individual source summaries exist (from cache or fresh), make one final LLM call. Pass all source summaries together and instruct the LLM to synthesize them into a single coherent combined summary, noting where sources agree and where they differ. This is the most important LLM call in the entire pipeline.

**Step 5.5 — Output to Context** The orchestrator receives both the individual source summaries and the combined synthesis summary. Updates current_stage. If FactCheck is enabled in the pipeline, passes both to the Fact Checker Agent. If not, passes combined summary directly to Report Builder.

---

## Phase 6 — Fact Checker Agent Execution

**Trigger:** Orchestrator calls Fact Checker with combined summary, individual source summaries, and raw source contents

**Step 6.1 — Claim Extraction** Make one LLM call with the combined summary. Instruct the LLM to extract every individual factual claim as a JSON array of strings. A claim is any sentence that asserts something specific and verifiable — numbers, statistics, named entities, causal statements. A typical summary of 5 sources might yield 8-15 claims.

**Step 6.2 — Per Claim Verification** For each extracted claim: Compute a text similarity score between the claim and each raw source content using a token overlap approach — count how many significant words in the claim appear in the source text within a reasonable window. If the similarity score against any single source exceeds the threshold (0.70 for GENERAL, 0.85 for MEDICAL and LEGAL because these domains require higher confidence), mark the claim as VERIFIED. If no source exceeds the threshold, mark the claim as UNVERIFIED. Note which source verified each claim for the citation trail.

**Step 6.3 — Contradiction Detection** Compare claims against each other. If two claims make opposing assertions about the same subject, flag them as CONFLICTING. This is done by finding claim pairs that share the same subject entities (named entities) but have opposing sentiment or opposing factual values. This step uses a simple LLM call with both claims presented together and asked to judge if they conflict.

**Step 6.4 — Confidence Score Calculation** Confidence score = number of verified claims divided by total number of claims. If there are conflicting claims, apply a penalty — subtract 0.05 per conflict pair. Final score is clamped between 0.0 and 1.0. This is a pure mathematical operation, no LLM needed.

**Step 6.5 — Verdict Generation** Make one final LLM call. Pass the claim verification results, the conflict list, and the confidence score. Ask the LLM to write a 2-3 sentence human-readable fact check verdict. For example: "8 of 10 claims were verified across sources. 2 claims regarding specific statistics were unverified. One conflicting claim was found regarding the timeline — sources disagree on whether this occurred in 2022 or 2023."

**Step 6.6 — Output to Context** Orchestrator receives the full FactCheckResult including claim map, confidence score, conflict list, and verdict. Updates current_stage. Passes to Analyst Agent if DEEP, or to Report Builder if STANDARD.

---

## Phase 7 — Analyst Agent Execution (DEEP only)

**Trigger:** Orchestrator calls Analyst Agent with summary, fact check result, and all source summaries

**Step 7.1 — Pattern Recognition** Make one LLM call with all source summaries and the combined summary. Instruct the LLM to identify recurring themes, patterns, and trends across sources. Output should be structured as a list of pattern descriptions.

**Step 7.2 — Perspective Mapping** Make one LLM call to identify distinct perspectives or viewpoints present in the sources. Some sources may be pro, some con, some neutral on the topic. This is especially valuable for GENERAL domain research on contested topics.

**Step 7.3 — Knowledge Gap Identification** Make one LLM call asking: given what these sources cover, what important aspects of this topic are NOT addressed? What questions remain unanswered? This is genuinely valuable output that a basic summarizer never produces.

**Step 7.4 — Further Reading Suggestions** Make one LLM call to suggest 3-5 specific follow-up research directions the user could take based on the identified knowledge gaps. These are specific query suggestions, not generic advice.

**Step 7.5 — Output to Context** Orchestrator receives structured analyst insights object containing patterns, perspectives, knowledge gaps, and further reading. Passes everything to Report Builder.

---

## Phase 8 — Report Builder Agent Execution

**Trigger:** Orchestrator calls Report Builder with all accumulated context

**Step 8.1 — Data Assembly** Collect all outputs from context: combined summary, individual source summaries, fact check result with confidence score and verdict, analyst insights if present, list of all sources with their trust status and scrape status, total execution time so far, agent metrics.

**Step 8.2 — Key Findings Extraction** Make one LLM call with the combined summary and fact check result. Ask the LLM to extract 3-7 key findings as a bulleted list — these should be the most important, verified, concrete takeaways. These go into the key_findings JSONB column.

**Step 8.3 — Format Rendering** Based on the output_format requested: For JSON — structure all data into the response object directly. No formatting needed. For MARKDOWN — render the report with proper headers, bullet points, source citations as numbered references, and a confidence score badge. For PLAIN — strip all formatting and write as flowing prose paragraphs.

**Step 8.4 — Metadata Attachment** Attach all metadata to the report: query used, domain, depth, total sources found, total sources processed, total time in milliseconds, timestamp, confidence score, number of LLM calls made across all agents (from agent_metrics), total tokens consumed.

**Step 8.5 — Database Persistence** Write the final report to the research_reports table. Write all source records with their final status. Write all agent_metrics records. Update the research_jobs record to status COMPLETED with completed_at timestamp.

**Step 8.6 — Cache Full Report** Store the complete report in Redis with the duplicate detection key created back in Phase 1.2. TTL is 30 minutes — if the same query comes in within 30 minutes, skip the pipeline entirely.

**Step 8.7 — Output** Return the final report object to the orchestrator, which returns it to the controller, which sends the HTTP response to the client.

---

## Phase 9 — Response Delivery

**For synchronous requests (QUICK depth):** The controller has been holding the HTTP connection open. The final report object is serialized to JSON and returned directly in the response body with status 200 OK.

**For asynchronous requests (STANDARD and DEEP depth):** The client has been polling GET /api/research/jobs/{jobId} every 3-5 seconds. Each poll hits the database for job status. Once status is COMPLETED, the response includes the full report. The client stops polling.

**Error responses:** If any unrecoverable failure occurred, the job status is FAILED and the error message explains which agent failed and why. The client receives a structured error response, not a raw exception.

---

## Phase 10 — Post Processing

This happens after the response is delivered. The client no longer needs to wait for this.

**Metrics Recording** The MetricsService computes aggregated stats from the agent_metrics records: total pipeline time, time per agent, LLM calls per agent, cache hit rate, sources success rate. These are stored and exposed via the /actuator/prometheus endpoint.

**Cleanup Jobs** A scheduled task runs nightly to delete research_jobs and reports older than 90 days for FREE users and older than 1 year for PRO users. Another scheduled task cleans expired entries from summary_cache.

---

## Complete Failure Handling Map

|Failure Point|What Happens|
|---|---|
|Search API down|Retry once, then FAILED with message|
|All URLs blocked by scraper|FAILED — insufficient sources|
|Fewer than 2 URLs scraped|FAILED — insufficient sources|
|LLM API rate limit hit|Exponential backoff, retry up to 3 times|
|LLM API down completely|FAILED with message|
|Single URL scrape fails|Skip that URL, continue with rest|
|Single chunk summarization fails|Skip that chunk, note it in report|
|Fact check claim extraction fails|Skip fact check, continue to report with null confidence|
|Database write fails|Log error, attempt retry once|
|Job times out after 120 seconds|Force status FAILED, release resources|

## Workflow State Machine for a Job

```
PENDING
  ↓ (orchestrator picks it up)
PROCESSING
  ↓ (each stage updates current_stage field)
  SEARCHING → SCRAPING → SUMMARIZING → FACT_CHECKING → ANALYZING → BUILDING
  ↓ (report written successfully)
COMPLETED
  
  OR at any point →
  
FAILED (with error_message explaining which stage failed)
```

---

## Data Flow Summary

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

Each arrow is an orchestrator handoff. No agent touches another agent directly. The ResearchContext object accumulates everything as it flows through.

---

This workflow is complete enough to begin implementation directly. Every decision point is defined, every failure case is handled, and every database interaction is accounted for. Want me to now define the exact API contract — all request and response schemas?

  
