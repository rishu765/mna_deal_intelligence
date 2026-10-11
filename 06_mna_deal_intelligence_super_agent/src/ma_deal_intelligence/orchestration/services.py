"""Service composition for the Project 6 orchestration graph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ma_deal_intelligence.intent import IntentClassifier
from ma_deal_intelligence.outputs import ProjectResultEnvelope
from ma_deal_intelligence.planning import ExecutionPlanner
from ma_deal_intelligence.reconciliation import ReconciliationService
from ma_deal_intelligence.registry import CapabilityRegistry, default_registry


class TransientAdapterError(RuntimeError):
    """Adapter/provider failure that may succeed within the configured retry bound."""


class SpecialistInvoker(Protocol):
    def invoke(self, capability_id: str, request: Any) -> ProjectResultEnvelope[Any]: ...


@dataclass(slots=True)
class RegistrySpecialistInvoker:
    registry: CapabilityRegistry

    def invoke(self, capability_id: str, request: Any) -> ProjectResultEnvelope[Any]:
        return self.registry.adapter(capability_id).invoke(capability_id, request)


@dataclass(slots=True)
class OrchestrationServices:
    registry: CapabilityRegistry
    classifier: IntentClassifier
    planner: ExecutionPlanner
    reconciler: ReconciliationService
    invoker: SpecialistInvoker


def default_services() -> OrchestrationServices:
    registry = default_registry()
    return OrchestrationServices(
        registry,
        IntentClassifier(),
        ExecutionPlanner(registry),
        ReconciliationService(),
        RegistrySpecialistInvoker(registry),
    )
