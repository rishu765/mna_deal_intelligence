"""Future user request and final synthesis contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from ma_deal_intelligence.identity import CanonicalEntityReference


class RequestMode(StrEnum):
    OFFLINE = "offline"
    LIVE = "live"
    AUTO = "auto"


@dataclass(frozen=True, slots=True)
class AnalystPreferences:
    review_threshold: str | None = None
    preferred_metric_basis: str | None = None
    preferred_valuation_methods: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class UserDealRequest:
    request_id: str
    user_query: str
    target: CanonicalEntityReference | None = None
    buyer: CanonicalEntityReference | None = None
    requested_capabilities: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    reporting_currency: str | None = None
    time_horizon: str | None = None
    mode: RequestMode = RequestMode.AUTO
    analyst_preferences: AnalystPreferences | None = None


@dataclass(frozen=True, slots=True)
class SynthesisSection:
    section_id: str
    title: str
    content: str | None
    source_artifact_ids: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    assumption_ids: tuple[str, ...] = ()
    warning_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FinalDealIntelligence:
    synthesis_id: str
    deal_id: str
    as_of_date: date
    deal_overview: SynthesisSection
    strategic_rationale: SynthesisSection
    company_intelligence: SynthesisSection
    target_screening: SynthesisSection
    trading_comps: SynthesisSection
    precedents: SynthesisSection
    due_diligence: SynthesisSection
    reconciled_metrics: SynthesisSection
    valuation_summary: SynthesisSection
    key_risks: SynthesisSection
    analyst_decisions: SynthesisSection
    open_questions: SynthesisSection
    limitations: SynthesisSection
    evidence_refs: tuple[str, ...]
    assumption_ids: tuple[str, ...]

    @property
    def sections(self) -> tuple[SynthesisSection, ...]:
        return (
            self.deal_overview,
            self.strategic_rationale,
            self.company_intelligence,
            self.target_screening,
            self.trading_comps,
            self.precedents,
            self.due_diligence,
            self.reconciled_metrics,
            self.valuation_summary,
            self.key_risks,
            self.analyst_decisions,
            self.open_questions,
            self.limitations,
        )
