from dataclasses import dataclass, field
from typing import Literal


ExperimentType = Literal[
    "pod-kill",
    "network-latency",
    "network-loss",
    "cpu-stress",
    "memory-stress",
    "dependency-failure",
    "hpa-load",
    "gitops-drift-detect",
]


@dataclass(frozen=True)
class ExperimentTarget:
    namespace: str
    service: str


@dataclass(frozen=True)
class ExperimentPlan:
    hypothesis: str
    target: ExperimentTarget
    experiment_type: ExperimentType
    duration: str
    blast_radius: str
    success_criteria: list[str]
    abort_criteria: list[str]
    rollback: str
    observability_plan: list[str]
    requires_human_approval: bool = True
    approved_by: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def is_approved(self) -> bool:
        return not self.requires_human_approval or bool(self.approved_by)


@dataclass(frozen=True)
class Observation:
    source: Literal["kubernetes", "prometheus", "dynatrace", "cloudwatch", "agent"]
    summary: str
    evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RCAReport:
    summary: str
    impact: str
    root_cause: str
    timeline: list[str]
    evidence: list[Observation]
    recommendations: list[str]
    confidence: Literal["low", "medium", "high"]
