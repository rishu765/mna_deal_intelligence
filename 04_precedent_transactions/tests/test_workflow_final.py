from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from typing import cast

from ma_precedent_transactions.discovery import (
    AcquisitionContext,
    CandidateTransaction,
    DealDiscoveryResult,
)
from ma_precedent_transactions.errors import DiscoveryUnavailableError, ExtractionProviderError
from ma_precedent_transactions.extraction import (
    StructuredTransactionService,
    VerifiedTransactionRecord,
)
from ma_precedent_transactions.pipeline import DealResearchCorpus, DealResearchPipeline
from ma_precedent_transactions.precedent import precedent_fixture_inputs
from ma_precedent_transactions.retrieval import (
    DealRetrievalResult,
    IndexingReport,
    InMemoryDealIndex,
)
from ma_precedent_transactions.workflow import (
    FailureCode,
    HumanReviewDecision,
    ObservationResolution,
    RetryPolicy,
    ReviewAction,
    ReviewPolicy,
    WorkflowApplication,
    WorkflowRequest,
    WorkflowStatus,
    build_offline_application,
    build_offline_services,
    build_workflow,
)


def _request(identifier: str, policy: ReviewPolicy = ReviewPolicy.ALWAYS) -> WorkflowRequest:
    comparable, valuation, _ = precedent_fixture_inputs()
    return WorkflowRequest(
        identifier,
        AcquisitionContext(
            identifier,
            "B2B fintech infrastructure",
            "Payments ledger banking API compliance infrastructure",
            ("United States", "United Kingdom"),
            date(2020, 1, 1),
            date(2025, 12, 31),
        ),
        comparable,
        valuation,
        policy,
    )


def _approval() -> HumanReviewDecision:
    return HumanReviewDecision(
        ReviewAction.APPROVE,
        "analyst@example.test",
        "Reviewed material ambiguity and approved the documented policy.",
        recorded_at=datetime.now(UTC),
    )


def test_graph_pauses_checkpoints_resumes_and_preserves_operational_trace() -> None:
    app = build_offline_application()
    paused = app.start(_request("workflow-happy"), thread_id="workflow-happy")

    assert paused["status"] is WorkflowStatus.AWAITING_HUMAN_REVIEW
    assert app.state(thread_id="workflow-happy")["request"].request_id == "workflow-happy"
    completed = app.resume(thread_id="workflow-happy", decision=_approval())

    assert completed["status"] is WorkflowStatus.COMPLETED
    assert completed["final_result"].valuation is not None
    assert completed["final_result"].valuation.ranges
    assert [event.node for event in completed["final_result"].trace] == [
        "validate_input",
        "research_deals",
        "extract_and_verify",
        "route_for_human_review",
        "human_review",
        "select_precedents",
        "calculate_valuation",
        "generate_explanation",
        "evaluate_run",
        "finalize",
    ]


def test_when_needed_routes_material_conflicts_to_review() -> None:
    app = build_offline_application()
    paused = app.start(
        _request("workflow-needed", ReviewPolicy.WHEN_NEEDED), thread_id="workflow-needed"
    )

    assert paused["status"] is WorkflowStatus.AWAITING_HUMAN_REVIEW
    assert "valuation.headline_deal_value" in paused["review_request"].conflict_fields


def test_never_review_policy_completes_without_interrupt_and_keeps_warnings() -> None:
    app = build_offline_application()
    completed = app.start(
        _request("workflow-no-review", ReviewPolicy.NEVER), thread_id="workflow-no-review"
    )

    assert completed["status"] is WorkflowStatus.COMPLETED
    assert completed.get("human_review") is None
    assert any("ambiguous" in warning for warning in completed["warnings"])


def test_review_rejection_terminates_without_valuation() -> None:
    app = build_offline_application()
    app.start(_request("workflow-reject"), thread_id="workflow-reject")
    rejected = app.resume(
        thread_id="workflow-reject",
        decision=HumanReviewDecision(
            ReviewAction.REJECT,
            "analyst@example.test",
            "Evidence is insufficient for valuation.",
            recorded_at=datetime.now(UTC),
        ),
    )

    assert rejected["status"] is WorkflowStatus.REJECTED
    assert rejected["final_result"].failure_code is FailureCode.USER_REJECTED
    assert rejected["final_result"].valuation is None


def test_valid_conflict_resolution_is_audited_and_removed_on_resume() -> None:
    app = build_offline_application()
    paused = app.start(_request("workflow-resolution"), thread_id="workflow-resolution")
    record = next(
        item
        for item in paused["verified_transactions"]
        if item.record.identity.transaction_id == "txn-conflict"
    )
    conflict = record.conflicts[0]
    decision = replace(
        _approval(),
        resolutions=(
            ObservationResolution(
                "txn-conflict",
                conflict.field,
                conflict.observation_ids[0],
                "Selected official current disclosure.",
            ),
        ),
    )
    completed = app.resume(thread_id="workflow-resolution", decision=decision)
    resolved = next(
        item
        for item in completed["verified_transactions"]
        if item.record.identity.transaction_id == "txn-conflict"
    )

    assert not resolved.conflicts
    review = completed["final_result"].human_review
    assert review is not None
    assert review.reviewer == decision.reviewer
    assert review.resolutions == decision.resolutions


