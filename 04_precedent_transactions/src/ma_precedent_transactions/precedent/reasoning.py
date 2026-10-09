"""Optional structured-output adapter for grounded valuation commentary."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Protocol, cast

from ma_precedent_transactions.errors import ValuationError
from ma_precedent_transactions.precedent.models import (
    CalculationStatus,
    PrecedentValuationOutput,
    ValuationExplanation,
)

EXPLANATION_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "precedent_set_assessment",
        "strongest_precedents",
        "weakest_precedents",
        "key_valuation_drivers",
        "outlier_commentary",
        "recommended_multiple_focus",
        "valuation_caveats",
        "evidence_ids",
    ],
    "properties": {
        "precedent_set_assessment": {"type": "string"},
        **{
            key: {"type": "array", "items": {"type": "string"}}
            for key in (
                "strongest_precedents",
                "weakest_precedents",
                "key_valuation_drivers",
                "outlier_commentary",
                "recommended_multiple_focus",
                "valuation_caveats",
                "evidence_ids",
            )
        },
    },
}

EXPLANATION_INSTRUCTIONS = """You explain a completed precedent-transaction analysis.
Use only the supplied structured facts and evidence IDs. Do not recalculate, alter, average, or
invent any number. Explain inclusions, exclusions, weak evidence, outliers, buyer-type and deal-
structure caveats. Precedent pricing can include control considerations, but never invent a
control premium. Return only fields required by the structured-output schema.
"""


class _StructuredRunnable(Protocol):
    def invoke(self, input: object) -> object: ...


class _LangChainChatModel(Protocol):
    def with_structured_output(self, schema: object) -> _StructuredRunnable: ...


class LangChainValuationExplanationProvider:
    """Inject a LangChain-compatible model without adding a required vendor dependency."""

    def __init__(self, model: _LangChainChatModel) -> None:
        self._runnable = model.with_structured_output(EXPLANATION_SCHEMA)

    def explain(self, context: PrecedentValuationOutput) -> ValuationExplanation:
        allowed_evidence = {
            evidence.evidence_id
            for multiple_set in context.multiple_sets
            for multiple in multiple_set.multiples
            for evidence in multiple.evidence
        }
        payload = _context_payload(context)
        try:
            raw = self._runnable.invoke(
                (
                    ("system", EXPLANATION_INSTRUCTIONS),
                    ("human", json.dumps(payload, sort_keys=True)),
                )
            )
        except Exception as error:
            raise ValuationError("LangChain valuation explanation failed") from error
        if hasattr(raw, "model_dump"):
            raw = raw.model_dump()
        if not isinstance(raw, Mapping):
            raise ValuationError("structured explanation output must be an object")
        explanation = _parse_explanation(cast(Mapping[object, object], raw))
        unsupported = set(explanation.evidence_ids) - allowed_evidence
        if unsupported:
            raise ValuationError(
                "explanation cited unknown evidence IDs: " + ", ".join(sorted(unsupported))
            )
        return explanation


def _context_payload(context: PrecedentValuationOutput) -> dict[str, object]:
    return {
        "selection": [
            {
                "transaction_id": item.transaction_id,
                "decision": item.decision.value,
                "rationale": item.rationale,
                "warnings": item.warnings,
            }
            for item in context.selection.decisions
        ],
        "multiple_sets": [
            {
                "kind": item.key.kind.value,
                "currency": item.key.currency,
                "period_kind": item.key.period_kind,
                "basis": item.key.basis.value,
                "statistics": {
                    "count": item.statistics.count,
                    "p25": _decimal(item.statistics.percentile_25),
                    "median": _decimal(item.statistics.median),
                    "p75": _decimal(item.statistics.percentile_75),
                    "outliers": item.statistics.outlier_multiple_ids,
                    "warnings": item.statistics.warnings,
                },
            }
            for item in context.multiple_sets
        ],
        "valuation_ranges": [
            {
                "kind": item.key.kind.value,
                "low": _decimal(item.low.implied_equity_value),
                "mid": _decimal(item.mid.implied_equity_value),
                "high": _decimal(item.high.implied_equity_value),
                "currency": item.mid.currency,
                "warnings": item.warnings,
            }
            for item in context.ranges
        ],
        "warnings": context.warnings,
    }


def _parse_explanation(raw: Mapping[object, object]) -> ValuationExplanation:
    assessment = raw.get("precedent_set_assessment")
    if not isinstance(assessment, str) or not assessment.strip():
        raise ValuationError("precedent_set_assessment must be a non-empty string")
    values: dict[str, tuple[str, ...]] = {}
    for key in (
        "strongest_precedents",
        "weakest_precedents",
        "key_valuation_drivers",
        "outlier_commentary",
        "recommended_multiple_focus",
        "valuation_caveats",
        "evidence_ids",
    ):
        item = raw.get(key)
        if not isinstance(item, list) or not all(isinstance(value, str) for value in item):
            raise ValuationError(f"{key} must be a list of strings")
        values[key] = tuple(cast(list[str], item))
    return ValuationExplanation(
        CalculationStatus.AVAILABLE,
        assessment,
        values["strongest_precedents"],
        values["weakest_precedents"],
        values["key_valuation_drivers"],
        values["outlier_commentary"],
        values["recommended_multiple_focus"],
        values["valuation_caveats"],
        values["evidence_ids"],
    )


def _decimal(value: object) -> str | None:
    return None if value is None else str(value)
