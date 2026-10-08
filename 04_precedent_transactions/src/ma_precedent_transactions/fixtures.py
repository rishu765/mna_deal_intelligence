"""Synthetic offline M0 fixtures. All companies and transactions are fictitious."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from ma_precedent_transactions.domain import (
    BuyerType,
    ConsiderationComponent,
    ConsiderationKind,
    ControlType,
    DealLifecycle,
    DealStatus,
    EvidenceReference,
    ExtractionMethod,
    FactStatus,
    FinancialUnit,
    MonetaryAmount,
    OwnershipObservation,
    PublicStatus,
    SourceReliability,
    TransactionIdentity,
    TransactionParty,
    TransactionRecord,
    TransactionStructure,
    TransactionType,
    ValuationBasis,
    ValuationMeasure,
    ValuationObservation,
)


def synthetic_transactions() -> tuple[TransactionRecord, ...]:
    """Return six cases that exercise M0 representation, without calculations."""

    return (
        _cash_acquisition(),
        _mixed_acquisition(),
        _partial_stake(),
        _withdrawn_deal(),
        _undisclosed_value(),
        _conflicting_values(),
    )


def _evidence(case: str, excerpt: str) -> EvidenceReference:
    return EvidenceReference(
        evidence_id=f"ev-{case}",
        source_type="acquisition_press_release",
        document_title=f"Synthetic {case} announcement",
        source_url=f"https://fixtures.invalid/{case}",
        publisher="Fictitious issuer",
        publication_date=date(2024, 2, 1),
        retrieved_at=datetime(2026, 10, 9, 9, 0, tzinfo=UTC),
        reliability=SourceReliability.PRIMARY_COMPANY,
        extraction_method=ExtractionMethod.MANUAL,
        document_id=f"doc-{case}",
        section="Transaction overview",
        excerpt_id=f"excerpt-{case}",
        excerpt=excerpt,
    )


def _parties(case: str, evidence: EvidenceReference) -> tuple[TransactionParty, TransactionParty]:
    return (
        TransactionParty(
            party_id=f"party-{case}-buyer",
            legal_name=f"{case.title()} Holdings Ltd.",
            public_status=PublicStatus.PUBLIC,
            country="US",
            evidence=(evidence,),
        ),
        TransactionParty(
            party_id=f"party-{case}-target",
            legal_name=f"{case.title()} Systems Ltd.",
            public_status=PublicStatus.PRIVATE,
            country="US",
            industry="Software",
            evidence=(evidence,),
        ),
    )


def _base(
    case: str,
    *,
    transaction_type: TransactionType,
    status: DealStatus,
    completion_date: date | None,
    valuations: tuple[ValuationObservation, ...],
    consideration: tuple[ConsiderationComponent, ...] = (),
    ownership: tuple[OwnershipObservation, ...] = (),
    control: ControlType = ControlType.CONTROL,
) -> TransactionRecord:
    evidence_by_id: dict[str, EvidenceReference] = {}
    for valuation_observation in valuations:
        evidence_by_id.update((item.evidence_id, item) for item in valuation_observation.evidence)
    for component in consideration:
        evidence_by_id.update((item.evidence_id, item) for item in component.evidence)
    for ownership_observation in ownership:
        evidence_by_id.update((item.evidence_id, item) for item in ownership_observation.evidence)
    all_evidence = tuple(evidence_by_id.values())
    if not all_evidence:
        all_evidence = (_evidence(case, "Synthetic source text for model demonstration only."),)
    acquirer, target = _parties(case, all_evidence[0])
    announced = date(2024, 2, 1)
    return TransactionRecord(
        identity=TransactionIdentity(
            transaction_id=f"txn-{case}",
            acquirer_party_id=acquirer.party_id,
            target_party_id=target.party_id,
            transaction_type=transaction_type,
            announcement_date=announced,
            identity_qualifier="Initial bid",
        ),
        acquirer=acquirer,
        target=target,
        lifecycle=DealLifecycle(
            status=status,
            announcement_date=announced,
            completion_date=completion_date,
            status_as_of=completion_date or date(2024, 8, 1),
            evidence=all_evidence,
        ),
        structure=TransactionStructure(
            transaction_type=transaction_type,
            buyer_type=BuyerType.STRATEGIC,
            control_type=control,
            jurisdiction="United States",
            evidence=all_evidence,
        ),
        valuations=valuations,
        consideration=consideration,
        ownership=ownership,
        evidence=all_evidence,
    )


def _amount(value: str, *, per_share: bool = False) -> MonetaryAmount:
    return MonetaryAmount(
        value=Decimal(value),
        currency="USD",
        unit=FinancialUnit.PER_SHARE if per_share else FinancialUnit.MILLION,
        measurement_date=date(2024, 2, 1),
    )


def _cash_acquisition() -> TransactionRecord:
    case = "cash"
    evidence = _evidence(case, "The buyer will acquire 100% for USD 420 million in cash.")
    return _base(
        case,
        transaction_type=TransactionType.STOCK_ACQUISITION,
        status=DealStatus.COMPLETED,
        completion_date=date(2024, 6, 3),
        valuations=(
            ValuationObservation(
                "val-cash-equity",
                ValuationMeasure.EQUITY_PURCHASE_PRICE,
                ValuationBasis.EXPLICITLY_DISCLOSED,
                FactStatus.DIRECTLY_DISCLOSED,
                (evidence,),
                _amount("420"),
            ),
        ),
        consideration=(
            ConsiderationComponent(
                "con-cash",
                ConsiderationKind.CASH,
                FactStatus.DIRECTLY_DISCLOSED,
                (evidence,),
                amount=_amount("420"),
            ),
        ),
        ownership=(
            OwnershipObservation(
                "own-cash",
                FactStatus.DIRECTLY_DISCLOSED,
                (evidence,),
                acquired_percent=Decimal("100"),
                post_deal_percent=Decimal("100"),
            ),
        ),
    )


def _mixed_acquisition() -> TransactionRecord:
    case = "mixed"
    evidence = _evidence(case, "Consideration comprises USD 150 million cash and buyer shares.")
    return _base(
        case,
        transaction_type=TransactionType.MERGER,
        status=DealStatus.COMPLETED,
        completion_date=date(2024, 7, 15),
        valuations=(
            ValuationObservation(
                "val-mixed-headline",
                ValuationMeasure.HEADLINE_DEAL_VALUE,
                ValuationBasis.EXPLICITLY_DISCLOSED,
                FactStatus.DIRECTLY_DISCLOSED,
                (evidence,),
                _amount("510"),
                notes="Headline basis was not described as equity value or enterprise value.",
            ),
        ),
        consideration=(
            ConsiderationComponent(
                "con-mixed-cash",
                ConsiderationKind.CASH,
                FactStatus.DIRECTLY_DISCLOSED,
                (evidence,),
                amount=_amount("150"),
            ),
            ConsiderationComponent(
                "con-mixed-stock",
                ConsiderationKind.SHARES,
                FactStatus.DIRECTLY_DISCLOSED,
                (evidence,),
                quantity=Decimal("12.5"),
                quantity_unit="million buyer shares",
            ),
        ),
    )


def _partial_stake() -> TransactionRecord:
    case = "partial"
    evidence = _evidence(case, "The buyer acquired an additional 20% stake for USD 75 million.")
    return _base(
        case,
        transaction_type=TransactionType.REMAINING_STAKE_ACQUISITION,
        status=DealStatus.COMPLETED,
        completion_date=date(2024, 5, 1),
        valuations=(
            ValuationObservation(
                "val-partial-price",
                ValuationMeasure.EQUITY_PURCHASE_PRICE,
                ValuationBasis.EXPLICITLY_DISCLOSED,
                FactStatus.DIRECTLY_DISCLOSED,
                (evidence,),
                _amount("75"),
                notes="Price paid for the incremental stake; no gross-up performed.",
            ),
        ),
        consideration=(
            ConsiderationComponent(
                "con-partial",
                ConsiderationKind.CASH,
                FactStatus.DIRECTLY_DISCLOSED,
                (evidence,),
                amount=_amount("75"),
            ),
        ),
        ownership=(
            OwnershipObservation(
                "own-partial",
                FactStatus.DIRECTLY_DISCLOSED,
                (evidence,),
                pre_deal_percent=Decimal("55"),
                acquired_percent=Decimal("20"),
                post_deal_percent=Decimal("75"),
            ),
        ),
    )


def _withdrawn_deal() -> TransactionRecord:
    case = "withdrawn"
    evidence = _evidence(case, "The announced offer was withdrawn before completion.")
    return _base(
        case,
        transaction_type=TransactionType.STOCK_ACQUISITION,
        status=DealStatus.WITHDRAWN,
        completion_date=None,
        valuations=(
            ValuationObservation(
                "val-withdrawn-headline",
                ValuationMeasure.HEADLINE_DEAL_VALUE,
                ValuationBasis.EXPLICITLY_DISCLOSED,
                FactStatus.DIRECTLY_DISCLOSED,
                (evidence,),
                _amount("300"),
            ),
        ),
    )


def _undisclosed_value() -> TransactionRecord:
    case = "undisclosed"
    evidence = _evidence(case, "Financial terms were not disclosed.")
    return _base(
        case,
        transaction_type=TransactionType.BUSINESS_UNIT_ACQUISITION,
        status=DealStatus.COMPLETED,
        completion_date=date(2024, 4, 30),
        valuations=(
            ValuationObservation(
                "val-undisclosed",
                ValuationMeasure.HEADLINE_DEAL_VALUE,
                ValuationBasis.UNAVAILABLE,
                FactStatus.UNKNOWN,
                (evidence,),
                amount=None,
                notes="The source explicitly says terms were undisclosed.",
            ),
        ),
    )


def _conflicting_values() -> TransactionRecord:
    case = "conflict"
    issuer = _evidence(case, "The issuer described the transaction as USD 600 million.")
    secondary = EvidenceReference(
        evidence_id="ev-conflict-secondary",
        source_type="financial_news",
        document_title="Synthetic report of transaction value",
        source_url="https://fixtures.invalid/conflict-secondary",
        publisher="Fictitious Financial News",
        publication_date=date(2024, 2, 2),
        retrieved_at=datetime(2026, 10, 9, 9, 5, tzinfo=UTC),
        reliability=SourceReliability.TRUSTED_SECONDARY,
        extraction_method=ExtractionMethod.MANUAL,
        excerpt_id="excerpt-conflict-secondary",
        excerpt="The report described a USD 640 million transaction.",
    )
    return _base(
        case,
        transaction_type=TransactionType.STOCK_ACQUISITION,
        status=DealStatus.PENDING,
        completion_date=None,
        valuations=(
            ValuationObservation(
                "val-conflict-issuer",
                ValuationMeasure.HEADLINE_DEAL_VALUE,
                ValuationBasis.AMBIGUOUS,
                FactStatus.CONFLICTING,
                (issuer,),
                _amount("600"),
            ),
            ValuationObservation(
                "val-conflict-secondary",
                ValuationMeasure.HEADLINE_DEAL_VALUE,
                ValuationBasis.AMBIGUOUS,
                FactStatus.CONFLICTING,
                (secondary,),
                _amount("640"),
            ),
        ),
    )
