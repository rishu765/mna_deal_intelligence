"""Final fixture-based subsystem and workflow evaluation for Project 4 V1."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from ma_precedent_transactions.demo import PROJECT_ROOT, build_fixture_pipeline
from ma_precedent_transactions.demo_m3 import build_fixture_records
from ma_precedent_transactions.discovery import AcquisitionContext
from ma_precedent_transactions.domain import MultipleKind, MultipleStatus
from ma_precedent_transactions.evaluation import load_benchmark, run_benchmark
from ma_precedent_transactions.extraction import (
    load_extraction_benchmark,
    run_extraction_benchmark,
)
from ma_precedent_transactions.precedent import (
    ComparableTransactionSelector,
    FixtureValuationExplanationProvider,
    ManualOverride,
    OverrideAction,
    PrecedentAnalysisService,
    SelectionDecision,
    precedent_fixture_inputs,
)
from ma_precedent_transactions.retrieval import HybridDealRetriever, RetrievalFilters
from ma_precedent_transactions.workflow import (
    HumanReviewDecision,
    ObservationResolution,
    ReviewAction,
    ReviewPolicy,
    WorkflowRequest,
    WorkflowStatus,
    build_offline_application,
)


@dataclass(frozen=True, slots=True)
class EvaluationMetric:
    subsystem: str
    metric: str
    result: str
    passed: bool
    interpretation: str


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    scenario: str
    expected_behavior: str
    passed: bool
    observed: str


@dataclass(frozen=True, slots=True)
class FinalEvaluationReport:
    metrics: tuple[EvaluationMetric, ...]
    scenarios: tuple[ScenarioResult, ...]
    representative_failures: tuple[str, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "metrics": [asdict(item) for item in self.metrics],
            "scenarios": [asdict(item) for item in self.scenarios],
            "representative_failures": list(self.representative_failures),
            "limitations": list(self.limitations),
        }


class _FailingExplanation:
    def explain(self, context: object) -> object:
        raise TimeoutError("fixture explanation timeout")


def run_final_evaluation(project_root: Path = PROJECT_ROOT) -> FinalEvaluationReport:
    context = _context("final-evaluation")
    pipeline = build_fixture_pipeline()
    corpus = pipeline.build(context)
    retriever = HybridDealRetriever(pipeline.index)
    retrieval = run_benchmark(
        retriever, load_benchmark(project_root / "evaluation" / "retrieval_cases.json")
    )
    records = build_fixture_records()
    extraction = run_extraction_benchmark(
        records,
        load_extraction_benchmark(project_root / "evaluation" / "extraction_cases.json"),
    )
    comparable, valuation_target, transactions = precedent_fixture_inputs()
    valuation = PrecedentAnalysisService().analyze(
        comparable,
        valuation_target,
        transactions,
        explanation_provider=FixtureValuationExplanationProvider(),
    )
    workflow = build_offline_application()
    paused = workflow.start(
        WorkflowRequest(
            "final-evaluation-workflow",
            _context("final-evaluation-workflow"),
            comparable,
            valuation_target,
            ReviewPolicy.ALWAYS,
        ),
        thread_id="final-evaluation-workflow",
    )
    conflict = next(
        item
        for record in paused["verified_transactions"]
        for item in record.conflicts
        if record.record.identity.transaction_id == "txn-conflict"
    )
    completed = workflow.resume(
        thread_id="final-evaluation-workflow",
        decision=HumanReviewDecision(
            ReviewAction.APPROVE,
            "fixture-analyst",
            "Reviewed the conflicting headline values and approved deterministic exclusions.",
            (
                ObservationResolution(
                    "txn-conflict",
                    conflict.field,
                    conflict.observation_ids[0],
                    "Preferred the official current observation for this fixture.",
                ),
            ),
            recorded_at=datetime.now(UTC),
        ),
    )
    discovery_ids = {item.candidate_id for item in corpus.discovery.transactions}
    expected_ids = {
        "txn-cash",
        "txn-stock",
        "txn-partial",
        "txn-withdrawn",
        "txn-undisclosed",
        "txn-amended",
        "txn-conflict",
    }
    selection = valuation.selection
    ev_revenue = next(
        item for item in valuation.multiple_sets if item.key.kind is MultipleKind.EV_REVENUE
    )
    explanation_ids = set(valuation.explanation.evidence_ids if valuation.explanation else ())
    available_ids = {
        evidence.evidence_id
        for multiple_set in valuation.multiple_sets
        for multiple in multiple_set.multiples
        for evidence in multiple.evidence
    }
    metrics = (
        EvaluationMetric(
            "deal_discovery",
            "candidate_recall",
            f"{len(discovery_ids & expected_ids)}/{len(expected_ids)}",
            discovery_ids == expected_ids,
            "All fixture economic transactions should survive provider filtering.",
        ),
        EvaluationMetric(
            "deal_discovery",
            "duplicate_handling",
            f"{corpus.discovery.raw_candidate_count} raw -> {len(discovery_ids)} resolved",
            corpus.discovery.raw_candidate_count == 8 and len(discovery_ids) == 7,
            "The duplicate cash-deal article should merge without merging distinct bids.",
        ),
        EvaluationMetric(
            "rag",
            "Hit@3 / Recall@3 / MRR",
            f"{retrieval.hit_at_k:.4f} / {retrieval.recall_at_k:.4f} / "
            f"{retrieval.mean_reciprocal_rank:.4f}",
            retrieval.hit_at_k == 1.0 and retrieval.recall_at_k == 1.0,
            "Tiny synthetic benchmark; rank quality is not production evidence.",
        ),
        EvaluationMetric(
            "extraction",
            "field / numeric / missing / evidence accuracy",
            f"{extraction.field_accuracy:.4f} / {extraction.numeric_accuracy:.4f} / "
            f"{extraction.missing_value_accuracy:.4f} / "
            f"{extraction.evidence_link_accuracy:.4f}",
            min(
                extraction.field_accuracy,
                extraction.numeric_accuracy,
                extraction.missing_value_accuracy,
                extraction.evidence_link_accuracy,
            )
            == 1.0,
            "Exact fixture regression over bounded evidence contexts.",
        ),
        EvaluationMetric(
            "verification",
            "conflict_detection_accuracy",
            f"{extraction.conflict_detection_accuracy:.4f}",
            extraction.conflict_detection_accuracy == 1.0,
            "Includes the conflicting headline-value fixture.",
        ),
        EvaluationMetric(
            "precedent_selection",
            "expected inclusion/exclusion",
            f"{len(selection.selected_transaction_ids)} selected",
            "txn-cash" in selection.selected_transaction_ids
            and "txn-partial" not in selection.selected_transaction_ids
            and "txn-withdrawn" not in selection.selected_transaction_ids,
            "Control, minority, lifecycle, and usable-value policies remain explicit.",
        ),
        EvaluationMetric(
            "valuation",
            "R7 median and implied range trace",
            str(ev_revenue.statistics.median),
            ev_revenue.statistics.count == 4
            and bool(valuation.ranges)
            and all(item.mid.trace.inputs for item in valuation.ranges),
            "Checks deterministic statistics and trace completeness, not market validity.",
        ),
        EvaluationMetric(
            "agent_workflow",
            "pause/resume/terminal routing",
            f"{paused['status'].value} -> {completed['status'].value}",
            paused["status"] is WorkflowStatus.AWAITING_HUMAN_REVIEW
            and completed["status"] is WorkflowStatus.COMPLETED,
            "In-memory checkpoint resume is deterministic within one process.",
        ),
        EvaluationMetric(
            "ai_explanation",
            "grounded evidence references",
            f"{len(explanation_ids)} cited IDs",
            bool(explanation_ids) and explanation_ids <= available_ids,
            "Fixture commentary contains no calculation authority.",
        ),
    )
    no_precedents = ComparableTransactionSelector().select(comparable, (transactions[-1],))
    override = ManualOverride(
        "txn-withdrawn",
        OverrideAction.FORCE_INCLUDE,
        "Sensitivity-only fixture override.",
        "fixture-analyst",
        datetime.now(UTC),
    )
    overridden = ComparableTransactionSelector().select(
        comparable, (transactions[-1],), (override,)
    )
    failing = PrecedentAnalysisService().analyze(
        comparable,
        valuation_target,
        transactions,
        explanation_provider=_FailingExplanation(),  # type: ignore[arg-type]
    )
    weak = retriever.retrieve(
        "unrelated zoological habitat question",
        top_k=3,
        filters=RetrievalFilters(transaction_id="txn-undisclosed"),
    )
    negative = next(
        multiple
        for multiple_set in valuation.multiple_sets
        for multiple in multiple_set.multiples
        if multiple.contract.transaction_id == "txn-negative"
        and multiple.contract.definition.kind is MultipleKind.EV_EBITDA
    )
    scenarios = (
        ScenarioResult(
            "clean_completed_set",
            "Complete with valuation ranges.",
            bool(valuation.ranges),
            f"{len(valuation.ranges)} ranges",
        ),
        ScenarioResult(
            "duplicate_discovery",
            "Resolve 8 observations to 7 deals.",
            len(discovery_ids) == 7,
            f"{len(discovery_ids)} deals",
        ),
        ScenarioResult(
            "ambiguous_value",
            "Route material ambiguity to review.",
            paused["status"] is WorkflowStatus.AWAITING_HUMAN_REVIEW,
            paused["status"].value,
        ),
        ScenarioResult(
            "partial_stake",
            "Exclude from control precedent set.",
            "txn-partial" not in selection.selected_transaction_ids,
            selection.decisions[-2].rationale,
        ),
        ScenarioResult(
            "conflicting_sources",
            "Detect and retain conflict before review.",
            bool(conflict),
            conflict.field,
        ),
        ScenarioResult(
            "negative_ebitda",
            "Mark EV/EBITDA not meaningful.",
            negative.contract.status is MultipleStatus.NOT_MEANINGFUL,
            negative.contract.status.value,
        ),
        ScenarioResult(
            "weak_retrieval",
            "Surface retrieval quality warnings.",
            bool(weak.warnings),
            ",".join(item.code.value for item in weak.warnings),
        ),
        ScenarioResult(
            "no_valid_precedents",
            "Return no selected deals without fabricating value.",
            not no_precedents.selected_transaction_ids,
            str(len(no_precedents.selected_transaction_ids)),
        ),
        ScenarioResult(
            "analyst_override",
            "Retain explicit force-include audit action.",
            overridden.decisions[0].decision is SelectionDecision.INCLUDE,
            overridden.decisions[0].rationale,
        ),
        ScenarioResult(
            "ai_explanation_failure",
            "Preserve deterministic ranges.",
            bool(failing.ranges)
            and failing.explanation is not None
            and failing.explanation.status.value == "unavailable",
            failing.explanation.status.value if failing.explanation else "missing",
        ),
    )
    return FinalEvaluationReport(
        metrics,
        scenarios,
        (
            "Weak or empty retrieval terminates or warns without invented evidence.",
            "Negative earnings are retained but produce not-meaningful multiples.",
            "Model explanation failure preserves deterministic valuation output.",
            "No eligible precedents terminates without an implied value.",
        ),
        (
            "Fixture-heavy evaluation is small and synthetic.",
            "No licensed transaction database or production embedding/model provider is evaluated.",
            "Checkpoint persistence is in-memory and process-local.",
            "Metrics do not establish production recall, legal completeness, "
            "or valuation accuracy.",
        ),
    )


def _context(context_id: str) -> AcquisitionContext:
    return AcquisitionContext(
        context_id,
        "B2B fintech infrastructure",
        "Payments, ledger, banking API, and compliance infrastructure",
        ("United States", "United Kingdom"),
        date(2020, 1, 1),
        date(2025, 12, 31),
    )


def main() -> None:
    print(json.dumps(run_final_evaluation().to_dict(), indent=2))


if __name__ == "__main__":
    main()
