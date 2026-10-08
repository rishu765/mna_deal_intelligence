"""Transparent source-priority, amendment, support, and conflict verification rules."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from ma_precedent_transactions.domain import EvidenceReference, SourceReliability
from ma_precedent_transactions.extraction.models import (
    CapitalFactObservation,
    ConsiderationObservation,
    DateObservation,
    ExtractedObservation,
    FactConflict,
    FieldVerification,
    FinancialFactObservation,
    OwnershipFactObservation,
    PartyObservation,
    RevisionKind,
    StatusObservation,
    StructureObservation,
    ValuationFactObservation,
    VerificationStatus,
)


@dataclass(frozen=True, slots=True)
class VerificationResult:
    fields: tuple[FieldVerification, ...]
    conflicts: tuple[FactConflict, ...]


class SourcePriorityPolicy:
    """Context-aware reliability ordering with publication recency as a tie breaker."""

    _priority = {
        SourceReliability.CONTRACTUAL: 0,
        SourceReliability.REGULATORY: 1,
        SourceReliability.PRIMARY_COMPANY: 2,
        SourceReliability.TRUSTED_SECONDARY: 3,
        SourceReliability.OTHER: 4,
        SourceReliability.UNKNOWN: 5,
    }

    def rank(self, evidence: EvidenceReference) -> tuple[int, int]:
        published = evidence.publication_date or date.min
        return self._priority[evidence.reliability], -published.toordinal()


class TransactionVerificationService:
    def __init__(
        self,
        evidence: tuple[EvidenceReference, ...],
        policy: SourcePriorityPolicy | None = None,
    ) -> None:
        self._evidence = {item.evidence_id: item for item in evidence}
        self._policy = policy or SourcePriorityPolicy()

    def verify(self, observations: tuple[ExtractedObservation, ...]) -> VerificationResult:
        groups: dict[str, list[ExtractedObservation]] = defaultdict(list)
        for observation in observations:
            groups[_field(observation)].append(observation)
        fields = []
        conflicts = []
        for field, items in sorted(groups.items()):
            verification, conflict = self._verify_group(field, tuple(items))
            fields.append(verification)
            if conflict is not None:
                conflicts.append(conflict)
        return VerificationResult(tuple(fields), tuple(conflicts))

    def missing(self, field: str) -> FieldVerification:
        return FieldVerification(
            field,
            VerificationStatus.MISSING,
            None,
            (),
            (),
            (),
            "No extracted observation was supported by the retrieved context.",
        )

    def _verify_group(
        self, field: str, items: tuple[ExtractedObservation, ...]
    ) -> tuple[FieldVerification, FactConflict | None]:
        current = _current_revision(items)
        values: dict[str, list[ExtractedObservation]] = defaultdict(list)
        for item in current:
            values[_value(item)].append(item)
        selected = min(current, key=self._observation_rank)
        selected_value = _value(selected)
        supporters = tuple(item.observation_id for item in values[selected_value])
        conflicting = tuple(
            item.observation_id
            for value, group in values.items()
            if value != selected_value
            for item in group
        )
        evidence_ids = tuple(
            dict.fromkeys(value for item in current for value in item.evidence_ids)
        )
        independent_sources = {
            self._evidence[evidence_id].document_id or evidence_id
            for item in values[selected_value]
            for evidence_id in item.evidence_ids
            if evidence_id in self._evidence
        }
        explicitly_unavailable = all(
            isinstance(item, ValuationFactObservation) and item.amount is None for item in current
        )
        if explicitly_unavailable:
            status = VerificationStatus.MISSING
            rationale = "Sources explicitly state that the value is unavailable or undisclosed."
        elif conflicting:
            status = VerificationStatus.CONFLICTING
            rationale = "Current source observations disagree; all values are retained."
        elif len(independent_sources) >= 2:
            status = VerificationStatus.VERIFIED
            rationale = "At least two independent documents support the same current value."
        elif independent_sources:
            status = VerificationStatus.SINGLE_SOURCE
            rationale = "One source document supports the current value."
        else:
            status = VerificationStatus.UNVERIFIED
            rationale = "The observation has no resolvable source document."
        verification = FieldVerification(
            field,
            status,
            selected.observation_id,
            supporters,
            conflicting,
            evidence_ids,
            rationale,
        )
        conflict = None
        if conflicting and not explicitly_unavailable:
            conflict = FactConflict(
                field,
                tuple(item.observation_id for item in current),
                tuple(dict.fromkeys(_value(item) for item in current)),
                f"Conflicting current observations for {field}; preferred source is retained only "
                "as a review candidate.",
            )
        return verification, conflict

    def _observation_rank(self, observation: ExtractedObservation) -> tuple[int, int, str]:
        ranks = [
            self._policy.rank(self._evidence[value])
            for value in observation.evidence_ids
            if value in self._evidence
        ]
        priority, recency = min(ranks, default=(99, 0))
        effective = observation.effective_date or date.min
        return priority, min(recency, -effective.toordinal()), observation.observation_id


def _current_revision(items: tuple[ExtractedObservation, ...]) -> tuple[ExtractedObservation, ...]:
    dated_amendments = [
        item
        for item in items
        if item.revision in {RevisionKind.AMENDED, RevisionKind.CURRENT}
        and item.effective_date is not None
    ]
    if not dated_amendments:
        return items
    effective_dates: list[date] = []
    for item in dated_amendments:
        if item.effective_date is not None:
            effective_dates.append(item.effective_date)
    latest = max(effective_dates)
    return tuple(item for item in dated_amendments if item.effective_date == latest)


def _field(observation: ExtractedObservation) -> str:
    if isinstance(observation, PartyObservation):
        return f"party.{observation.role.value}"
    if isinstance(observation, DateObservation):
        return f"date.{observation.kind.value}"
    if isinstance(observation, StatusObservation):
        return "lifecycle.status"
    if isinstance(observation, StructureObservation):
        return "transaction.structure"
    if isinstance(observation, ConsiderationObservation):
        return f"consideration.{observation.kind.value}"
    if isinstance(observation, OwnershipFactObservation):
        return "ownership"
    if isinstance(observation, ValuationFactObservation):
        return f"valuation.{observation.measure.value}"
    if isinstance(observation, FinancialFactObservation):
        basis = observation.basis.value
        return f"financial.{observation.name.value}.{observation.period}.{basis}"
    if isinstance(observation, CapitalFactObservation):
        return f"capital.{observation.kind.value}"
    name = type(observation).__name__.removesuffix("Observation").casefold()
    return name


def _value(observation: ExtractedObservation) -> str:
    if isinstance(observation, PartyObservation):
        return observation.legal_name.casefold()
    if isinstance(observation, DateObservation):
        return observation.value.isoformat()
    if isinstance(observation, StatusObservation):
        return observation.status.value
    if isinstance(observation, StructureObservation):
        return "|".join(
            (
                observation.transaction_type.value,
                observation.buyer_type.value,
                observation.jurisdiction or "?",
            )
        )
    if isinstance(observation, ConsiderationObservation):
        amount = (
            "?"
            if observation.amount is None
            else "|".join(
                (observation.amount.value, observation.amount.currency, observation.amount.unit)
            )
        )
        return f"{amount}|{observation.quantity or '?'}|{observation.quantity_unit or '?'}"
    if isinstance(observation, OwnershipFactObservation):
        return "|".join(
            value or "?"
            for value in (
                observation.pre_deal_percent,
                observation.acquired_percent,
                observation.post_deal_percent,
            )
        )
    if isinstance(observation, ValuationFactObservation):
        if observation.amount is None:
            return "unavailable"
        return "|".join(
            (observation.amount.value, observation.amount.currency, observation.amount.unit)
        )
    if isinstance(observation, FinancialFactObservation):
        return "|".join(
            (
                observation.value,
                observation.currency,
                observation.unit,
                observation.period,
                observation.basis.value,
            )
        )
    if isinstance(observation, CapitalFactObservation):
        assert observation.amount is not None
        return "|".join(
            (observation.amount.value, observation.amount.currency, observation.amount.unit)
        )
    return observation.source_wording.casefold()
