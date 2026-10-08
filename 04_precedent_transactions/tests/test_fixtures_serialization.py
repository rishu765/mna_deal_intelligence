from decimal import Decimal

import pytest

from ma_precedent_transactions import (
    DealStatus,
    FactStatus,
    SerializationError,
    UnsupportedSchemaVersionError,
    ValuationBasis,
    transaction_from_dict,
    transaction_from_json,
    transaction_to_dict,
    transaction_to_json,
)
from ma_precedent_transactions.fixtures import synthetic_transactions


def test_six_synthetic_fixture_scenarios_are_present() -> None:
    transactions = synthetic_transactions()

    assert len(transactions) == 6
    assert transactions[0].ownership[0].acquired_percent == Decimal("100")
    assert len(transactions[1].consideration) == 2
    assert transactions[2].ownership[0].acquired_percent == Decimal("20")
    assert transactions[3].lifecycle.status is DealStatus.WITHDRAWN
    assert transactions[4].valuations[0].basis is ValuationBasis.UNAVAILABLE
    assert all(item.fact_status is FactStatus.CONFLICTING for item in transactions[5].valuations)


def test_conflicting_values_remain_multiple_observations() -> None:
    conflict = synthetic_transactions()[-1]

    assert len(conflict.valuations) == 2
    assert {item.amount.value for item in conflict.valuations if item.amount} == {
        Decimal("600"),
        Decimal("640"),
    }
    assert len({item.evidence[0].evidence_id for item in conflict.valuations}) == 2
    assert {item.evidence_id for item in conflict.evidence} == {
        "ev-conflict",
        "ev-conflict-secondary",
    }


@pytest.mark.parametrize("transaction", synthetic_transactions())
def test_serialization_round_trip_preserves_each_fixture(transaction: object) -> None:
    payload = transaction_to_json(transaction)  # type: ignore[arg-type]
    restored = transaction_from_json(payload)

    assert restored == transaction


def test_dict_serialization_is_schema_versioned() -> None:
    transaction = synthetic_transactions()[0]
    payload = transaction_to_dict(transaction)

    assert payload["schema_version"] == 1
    assert transaction_from_dict(payload) == transaction


def test_unsupported_schema_and_invalid_json_raise_clear_errors() -> None:
    with pytest.raises(UnsupportedSchemaVersionError):
        transaction_from_dict({"schema_version": 999, "transaction": {}})

    with pytest.raises(SerializationError, match="invalid JSON"):
        transaction_from_json("{")


def test_evidence_detail_survives_round_trip() -> None:
    restored = transaction_from_json(transaction_to_json(synthetic_transactions()[0]))
    evidence = restored.valuations[0].evidence[0]

    assert evidence.document_id == "doc-cash"
    assert evidence.excerpt_id == "excerpt-cash"
    assert evidence.source_url == "https://fixtures.invalid/cash"
