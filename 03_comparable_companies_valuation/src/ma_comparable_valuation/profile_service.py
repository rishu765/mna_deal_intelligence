"""Deterministic service for building an auditable target financial profile."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace

from ma_comparable_valuation.domain import (
    CapitalStructure,
    DataQualityFlag,
    FinancialMetric,
    FinancialObservation,
    MarketMetric,
    MarketMetricKind,
    ProfileCompleteness,
    ProfileCompletenessStatus,
    ProfileConflict,
    ProfileIssue,
    ProfileIssueKind,
    ShareCountBasis,
    TargetCompany,
    TargetFinancialProfile,
)
from ma_comparable_valuation.normalization import normalize_observation

DEFAULT_REQUIRED_FIELDS = (
    "revenue",
    "ebitda",
    "cash_and_equivalents",
    "debt",
    "diluted_shares_end_of_period",
)


@dataclass(frozen=True, slots=True)
class TargetFinancialProfileService:
    required_fields: tuple[str, ...] = DEFAULT_REQUIRED_FIELDS
    capital_structure_policy_id: str = "target-capital-structure-v1"

    def build(
        self,
        target: TargetCompany,
        observations: tuple[FinancialObservation, ...],
    ) -> TargetFinancialProfile:
        financial: list[FinancialMetric] = []
        capital: list[MarketMetric] = []
        decisions = []
        issues: list[ProfileIssue] = []
        seen_signatures: dict[tuple[object, ...], str] = {}

        for observation in observations:
            signature = _source_signature(observation)
            prior_id = seen_signatures.get(signature)
            if prior_id is not None:
                issues.append(
                    ProfileIssue(
                        ProfileIssueKind.DUPLICATE,
                        "Exact duplicate source observation was not normalized twice.",
                        (prior_id, observation.observation_id),
                    )
                )
                continue
            seen_signatures[signature] = observation.observation_id
            try:
                result = normalize_observation(observation)
            except ValueError as error:
                issues.append(
                    ProfileIssue(
                        _issue_kind(error),
                        str(error),
                        (observation.observation_id,),
                    )
                )
                continue
            decisions.append(result.decision)
            if isinstance(result.metric, FinancialMetric):
                financial.append(result.metric)
            else:
                capital.append(result.metric)

        financial_conflicts, financial = _financial_conflicts(financial)
        capital_conflicts, capital = _capital_conflicts(capital)
        conflicts = (*financial_conflicts, *capital_conflicts)
        issues.extend(
            ProfileIssue(
                ProfileIssueKind.CONFLICT,
                conflict.reason,
                conflict.observation_ids,
            )
            for conflict in conflicts
        )

        capital_structure = None
        if capital:
            capital_structure = CapitalStructure(
                snapshot_id=f"target-capital:{target.identity.company_id}",
                as_of=max(item.as_of for item in capital),
                policy_id=self.capital_structure_policy_id,
                components=tuple(capital),
            )
        completeness = _completeness(
            tuple(financial), tuple(capital), self.required_fields, bool(conflicts)
        )
        issues.extend(
            ProfileIssue(ProfileIssueKind.MISSING, f"Missing required field: {field}")
            for field in completeness.missing
        )
        warnings = tuple(issue.message for issue in issues)
        return TargetFinancialProfile(
            target=target,
            metrics=tuple(financial),
            capital_structure=capital_structure,
            observations=observations,
            normalization_decisions=tuple(decisions),
            conflicts=tuple(conflicts),
            completeness=completeness,
            issues=tuple(issues),
            warnings=tuple(dict.fromkeys(warnings)),
        )


def _source_signature(observation: FinancialObservation) -> tuple[object, ...]:
    return (
        observation.raw_metric_name.casefold(),
        observation.value,
        observation.currency,
        None if observation.unit is None else observation.unit.casefold(),
        observation.period,
        observation.as_of,
        observation.basis,
        observation.adjustment_label,
        tuple(item.evidence_id for item in observation.evidence),
    )


def _financial_key(metric: FinancialMetric) -> tuple[object, ...]:
    return (metric.name, metric.period, metric.basis, metric.currency)


def _capital_key(metric: MarketMetric) -> tuple[object, ...]:
    return (metric.kind, metric.share_basis, metric.as_of, metric.currency)


def _financial_conflicts(
    metrics: list[FinancialMetric],
) -> tuple[tuple[ProfileConflict, ...], list[FinancialMetric]]:
    grouped: dict[tuple[object, ...], list[int]] = defaultdict(list)
    for index, metric in enumerate(metrics):
        grouped[_financial_key(metric)].append(index)
    conflicts: list[ProfileConflict] = []
    for indexes in grouped.values():
        values = {(metrics[index].value, metrics[index].unit) for index in indexes}
        if len(values) <= 1:
            continue
        observations = tuple(
            observation_id
            for index in indexes
            for observation_id in metrics[index].source_observation_ids
        )
        first = metrics[indexes[0]]
        conflicts.append(
            ProfileConflict(
                conflict_id=f"conflict:{first.name.value}:{len(conflicts) + 1}",
                field=first.name.value,
                observation_ids=observations,
                reason=(
                    "Different normalized values were reported for the same metric, period, "
                    "basis, and currency."
                ),
            )
        )
        for index in indexes:
            metrics[index] = _with_financial_conflicting_flag(metrics[index])
    return tuple(conflicts), metrics


def _capital_conflicts(
    metrics: list[MarketMetric],
) -> tuple[tuple[ProfileConflict, ...], list[MarketMetric]]:
    grouped: dict[tuple[object, ...], list[int]] = defaultdict(list)
    for index, metric in enumerate(metrics):
        grouped[_capital_key(metric)].append(index)
    conflicts: list[ProfileConflict] = []
    for indexes in grouped.values():
        values = {(metrics[index].value, metrics[index].unit) for index in indexes}
        if len(values) <= 1:
            continue
        observations = tuple(
            observation_id
            for index in indexes
            for observation_id in metrics[index].source_observation_ids
        )
        first = metrics[indexes[0]]
        conflicts.append(
            ProfileConflict(
                conflict_id=f"conflict:{first.kind.value}:{len(conflicts) + 1}",
                field=first.kind.value,
                observation_ids=observations,
                reason=(
                    "Different normalized values were reported for the same capital-structure "
                    "field, as-of time, share basis, and currency."
                ),
            )
        )
        for index in indexes:
            metrics[index] = _with_market_conflicting_flag(metrics[index])
    return tuple(conflicts), metrics


def _with_financial_conflicting_flag(metric: FinancialMetric) -> FinancialMetric:
    flags = metric.quality_flags
    if DataQualityFlag.CONFLICTING not in flags:
        flags = (*flags, DataQualityFlag.CONFLICTING)
    return replace(metric, quality_flags=flags)


def _with_market_conflicting_flag(metric: MarketMetric) -> MarketMetric:
    flags = metric.quality_flags
    if DataQualityFlag.CONFLICTING not in flags:
        flags = (*flags, DataQualityFlag.CONFLICTING)
    return replace(metric, quality_flags=flags)


def _completeness(
    financial: tuple[FinancialMetric, ...],
    capital: tuple[MarketMetric, ...],
    required_fields: tuple[str, ...],
    has_conflicts: bool,
) -> ProfileCompleteness:
    available = {item.name.value for item in financial}
    available.update(item.kind.value for item in capital)
    if any(
        item.kind is MarketMetricKind.DILUTED_SHARES
        and item.share_basis is ShareCountBasis.DILUTED_END_OF_PERIOD
        for item in capital
    ):
        available.add("diluted_shares_end_of_period")
    present = tuple(field for field in required_fields if field in available)
    missing = tuple(field for field in required_fields if field not in available)
    if not present:
        status = ProfileCompletenessStatus.INSUFFICIENT
    elif missing or has_conflicts:
        status = ProfileCompletenessStatus.PARTIAL
    else:
        status = ProfileCompletenessStatus.COMPLETE
    return ProfileCompleteness(present=present, missing=missing, status=status)


def _issue_kind(error: ValueError) -> ProfileIssueKind:
    message = str(error).casefold()
    if "unsupported" in message:
        return ProfileIssueKind.UNSUPPORTED
    return ProfileIssueKind.INVALID
