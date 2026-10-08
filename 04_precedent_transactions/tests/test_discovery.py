from datetime import UTC, date, datetime

from conftest import FIXTURE_ROOT
from ma_precedent_transactions.discovery import (
    AcquisitionContext,
    CandidateTransaction,
    DealDiscoveryService,
    DiscoverySourceReference,
    FixtureDealDiscoveryProvider,
    ResolutionDisposition,
    TransactionIdentityResolver,
)
from ma_precedent_transactions.discovery.models import ProviderDiscoveryResult
from ma_precedent_transactions.domain import BuyerType, DealStatus, TransactionType


def test_fixture_provider_discovers_structurally_relevant_deals() -> None:
    provider = FixtureDealDiscoveryProvider(FIXTURE_ROOT / "discovered_deals.json")
    result = provider.discover(
        AcquisitionContext(
            "ctx-1",
            target_industry="fintech infrastructure",
            geographies=("United States",),
            announced_from=date(2024, 1, 1),
        )
    )

    assert result.provider_name == "fixture_deal_dataset"
    assert {item.candidate_id for item in result.candidates} == {
        "cash-official",
        "cash-secondary-duplicate",
        "conflict-official",
    }


def test_discovery_service_deduplicates_same_deal_across_sources() -> None:
    service = DealDiscoveryService(
        (FixtureDealDiscoveryProvider(FIXTURE_ROOT / "discovered_deals.json"),)
    )
    result = service.discover(
        AcquisitionContext("ctx-2", target_industry="B2B fintech infrastructure")
    )

    assert result.raw_candidate_count == 8
    assert len(result.transactions) == 7
    cash = next(item for item in result.transactions if item.candidate_id == "txn-cash")
    assert len(cash.discovery_sources) == 2
    decision = next(
        item for item in result.resolution_decisions if item.output_transaction_ids == ("txn-cash",)
    )
    assert decision.disposition is ResolutionDisposition.MERGED


def test_identity_resolution_preserves_competing_bid_ambiguity() -> None:
    source = DiscoverySourceReference(
        "ref-1",
        "fixture",
        "fixture source",
        "official",
        datetime(2026, 10, 9, tzinfo=UTC),
    )
    first = CandidateTransaction(
        "bid-a",
        "Alpha Buyer",
        "Shared Target",
        date(2024, 1, 1),
        DealStatus.ANNOUNCED,
        TransactionType.STOCK_ACQUISITION,
        BuyerType.STRATEGIC,
        "Potential strategic acquisition.",
        (source,),
    )
    second = CandidateTransaction(
        "bid-b",
        "Beta Buyer",
        "Shared Target Ltd.",
        date(2024, 1, 8),
        DealStatus.ANNOUNCED,
        TransactionType.STOCK_ACQUISITION,
        BuyerType.STRATEGIC,
        "Competing bid.",
        (source,),
    )

    result = TransactionIdentityResolver().resolve((first, second))

    assert len(result.transactions) == 2
    assert any(item.disposition is ResolutionDisposition.AMBIGUOUS for item in result.decisions)
    assert result.warnings


def test_fixture_provider_returns_explicit_no_result_warning() -> None:
    provider = FixtureDealDiscoveryProvider(FIXTURE_ROOT / "discovered_deals.json")
    result = provider.discover(
        AcquisitionContext("ctx-none", target_industry="Martian mineral logistics")
    )

    assert result.candidates == ()
    assert "no candidate" in result.warnings[0]


def test_discovery_preserves_fixture_results_when_another_provider_fails() -> None:
    class FailingProvider:
        provider_name = "failing_provider"

        def discover(self, context: AcquisitionContext) -> ProviderDiscoveryResult:
            del context
            raise ValueError("synthetic provider failure")

    service = DealDiscoveryService(
        (
            FailingProvider(),
            FixtureDealDiscoveryProvider(FIXTURE_ROOT / "discovered_deals.json"),
        )
    )

    result = service.discover(
        AcquisitionContext("ctx-partial", target_industry="fintech infrastructure")
    )

    assert result.transactions
    assert "Discovery provider failed: failing_provider" in result.warnings
