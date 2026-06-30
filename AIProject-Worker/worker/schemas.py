from uuid import UUID

from typing import Annotated
from pydantic import BaseModel, Field

from worker.enums import (
    Depth,
    Domain,
    JobStatus,
    OutputFormat,
    PipelineStage,
    SourceStatus,
)



class ResearchRequest(BaseModel):
    query: Annotated[str, Field(min_length=1, max_length=500)] = Field(
        description="The user's research question"
    )
    domain: Domain = Field(
        default=Domain.GENERAL,
        description="Research domain that controls config thresholds and prompt templates",
    )
    depth: Depth = Field(
        default=Depth.STANDARD,
        description="Pipeline depth: QUICK skips FactCheck, DEEP adds Analyst",
    )
    factCheck: bool = Field(
        default=True,
        description="Whether to run FactCheck (only meaningful at STANDARD depth)",
    )
    maxSources: Annotated[int, Field(ge=1, le=20)] = Field(
        default=5,
        description="Maximum number of URLs to scrape and summarize",
    )
    outputFormat: OutputFormat = Field(
        default=OutputFormat.JSON,
        description="Requested output format — Java does final rendering",
    )




# Worker → Java request/response DTOs


class WorkerJobDetailsResponse(BaseModel):
    jobId: UUID = Field(
        description="The job identifier used for all callbacks to the Java API"
    )
    query: str = Field(
        min_length=1,
        max_length=500,
        description="The original user research query",
    )
    domain: Domain = Field(
        description="Research domain that controls config thresholds"
    )
    depth: Depth = Field(
        description="Pipeline depth: QUICK skips FactCheck, DEEP adds Analyst"
    )
    factCheckEnabled: bool = Field(
        description="Override to skip FactCheck even at STANDARD depth"
    )
    maxSources: int = Field(
        ge=1, le=20, description="Maximum number of URLs to scrape and summarize"
    )
class WorkerStatusUpdateRequest(BaseModel):
    status: JobStatus
    currentStage: PipelineStage | None = Field(
        description="The stage the pipeline is at"
    )
    progressPercent: int | None


class WorkerSourceItem(BaseModel):
    url: str = Field(description="Source URL")
    title: str | None = Field(description="Page title from HTML")
    domainName: str | None = Field(description="Extracted domain from URL")
    scrapeStatus: SourceStatus = Field(
        description="SUCCESS | FAILED | BLOCKED | SKIPPED"
    )
    contentLength: int | None = Field(description="Extracted text length in characters")
    summary: str | None = Field(description="Per-source LLM summary")
class WorkerCompleteRequest(BaseModel):
    summary: str = Field(min_length=1, description="Combined research summary")
    keyFindings: Annotated[list[str], Field(min_length=1)] = Field(
        description="3–7 bullet-point key findings"
    )
    sources: list[WorkerSourceItem] = Field(
        default_factory=list, description="Per-source details with scrape status and summaries"
    )
    totalSourcesFound: int = Field(
        ge=0, description="Count from Search phase before filtering"
    )
    totalSourcesProcessed: int = Field(
        ge=0, description="Count of successfully scraped + summarized URLs"
    )
    totalTimeMs: int = Field(
        ge=0, description="Pipeline wall-clock time in milliseconds"
    )
    factCheck: dict | None = Field(
        default=None, description="Optional fact-check details"
    )
    analystInsights: dict | None = Field(
        default=None, description="Optional deep research analysis"
    )


class WorkerFailRequest(BaseModel):
    errorMessage: str = Field(
        min_length=1, description="Human-readable reason for pipeline failure"
    )
