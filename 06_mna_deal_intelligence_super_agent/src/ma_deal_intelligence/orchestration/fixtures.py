"""Deterministic orchestration fixtures and injectable failure behavior."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from ma_deal_intelligence.contracts import CapabilityId
from ma_deal_intelligence.orchestration.services import (
    OrchestrationServices,
    RegistrySpecialistInvoker,
    SpecialistInvoker,
    default_services,
)
from ma_deal_intelligence.outputs import ProjectResultEnvelope
from ma_deal_intelligence.reconciliation_fixtures import rich_reconciliation_state


@dataclass(slots=True)
class ScriptedSpecialistInvoker:
    """Wrap real fixture adapters while injecting deterministic boundary failures."""

    delegate: SpecialistInvoker
    failures: dict[str, tuple[Exception, ...]] = field(default_factory=dict)
    calls: dict[str, int] = field(default_factory=dict)

    def invoke(self, capability_id: str, request: Any) -> ProjectResultEnvelope[Any]:
        call = self.calls.get(capability_id, 0)
        self.calls[capability_id] = call + 1
        scripted = self.failures.get(capability_id, ())
        if call < len(scripted):
            raise scripted[call]
        return self.delegate.invoke(capability_id, request)


@dataclass(slots=True)
class RichDiligenceFixtureInvoker:
    """Use the M3 rich Project 5 envelope after the normal adapter boundary is exercised."""

    delegate: SpecialistInvoker

    def invoke(self, capability_id: str, request: Any) -> ProjectResultEnvelope[Any]:
        actual = self.delegate.invoke(capability_id, request)
        if capability_id != CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS:
            return actual
        source = rich_reconciliation_state().diligence_results[0]
        return replace(
            source,
            run_id=actual.run_id,
            generated_at=actual.generated_at,
            data_as_of=actual.data_as_of,
        )


def services_with_invoker(invoker: SpecialistInvoker | None = None) -> OrchestrationServices:
    services = default_services()
    services.invoker = invoker or RegistrySpecialistInvoker(services.registry)
    return services


def scripted_services(
    failures: dict[str, tuple[Exception, ...]],
) -> tuple[OrchestrationServices, ScriptedSpecialistInvoker]:
    services = default_services()
    invoker = ScriptedSpecialistInvoker(
        RegistrySpecialistInvoker(services.registry), failures=failures
    )
    services.invoker = invoker
    return services, invoker


def rich_review_services() -> OrchestrationServices:
    services = default_services()
    services.invoker = RichDiligenceFixtureInvoker(RegistrySpecialistInvoker(services.registry))
    return services
