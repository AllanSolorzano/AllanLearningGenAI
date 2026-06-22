from typing import Protocol

from .models import ExperimentPlan, Observation


class KubernetesTools(Protocol):
    def get_workloads(self, namespace: str) -> dict:
        """Return pods, deployments, services, HPA, PDB, ingress, and events."""


class ObservabilityTools(Protocol):
    def query_metrics(self, query: str) -> Observation:
        """Query Prometheus or another metrics backend."""

    def query_logs(self, service: str, window: str) -> Observation:
        """Query logs for a service."""

    def query_traces(self, service: str, window: str) -> Observation:
        """Query traces for a service."""


class ChaosTools(Protocol):
    def create_experiment(self, plan: ExperimentPlan) -> str:
        """Create an approved, bounded chaos experiment and return its name."""

    def delete_experiment(self, name: str) -> None:
        """Delete a previously created chaos experiment."""
