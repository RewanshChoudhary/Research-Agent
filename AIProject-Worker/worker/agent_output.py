from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from worker.schemas import ResearchRequest


@dataclass
class ResearchContext:
    request: ResearchRequest
    urls: list[str] =field(default_factory=list)
    search_results: dict[str, dict[str, str]] = field(default_factory=dict)
    scraped_content: dict[str, str] = field(default_factory=dict)
    scrape_status: dict[str, str] = field(default_factory=dict)
    source_summaries: dict[str, str] = field(default_factory=dict)
    combined_summary: str | None = None
    fact_check: "FactCheckResult | None" = None
    analyst_insights: "AnalystInsights | None" = None
    agent_metrics: dict[str, "AgentMetric"] = field(default_factory=dict)
    chunks: dict[str, list[str]] = field(default_factory=dict)
    key_findings: list[str] = field(default_factory=list)
    total_tokens: int = 0
    llm_calls: int = 0


@dataclass
class FactCheckResult:
    confidence_score: float
    confidence_label: str
    total_claims: int
    verified_claims: int
    unverified_claims: int
    conflicting_claims: list["ConflictingClaim"]
    verdict: str


@dataclass
class AgentMetric:
    duration_ms: int = 0
    llm_calls_made: int = 0
    tokens_used: int = 0
    success: bool = True


class AnalystInsights(BaseModel):
    patterns: list[str] = Field(default_factory=list)
    perspectives: list["Perspective"] = Field(default_factory=list)
    knowledge_gaps: list[str] = Field(default_factory=list)
    further_reading: list[str] = Field(default_factory=list)


class Perspective(BaseModel):
    viewpoint: str
    description: str
    supporting_source_urls: list[str] = Field(default_factory=list)


class ConflictingClaim(BaseModel):
    claim_a: str = Field(description="One side of the contradiction")
    claim_b: str = Field(description="The opposing side of the contradiction")
    source_a: str = Field(description="URL supporting claim_a")
    source_b: str = Field(description="URL supporting claim_b")
    conflict_description: str = Field(
        description="Human-readable explanation of why the claims contradict"
    )
