import json

from worker.agent_output import ResearchContext
from worker.enums import SourceStatus
from worker.schemas import WorkerCompleteRequest, WorkerSourceItem
from worker.agents.search import domain_for


async def run(ctx: ResearchContext, config: dict, llm: callable) -> None:
    if not ctx.combined_summary:
        ctx.combined_summary = "No summary could be generated from the available sources."

    findings = await _key_findings(ctx, config, llm)
    ctx.key_findings = findings or _fallback_findings(ctx.combined_summary)


def build_worker_request(ctx: ResearchContext, elapsed_ms: int) -> WorkerCompleteRequest:
    sources = []
    for url in ctx.urls:
        metadata = ctx.search_results.get(url, {})
        status = ctx.scrape_status.get(url, SourceStatus.SKIPPED.value)
        sources.append(
            WorkerSourceItem(
                url=url,
                title=metadata.get("title"),
                domainName=metadata.get("domain") or domain_for(url),
                scrapeStatus=SourceStatus(status),
                contentLength=len(ctx.scraped_content.get(url, "")) or None,
                summary=ctx.source_summaries.get(url),
                trustedSource=metadata.get("trusted") == "true",
            )
        )

    return WorkerCompleteRequest(
        summary=ctx.combined_summary or "No summary could be generated.",
        keyFindings=ctx.key_findings or _fallback_findings(ctx.combined_summary or ""),
        sources=sources,
        totalSourcesFound=len(ctx.urls),
        totalSourcesProcessed=len(ctx.source_summaries),
        totalTimeMs=elapsed_ms,
        factCheck=_fact_check_payload(ctx),
        analystInsights=_analyst_payload(ctx),
    )


async def _key_findings(ctx: ResearchContext, config: dict, llm: callable) -> list[str]:
    try:
        result = await llm(
            prompt=(
                "Extract 3 to 7 concise key findings from this research summary. "
                "Return only a JSON array of strings.\n\n"
                f"{ctx.combined_summary}"
            ),
            system=config.get("system_prompt", ""),
        )
        ctx.llm_calls += 1
        ctx.total_tokens += result.total_tokens
        parsed = json.loads(result.content)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()][:7]
    except Exception:
        return []
    return []


def _fallback_findings(summary: str) -> list[str]:
    sentences = [item.strip() for item in summary.replace("\n", " ").split(".") if item.strip()]
    findings = [sentence + "." for sentence in sentences[:7]]
    while len(findings) < 3:
        findings.append("The report is based on the successfully processed source material.")
    return findings[:7]


def _fact_check_payload(ctx: ResearchContext) -> dict | None:
    if not ctx.fact_check:
        return None
    return {
        "confidenceScore": ctx.fact_check.confidence_score,
        "confidenceLabel": ctx.fact_check.confidence_label,
        "totalClaims": ctx.fact_check.total_claims,
        "verifiedClaims": ctx.fact_check.verified_claims,
        "unverifiedClaims": ctx.fact_check.unverified_claims,
        "conflictingClaims": [claim.model_dump(mode="json") for claim in ctx.fact_check.conflicting_claims],
        "verdict": ctx.fact_check.verdict,
    }


def _analyst_payload(ctx: ResearchContext) -> dict | None:
    if not ctx.analyst_insights:
        return None
    return {
        "patterns": ctx.analyst_insights.patterns,
        "perspectives": [
            {
                "viewpoint": item.viewpoint,
                "description": item.description,
                "supportingSourceUrls": item.supporting_source_urls,
            }
            for item in ctx.analyst_insights.perspectives
        ],
        "knowledgeGaps": ctx.analyst_insights.knowledge_gaps,
        "furtherReadingSuggestions": ctx.analyst_insights.further_reading,
    }
