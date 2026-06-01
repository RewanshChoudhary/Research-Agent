import json
import re

from worker.agent_output import ConflictingClaim, FactCheckResult, ResearchContext


STOP_WORDS = {
    "about", "after", "again", "also", "because", "before", "being", "between", "could",
    "from", "have", "into", "more", "most", "that", "their", "there", "these", "this",
    "those", "through", "were", "what", "when", "where", "which", "while", "with", "would",
}


async def run(ctx: ResearchContext, config: dict, llm: callable) -> None:
    if not ctx.combined_summary:
        return
    try:
        claims = await _extract_claims(ctx.combined_summary, config, llm, ctx)
    except Exception:
        return
    if not claims:
        return

    threshold = float(config.get("fact_check_threshold", 0.7))
    verified = 0
    unverified = 0
    for claim in claims:
        best = max((_token_overlap(claim, text) for text in ctx.scraped_content.values()), default=0.0)
        if best >= threshold:
            verified += 1
        else:
            unverified += 1

    confidence = calculate_confidence(verified, len(claims), 0)
    verdict = await _verdict(claims, verified, unverified, confidence, config, llm, ctx)
    ctx.fact_check = FactCheckResult(
        confidence_score=confidence,
        confidence_label=_confidence_label(confidence),
        total_claims=len(claims),
        verified_claims=verified,
        unverified_claims=unverified,
        conflicting_claims=[],
        verdict=verdict,
    )


def calculate_confidence(verified_claims: int, total_claims: int, conflicts: int) -> float:
    if total_claims <= 0:
        return 0.0
    score = verified_claims / total_claims
    score -= conflicts * 0.05
    return max(0.0, min(1.0, round(score, 3)))


async def _extract_claims(summary: str, config: dict, llm: callable, ctx: ResearchContext) -> list[str]:
    result = await llm(
        prompt=(
            "Extract up to 12 specific factual claims from this research summary. "
            "Return only a JSON array of strings.\n\n"
            f"{summary}"
        ),
        system=config.get("system_prompt", ""),
    )
    ctx.llm_calls += 1
    ctx.total_tokens += result.total_tokens
    try:
        parsed = json.loads(result.content)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()][:12]
    except json.JSONDecodeError:
        pass
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", summary) if len(sentence.split()) >= 6][:12]


async def _verdict(
    claims: list[str],
    verified: int,
    unverified: int,
    confidence: float,
    config: dict,
    llm: callable,
    ctx: ResearchContext,
) -> str:
    result = await llm(
        prompt=(
            "Write a 2 sentence fact-check verdict for this report. "
            f"Verified claims: {verified}. Unverified claims: {unverified}. Confidence: {confidence}.\n\n"
            + "\n".join(f"- {claim}" for claim in claims)
        ),
        system=config.get("system_prompt", ""),
    )
    ctx.llm_calls += 1
    ctx.total_tokens += result.total_tokens
    return result.content.strip()


def _token_overlap(claim: str, source_text: str) -> float:
    claim_terms = _terms(claim)
    if not claim_terms:
        return 0.0
    source_terms = set(_terms(source_text))
    return len([term for term in claim_terms if term in source_terms]) / len(claim_terms)


def _terms(text: str) -> list[str]:
    return [
        term for term in re.findall(r"[a-zA-Z0-9]+", text.lower())
        if len(term) > 3 and term not in STOP_WORDS
    ]


def _confidence_label(score: float) -> str:
    if score >= 0.8:
        return "HIGH"
    if score >= 0.5:
        return "MEDIUM"
    return "LOW"
