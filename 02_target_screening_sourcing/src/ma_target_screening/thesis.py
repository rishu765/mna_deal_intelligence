"""Typed, serializable acquisition-thesis and screening-criterion models."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Self


class CriterionRequirement(StrEnum):
    """Consequence of satisfying or failing a criterion."""

    HARD = "hard"
    SOFT = "soft"
    EXCLUSION = "exclusion"


class CriterionValueType(StrEnum):
    """Shape and business meaning of a criterion value."""

    NUMERIC = "numeric"
    FINANCIAL = "financial"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"
    GEOGRAPHIC = "geographic"
    SEMANTIC = "semantic"
    DERIVED = "derived"


class EvaluationMethod(StrEnum):
    """Planned evaluation boundary; no evaluation occurs in M1."""

    DETERMINISTIC = "deterministic"
    SEMANTIC = "semantic"


class CriterionOperator(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    BETWEEN = "between"
    IN = "in"
    CONTAINS = "contains"
    IS_TRUE = "is_true"
    IS_FALSE = "is_false"
    SEMANTIC_MATCH = "semantic_match"


class CriterionCategory(StrEnum):
    INDUSTRY = "industry"
    SUB_INDUSTRY = "sub_industry"
    PRODUCT_CAPABILITY = "product_capability"
    GEOGRAPHY = "geography"
    REVENUE = "revenue"
    PROFITABILITY = "profitability"
    COMPANY_SIZE = "company_size"
    EMPLOYEE_COUNT = "employee_count"
    FOUNDED_YEAR = "founded_year"
    GROWTH = "growth"
    OWNERSHIP = "ownership"
    CUSTOMER_TYPE = "customer_type"
    TECHNOLOGY = "technology"
    STRATEGIC_FIT = "strategic_fit"
    OTHER = "other"


class CriterionPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FinancialUnit(StrEnum):
    UNIT = "unit"
    THOUSAND = "thousand"
    MILLION = "million"
    BILLION = "billion"
    LAKH = "lakh"
    CRORE = "crore"


_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
_PERIOD_PATTERN = re.compile(r"^(?:(?:FY|CY)\d{4}|LTM|NTM)$")


def _clean_text(value: str, field_name: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    return normalized


def _optional_text(value: str | None, field_name: str) -> str | None:
    return None if value is None else _clean_text(value, field_name)


def _decimal(value: Decimal | int | str, field_name: str) -> Decimal:
    try:
        normalized = Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{field_name} must be a valid decimal") from error
    if not normalized.is_finite():
        raise ValueError(f"{field_name} must be finite")
    return normalized


@dataclass(frozen=True, slots=True)
class AcquirerIdentity:
    name: str
    country: str | None = None
    industry: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _clean_text(self.name, "acquirer name"))
        object.__setattr__(self, "country", _optional_text(self.country, "acquirer country"))
        object.__setattr__(self, "industry", _optional_text(self.industry, "acquirer industry"))


@dataclass(frozen=True, slots=True)
class NumericRange:
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    unit: str | None = None
    period: str | None = None

    def __post_init__(self) -> None:
        if self.minimum is None and self.maximum is None:
            raise ValueError("numeric range requires a minimum or maximum")
        minimum = None if self.minimum is None else _decimal(self.minimum, "minimum")
        maximum = None if self.maximum is None else _decimal(self.maximum, "maximum")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError("numeric range minimum must not exceed maximum")
        object.__setattr__(self, "minimum", minimum)
        object.__setattr__(self, "maximum", maximum)
        object.__setattr__(self, "unit", _optional_text(self.unit, "numeric range unit"))
        object.__setattr__(self, "period", _optional_text(self.period, "numeric range period"))


@dataclass(frozen=True, slots=True)
class MoneyAmount:
    amount: Decimal
    currency: str
    unit: FinancialUnit = FinancialUnit.UNIT
    fiscal_period: str | None = None

    def __post_init__(self) -> None:
        amount = _decimal(self.amount, "money amount")
        if amount < 0:
            raise ValueError("money amount must not be negative")
        currency = self.currency.strip().upper()
        if not _CURRENCY_PATTERN.fullmatch(currency):
            raise ValueError("currency must be a three-letter ISO-style code")
        period = None
        if self.fiscal_period is not None:
            period = self.fiscal_period.strip().upper().replace(" ", "")
            if not _PERIOD_PATTERN.fullmatch(period):
                raise ValueError("fiscal_period must be FY####, CY####, LTM, or NTM")
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "fiscal_period", period)

    @property
    def comparison_basis(self) -> tuple[str, FinancialUnit, str | None]:
        return (self.currency, self.unit, self.fiscal_period)


@dataclass(frozen=True, slots=True)
class MoneyRange:
    minimum: MoneyAmount | None = None
    maximum: MoneyAmount | None = None

    def __post_init__(self) -> None:
        if self.minimum is None and self.maximum is None:
            raise ValueError("money range requires a minimum or maximum")
        if self.minimum is not None and self.maximum is not None:
            if self.minimum.comparison_basis != self.maximum.comparison_basis:
                raise ValueError("money range bounds must use the same currency, unit, and period")
            if self.minimum.amount > self.maximum.amount:
                raise ValueError("money range minimum must not exceed maximum")


CriterionPayload = str | tuple[str, ...] | bool | Decimal | NumericRange | MoneyRange


@dataclass(frozen=True, slots=True)
class ScreeningCriterion:
    """One typed target requirement, preference, or exclusion."""

    criterion_id: str
    category: CriterionCategory
    requirement: CriterionRequirement
    value_type: CriterionValueType
    operator: CriterionOperator
    value: CriterionPayload
    evaluation_method: EvaluationMethod
    description: str | None = None
    priority: CriterionPriority | None = None
    weight: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "criterion_id", _clean_text(self.criterion_id, "criterion_id"))
        object.__setattr__(
            self, "description", _optional_text(self.description, "criterion description")
        )
        if self.weight is not None:
            weight = _decimal(self.weight, "criterion weight")
            if weight <= 0 or weight > 1:
                raise ValueError("criterion weight must be greater than 0 and at most 1")
            object.__setattr__(self, "weight", weight)
        self._validate_payload()
        self._validate_operator()
        if self.value_type is CriterionValueType.SEMANTIC:
            if self.evaluation_method is not EvaluationMethod.SEMANTIC:
                raise ValueError("semantic criteria require semantic evaluation")
        elif self.evaluation_method is EvaluationMethod.SEMANTIC:
            raise ValueError("semantic evaluation requires semantic value_type")

    def _validate_payload(self) -> None:
        value = self.value
        valid = {
            CriterionValueType.NUMERIC: isinstance(value, (Decimal, NumericRange))
            and not isinstance(value, bool),
            CriterionValueType.FINANCIAL: isinstance(value, MoneyRange),
            CriterionValueType.CATEGORICAL: isinstance(value, (str, tuple)),
            CriterionValueType.BOOLEAN: isinstance(value, bool),
            CriterionValueType.GEOGRAPHIC: isinstance(value, (str, tuple)),
            CriterionValueType.SEMANTIC: isinstance(value, str),
            CriterionValueType.DERIVED: isinstance(value, (str, Decimal, NumericRange))
            and not isinstance(value, bool),
        }[self.value_type]
        if not valid:
            raise ValueError(f"value is incompatible with value_type {self.value_type.value}")
        if isinstance(value, str):
            object.__setattr__(self, "value", _clean_text(value, "criterion value"))
        elif isinstance(value, tuple):
            normalized = tuple(_clean_text(item, "criterion value item") for item in value)
            if not normalized:
                raise ValueError("criterion value list must not be empty")
            if len({item.casefold() for item in normalized}) != len(normalized):
                raise ValueError("criterion value list must not contain duplicates")
            object.__setattr__(self, "value", normalized)
        elif isinstance(value, Decimal):
            object.__setattr__(self, "value", _decimal(value, "criterion value"))

    def _validate_operator(self) -> None:
        allowed = {
            CriterionValueType.NUMERIC: {
                CriterionOperator.EQUALS,
                CriterionOperator.NOT_EQUALS,
                CriterionOperator.GREATER_THAN,
                CriterionOperator.GREATER_THAN_OR_EQUAL,
                CriterionOperator.LESS_THAN,
                CriterionOperator.LESS_THAN_OR_EQUAL,
                CriterionOperator.BETWEEN,
            },
            CriterionValueType.FINANCIAL: {
                CriterionOperator.GREATER_THAN_OR_EQUAL,
                CriterionOperator.LESS_THAN_OR_EQUAL,
                CriterionOperator.BETWEEN,
            },
            CriterionValueType.CATEGORICAL: {
                CriterionOperator.EQUALS,
                CriterionOperator.NOT_EQUALS,
                CriterionOperator.IN,
                CriterionOperator.CONTAINS,
            },
            CriterionValueType.BOOLEAN: {
                CriterionOperator.IS_TRUE,
                CriterionOperator.IS_FALSE,
            },
            CriterionValueType.GEOGRAPHIC: {
                CriterionOperator.EQUALS,
                CriterionOperator.NOT_EQUALS,
                CriterionOperator.IN,
            },
            CriterionValueType.SEMANTIC: {CriterionOperator.SEMANTIC_MATCH},
            CriterionValueType.DERIVED: set(CriterionOperator),
        }[self.value_type]
        if self.operator not in allowed:
            raise ValueError(
                f"operator {self.operator.value} is invalid for {self.value_type.value} criteria"
            )
        if isinstance(self.value, (NumericRange, MoneyRange)):
            minimum = self.value.minimum
            maximum = self.value.maximum
            if minimum is not None and maximum is not None:
                expected = CriterionOperator.BETWEEN
            elif minimum is not None:
                expected = CriterionOperator.GREATER_THAN_OR_EQUAL
            else:
                expected = CriterionOperator.LESS_THAN_OR_EQUAL
            if self.operator is not expected:
                raise ValueError(
                    f"range shape requires operator {expected.value}, not {self.operator.value}"
                )
        if self.value_type is CriterionValueType.BOOLEAN:
            expected_value = self.operator is CriterionOperator.IS_TRUE
            if self.value is not expected_value:
                raise ValueError("boolean value must agree with is_true/is_false operator")


@dataclass(frozen=True, slots=True)
class AcquisitionThesis:
    """Validated source of truth for target requirements before discovery."""

    thesis_id: str
    acquirer: AcquirerIdentity
    objective: str | None = None
    strategic_rationale: str | None = None
    criteria: tuple[ScreeningCriterion, ...] = ()
    source_text: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "thesis_id", _clean_text(self.thesis_id, "thesis_id"))
        for field_name in ("objective", "strategic_rationale", "source_text", "notes"):
            object.__setattr__(
                self, field_name, _optional_text(getattr(self, field_name), field_name)
            )
        criterion_ids = [criterion.criterion_id.casefold() for criterion in self.criteria]
        if len(set(criterion_ids)) != len(criterion_ids):
            raise ValueError("criterion IDs must be unique within a thesis")
        self._validate_geographies()

    def _validate_geographies(self) -> None:
        hard: set[str] = set()
        excluded: set[str] = set()
        for criterion in self.criteria:
            if criterion.value_type is not CriterionValueType.GEOGRAPHIC:
                continue
            values: tuple[str, ...]
            if isinstance(criterion.value, str):
                values = (criterion.value,)
            elif isinstance(criterion.value, tuple):
                values = criterion.value
            else:
                raise ValueError("geographic criteria require text or list values")
            normalized = {value.casefold() for value in values}
            if criterion.requirement is CriterionRequirement.HARD:
                hard.update(normalized)
            elif criterion.requirement is CriterionRequirement.EXCLUSION:
                excluded.update(normalized)
        conflict = sorted(hard & excluded)
        if conflict:
            raise ValueError(
                "geographies cannot be both hard requirements and exclusions: "
                + ", ".join(conflict)
            )

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-compatible representation."""

        return {
            "schema_version": 1,
            "thesis_id": self.thesis_id,
            "acquirer": {
                "name": self.acquirer.name,
                "country": self.acquirer.country,
                "industry": self.acquirer.industry,
            },
            "objective": self.objective,
            "strategic_rationale": self.strategic_rationale,
            "criteria": [_criterion_to_dict(item) for item in self.criteria],
            "source_text": self.source_text,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Validate and construct a thesis from its JSON-compatible representation."""

        if data.get("schema_version") != 1:
            raise ValueError("schema_version must be 1")
        try:
            acquirer_data = data["acquirer"]
            return cls(
                thesis_id=data["thesis_id"],
                acquirer=AcquirerIdentity(
                    name=acquirer_data["name"],
                    country=acquirer_data.get("country"),
                    industry=acquirer_data.get("industry"),
                ),
                objective=data.get("objective"),
                strategic_rationale=data.get("strategic_rationale"),
                criteria=tuple(_criterion_from_dict(item) for item in data.get("criteria", [])),
                source_text=data.get("source_text"),
                notes=data.get("notes"),
            )
        except (KeyError, TypeError) as error:
            raise ValueError(f"invalid acquisition thesis structure: {error}") from error

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, value: str) -> Self:
        try:
            data = json.loads(value)
        except json.JSONDecodeError as error:
            raise ValueError("invalid acquisition thesis JSON") from error
        if not isinstance(data, dict):
            raise ValueError("acquisition thesis JSON must contain an object")
        return cls.from_dict(data)


def _criterion_to_dict(criterion: ScreeningCriterion) -> dict[str, Any]:
    return {
        "criterion_id": criterion.criterion_id,
        "category": criterion.category.value,
        "requirement": criterion.requirement.value,
        "value_type": criterion.value_type.value,
        "operator": criterion.operator.value,
        "value": _payload_to_dict(criterion.value),
        "evaluation_method": criterion.evaluation_method.value,
        "description": criterion.description,
        "priority": None if criterion.priority is None else criterion.priority.value,
        "weight": None if criterion.weight is None else str(criterion.weight),
    }


def _payload_to_dict(value: CriterionPayload) -> Any:
    if isinstance(value, Decimal):
        return {"number": str(value)}
    if isinstance(value, NumericRange):
        return {
            "numeric_range": {
                "minimum": None if value.minimum is None else str(value.minimum),
                "maximum": None if value.maximum is None else str(value.maximum),
                "unit": value.unit,
                "period": value.period,
            }
        }
    if isinstance(value, MoneyRange):
        return {
            "money_range": {
                "minimum": _money_to_dict(value.minimum),
                "maximum": _money_to_dict(value.maximum),
            }
        }
    if isinstance(value, tuple):
        return {"items": list(value)}
    if isinstance(value, bool):
        return {"boolean": value}
    return {"text": value}


def _money_to_dict(value: MoneyAmount | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "amount": str(value.amount),
        "currency": value.currency,
        "unit": value.unit.value,
        "fiscal_period": value.fiscal_period,
    }


def _criterion_from_dict(data: dict[str, Any]) -> ScreeningCriterion:
    try:
        return ScreeningCriterion(
            criterion_id=data["criterion_id"],
            category=CriterionCategory(data["category"]),
            requirement=CriterionRequirement(data["requirement"]),
            value_type=CriterionValueType(data["value_type"]),
            operator=CriterionOperator(data["operator"]),
            value=_payload_from_dict(data["value"]),
            evaluation_method=EvaluationMethod(data["evaluation_method"]),
            description=data.get("description"),
            priority=(
                None if data.get("priority") is None else CriterionPriority(data["priority"])
            ),
            weight=None if data.get("weight") is None else _decimal(data["weight"], "weight"),
        )
    except (KeyError, TypeError, ValueError) as error:
        criterion_id = (
            data.get("criterion_id", "<unknown>") if isinstance(data, dict) else "<unknown>"
        )
        raise ValueError(f"invalid criterion {criterion_id}: {error}") from error


def _payload_from_dict(data: dict[str, Any]) -> CriterionPayload:
    if not isinstance(data, dict) or len(data) != 1:
        raise ValueError("criterion value must contain exactly one typed payload")
    key, value = next(iter(data.items()))
    if key == "text":
        return str(value)
    if key == "items":
        if not isinstance(value, list):
            raise ValueError("items payload must be a list")
        return tuple(str(item) for item in value)
    if key == "boolean":
        if not isinstance(value, bool):
            raise ValueError("boolean payload must be true or false")
        return value
    if key == "number":
        return _decimal(value, "number")
    if key == "numeric_range":
        return NumericRange(
            minimum=value.get("minimum"),
            maximum=value.get("maximum"),
            unit=value.get("unit"),
            period=value.get("period"),
        )
    if key == "money_range":
        return MoneyRange(
            minimum=_money_from_dict(value.get("minimum")),
            maximum=_money_from_dict(value.get("maximum")),
        )
    raise ValueError(f"unknown criterion payload type: {key}")


def _money_from_dict(data: dict[str, Any] | None) -> MoneyAmount | None:
    if data is None:
        return None
    return MoneyAmount(
        amount=_decimal(data["amount"], "money amount"),
        currency=data["currency"],
        unit=FinancialUnit(data["unit"]),
        fiscal_period=data.get("fiscal_period"),
    )
