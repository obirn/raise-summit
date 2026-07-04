from dataclasses import dataclass, field


@dataclass(frozen=True)
class AppRecord:
    id: str
    state: str | None
    source: str


@dataclass(frozen=True)
class IncidentAnalysis:
    system_id: str
    states: dict[str, str | None]
    normalized_states: dict[str, str | None]
    majority_state: str | None
    outlier_app: str | None
    outlier_state: str | None
    confidence: float
    description: str


@dataclass(frozen=True)
class MemoryMatch:
    fix_id: int
    issue_id: int
    similarity_score: float
    previous_action: str
    action_plan: dict | None = None


@dataclass(frozen=True)
class Decision:
    decision: str
    action_details: str
    action_plan: dict
    memory_match: MemoryMatch | None = None
    human_input: str | None = None


@dataclass(frozen=True)
class PipelineResult:
    issue_id: int
    system_id: str
    decision: str
    fix_id: int | None
    execution_status: str
    memory_match: MemoryMatch | None = None
    action_plan: dict = field(default_factory=dict)
