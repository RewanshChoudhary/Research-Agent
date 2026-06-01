import json

from worker.agent_output import AnalystInsights, Perspective, ResearchContext


async def run(ctx: ResearchContext, config: dict, llm: callable) -> None:
    if not ctx.combined_summary:
        return
    source_block = "\n\n".join(
        f"{url}\n{summary}" for url, summary in ctx.source_summaries.items()
    )
    result = await llm(
        prompt=(
            "Analyze this research material. Return only JSON with keys: "
            "patterns (array of strings), perspectives (array of objects with viewpoint, description, "
            "supporting_source_urls), knowledge_gaps (array of strings), further_reading (array of strings).\n\n"
            f"Combined summary:\n{ctx.combined_summary}\n\nSource summaries:\n{source_block}"
        ),
        system=config.get("system_prompt", ""),
    )
    ctx.llm_calls += 1
    ctx.total_tokens += result.total_tokens
    ctx.analyst_insights = _parse_insights(result.content)


def _parse_insights(content: str) -> AnalystInsights:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = {}

    perspectives = []
    for item in data.get("perspectives", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue
        perspectives.append(
            Perspective(
                viewpoint=str(item.get("viewpoint", "")),
                description=str(item.get("description", "")),
                supporting_source_urls=[str(url) for url in item.get("supporting_source_urls", [])],
            )
        )

    return AnalystInsights(
        patterns=_string_list(data.get("patterns", [])) if isinstance(data, dict) else [],
        perspectives=perspectives,
        knowledge_gaps=_string_list(data.get("knowledge_gaps", [])) if isinstance(data, dict) else [],
        further_reading=_string_list(data.get("further_reading", [])) if isinstance(data, dict) else [],
    )


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
