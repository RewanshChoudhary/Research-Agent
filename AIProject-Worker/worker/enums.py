from enum import Enum


class Domain(str, Enum):
    GENERAL = "GENERAL"
    MEDICAL = "MEDICAL"
    LEGAL = "LEGAL"
    TECHNICAL = "TECHNICAL"
    OTHER = "OTHER"


class Depth(str, Enum):
    QUICK = "QUICK"
    STANDARD = "STANDARD"
    DEEP = "DEEP"


class OutputFormat(str, Enum):
    JSON = "json"
    MARKDOWN = "markdown"
    PLAIN = "plain"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PipelineStage(str, Enum):
    SEARCHING = "searching"
    SCRAPING = "scraping"
    SUMMARIZING = "summarizing"
    FACT_CHECKING = "fact_checking"
    ANALYZING = "analyzing"
    BUILDING = "building"


class SourceStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


class ClaimVerdict(str, Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    CONFLICTING = "conflicting"


class UserPlan(str, Enum):
    FREE = "free"
    PRO = "pro"

