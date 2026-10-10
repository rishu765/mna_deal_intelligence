"""Deterministic M1/2 request and state fixtures."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from ma_deal_intelligence.evidence import ProjectId
from ma_deal_intelligence.fixtures import representative_deal_state
from ma_deal_intelligence.identity import CanonicalEntityReference, DealContext
from ma_deal_intelligence.requests import RequestMode, UserDealRequest
from ma_deal_intelligence.state import DealState, SourceDocumentReference

TARGET = CanonicalEntityReference(
    "entity:targetco", display_name="TargetCo", country="IN", sector="B2B SaaS"
)


def fixture_state(
    *, target: bool = True, documents: bool = True, financials: bool = False
) -> DealState:
    context = DealContext(
        "deal:fixture",
        engagement_id="engagement:fixture",
        target_entity_id=TARGET.canonical_entity_id if target else None,
        sectors=("B2B SaaS",) if target else (),
        geographies=("India",),
        reporting_currency="USD",
        as_of_date=date(2026, 1, 1),
    )
    source_documents = (
        (SourceDocumentReference("doc:fixture-vdr", ProjectId.PROJECT_1, "Fixture VDR"),)
        if documents
        else ()
    )
    state = DealState(context, (TARGET,) if target else (), source_documents)
    if financials:
        sample = representative_deal_state()
        state = replace(state, financial_metrics=(sample.financial_metrics[0],))
    return state


def fixture_requests() -> dict[str, UserDealRequest]:
    return {
        "company_research": _request("company-research", "Research TargetCo", TARGET),
        "find_targets": _request("find-targets", "Find Indian B2B fintech targets"),
        "trading_comps": _request("trading-comps", "Value TargetCo using trading comps", TARGET),
        "precedents": _request(
            "precedents", "What have buyers historically paid for companies like TargetCo?", TARGET
        ),
        "diligence": _request("diligence", "Review this VDR for red flags", TARGET),
        "compare": _request("compare", "Compare trading comps and precedents for TargetCo", TARGET),
        "evaluation": _request("evaluation", "Evaluate the acquisition of TargetCo", TARGET),
        "multi_intent": _request("multi", "Find B2B SaaS targets in India and value the top 3"),
        "missing_target": _request("missing-target", "Value a target using trading comps"),
        "missing_vdr": _request("missing-vdr", "Run due diligence on TargetCo", TARGET),
        "unavailable_specialist": _request(
            "unavailable", "Compare trading comps and precedents for TargetCo", TARGET
        ),
        "dependency_cycle": _request("cycle", "Run a full deal analysis for TargetCo", TARGET),
    }


def _request(
    request_id: str, query: str, target: CanonicalEntityReference | None = None
) -> UserDealRequest:
    return UserDealRequest(request_id, query, target=target, mode=RequestMode.OFFLINE)
