"""JSON-compatible presentation of complete valuation workflow results."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from ma_comparable_valuation.domain import EvidenceReference, FinancialMetric, MarketMetric
from ma_comparable_valuation.valuation import ValuationOutput
from ma_comparable_valuation.workflow import EndToEndValuationResult


def workflow_to_dict(result: EndToEndValuationResult) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "target_profile": result.target_profile.to_dict(),
        "universe": {
            "universe_id": result.universe.universe_id,
            "target_id": result.universe.target_id,
            "provider_name": result.universe.provider_name,
            "observed_at": result.universe.observed_at.isoformat(),
            "companies": [
                {
                    "company_id": item.identity.company_id,
                    "name": item.identity.name,
                    "ticker": item.identity.ticker,
                    "exchange": item.identity.exchange,
                    "country": item.identity.country,
                    "industry": item.industry,
                    "sub_industry": item.sub_industry,
                    "evidence_ids": [value.evidence_id for value in item.evidence],
                }
                for item in result.universe.companies
            ],
            "warnings": list(result.universe.warnings),
        },
        "selection": {
            "policy_id": result.selection.policy_id,
            "selected_at": (
                None
                if result.selection.selected_at is None
                else result.selection.selected_at.isoformat()
            ),
            "decisions": [
                {
                    "company_id": item.company_id,
                    "decision": item.decision.value,
                    "score": _decimal(item.score),
                    "confidence": str(item.confidence),
                    "rationale": item.rationale,
                    "warnings": list(item.warnings),
                    "evidence_ids": [value.evidence_id for value in item.evidence],
                }
                for item in result.selection.decisions
            ],
            "warnings": list(result.selection.warnings),
        },
        "peer_set": {
            "peer_set_id": result.peer_set.peer_set_id,
            "created_at": (
                None
                if result.peer_set.created_at is None
                else result.peer_set.created_at.isoformat()
            ),
            "policy_id": result.peer_set.policy_id,
            "snapshots": [
                {
                    "company_id": item.company.identity.company_id,
                    "company_name": item.company.identity.name,
                    "as_of": item.as_of.isoformat(),
                    "financial_metrics": [
                        _financial_metric(value) for value in item.financial_metrics
                    ],
                    "market_metrics": [_market_metric(value) for value in item.market_metrics],
                    "quality_flags": [value.value for value in item.quality_flags],
                    "warnings": list(item.warnings),
                }
                for item in result.peer_set.snapshots
            ],
            "warnings": list(result.peer_set.warnings),
        },
        "valuation": valuation_to_dict(result.valuation),
    }


def valuation_to_dict(output: ValuationOutput) -> dict[str, Any]:
    return {
        "output_id": output.output_id,
        "target_id": output.target_id,
        "peer_set_id": output.peer_set_id,
        "multiple_sets": [
            {
                "set_id": item.set_id,
                "label": item.request.label,
                "period": item.request.period_label,
                "basis": item.request.basis.value,
                "multiple_kind": item.request.definition.kind.value,
                "observations": [
                    {
                        "multiple_id": value.multiple_id,
                        "company_id": value.company_id,
                        "status": value.status.value,
                        "value": _decimal(value.value),
                        "numerator_value": _decimal(value.numerator_value),
                        "denominator_value": _decimal(value.denominator_value),
                        "denominator_period": (
                            None
                            if value.denominator_period is None
                            else value.denominator_period.label
                        ),
                        "treatment_reason": value.treatment_reason,
                        "evidence_ids": [evidence.evidence_id for evidence in value.evidence],
                        "warnings": list(value.warnings),
                    }
                    for value in item.multiples
                ],
                "statistics": {
                    "statistics_id": item.statistics.statistics_id,
                    "valid_count": item.statistics.count,
                    "excluded_count": item.statistics.excluded_count,
                    "minimum": _decimal(item.statistics.minimum),
                    "percentile_25": _decimal(item.statistics.percentile_25),
                    "median": _decimal(item.statistics.median),
                    "percentile_75": _decimal(item.statistics.percentile_75),
                    "maximum": _decimal(item.statistics.maximum),
                    "mean": _decimal(item.statistics.mean),
                    "percentile_method": item.statistics.percentile_method,
                    "excluded": [list(value) for value in item.statistics.excluded],
                    "outlier_multiple_ids": list(item.statistics.outlier_multiple_ids),
                    "warnings": list(item.statistics.warnings),
                },
            }
            for item in output.multiple_sets
        ],
        "ranges": [
            {
                "range_id": item.range_id,
                "method": item.request.label,
                "low": _implied(item.low),
                "mid": _implied(item.mid),
                "high": _implied(item.high),
                "warnings": list(item.warnings),
            }
            for item in output.ranges
        ],
        "explanation": (
            None
            if output.explanation is None
            else {
                "status": output.explanation.status.value,
                "peer_set_assessment": output.explanation.peer_set_assessment,
                "preferred_metrics": list(output.explanation.preferred_metrics),
                "key_drivers": list(output.explanation.key_drivers),
                "outlier_commentary": list(output.explanation.outlier_commentary),
                "range_interpretation": output.explanation.range_interpretation,
                "risks_and_caveats": list(output.explanation.risks_and_caveats),
                "evidence_ids": list(output.explanation.evidence_ids),
                "warnings": list(output.explanation.warnings),
            }
        ),
        "warnings": list(output.warnings),
    }


def _implied(value: Any) -> dict[str, Any]:
    return {
        "valuation_id": value.valuation_id,
        "anchor": value.anchor,
        "multiple": str(value.multiple),
        "target_metric_id": value.target_metric_id,
        "value_family": value.value_family.value,
        "implied_value": str(value.implied_value),
        "implied_equity_value": _decimal(value.implied_equity_value),
        "implied_per_share": _decimal(value.implied_per_share),
        "currency": value.currency,
        "unit": value.unit.value,
        "trace": {
            "trace_id": value.trace.trace_id,
            "formula": value.trace.formula,
            "policy_id": value.trace.policy_id,
            "input_ids": [item.input_id for item in value.trace.inputs],
        },
        "bridge": (
            None
            if value.bridge is None
            else {
                "bridge_id": value.bridge.bridge_id,
                "status": value.bridge.status.value,
                "component_ids": list(value.bridge.component_ids),
                "omitted_components": [item.value for item in value.bridge.omitted_components],
                "warnings": list(value.bridge.warnings),
            }
        ),
        "warnings": list(value.warnings),
    }


def _financial_metric(value: FinancialMetric) -> dict[str, Any]:
    return {
        "metric_id": value.metric_id,
        "name": value.name.value,
        "value": str(value.value),
        "currency": value.currency,
        "unit": value.unit.value,
        "period": value.period.label,
        "estimate_status": value.period.estimate_status.value,
        "basis": value.basis.value,
        "as_of": None if value.as_of is None else value.as_of.isoformat(),
        "evidence": [_evidence(item) for item in value.evidence],
        "quality_flags": [item.value for item in value.quality_flags],
    }


def _market_metric(value: MarketMetric) -> dict[str, Any]:
    return {
        "metric_id": value.metric_id,
        "kind": value.kind.value,
        "value": str(value.value),
        "currency": value.currency,
        "unit": value.unit.value,
        "as_of": value.as_of.isoformat(),
        "share_basis": None if value.share_basis is None else value.share_basis.value,
        "evidence": [_evidence(item) for item in value.evidence],
        "quality_flags": [item.value for item in value.quality_flags],
    }


def _evidence(value: EvidenceReference) -> dict[str, Any]:
    return {
        "evidence_id": value.evidence_id,
        "source_type": value.source_type,
        "source_name": value.source_name,
        "source_locator": value.source_locator,
        "observed_at": value.observed_at.isoformat(),
    }


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)
