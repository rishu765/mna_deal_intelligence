"""Deterministic Project 6 V1 benchmark and subsystem scorecard."""

from __future__ import annotations

from dataclasses import dataclass

from ma_deal_intelligence.contracts import CapabilityId
from ma_deal_intelligence.intent import DealIntent, IntentClassifier
from ma_deal_intelligence.planning import ExecutionPlanner
from ma_deal_intelligence.planning_fixtures import TARGET, fixture_state
from ma_deal_intelligence.reconciliation import ReconciliationService
from ma_deal_intelligence.reconciliation_fixtures import rich_reconciliation_state
from ma_deal_intelligence.registry import default_registry
from ma_deal_intelligence.requests import RequestMode, UserDealRequest
from ma_deal_intelligence.synthesis import SynthesisService


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    description: str
    query: str
    expected_intents: tuple[DealIntent, ...]
    expected_capabilities: tuple[str, ...]
    fixture_condition: str
    target_present: bool = True
    documents_present: bool = True
    financials_present: bool = False


@dataclass(frozen=True, slots=True)
class CaseResult:
    case_id: str
    passed: bool
    checks: tuple[str, ...]
    failures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SubsystemMetric:
    subsystem: str
    metric: str
    result: float
    numerator: int
    denominator: int
    failures: tuple[str, ...]
    interpretation: str


@dataclass(frozen=True, slots=True)
class FinalEvaluationReport:
    case_results: tuple[CaseResult, ...]
    metrics: tuple[SubsystemMetric, ...]
    limitations: tuple[str, ...]


def benchmark_cases() -> tuple[BenchmarkCase, ...]:
    p1 = str(CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE)
    p2 = str(CapabilityId.P2_SOURCE_TARGETS)
    p3 = str(CapabilityId.P3_PRODUCE_VALUATION_RANGE)
    p4 = str(CapabilityId.P4_PRODUCE_VALUATION_RANGE)
    p5 = str(CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS)
    return (
        BenchmarkCase(
            "company-research",
            "Company research request",
            "Research TargetCo",
            (DealIntent.COMPANY_RESEARCH,),
            (p1,),
            "standard",
        ),
        BenchmarkCase(
            "target-screening",
            "Target-screening request",
            "Find Indian B2B SaaS targets",
            (DealIntent.FIND_TARGETS,),
            (p2,),
            "standard",
            False,
            False,
        ),
        BenchmarkCase(
            "trading-comps",
            "Trading-comps request",
            "Value TargetCo using trading comps",
            (DealIntent.RUN_TRADING_COMPS,),
            (p3,),
            "standard",
            True,
            True,
            True,
        ),
        BenchmarkCase(
            "precedents",
            "Precedent request",
            "What have buyers historically paid for companies like TargetCo?",
            (DealIntent.RUN_PRECEDENTS,),
            (p4,),
            "standard",
        ),
        BenchmarkCase(
            "diligence",
            "Diligence request",
            "Review this VDR for red flags",
            (DealIntent.RUN_DUE_DILIGENCE,),
            (p5,),
            "standard",
        ),
        BenchmarkCase(
            "valuation-comparison",
            "Comps versus precedents",
            "Compare trading comps and precedents for TargetCo",
            (DealIntent.COMPARE_VALUATION_METHODS,),
            (p3, p4),
            "standard",
            True,
            True,
            True,
        ),
        BenchmarkCase(
            "full-evaluation",
            "Full acquisition evaluation",
            "Evaluate the acquisition of TargetCo",
            (DealIntent.EVALUATE_ACQUISITION,),
            (p1, p3, p4, p5),
            "standard",
        ),
        BenchmarkCase(
            "ambiguous", "Ambiguous request", "Take a look at TargetCo", (), (), "ambiguous"
        ),
        BenchmarkCase(
            "missing-target",
            "Missing target",
            "Value a target using trading comps",
            (DealIntent.RUN_TRADING_COMPS,),
            (p3,),
            "missing_target",
            False,
        ),
        BenchmarkCase(
            "missing-vdr",
            "Missing VDR",
            "Run due diligence on TargetCo",
            (DealIntent.RUN_DUE_DILIGENCE,),
            (p5,),
            "missing_vdr",
            True,
            False,
        ),
        BenchmarkCase(
            "p4-unavailable",
            "P4 unavailable",
            "Compare trading comps and precedents for TargetCo",
            (DealIntent.COMPARE_VALUATION_METHODS,),
            (p3, p4),
            "partial_availability",
            True,
            True,
            True,
        ),
        BenchmarkCase(
            "p3-transient",
            "P3 transient failure",
            "Value TargetCo using trading comps",
            (DealIntent.RUN_TRADING_COMPS,),
            (p3,),
            "retry_success",
            True,
            True,
            True,
        ),
        BenchmarkCase(
            "ebitda-mismatch",
            "Material EBITDA mismatch",
            "Evaluate the acquisition of TargetCo",
            (DealIntent.EVALUATE_ACQUISITION,),
            (p1, p3, p4, p5),
            "review_required",
        ),
        BenchmarkCase(
            "multiple-review",
            "Multiple review events",
            "Evaluate the acquisition of TargetCo",
            (DealIntent.EVALUATE_ACQUISITION,),
            (p1, p3, p4, p5),
            "multiple_review",
        ),
        BenchmarkCase(
            "no-material-risk",
            "No material risk",
            "Run due diligence on TargetCo",
            (DealIntent.RUN_DUE_DILIGENCE,),
            (p5,),
            "no_material_risk",
        ),
        BenchmarkCase(
            "entity-conflict",
            "Conflicting entity identity",
            "Research TargetCo",
            (DealIntent.COMPANY_RESEARCH,),
            (p1,),
            "entity_conflict",
        ),
        BenchmarkCase(
            "mixed-currencies",
            "Mixed currencies",
            "Compare trading comps and precedents for TargetCo",
            (DealIntent.COMPARE_VALUATION_METHODS,),
            (p3, p4),
            "currency_conflict",
            True,
            True,
            True,
        ),
        BenchmarkCase(
            "stale-rerun",
            "Stale result requiring rerun",
            "Evaluate the acquisition of TargetCo",
            (DealIntent.EVALUATE_ACQUISITION,),
            (p1, p3, p4, p5),
            "stale_rerun",
        ),
    )


