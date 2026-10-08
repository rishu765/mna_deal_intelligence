"""Deterministic subsystem evaluation against controlled fixture expectations."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from ma_comparable_valuation.domain import (
    FinancialMetricName,
    FinancialUnit,
    ManualOverrideAction,
    ManualPeerOverride,
    MarketMetricKind,
    MetricBasis,
    MultipleKind,
    MultipleStatus,
    SelectionDecision,
)
from ma_comparable_valuation.evaluation.dataset import EvaluationDataset
from ma_comparable_valuation.evaluation.models import (
    EvaluationCheck,
    EvaluationReport,
    SubsystemEvaluation,
)
from ma_comparable_valuation.fixtures import FixtureTargetProfileProvider
from ma_comparable_valuation.ingestion import ComparableSnapshotService
from ma_comparable_valuation.peer_fixtures import (
    FIXTURE_VALUATION_TIME,
    FixtureComparableUniverseProvider,
    FixtureFinancialDataProvider,
    FixtureMarketDataProvider,
    FixtureSemanticSimilarityEvaluator,
)
from ma_comparable_valuation.profile_service import TargetFinancialProfileService
from ma_comparable_valuation.selection import ComparableSelectionService
from ma_comparable_valuation.valuation import CalculationStatus, ValuationEngine
from ma_comparable_valuation.valuation_fixtures import VALUATION_TIME
from ma_comparable_valuation.workflow import OfflineValuationService


class EvaluationRunner:
    """Run separate checks; no aggregate quality score is produced."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def run(self, dataset: EvaluationDataset) -> EvaluationReport:
        result = OfflineValuationService().run()
        subsystems = (
            self._target_profile(result.target_profile, result.peer_set),
            self._selection(),
            self._ingestion(result),
            self._multiples(result),
            self._statistics(result),
            self._valuation(result),
            self._explanation(result),
        )
        return EvaluationReport(
            dataset.dataset_id,
            VALUATION_TIME.isoformat(),
            len(dataset.cases),
            subsystems,
            (
                "Eight synthetic cases and deterministic fixtures are a regression benchmark, "
                "not production-grade validation.",
                "No licensed live market-data or consensus-estimate provider is evaluated.",
                "The explanation rubric checks the offline structured provider; a live LLM judge "
                "is optional and not part of the correctness baseline.",
            ),
        )

    def _target_profile(self, target, peer_set) -> SubsystemEvaluation:  # type: ignore[no-untyped-def]
        peer_a = next(
            item for item in peer_set.snapshots if item.company.identity.company_id == "peer-a"
        )
        financial_gold = {
            FinancialMetricName.REVENUE: Decimal("4200"),
            FinancialMetricName.EBITDA: Decimal("680"),
            FinancialMetricName.EBIT: Decimal("510"),
            FinancialMetricName.NET_INCOME: Decimal("350"),
            FinancialMetricName.EPS: Decimal("7"),
        }
        actual_financial = {
            item.name: item.value
            for item in peer_a.financial_metrics
            if item.period.label == "LTM Jun-2026"
        }
        capital_gold = {
            MarketMetricKind.CASH_AND_EQUIVALENTS: Decimal("400"),
            MarketMetricKind.DEBT: Decimal("1000"),
            MarketMetricKind.DILUTED_SHARES: Decimal("50"),
        }
        actual_capital = (
            {}
            if target.capital_structure is None
            else {item.kind: item.value for item in target.capital_structure.components}
        )
        target_ltm = {
            item.name: item for item in target.metrics if item.period.label == "LTM Jun-2026"
        }
        provider = FixtureTargetProfileProvider(
            self.project_root / "data" / "targetco_profile.json"
        )
        raw_target, observations = provider.load()
        conflicting = replace(
            observations[0],
            observation_id="evaluation-conflicting-revenue",
            value=observations[0].value + Decimal("1"),
        )
        conflict_profile = TargetFinancialProfileService().build(
            raw_target, (*observations, conflicting)
        )
        checks = (
            _check(
                "financial-gold-values",
                "profitable-software",
                actual_financial == financial_gold,
                str(financial_gold),
                str(actual_financial),
            ),
            _check(
                "capital-gold-values",
                "industrial-debt",
                actual_capital == capital_gold,
                str(capital_gold),
                str(actual_capital),
            ),
            _check(
                "unit-normalization",
                "profitable-software",
                all(
                    item.unit in {FinancialUnit.MILLION, FinancialUnit.PER_SHARE}
                    for item in (*target.metrics, *peer_a.financial_metrics)
                ),
                "million aggregate values and per_share EPS",
                "normalized units preserved",
            ),
            _check(
                "period-and-basis",
                "mixed-basis",
                all(
                    item.period.label == "LTM Jun-2026" and item.basis is MetricBasis.REPORTED
                    for item in target_ltm.values()
                ),
                "exact LTM Jun-2026 reported semantics",
                str([(item.period.label, item.basis.value) for item in target_ltm.values()]),
            ),
            _check(
                "evidence-retention",
                "profitable-software",
                all(item.evidence for item in (*target.metrics, *peer_a.financial_metrics)),
                "evidence on every financial metric",
                "all metrics source-backed",
            ),
            _check(
                "conflict-handling",
                "mixed-basis",
                bool(conflict_profile.conflicts),
                "conflicting duplicate observations retained and flagged",
                f"{len(conflict_profile.conflicts)} conflict(s)",
            ),
        )
        return SubsystemEvaluation(
            "target_financial_profile",
            checks,
            "Gold values cover controlled INR fixtures, not arbitrary issuer disclosures.",
        )

    def _selection(self) -> SubsystemEvaluation:
        provider = FixtureTargetProfileProvider(
            self.project_root / "data" / "targetco_profile.json"
        )
        target, _ = provider.load()
        profile = provider.get_target_profile(target)
        universe = FixtureComparableUniverseProvider().get_universe(profile.target)
        financial = FixtureFinancialDataProvider()
        candidate_financials = {
            item.identity.company_id: financial.get_financial_metrics(item.identity.company_id)
            for item in universe.companies
        }
        service = ComparableSelectionService(
            semantic_evaluator=FixtureSemanticSimilarityEvaluator()
        )
        selection = service.select(profile, universe, candidate_financials=candidate_financials)
        decisions = {item.company_id: item for item in selection.decisions}
        overridden = service.select(
            profile,
            universe,
            candidate_financials=candidate_financials,
            overrides=(
                ManualPeerOverride(
                    "peer-e",
                    ManualOverrideAction.FORCE_INCLUDE,
                    "Evaluation analyst override.",
                    "evaluation",
                    FIXTURE_VALUATION_TIME,
                    universe.companies[-1].evidence,
                ),
            ),
        )
        override_e = next(item for item in overridden.decisions if item.company_id == "peer-e")
        checks = (
            _check(
                "strong-comp-overlap",
                "profitable-software",
                selection.selected_company_ids == ("peer-a", "peer-c"),
                "peer-a and peer-c selected",
                str(selection.selected_company_ids),
            ),
            _check(
                "obvious-exclusion",
                "profitable-software",
                decisions["peer-b"].decision is SelectionDecision.EXCLUDE,
                "peer-b excluded",
                decisions["peer-b"].decision.value,
            ),
            _check(
                "insufficient-data",
                "stale-market",
                decisions["peer-d"].decision is SelectionDecision.INSUFFICIENT_DATA,
                "peer-d insufficient_data",
                decisions["peer-d"].decision.value,
            ),
            _check(
                "rationale-quality",
                "profitable-software",
                all(item.rationale and item.evaluations for item in selection.decisions),
                "non-empty rationale with criterion evaluations",
                "all decisions explain criteria",
            ),
            _check(
                "manual-override",
                "profitable-software",
                override_e.decision is SelectionDecision.INCLUDE
                and override_e.manual_override is not None,
                "peer-e force-included with recorded override",
                override_e.decision.value,
            ),
        )
        return SubsystemEvaluation(
            "comparable_selection",
            checks,
            (
                "The five-company benchmark is illustrative and does not establish "
                "market-wide relevance."
            ),
        )

    def _ingestion(self, result) -> SubsystemEvaluation:  # type: ignore[no-untyped-def]
        snapshots = result.peer_set.snapshots
        peer_e = next(item for item in snapshots if item.company.identity.company_id == "peer-e")
        provider = FixtureTargetProfileProvider(
            self.project_root / "data" / "targetco_profile.json"
        )
        target, _ = provider.load()
        profile = provider.get_target_profile(target)
        universe = FixtureComparableUniverseProvider().get_universe(profile.target)
        financial = FixtureFinancialDataProvider()
        selection = ComparableSelectionService(
            semantic_evaluator=FixtureSemanticSimilarityEvaluator()
        ).select(
            profile,
            universe,
            candidate_financials={
                item.identity.company_id: financial.get_financial_metrics(item.identity.company_id)
                for item in universe.companies
            },
        )
        failed = ComparableSnapshotService(
            FixtureFinancialDataProvider(fail_company_ids=("peer-a",)),
            FixtureMarketDataProvider(fail_company_ids=("peer-a",)),
        ).build_peer_set(universe, selection, valuation_time=FIXTURE_VALUATION_TIME)
        failed_a = next(
            item for item in failed.snapshots if item.company.identity.company_id == "peer-a"
        )
        checks = (
            _check(
                "snapshot-as-of",
                "profitable-software",
                all(item.as_of == VALUATION_TIME for item in snapshots),
                VALUATION_TIME.isoformat(),
                str({item.as_of.isoformat() for item in snapshots}),
            ),
            _check(
                "source-preservation",
                "profitable-software",
                all(
                    metric.evidence
                    for snapshot in snapshots
                    for metric in (*snapshot.financial_metrics, *snapshot.market_metrics)
                ),
                "evidence on every ingested metric",
                "all ingested metrics source-backed",
            ),
            _check(
                "financial-periods",
                "forward-estimates",
                {"LTM Jun-2026", "FY2027E"}
                <= {
                    metric.period.label
                    for snapshot in snapshots
                    for metric in snapshot.financial_metrics
                },
                "LTM Jun-2026 and FY2027E preserved",
                "historical and forecast periods remain distinct",
            ),
            _check(
                "missing-market-data",
                "stale-market",
                any("debt" in warning.casefold() for warning in peer_e.warnings),
                "missing debt warning on peer-e",
                "; ".join(peer_e.warnings),
            ),
            _check(
                "provider-failure",
                "stale-market",
                not failed_a.financial_metrics and not failed_a.market_metrics,
                "provider failures produce partial snapshot without exception",
                (
                    f"financial={len(failed_a.financial_metrics)}, "
                    f"market={len(failed_a.market_metrics)}"
                ),
            ),
        )
        return SubsystemEvaluation(
            "market_financial_ingestion",
            checks,
            "Provider behavior is evaluated with deterministic fixture failures, not live outages.",
        )

    def _multiples(self, result) -> SubsystemEvaluation:  # type: ignore[no-untyped-def]
        sets = {
            (item.request.definition.kind, item.request.period_label): item
            for item in result.valuation.multiple_sets
        }
        peer_a = {
            key: next(value for value in item.multiples if value.company_id == "peer-a")
            for key, item in sets.items()
        }
        negative = next(
            value
            for value in sets[(MultipleKind.EV_EBITDA, "LTM Jun-2026")].multiples
            if value.company_id == "peer-d"
        )
        expected = {
            (MultipleKind.EV_REVENUE, "LTM Jun-2026"): Decimal("25700") / Decimal("4200"),
            (MultipleKind.EV_EBITDA, "LTM Jun-2026"): Decimal("25700") / Decimal("680"),
            (MultipleKind.EV_EBIT, "LTM Jun-2026"): Decimal("25700") / Decimal("510"),
            (MultipleKind.PRICE_EARNINGS, "LTM Jun-2026"): Decimal("125") / Decimal("7"),
        }
        checks = tuple(
            _check(
                f"{kind.value}-arithmetic",
                "profitable-software",
                peer_a[(kind, period)].value == value,
                str(value),
                str(peer_a[(kind, period)].value),
            )
            for (kind, period), value in expected.items()
        ) + (
            _check(
                "negative-denominator",
                "negative-ebitda",
                negative.status is MultipleStatus.NOT_MEANINGFUL
                and negative.denominator_value == Decimal("-100"),
                "not_meaningful with raw -100 denominator",
                f"{negative.status.value}, {negative.denominator_value}",
            ),
            _check(
                "forward-label",
                "forward-estimates",
                peer_a[(MultipleKind.EV_REVENUE, "FY2027E")].denominator_period.label == "FY2027E",
                "FY2027E",
                peer_a[(MultipleKind.EV_REVENUE, "FY2027E")].denominator_period.label,
            ),
        )
        return SubsystemEvaluation(
            "trading_multiples",
            checks,
            "Exact arithmetic covers four V1 multiple definitions on controlled Decimal inputs.",
        )

    def _statistics(self, result) -> SubsystemEvaluation:  # type: ignore[no-untyped-def]
        revenue = next(
            item
            for item in result.valuation.multiple_sets
            if item.request.definition.kind is MultipleKind.EV_REVENUE
            and item.request.period_label == "LTM Jun-2026"
        ).statistics
        expected = (
            Decimal("3.725"),
            Decimal("4.915625"),
            Decimal("5.715773809523809523809523810"),
            Decimal("7.982142857142857142857142857"),
            Decimal("13.57142857142857142857142857"),
        )
        actual = (
            revenue.minimum,
            revenue.percentile_25,
            revenue.median,
            revenue.percentile_75,
            revenue.maximum,
        )
        checks = (
            _check(
                "five-number-summary",
                "profitable-software",
                actual == expected,
                str(expected),
                str(actual),
            ),
            _check(
                "outlier-policy",
                "profitable-software",
                len(revenue.outlier_multiple_ids) == 1
                and revenue.count == 4
                and revenue.percentile_method == "linear_interpolation_r7",
                "one retained IQR outlier; four valid values; type-7 interpolation",
                (
                    f"outliers={len(revenue.outlier_multiple_ids)}, count={revenue.count}, "
                    f"method={revenue.percentile_method}"
                ),
            ),
        )
        return SubsystemEvaluation(
            "peer_statistics",
            checks,
            "Small peer counts make quartiles sensitive even when interpolation is exact.",
        )

    def _valuation(self, result) -> SubsystemEvaluation:  # type: ignore[no-untyped-def]
        ebitda = next(
            item
            for item in result.valuation.ranges
            if item.request.definition.kind is MultipleKind.EV_EBITDA
        )
        bridge = ValuationEngine().bridge_target(
            result.target_profile,
            Decimal("1000"),
            "INR",
            FinancialUnit.MILLION,
            "evaluation",
        )
        checks = (
            _check(
                "implied-ev-range",
                "profitable-software",
                ebitda.low.implied_value == Decimal("820") * ebitda.low.multiple
                and ebitda.mid.implied_value == Decimal("820") * ebitda.mid.multiple
                and ebitda.high.implied_value == Decimal("820") * ebitda.high.multiple,
                "each EV anchor equals target EBITDA 820 times peer anchor",
                (
                    f"{ebitda.low.implied_value}, {ebitda.mid.implied_value}, "
                    f"{ebitda.high.implied_value}"
                ),
            ),
            _check(
                "bridge-signs",
                "industrial-debt",
                bridge.implied_equity_value == Decimal("400"),
                "1000 EV - 1000 debt + 400 cash = 400 equity",
                str(bridge.implied_equity_value),
            ),
            _check(
                "per-share",
                "industrial-debt",
                ebitda.mid.implied_per_share == ebitda.mid.implied_equity_value / Decimal("50"),
                "mid equity value divided by 50 million diluted shares",
                str(ebitda.mid.implied_per_share),
            ),
            _check(
                "multi-method-output",
                "forward-estimates",
                len(result.valuation.multiple_sets) == 7
                and {item.request.definition.kind for item in result.valuation.ranges}
                == {MultipleKind.EV_REVENUE, MultipleKind.EV_EBITDA},
                "seven peer sets and only compatible target ranges",
                (
                    f"sets={len(result.valuation.multiple_sets)}, "
                    f"ranges={len(result.valuation.ranges)}"
                ),
            ),
        )
        return SubsystemEvaluation(
            "implied_valuation",
            checks,
            (
                "Target fixture lacks EBIT/EPS/forward metrics, so those peer sets "
                "do not imply ranges."
            ),
        )

    def _explanation(self, result) -> SubsystemEvaluation:  # type: ignore[no-untyped-def]
        explanation = result.valuation.explanation
        assert explanation is not None
        valid_count = sum(item.statistics.count for item in result.valuation.multiple_sets)
        excluded_count = sum(
            item.statistics.excluded_count for item in result.valuation.multiple_sets
        )
        expected_assessment = (
            f"The peer evidence supplies {valid_count} usable multiple observations and "
            f"{excluded_count} explicit exclusions across the requested methods."
        )
        checks = (
            _check(
                "grounding",
                "profitable-software",
                bool(explanation.evidence_ids),
                "one or more evidence references",
                f"{len(explanation.evidence_ids)} evidence IDs",
            ),
            _check(
                "deterministic-consistency",
                "profitable-software",
                explanation.peer_set_assessment == expected_assessment,
                expected_assessment,
                explanation.peer_set_assessment,
            ),
            _check(
                "outlier-commentary",
                "profitable-software",
                bool(explanation.outlier_commentary),
                "comment on flagged outlier",
                str(explanation.outlier_commentary),
            ),
            _check(
                "caveat-quality",
                "negative-earnings",
                "true value" in explanation.range_interpretation.casefold(),
                "explicitly reject false certainty",
                explanation.range_interpretation,
            ),
            _check(
                "structured-status",
                "profitable-software",
                explanation.status is CalculationStatus.AVAILABLE,
                "available structured explanation",
                explanation.status.value,
            ),
        )
        return SubsystemEvaluation(
            "ai_explanation",
            checks,
            "The offline explanation fixture tests grounding rules, not open-ended prose quality.",
        )


def _check(
    check_id: str,
    case_id: str,
    passed: bool,
    expected: str,
    actual: str,
) -> EvaluationCheck:
    return EvaluationCheck(
        check_id,
        case_id,
        passed,
        expected,
        actual,
        None if passed else f"Expected {expected}; observed {actual}.",
    )
