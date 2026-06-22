import re
from dataclasses import dataclass, field

from .models import ExperimentPlan


class GuardrailViolation(ValueError):
    """Raised when an experiment plan violates Arena guardrails."""


@dataclass(frozen=True)
class GuardrailPolicy:
    allowed_namespace: str
    allowed_services: set[str]
    allowed_experiment_types: set[str]
    max_duration_seconds: int = 300
    forbidden_terms: set[str] = field(default_factory=set)

    @classmethod
    def default(cls) -> "GuardrailPolicy":
        return cls(
            allowed_namespace="chaos-app",
            allowed_services={
                "api-gateway",
                "order-service",
                "inventory-service",
                "payment-service",
                "frontend",
            },
            allowed_experiment_types={
                "pod-kill",
                "network-latency",
                "network-loss",
                "cpu-stress",
                "memory-stress",
                "dependency-failure",
                "hpa-load",
                "gitops-drift-detect",
            },
            forbidden_terms={
                "delete namespace",
                "delete pvc",
                "delete persistentvolumeclaim",
                "delete persistentvolume",
                "delete secret",
                "read secret",
                "patch secret",
                "modify iam",
                "modify vpc",
                "modify securitygroup",
                "modify route53",
                "modify dynatrace",
                "database drop",
            },
        )

    def validate(self, plan: ExperimentPlan) -> None:
        if plan.target.namespace != self.allowed_namespace:
            raise GuardrailViolation(f"namespace {plan.target.namespace!r} is not allowed")

        if plan.target.service not in self.allowed_services:
            raise GuardrailViolation(f"service {plan.target.service!r} is not an allowed chaos target")

        if plan.experiment_type not in self.allowed_experiment_types:
            raise GuardrailViolation(f"experiment type {plan.experiment_type!r} is not allowed")

        duration_seconds = parse_duration_seconds(plan.duration)
        if duration_seconds <= 0 or duration_seconds > self.max_duration_seconds:
            raise GuardrailViolation(
                f"duration {plan.duration!r} exceeds {self.max_duration_seconds}s guardrail"
            )

        if not plan.success_criteria:
            raise GuardrailViolation("success criteria are required")

        if not plan.abort_criteria:
            raise GuardrailViolation("abort criteria are required")

        if not plan.rollback:
            raise GuardrailViolation("rollback action is required")

        if plan.requires_human_approval and not plan.approved_by:
            raise GuardrailViolation("human approval is required before execution")

        combined_text = " ".join(
            [
                plan.hypothesis,
                plan.blast_radius,
                plan.rollback,
                " ".join(plan.success_criteria),
                " ".join(plan.abort_criteria),
            ]
        ).lower()
        compact_text = re.sub(r"[^a-z0-9]+", "", combined_text)

        for term in self.forbidden_terms:
            if term.replace(" ", "") in compact_text:
                raise GuardrailViolation(f"plan references forbidden action or resource: {term}")


def parse_duration_seconds(value: str) -> int:
    match = re.fullmatch(r"\s*(\d+)\s*([smh]?)\s*", value)
    if not match:
        raise GuardrailViolation(f"duration {value!r} must use seconds, minutes, or hours")

    amount = int(match.group(1))
    unit = match.group(2) or "s"
    multiplier = {"s": 1, "m": 60, "h": 3600}[unit]
    return amount * multiplier
