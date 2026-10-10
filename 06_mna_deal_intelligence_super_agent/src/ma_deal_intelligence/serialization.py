"""Versioned, lossless serialization for the canonical deal state."""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from importlib import import_module
from typing import Any, cast

from ma_deal_intelligence.state import DEAL_STATE_SCHEMA_VERSION, DealState

SERIALIZATION_VERSION = 1
_MODEL_MODULES = (
    "ma_deal_intelligence.evidence",
    "ma_deal_intelligence.identity",
    "ma_deal_intelligence.finance",
    "ma_deal_intelligence.workflow",
    "ma_deal_intelligence.outputs",
    "ma_deal_intelligence.contracts",
    "ma_deal_intelligence.requests",
    "ma_deal_intelligence.state",
)


class SerializationError(ValueError):
    """Raised when a state payload is unsupported or malformed."""


def _registry() -> dict[str, type[Any]]:
    registered: dict[str, type[Any]] = {}
    for module_name in _MODEL_MODULES:
        module = import_module(module_name)
        for name, value in vars(module).items():
            if isinstance(value, type) and (is_dataclass(value) or issubclass(value, Enum)):
                existing = registered.get(name)
                if existing is not None and existing is not value:
                    raise SerializationError(f"duplicate model name: {name}")
                registered[name] = value
    return registered


def state_to_dict(state: DealState) -> dict[str, object]:
    return {
        "serialization_version": SERIALIZATION_VERSION,
        "schema_version": state.schema_version,
        "state": _encode(state),
    }


def state_from_dict(data: dict[str, object]) -> DealState:
    if data.get("serialization_version") != SERIALIZATION_VERSION:
        raise SerializationError("unsupported serialization_version")
    if data.get("schema_version") != DEAL_STATE_SCHEMA_VERSION:
        raise SerializationError("unsupported schema_version")
    try:
        decoded = _decode(data["state"])
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, SerializationError):
            raise
        raise SerializationError(f"invalid deal state: {error}") from error
    if not isinstance(decoded, DealState):
        raise SerializationError("state payload did not decode to DealState")
    return decoded


def state_to_json(state: DealState, *, indent: int | None = 2) -> str:
    return json.dumps(state_to_dict(state), indent=indent, ensure_ascii=False)


def state_from_json(payload: str) -> DealState:
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as error:
        raise SerializationError(f"invalid JSON: {error.msg}") from error
    if not isinstance(decoded, dict):
        raise SerializationError("deal state JSON root must be an object")
    return state_from_dict(cast(dict[str, object], decoded))


def _encode(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "__type__": type(value).__name__,
            **{field.name: _encode(getattr(value, field.name)) for field in fields(value)},
        }
    if isinstance(value, Enum):
        return {"__enum__": type(value).__name__, "value": value.value}
    if isinstance(value, Decimal):
        return {"__decimal__": str(value)}
    if isinstance(value, datetime):
        return {"__datetime__": value.isoformat()}
    if isinstance(value, date):
        return {"__date__": value.isoformat()}
    if isinstance(value, tuple):
        return {"__tuple__": [_encode(item) for item in value]}
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise SerializationError(f"unsupported value type: {type(value).__name__}")


def _decode(value: object) -> object:
    if not isinstance(value, dict):
        return value
    mapping = cast(dict[str, object], value)
    if "__decimal__" in mapping:
        return Decimal(_string(mapping["__decimal__"], "decimal"))
    if "__datetime__" in mapping:
        return datetime.fromisoformat(_string(mapping["__datetime__"], "datetime"))
    if "__date__" in mapping:
        return date.fromisoformat(_string(mapping["__date__"], "date"))
    if "__tuple__" in mapping:
        items = mapping["__tuple__"]
        if not isinstance(items, list):
            raise SerializationError("tuple payload must be a list")
        return tuple(_decode(item) for item in items)
    registry = _registry()
    if "__enum__" in mapping:
        name = _string(mapping["__enum__"], "enum name")
        enum_type = registry.get(name)
        if enum_type is None or not issubclass(enum_type, Enum):
            raise SerializationError(f"unknown enum type: {name}")
        return enum_type(_string(mapping.get("value"), "enum value"))
    if "__type__" in mapping:
        name = _string(mapping["__type__"], "model name")
        model_type = registry.get(name)
        if model_type is None or not is_dataclass(model_type):
            raise SerializationError(f"unknown model type: {name}")
        kwargs = {key: _decode(item) for key, item in mapping.items() if key != "__type__"}
        return model_type(**kwargs)
    return {key: _decode(item) for key, item in mapping.items()}


def _string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise SerializationError(f"{name} must be a string")
    return value
