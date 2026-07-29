import asyncio
import json

import structlog

from worker.agent_output import AnalystInsights, Perspective, ResearchContext
from worker.core.json_utils import parse_json_from_llm
from worker.core.prompt_chunker import chunk_content, count_tokens, MAX_PROMPT_TOKENS

log = structlog.get_logger()


async def run(ctx: ResearchContext, config: dict, llm: callable) -> None:
    if not ctx.combined_summary:
        return
    system_prompt = config.get("system_prompt", "")
    source_block = "\n\n".join(
        f"{url}\n{summary}" for url, summary in ctx.source_summaries.items()
    )
    analysis_prompt = (
        "Analyze this research material. Return only JSON with keys: "
        "patterns (array of strings), perspectives (array of objects with viewpoint, description, "
        "supporting_source_urls), knowledge_gaps (array of strings), further_reading (array of strings). "
        "Do not wrap the JSON in markdown code fences.\n\n"
        f"Combined summary:\n{ctx.combined_summary}\n\nSource summaries:\n"
    )

    system_tok = count_tokens(system_prompt)
    prefix_tok = count_tokens(analysis_prompt)
    available = MAX_PROMPT_TOKENS - system_tok - prefix_tok

    content_chunks = chunk_content(source_block, max_tokens=available)

    if len(content_chunks) == 1:
        result = await llm(
            prompt=analysis_prompt + source_block,
            system=system_prompt,
        )
        ctx.llm_calls += 1
        ctx.total_tokens += result.total_tokens
        ctx.analyst_insights = _parse_insights(result.content)
        return

    log.info("analyst_chunked", chunks=len(content_chunks))
    async def analyze(chunk: str) -> AnalystInsights:
        r = await llm(
            prompt=analysis_prompt + chunk,
            system=system_prompt,
        )
        ctx.llm_calls += 1
        ctx.total_tokens += r.total_tokens
        return _parse_insights(r.content)

    partials = await asyncio.gather(*[analyze(chunk) for chunk in content_chunks])
    ctx.analyst_insights = _merge_insights(partials)


def _merge_insights(insights: list[AnalystInsights]) -> AnalystInsights:
    seen_patterns: set[str] = set()
    seen_gaps: set[str] = set()
    seen_reading: set[str] = set()
    all_patterns: list[str] = []
    all_gaps: list[str] = []
    all_reading: list[str] = []
    all_perspectives: list[Perspective] = []

    for ins in insights:
        for p in ins.patterns:
            key = p.lower().strip()
            if key not in seen_patterns:
                seen_patterns.add(key)
                all_patterns.append(p)
        for g in ins.knowledge_gaps:
            key = g.lower().strip()
            if key not in seen_gaps:
                seen_gaps.add(key)
                all_gaps.append(g)
        for r in ins.further_reading:
            key = r.lower().strip()
            if key not in seen_reading:
                seen_reading.add(key)
                all_reading.append(r)
        all_perspectives.extend(ins.perspectives)

    return AnalystInsights(
        patterns=all_patterns,
        perspectives=all_perspectives,
        knowledge_gaps=all_gaps,
        further_reading=all_reading,
    )


def _parse_insights(content: str) -> AnalystInsights:
    try:
        data = parse_json_from_llm(content)
    except Exception:
        data = {}

    perspectives = []
    for item in data.get("perspectives", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue
        perspectives.append(
            Perspective(
                viewpoint=str(item.get("viewpoint", "")),
                description=str(item.get("description", "")),
                supporting_source_urls=[
                    str(url) for url in item.get("supporting_source_urls", [])
                ],
            )
        )

    return AnalystInsights(
        patterns=_string_list(data.get("patterns", []))
        if isinstance(data, dict)
        else [],
        perspectives=perspectives,
        knowledge_gaps=_string_list(data.get("knowledge_gaps", []))
        if isinstance(data, dict)
        else [],
        further_reading=_string_list(data.get("further_reading", []))
        if isinstance(data, dict)
        else [],
    )


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
