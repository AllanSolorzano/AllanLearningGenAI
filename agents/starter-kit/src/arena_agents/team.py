from .guardrails import GuardrailPolicy
from .models import ExperimentPlan, Observation, RCAReport
from .tools import ChaosTools, KubernetesTools, ObservabilityTools


class DiscoveryAgent:
    def __init__(self, kubernetes: KubernetesTools):
        self.kubernetes = kubernetes

    def discover(self, namespace: str = "chaos-app") -> dict:
        return self.kubernetes.get_workloads(namespace)


class ChaosPlanningAgent:
    def draft_plan(self, plan: ExperimentPlan) -> ExperimentPlan:
        return plan


class SafetyOfficerAgent:
    def __init__(self, policy: GuardrailPolicy | None = None):
        self.policy = policy or GuardrailPolicy.default()

    def approve_for_execution(self, plan: ExperimentPlan) -> None:
        self.policy.validate(plan)


class ExecutionAgent:
    def __init__(self, chaos: ChaosTools, safety: SafetyOfficerAgent):
        self.chaos = chaos
        self.safety = safety

    def execute(self, plan: ExperimentPlan) -> str:
        self.safety.approve_for_execution(plan)
        return self.chaos.create_experiment(plan)

    def rollback(self, experiment_name: str) -> None:
        self.chaos.delete_experiment(experiment_name)


class ObserverAgent:
    def __init__(self, observability: ObservabilityTools):
        self.observability = observability

    def collect(self, service: str, window: str) -> list[Observation]:
        return [
            self.observability.query_logs(service, window),
            self.observability.query_traces(service, window),
        ]


class RCAAgent:
    def summarize(
        self,
        summary: str,
        impact: str,
        root_cause: str,
        timeline: list[str],
        evidence: list[Observation],
        recommendations: list[str],
        confidence: str = "medium",
    ) -> RCAReport:
        if confidence not in {"low", "medium", "high"}:
            raise ValueError("confidence must be low, medium, or high")

        return RCAReport(
            summary=summary,
            impact=impact,
            root_cause=root_cause,
            timeline=timeline,
            evidence=evidence,
            recommendations=recommendations,
            confidence=confidence,  # type: ignore[arg-type]
        )
