"""Retrieved-evidence to verified transaction-record application service."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import TypeVar

from ma_precedent_transactions.discovery import CandidateTransaction
from ma_precedent_transactions.domain import (
    CapitalComponentKind,
    CapitalStructureComponent,
    CapitalStructureSnapshot,
    ConsiderationComponent,
    ControlType,
    DealLifecycle,
    DealStatus,
    EvidenceReference,
    FactStatus,
    FinancialMetric,
    OwnershipObservation,
    TransactionIdentity,
    TransactionParty,
    TransactionRecord,
    TransactionStructure,
    ValuationMeasure,
    ValuationObservation,
)
from ma_precedent_transactions.errors import ExtractionError, NormalizationError
from ma_precedent_transactions.extraction.models import (
    DateObservation,
    DealDateKind,
    ExtractedObservation,
    ExtractionBatch,
    ExtractionTrace,
    FieldVerification,
    PartyObservation,
    PartyRole,
    StatusObservation,
    StructureObservation,
    VerificationStatus,
    VerifiedTransactionRecord,
)
from ma_precedent_transactions.extraction.normalization import (
    FinancialNormalizationService,
    derive_enterprise_value,
)
from ma_precedent_transactions.extraction.ports import (
    ExtractionRequest,
    StructuredTransactionExtractor,
)
from ma_precedent_transactions.extraction.verification import (
    TransactionVerificationService,
)
from ma_precedent_transactions.retrieval import DealRetrievalResult

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ExtractionOutcome:
    transaction: VerifiedTransactionRecord | None
    error: str | None = None


class StructuredTransactionService:
    def __init__(self, extractor: StructuredTransactionExtractor) -> None:
        self._extractor = extractor

    def build(
        self,
        candidate: CandidateTransaction,
        results: tuple[DealRetrievalResult, ...],
    ) -> VerifiedTransactionRecord:
        if not results:
            raise ExtractionError("structured extraction requires retrieved evidence")
        if any(item.transaction_id != candidate.candidate_id for item in results):
            raise ExtractionError("retrieved evidence crossed transaction boundaries")
        batch = self._extractor.extract(ExtractionRequest(candidate.candidate_id, results))
        if batch.transaction_id != candidate.candidate_id:
            raise ExtractionError("extraction transaction ID does not match candidate")
        evidence = _unique_evidence(results)
        verifier = TransactionVerificationService(evidence)
        verified = verifier.verify(batch.observations)
        selected = {
            item.field: item.selected_observation_id
            for item in verified.fields
            if item.selected_observation_id is not None
        }
        by_id = {item.observation_id: item for item in batch.observations}
        warnings = list(batch.warnings)
        normalizer = FinancialNormalizationService(evidence)

        acquirer_obs = _selected_party(selected, by_id, PartyRole.ACQUIRER)
        target_obs = _selected_party(selected, by_id, PartyRole.TARGET)
        if acquirer_obs is None:
            warnings.append("Acquirer was not extracted; candidate identity supplied the name.")
        if target_obs is None:
            warnings.append("Target was not extracted; candidate identity supplied the name.")
        acquirer_name = acquirer_obs.legal_name if acquirer_obs else candidate.acquirer_name
        target_name = target_obs.legal_name if target_obs else candidate.target_name
        acquirer = TransactionParty(
            f"party:{candidate.candidate_id}:acquirer",
            acquirer_name,
            alternative_names=acquirer_obs.aliases if acquirer_obs else (),
            evidence=normalizer.evidence_for(acquirer_obs.evidence_ids) if acquirer_obs else (),
        )
        target = TransactionParty(
            f"party:{candidate.candidate_id}:target",
            target_name,
            alternative_names=target_obs.aliases if target_obs else (),
            industry=candidate.industry,
            business_description=candidate.business_description,
            evidence=normalizer.evidence_for(target_obs.evidence_ids) if target_obs else (),
        )

        structure_obs = _selected(selected, by_id, "transaction.structure", StructureObservation)
        if structure_obs is None:
            warnings.append(
                "Transaction structure was not extracted; candidate discovery metadata was used."
            )
        transaction_type = (
            structure_obs.transaction_type
            if structure_obs is not None
            else candidate.transaction_type
        )
        structure = TransactionStructure(
            transaction_type,
            structure_obs.buyer_type if structure_obs else candidate.buyer_type,
            _control_type(batch),
            structure_obs.jurisdiction if structure_obs else candidate.jurisdiction,
            evidence=(normalizer.evidence_for(structure_obs.evidence_ids) if structure_obs else ()),
        )

        announcement = _selected_date(selected, by_id, DealDateKind.ANNOUNCEMENT)
        completion = _selected_date(selected, by_id, DealDateKind.COMPLETION)
        termination = _selected_date(selected, by_id, DealDateKind.TERMINATION)
        status_obs = _selected(selected, by_id, "lifecycle.status", StatusObservation)
        if announcement is None and candidate.announcement_date is not None:
            warnings.append(
                "Announcement date was not extracted; candidate discovery metadata was used."
            )
        if status_obs is None:
            warnings.append("Status was not extracted; candidate discovery metadata was used.")
        status = status_obs.status if status_obs else candidate.status
        if status is DealStatus.COMPLETED and completion is None:
            warnings.append("Completed status lacked a completion date; final status is unknown.")
            status = DealStatus.UNKNOWN
        lifecycle_evidence_ids = tuple(
            dict.fromkeys(
                value
                for observation in (announcement, completion, termination, status_obs)
                if observation is not None
                for value in observation.evidence_ids
            )
        )
        lifecycle = DealLifecycle(
            status,
            _status_as_of(batch, evidence),
            announcement.value if announcement else candidate.announcement_date,
            completion.value if completion else None,
            normalizer.evidence_for(lifecycle_evidence_ids) if lifecycle_evidence_ids else (),
        )

        consideration: list[ConsiderationComponent] = []
        ownership: list[OwnershipObservation] = []
        valuations: list[ValuationObservation] = []
        financials: list[FinancialMetric] = []
        capital: list[CapitalStructureComponent] = []
        traces: list[ExtractionTrace] = []
        for consideration_observation in batch.consideration:
            try:
                component, _ = normalizer.consideration(consideration_observation)
                consideration.append(component)
                traces.append(
                    _trace(
                        f"consideration.{consideration_observation.kind.value}",
                        consideration_observation,
                    )
                )
            except NormalizationError as error:
                warnings.append(f"Skipped {consideration_observation.observation_id}: {error}")
        for ownership_observation in batch.ownership:
            try:
                ownership.append(normalizer.ownership(ownership_observation))
                traces.append(_trace("ownership", ownership_observation))
            except (NormalizationError, ValueError) as error:
                warnings.append(f"Skipped {ownership_observation.observation_id}: {error}")
        for valuation_observation in batch.valuations:
            try:
                valuation, _ = normalizer.valuation(valuation_observation)
                valuations.append(valuation)
                traces.append(
                    _trace(
                        f"valuation.{valuation_observation.measure.value}",
                        valuation_observation,
                    )
                )
            except (NormalizationError, ValueError) as error:
                warnings.append(f"Skipped {valuation_observation.observation_id}: {error}")
        for financial_observation in batch.financials:
            try:
                metric, _ = normalizer.financial(financial_observation)
                financials.append(metric)
                traces.append(
                    _trace(
                        f"financial.{financial_observation.name.value}."
                        f"{metric.period.label}.{metric.basis.value}",
                        financial_observation,
                    )
                )
            except (NormalizationError, ValueError) as error:
                warnings.append(f"Skipped {financial_observation.observation_id}: {error}")
        for capital_observation in batch.capital_structure:
            try:
                capital.append(normalizer.capital(capital_observation))
                traces.append(
                    _trace(f"capital.{capital_observation.kind.value}", capital_observation)
                )
            except (NormalizationError, ValueError) as error:
                warnings.append(f"Skipped {capital_observation.observation_id}: {error}")

        derived_verification: FieldVerification | None = None
        if not any(
            item.measure is ValuationMeasure.TRANSACTION_ENTERPRISE_VALUE
            and item.amount is not None
            for item in valuations
        ):
            equity = next(
                (
                    item
                    for item in valuations
                    if item.measure is ValuationMeasure.EQUITY_PURCHASE_PRICE
                    and item.amount is not None
                ),
                None,
            )
            debt = next((item for item in capital if item.kind is CapitalComponentKind.DEBT), None)
            cash = next((item for item in capital if item.kind is CapitalComponentKind.CASH), None)
            if equity is not None and debt is not None and cash is not None:
                try:
                    derived, calculation = derive_enterprise_value(
                        equity=equity,
                        debt=debt,
                        cash=cash,
                        observation_id=f"valuation:derived-ev:{candidate.candidate_id}",
                    )
                    valuations.append(derived)
                    evidence_ids = tuple(item.evidence_id for item in derived.evidence)
                    traces.append(
                        ExtractionTrace(
                            "valuation.transaction_enterprise_value",
                            (equity.observation_id, debt.component_id, cash.component_id),
                            evidence_ids,
                            calculation,
                        )
                    )
                    derived_verification = FieldVerification(
                        "valuation.transaction_enterprise_value",
                        VerificationStatus.DERIVED,
                        derived.observation_id,
                        (equity.observation_id, debt.component_id, cash.component_id),
                        (),
                        evidence_ids,
                        calculation,
                    )
                except NormalizationError as error:
                    warnings.append(f"Enterprise value was not derived: {error}")

        snapshots: tuple[CapitalStructureSnapshot, ...] = ()
        if capital:
            snapshot_date = max(item.as_of for item in capital)
            snapshots = (
                CapitalStructureSnapshot(
                    f"capital-snapshot:{candidate.candidate_id}:{snapshot_date.isoformat()}",
                    snapshot_date,
                    tuple(capital),
                ),
            )
        record = TransactionRecord(
            TransactionIdentity(
                candidate.candidate_id,
                acquirer.party_id,
                target.party_id,
                transaction_type,
                lifecycle.announcement_date,
            ),
            acquirer,
            target,
            lifecycle,
            structure,
            tuple(valuations),
            tuple(consideration),
            tuple(ownership),
            tuple(financials),
            snapshots,
            evidence,
        )
        verifications = list(verified.fields)
        if derived_verification:
            verifications.append(derived_verification)
        expected = {
            "party.acquirer",
            "party.target",
            "date.announcement",
            "lifecycle.status",
            "valuation.headline_deal_value",
            "financial.ebitda",
        }
        existing = {item.field for item in verifications}
        if any(field.startswith("financial.ebitda.") for field in existing):
            existing.add("financial.ebitda")
        for field in sorted(expected - existing):
            verifications.append(verifier.missing(field))
        related = tuple(
            item for item in batch.parties if item.role in {PartyRole.SELLER, PartyRole.PARENT}
        )
        overall = FactStatus.CONFLICTING if verified.conflicts else FactStatus.DIRECTLY_DISCLOSED
        return VerifiedTransactionRecord(
            record,
            related,
            tuple(sorted(verifications, key=lambda item: item.field)),
            verified.conflicts,
            tuple(traces),
            tuple(dict.fromkeys(warnings)),
            overall,
        )

    def build_partial(
        self,
        candidate: CandidateTransaction,
        results: tuple[DealRetrievalResult, ...],
    ) -> ExtractionOutcome:
        try:
            return ExtractionOutcome(self.build(candidate, results))
        except ExtractionError as error:
            return ExtractionOutcome(None, str(error))


def _unique_evidence(results: tuple[DealRetrievalResult, ...]) -> tuple[EvidenceReference, ...]:
    return tuple({item.evidence.evidence_id: item.evidence for item in results}.values())


def _selected_party(
    selected: dict[str, str],
    observations: Mapping[str, ExtractedObservation],
    role: PartyRole,
) -> PartyObservation | None:
    return _selected(selected, observations, f"party.{role.value}", PartyObservation)


def _selected_date(
    selected: dict[str, str],
    observations: Mapping[str, ExtractedObservation],
    kind: DealDateKind,
) -> DateObservation | None:
    return _selected(selected, observations, f"date.{kind.value}", DateObservation)


def _selected(
    selected: dict[str, str],
    observations: Mapping[str, ExtractedObservation],
    field: str,
    expected: type[T],
) -> T | None:
    observation_id = selected.get(field)
    value = observations.get(observation_id) if observation_id else None
    return value if isinstance(value, expected) else None


def _control_type(batch: ExtractionBatch) -> ControlType:
    acquired = [item.acquired_percent for item in batch.ownership if item.acquired_percent]
    if not acquired:
        return ControlType.UNKNOWN
    try:
        maximum = max(float(item) for item in acquired)
    except ValueError:
        return ControlType.UNKNOWN
    return ControlType.CONTROL if maximum > 50 else ControlType.MINORITY


def _status_as_of(batch: ExtractionBatch, evidence: tuple[EvidenceReference, ...]) -> date:
    dates = [item.effective_date for item in batch.observations if item.effective_date]
    dates.extend(item.publication_date for item in evidence if item.publication_date)
    return max(dates, default=date.today())


def _trace(field: str, observation: ExtractedObservation) -> ExtractionTrace:
    return ExtractionTrace(
        field,
        (observation.observation_id,),
        observation.evidence_ids,
    )
