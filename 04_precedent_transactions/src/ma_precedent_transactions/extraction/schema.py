"""Strict conversion from model/fixture JSON into application-owned extraction contracts."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any, TypedDict

from ma_precedent_transactions.domain import (
    BuyerType,
    CapitalComponentKind,
    ConsiderationKind,
    DealStatus,
    FinancialMetricName,
    MetricBasis,
    TransactionType,
    ValuationMeasure,
)
from ma_precedent_transactions.errors import ExtractionValidationError
from ma_precedent_transactions.extraction.models import (
    CapitalFactObservation,
    ConsiderationObservation,
    DateObservation,
    DealDateKind,
    ExtractionBatch,
    FinancialFactObservation,
    OwnershipFactObservation,
    PartyObservation,
    PartyRole,
    RawMoney,
    RevisionKind,
    StatusObservation,
    StructureObservation,
    ValuationFactObservation,
)

EXTRACTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["transaction_id"],
    "properties": {
        "transaction_id": {"type": "string"},
        "parties": {"type": "array", "items": {"type": "object"}},
        "dates": {"type": "array", "items": {"type": "object"}},
        "statuses": {"type": "array", "items": {"type": "object"}},
        "structures": {"type": "array", "items": {"type": "object"}},
        "consideration": {"type": "array", "items": {"type": "object"}},
        "ownership": {"type": "array", "items": {"type": "object"}},
        "valuations": {"type": "array", "items": {"type": "object"}},
        "financials": {"type": "array", "items": {"type": "object"}},
        "capital_structure": {"type": "array", "items": {"type": "object"}},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
}


def load_extraction_fixture(path: Path) -> dict[str, ExtractionBatch]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ExtractionValidationError(f"unable to load extraction fixture: {path}") from error
    if not isinstance(payload, list):
        raise ExtractionValidationError("extraction fixture must be a JSON list")
    batches = tuple(parse_extraction_payload(_mapping(item, "fixture item")) for item in payload)
    if len({item.transaction_id for item in batches}) != len(batches):
        raise ExtractionValidationError("fixture transaction IDs must be unique")
    return {item.transaction_id: item for item in batches}


def parse_extraction_payload(payload: Mapping[str, object]) -> ExtractionBatch:
    try:
        return ExtractionBatch(
            transaction_id=_string(payload, "transaction_id"),
            parties=tuple(_party(item) for item in _items(payload, "parties")),
            dates=tuple(_date_observation(item) for item in _items(payload, "dates")),
            statuses=tuple(_status(item) for item in _items(payload, "statuses")),
            structures=tuple(_structure(item) for item in _items(payload, "structures")),
            consideration=tuple(_consideration(item) for item in _items(payload, "consideration")),
            ownership=tuple(_ownership(item) for item in _items(payload, "ownership")),
            valuations=tuple(_valuation(item) for item in _items(payload, "valuations")),
            financials=tuple(_financial(item) for item in _items(payload, "financials")),
            capital_structure=tuple(
                _capital(item) for item in _items(payload, "capital_structure")
            ),
            warnings=tuple(
                _string_value(item, "warning")
                for item in _sequence(payload, "warnings", required=False)
            ),
        )
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, ExtractionValidationError):
            raise
        raise ExtractionValidationError(f"invalid extraction payload: {error}") from error


class _BaseKwargs(TypedDict):
    observation_id: str
    evidence_ids: tuple[str, ...]
    source_wording: str
    effective_date: date | None
    revision: RevisionKind
    notes: str | None


def _base(data: Mapping[str, object]) -> _BaseKwargs:
    return {
        "observation_id": _string(data, "observation_id"),
        "evidence_ids": tuple(
            _string_value(item, "evidence_id") for item in _sequence(data, "evidence_ids")
        ),
        "source_wording": _string(data, "source_wording"),
        "effective_date": _optional_date(data.get("effective_date")),
        "revision": RevisionKind(str(data.get("revision", "unspecified"))),
        "notes": _optional_string(data.get("notes")),
    }


def _party(data: Mapping[str, object]) -> PartyObservation:
    return PartyObservation(
        **_base(data),
        role=PartyRole(_string(data, "role")),
        legal_name=_string(data, "legal_name"),
        aliases=tuple(
            _string_value(item, "alias") for item in _sequence(data, "aliases", required=False)
        ),
        relationship=_optional_string(data.get("relationship")),
    )


def _date_observation(data: Mapping[str, object]) -> DateObservation:
    return DateObservation(
        **_base(data), kind=DealDateKind(_string(data, "kind")), value=_date(data, "value")
    )


def _status(data: Mapping[str, object]) -> StatusObservation:
    return StatusObservation(**_base(data), status=DealStatus(_string(data, "status")))


def _structure(data: Mapping[str, object]) -> StructureObservation:
    return StructureObservation(
        **_base(data),
        transaction_type=TransactionType(_string(data, "transaction_type")),
        buyer_type=BuyerType(str(data.get("buyer_type", "unknown"))),
        jurisdiction=_optional_string(data.get("jurisdiction")),
    )


def _money(value: object) -> RawMoney | None:
    if value is None:
        return None
    data = _mapping(value, "money")
    return RawMoney(
        value=_string(data, "value"),
        currency=_string(data, "currency"),
        unit=_string(data, "unit"),
        measurement_date=_optional_date(data.get("measurement_date")),
    )


def _consideration(data: Mapping[str, object]) -> ConsiderationObservation:
    return ConsiderationObservation(
        **_base(data),
        kind=ConsiderationKind(_string(data, "kind")),
        amount=_money(data.get("amount")),
        quantity=_optional_string(data.get("quantity")),
        quantity_unit=_optional_string(data.get("quantity_unit")),
        per_share=bool(data.get("per_share", False)),
    )


def _ownership(data: Mapping[str, object]) -> OwnershipFactObservation:
    return OwnershipFactObservation(
        **_base(data),
        pre_deal_percent=_optional_string(data.get("pre_deal_percent")),
        acquired_percent=_optional_string(data.get("acquired_percent")),
        post_deal_percent=_optional_string(data.get("post_deal_percent")),
    )


def _valuation(data: Mapping[str, object]) -> ValuationFactObservation:
    return ValuationFactObservation(
        **_base(data),
        measure=ValuationMeasure(_string(data, "measure")),
        amount=_money(data.get("amount")),
        disclosed=bool(data.get("disclosed", True)),
        ambiguous_basis=bool(data.get("ambiguous_basis", False)),
    )


def _financial(data: Mapping[str, object]) -> FinancialFactObservation:
    return FinancialFactObservation(
        **_base(data),
        name=FinancialMetricName(_string(data, "name")),
        value=_string(data, "value"),
        currency=_string(data, "currency"),
        unit=_string(data, "unit"),
        period=_string(data, "period"),
        basis=MetricBasis(str(data.get("basis", "reported"))),
        adjustment_label=_optional_string(data.get("adjustment_label")),
        measurement_date=_optional_date(data.get("measurement_date")),
    )


def _capital(data: Mapping[str, object]) -> CapitalFactObservation:
    return CapitalFactObservation(
        **_base(data),
        kind=CapitalComponentKind(_string(data, "kind")),
        amount=_money(data.get("amount")),
        as_of=_date(data, "as_of"),
    )


def _items(payload: Mapping[str, object], key: str) -> tuple[Mapping[str, object], ...]:
    return tuple(_mapping(item, key) for item in _sequence(payload, key, required=False))


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ExtractionValidationError(f"{name} must be an object")
    return value


def _sequence(
    payload: Mapping[str, object], key: str, *, required: bool = True
) -> Sequence[object]:
    value = payload.get(key, [] if not required else None)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ExtractionValidationError(f"{key} must be an array")
    return value


def _string(payload: Mapping[str, object], key: str) -> str:
    return _string_value(payload[key], key)


def _string_value(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExtractionValidationError(f"{name} must be a non-empty string")
    return value.strip()


def _optional_string(value: object) -> str | None:
    return None if value is None else _string_value(value, "optional string")


def _date(payload: Mapping[str, object], key: str) -> date:
    value = _optional_date(payload[key])
    if value is None:
        raise ExtractionValidationError(f"{key} must be a date")
    return value


def _optional_date(value: object) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(_string_value(value, "date"))
    except ValueError as error:
        raise ExtractionValidationError(f"invalid ISO date: {value}") from error