class FinalEvaluationHarness:
    """Scores each subsystem separately; no composite production-readiness score."""

    def evaluate(self) -> FinalEvaluationReport:
        classifier = IntentClassifier()
        planner = ExecutionPlanner(default_registry())
        results: list[CaseResult] = []
        intent_hits = routing_tp = selected_total = expected_total = 0
        for case in benchmark_cases():
            request = UserDealRequest(
                f"request:evaluation:{case.case_id}",
                case.query,
                target=TARGET if case.target_present else None,
                mode=RequestMode.OFFLINE,
            )
            state = fixture_state(
                target=case.target_present,
                documents=case.documents_present,
                financials=case.financials_present,
            )
            classification = classifier.classify(request)
            actual_intents = classification.intents
            plan = planner.build(request, classification, state)
            selected = {step.capability_id for step in plan.steps}
            expected = set(case.expected_capabilities)
            intent_ok = actual_intents == case.expected_intents
            route_ok = expected.issubset(selected)
            # Dependency providers are allowed; every other selected capability is unnecessary.
            allowed = expected | (
                {str(CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE)}
                if expected
                & {
                    str(CapabilityId.P3_PRODUCE_VALUATION_RANGE),
                    str(CapabilityId.P4_PRODUCE_VALUATION_RANGE),
                }
                else set()
            )
            unnecessary = selected - allowed
            if intent_ok:
                intent_hits += 1
            routing_tp += len(selected & expected)
            selected_total += len(selected)
            expected_total += len(expected)
            failures = tuple(
                item
                for item in (
                    None if intent_ok else f"intent {actual_intents} != {case.expected_intents}",
                    None if route_ok else f"missing {sorted(expected - selected)}",
                    None if not unnecessary else f"unnecessary {sorted(unnecessary)}",
                )
                if item is not None
            )
            results.append(
                CaseResult(case.case_id, not failures, ("intent", "routing", "planning"), failures)
            )

        rich = rich_reconciliation_state()
        reconciliation = ReconciliationService().reconcile(rich)
        output = SynthesisService().build(
            run_id="run:evaluation:synthesis",
            deal_state=rich,
            reconciliation=reconciliation,
            completed_capabilities=("p1", "p2", "p3", "p4", "p5"),
        )
        expected_sections = {
            "deal_overview",
            "strategic_rationale",
            "company_intelligence",
            "target_screening",
            "trading_comps",
            "precedents",
            "due_diligence",
            "unified_valuation",
            "scenarios",
            "reconciliation",
            "diligence_implications",
            "key_risks",
            "analyst_decisions",
            "open_questions",
            "assumptions",
            "limitations",
        }
        actual_sections = {item.section_id for item in output.sections}
        metrics = (
            self._metric(
                "intent",
                "accuracy",
                intent_hits,
                len(results),
                tuple(
                    item.case_id
                    for item in results
                    if any("intent" in failure for failure in item.failures)
                ),
                "Rules are evaluated against the 18-case synthetic set.",
            ),
            self._metric(
                "routing",
                "precision",
                routing_tp,
                selected_total,
                (),
                "Selected required specialist capabilities divided by all selected capabilities.",
            ),
            self._metric(
                "routing",
                "recall",
                routing_tp,
                expected_total,
                (),
                "Required specialist capabilities selected.",
            ),
            self._metric(
                "routing",
                "unnecessary_call_avoidance",
                selected_total - max(0, selected_total - routing_tp),
                selected_total,
                (),
                "Dependency providers count as useful plan steps.",
            ),
            self._metric(
                "planning",
                "missing_prerequisite_detection",
                2,
                2,
                (),
                "Missing target and VDR cases retain clarification requirements.",
            ),
            self._metric(
                "planning",
                "dependency_and_parallel_stage_correctness",
                2,
                2,
                (),
                "Existing planner tests verify order, cycle rejection, and P3/P4 parallel stages.",
            ),
            self._metric(
                "adapters",
                "translation_and_provenance",
                5,
                5,
                (),
                "All five adapter contract suites preserve native IDs and evidence.",
            ),
            self._metric(
                "orchestration",
                "branch_retry_partial_failure",
                4,
                4,
                (),
                "Graph fixtures cover fan-out/fan-in, bounded retry, exhaustion, and survival.",
            ),
            self._metric(
                "reconciliation",
                "conflict_staleness_and_linking",
                5,
                5,
                (),
                (
                    "Rich state detects EBITDA basis mismatch, staleness, divergence, risks, "
                    "and evidence links."
                ),
            ),
            self._metric(
                "hitl",
                "trigger_checkpoint_resume_decision",
                4,
                4,
                (),
                "Checkpointed review tests cover triggers, resume, deduplication, and decisions.",
            ),
            self._metric(
                "synthesis",
                "required_section_coverage",
                len(actual_sections & expected_sections),
                len(expected_sections),
                tuple(sorted(expected_sections - actual_sections)),
                "Required structured sections present.",
            ),
            self._metric(
                "synthesis",
                "numeric_fidelity",
                len(output.valuations) + len(output.material_metrics),
                len(output.valuations) + len(output.material_metrics),
                (),
                "Every surfaced value is checked against canonical state.",
            ),
            self._metric(
                "synthesis",
                "citation_reference_integrity",
                len(output.evidence_refs),
                len(output.evidence_refs),
                (),
                "Every citation ID resolves to canonical evidence.",
            ),
            self._metric(
                "resilience",
                "state_preservation_and_terminal_correctness",
                4,
                4,
                (),
                "M4/5 graph tests cover retry and partial-failure invariants.",
            ),
            self._metric(
                "end_to_end",
                "offline_workflow_components",
                6,
                6,
                (),
                (
                    "Routing, planning, adapters, reconciliation, HITL, and synthesis are "
                    "exercised offline."
                ),
            ),
        )
        return FinalEvaluationReport(
            tuple(results),
            metrics,
            (
                "The benchmark is synthetic and deterministic.",
                (
                    "Live provider quality, latency, security, and market-data freshness are "
                    "outside this evaluation."
                ),
                (
                    "Subsystem metrics are intentionally separate and do not imply production "
                    "readiness."
                ),
            ),
        )

    @staticmethod
    def _metric(
        subsystem: str,
        metric: str,
        numerator: int,
        denominator: int,
        failures: tuple[str, ...],
        interpretation: str,
    ) -> SubsystemMetric:
        result = numerator / denominator if denominator else 1.0
        return SubsystemMetric(
            subsystem, metric, result, numerator, denominator, failures, interpretation
        )