@dataclass
class _FlakyResearch:
    delegate: DealResearchPipeline
    failures: int
    calls: int = 0

    @property
    def index(self) -> InMemoryDealIndex:
        return self.delegate.index

    def build(self, context: AcquisitionContext) -> DealResearchCorpus:
        self.calls += 1
        if self.calls <= self.failures:
            raise DiscoveryUnavailableError("temporary fixture provider failure")
        return self.delegate.build(context)


def test_recoverable_research_failure_retries_once_then_recovers() -> None:
    services = build_offline_services()
    flaky = _FlakyResearch(services.research, 1)
    services = replace(services, research=cast(DealResearchPipeline, flaky))
    app = WorkflowApplication(
        build_workflow(services, retry_policy=RetryPolicy(research=1, extraction=0))
    )
    paused = app.start(_request("workflow-retry"), thread_id="workflow-retry")

    assert paused["status"] is WorkflowStatus.AWAITING_HUMAN_REVIEW
    assert flaky.calls == 2
    assert paused["retry_counts"] == {"research": 1}
    assert paused["errors"][0].recoverable is True


@dataclass
class _EmptyResearch:
    delegate: DealResearchPipeline

    @property
    def index(self) -> InMemoryDealIndex:
        return self.delegate.index

    def build(self, context: AcquisitionContext) -> DealResearchCorpus:
        discovery = DealDiscoveryResult(context.context_id, 0, (), ("empty",), (), ())
        report = IndexingReport(0, 0, 0, 0, 0, "fixture", "fixture")
        return DealResearchCorpus(discovery, (), (), (), report)


def test_no_deals_found_terminates_gracefully() -> None:
    services = build_offline_services()
    empty = _EmptyResearch(services.research)
    services = replace(services, research=cast(DealResearchPipeline, empty))
    app = WorkflowApplication(build_workflow(services))
    failed = app.start(_request("workflow-empty"), thread_id="workflow-empty")

    assert failed["status"] is WorkflowStatus.FAILED
    assert failed["final_result"].failure_code is FailureCode.NO_DEALS_FOUND
    assert failed["final_result"].verified_transactions == ()


def test_no_eligible_precedents_terminates_without_valuation() -> None:
    services = build_offline_services()
    default_preparer = services.transaction_preparer

    def withdrawn_only(
        records: dict[str, VerifiedTransactionRecord],
    ) -> tuple[VerifiedTransactionRecord, ...]:
        prepared = default_preparer(records)
        return tuple(
            item for item in prepared if item.record.identity.transaction_id == "txn-withdrawn"
        )

    services = replace(services, transaction_preparer=withdrawn_only)
    app = WorkflowApplication(build_workflow(services))
    paused = app.start(_request("workflow-no-precedents"), thread_id="workflow-no-precedents")
    failed = app.resume(thread_id="workflow-no-precedents", decision=_approval())

    assert paused["status"] is WorkflowStatus.AWAITING_HUMAN_REVIEW
    assert failed["status"] is WorkflowStatus.FAILED
    assert failed["failure_code"] is FailureCode.NO_ELIGIBLE_PRECEDENTS
    assert failed["final_result"].valuation is None


@dataclass
class _FlakyExtraction:
    delegate: StructuredTransactionService
    failures: int
    calls: int = 0

    def build(
        self,
        candidate: CandidateTransaction,
        evidence: tuple[DealRetrievalResult, ...],
    ) -> VerifiedTransactionRecord:
        self.calls += 1
        if self.calls <= self.failures:
            raise ExtractionProviderError("temporary fixture model failure")
        return self.delegate.build(candidate, evidence)


def test_recoverable_extraction_failure_retries_then_recovers() -> None:
    services = build_offline_services()
    flaky = _FlakyExtraction(services.extraction, 1)
    services = replace(services, extraction=cast(StructuredTransactionService, flaky))
    app = WorkflowApplication(
        build_workflow(services, retry_policy=RetryPolicy(research=0, extraction=1))
    )
    paused = app.start(_request("workflow-extraction-retry"), thread_id="workflow-extraction-retry")

    assert paused["status"] is WorkflowStatus.AWAITING_HUMAN_REVIEW
    assert flaky.calls >= 2
    assert paused["retry_counts"] == {"extraction": 1}


class _FailingExplanation:
    def explain(self, context: object) -> object:
        raise TimeoutError("fixture model timeout")


def test_ai_explanation_failure_does_not_change_deterministic_valuation() -> None:
    services = replace(
        build_offline_services(),
        explanation=_FailingExplanation(),  # type: ignore[arg-type]
    )
    app = WorkflowApplication(build_workflow(services))
    app.start(_request("workflow-ai-failure"), thread_id="workflow-ai-failure")
    completed = app.resume(thread_id="workflow-ai-failure", decision=_approval())

    assert completed["status"] is WorkflowStatus.COMPLETED
    assert completed["valuation"].ranges
    assert completed["valuation"].explanation is not None
    assert completed["valuation"].explanation.status.value == "unavailable"
    assert any("deterministic valuation remains valid" in item for item in completed["warnings"])
