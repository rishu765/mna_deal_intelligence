"""Versioned JSON-compatible serialization for M1 target financial profiles."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from ma_comparable_valuation.domain import (
    CapitalStructure,
    CompanyIdentity,
    DataQualityFlag,
    EstimateStatus,
    EvidenceReference,
    FinancialMetric,
    FinancialObservation,
    FinancialPeriod,
    FinancialUnit,
    MarketMetric,
    MarketMetricKind,
    MetricBasis,
    NormalizationDecision,
    PeriodKind,
    ProfileCompleteness,
    ProfileCompletenessStatus,
    ProfileConflict,
    ProfileIssue,
    ProfileIssueKind,
    ShareCountBasis,
    TargetCompany,
    TargetFinancialProfile,
)


def target_profile_to_dict(profile: TargetFinancialProfile) -> dict[str, object]:
    return {
        "schema_version": 1,
        "target": _target_to_dict(profile.target),
        "metrics": [item.to_dict() for item in profile.metrics],
        "capital_structure": (
            None
            if profile.capital_structure is None
            else _capital_structure_to_dict(profile.capital_structure)
        ),
        "observations": [_observation_to_dict(item) for item in profile.observations],
        "normalization_decisions": [
            _decision_to_dict(item) for item in profile.normalization_decisions
        ],
        "conflicts": [_conflict_to_dict(item) for item in profile.conflicts],
        "completeness": (
            None if profile.completeness is None else _completeness_to_dict(profile.completeness)
        ),
        "issues": [_issue_to_dict(item) for item in profile.issues],
        "warnings": list(profile.warnings),
    }


def target_company_to_dict(target: TargetCompany) -> dict[str, object]:
    return _target_to_dict(target)


def target_company_from_dict(data: Mapping[str, object]) -> TargetCompany:
    return _target_from_dict(data)


def financial_observation_to_dict(value: FinancialObservation) -> dict[str, object]:
    return _observation_to_dict(value)


def financial_observation_from_dict(data: Mapping[str, object]) -> FinancialObservation:
    return _observation_from_dict(data)


def target_profile_from_dict(data: Mapping[str, object]) -> TargetFinancialProfile:
    if data.get("schema_version") != 1:
        raise ValueError("target financial profile schema_version must be 1")
    try:
        capital_data = data.get("capital_structure")
        completeness_data = data.get("completeness")
        return TargetFinancialProfile(
            target=_target_from_dict(_mapping(data["target"], "target")),
            metrics=tuple(
                FinancialMetric.from_dict(_mapping(item, "metric"))
                for item in _sequence(data.get("metrics", []), "metrics")
            ),
            capital_structure=(
                None
                if capital_data is None
                else _capital_structure_from_dict(_mapping(capital_data, "capital_structure"))
            ),
            observations=tuple(
                _observation_from_dict(_mapping(item, "observation"))
                for item in _sequence(data.get("observations", []), "observations")
            ),
            normalization_decisions=tuple(
                _decision_from_dict(_mapping(item, "normalization decision"))
                for item in _sequence(
                    data.get("normalization_decisions", []), "normalization_decisions"
                )
            ),
            conflicts=tuple(
                _conflict_from_dict(_mapping(item, "conflict"))
                for item in _sequence(data.get("conflicts", []), "conflicts")
            ),
            completeness=(
                None
                if completeness_data is None
                else _completeness_from_dict(_mapping(completeness_data, "completeness"))
            ),
            issues=tuple(
                _issue_from_dict(_mapping(item, "issue"))
                for item in _sequence(data.get("issues", []), "issues")
            ),
            warnings=tuple(
                _string(item, "warning") for item in _sequence(data.get("warnings", []), "warnings")
            ),
        )
    except (KeyError, InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"invalid target financial profile: {error}") from error


def _target_to_dict(target: TargetCompany) -> dict[str, object]:
    return {
        "identity": {
            "company_id": target.identity.company_id,
            "name": target.identity.name,
            "ticker": target.identity.ticker,
            "exchange": target.identity.exchange,
            "country": target.identity.country,
            "identifiers": [list(item) for item in target.identity.identifiers],
        },
        "industry": target.industry,
        "sub_industry": target.sub_industry,
        "fiscal_year_end": target.fiscal_year_end,
        "reporting_currency": target.reporting_currency,
        "business_description": target.business_description,
        "customer_type": target.customer_type,
        "business_model": target.business_model,
        "evidence": [_evidence_to_dict(item) for item in target.evidence],
    }


def _target_from_dict(data: Mapping[str, object]) -> TargetCompany:
    identity = _mapping(data["identity"], "identity")
    identifier_values = _sequence(identity.get("identifiers", []), "identifiers")
    identifiers: list[tuple[str, str]] = []
    for item in identifier_values:
        pair = _sequence(item, "identifier")
        if len(pair) != 2:
            raise ValueError("identifier must contain scheme and value")
        identifiers.append(
            (_string(pair[0], "identifier scheme"), _string(pair[1], "identifier value"))
        )
    return TargetCompany(
        identity=CompanyIdentity(
            company_id=_string(identity["company_id"], "company_id"),
            name=_string(identity["name"], "company name"),
            ticker=_none_or_string(identity.get("ticker"), "ticker"),
            exchange=_none_or_string(identity.get("exchange"), "exchange"),
            country=_none_or_string(identity.get("country"), "country"),
            identifiers=tuple(identifiers),
        ),
        industry=_none_or_string(data.get("industry"), "industry"),
        sub_industry=_none_or_string(data.get("sub_industry"), "sub_industry"),
        fiscal_year_end=_none_or_string(data.get("fiscal_year_end"), "fiscal_year_end"),
        reporting_currency=_none_or_string(data.get("reporting_currency"), "reporting_currency"),
        business_description=_none_or_string(
            data.get("business_description"), "business_description"
        ),
        customer_type=_none_or_string(data.get("customer_type"), "customer_type"),
        business_model=_none_or_string(data.get("business_model"), "business_model"),
        evidence=tuple(
            _evidence_from_dict(_mapping(item, "evidence"))
            for item in _sequence(data.get("evidence", []), "evidence")
        ),
    )


def _period_to_dict(period: FinancialPeriod | None) -> dict[str, object] | None:
    if period is None:
        return None
    return {
        "kind": period.kind.value,
        "label": period.label,
        "estimate_status": period.estimate_status.value,
        "start_date": None if period.start_date is None else period.start_date.isoformat(),
        "end_date": None if period.end_date is None else period.end_date.isoformat(),
    }


def _period_from_dict(data: Mapping[str, object] | None) -> FinancialPeriod | None:
    if data is None:
        return None
    return FinancialPeriod(
        kind=PeriodKind(_string(data["kind"], "period kind")),
        label=_string(data["label"], "period label"),
        estimate_status=EstimateStatus(_string(data["estimate_status"], "estimate_status")),
        start_date=_optional_date(data.get("start_date"), "start_date"),
        end_date=_optional_date(data.get("end_date"), "end_date"),
    )


def _evidence_to_dict(value: EvidenceReference) -> dict[str, object]:
    return {
        "evidence_id": value.evidence_id,
        "source_type": value.source_type,
        "source_name": value.source_name,
        "observed_at": value.observed_at.isoformat(),
        "source_locator": value.source_locator,
        "document_id": value.document_id,
        "chunk_id": value.chunk_id,
        "page_numbers": list(value.page_numbers),
        "excerpt": value.excerpt,
        "published_at": None if value.published_at is None else value.published_at.isoformat(),
        "section": value.section,
        "extraction_method": value.extraction_method,
    }


def _evidence_from_dict(data: Mapping[str, object]) -> EvidenceReference:
    return EvidenceReference(
        evidence_id=_string(data["evidence_id"], "evidence_id"),
        source_type=_string(data["source_type"], "source_type"),
        source_name=_string(data["source_name"], "source_name"),
        observed_at=_datetime(data["observed_at"], "observed_at"),
        source_locator=_none_or_string(data.get("source_locator"), "source_locator"),
        document_id=_none_or_string(data.get("document_id"), "document_id"),
        chunk_id=_none_or_string(data.get("chunk_id"), "chunk_id"),
        page_numbers=tuple(
            _positive_int(item, "page number")
            for item in _sequence(data.get("page_numbers", []), "page_numbers")
        ),
        excerpt=_none_or_string(data.get("excerpt"), "excerpt"),
        published_at=_optional_datetime(data.get("published_at"), "published_at"),
        section=_none_or_string(data.get("section"), "section"),
        extraction_method=_none_or_string(data.get("extraction_method"), "extraction_method"),
    )


def _observation_to_dict(value: FinancialObservation) -> dict[str, object]:
    return {
        "observation_id": value.observation_id,
        "raw_metric_name": value.raw_metric_name,
        "value": str(value.value),
        "unit": value.unit,
        "currency": value.currency,
        "period": _period_to_dict(value.period),
        "as_of": None if value.as_of is None else value.as_of.isoformat(),
        "basis": None if value.basis is None else value.basis.value,
        "adjustment_label": value.adjustment_label,
        "notes": value.notes,
        "quality_flags": [item.value for item in value.quality_flags],
        "evidence": [_evidence_to_dict(item) for item in value.evidence],
    }


def _observation_from_dict(data: Mapping[str, object]) -> FinancialObservation:
    period_value = data.get("period")
    basis_value = data.get("basis")
    return FinancialObservation(
        observation_id=_string(data["observation_id"], "observation_id"),
        raw_metric_name=_string(data["raw_metric_name"], "raw_metric_name"),
        value=_decimal(data["value"], "value"),
        unit=_none_or_string(data.get("unit"), "unit"),
        currency=_none_or_string(data.get("currency"), "currency"),
        period=_period_from_dict(
            None if period_value is None else _mapping(period_value, "period")
        ),
        as_of=_optional_datetime(data.get("as_of"), "as_of"),
        basis=None if basis_value is None else MetricBasis(_string(basis_value, "basis")),
        adjustment_label=_none_or_string(data.get("adjustment_label"), "adjustment_label"),
        notes=_none_or_string(data.get("notes"), "notes"),
        quality_flags=tuple(
            DataQualityFlag(_string(item, "quality flag"))
            for item in _sequence(data.get("quality_flags", []), "quality_flags")
        ),
        evidence=tuple(
            _evidence_from_dict(_mapping(item, "evidence"))
            for item in _sequence(data.get("evidence", []), "evidence")
        ),
    )


def _market_metric_to_dict(value: MarketMetric) -> dict[str, object]:
    return {
        "metric_id": value.metric_id,
        "kind": value.kind.value,
        "value": str(value.value),
        "unit": value.unit.value,
        "as_of": value.as_of.isoformat(),
        "currency": value.currency,
        "quality_flags": [item.value for item in value.quality_flags],
        "share_basis": None if value.share_basis is None else value.share_basis.value,
        "notes": value.notes,
        "source_observation_ids": list(value.source_observation_ids),
        "evidence": [_evidence_to_dict(item) for item in value.evidence],
    }


def _market_metric_from_dict(data: Mapping[str, object]) -> MarketMetric:
    share_basis = data.get("share_basis")
    return MarketMetric(
        metric_id=_string(data["metric_id"], "metric_id"),
        kind=MarketMetricKind(_string(data["kind"], "market metric kind")),
        value=_decimal(data["value"], "value"),
        unit=FinancialUnit(_string(data["unit"], "unit")),
        as_of=_datetime(data["as_of"], "as_of"),
        currency=_none_or_string(data.get("currency"), "currency"),
        quality_flags=tuple(
            DataQualityFlag(_string(item, "quality flag"))
            for item in _sequence(data.get("quality_flags", []), "quality_flags")
        ),
        share_basis=(
            None if share_basis is None else ShareCountBasis(_string(share_basis, "share_basis"))
        ),
        notes=_none_or_string(data.get("notes"), "notes"),
        source_observation_ids=tuple(
            _string(item, "source_observation_id")
            for item in _sequence(data.get("source_observation_ids", []), "source_observation_ids")
        ),
        evidence=tuple(
            _evidence_from_dict(_mapping(item, "evidence"))
            for item in _sequence(data.get("evidence", []), "evidence")
        ),
    )


def _capital_structure_to_dict(value: CapitalStructure) -> dict[str, object]:
    return {
        "snapshot_id": value.snapshot_id,
        "as_of": value.as_of.isoformat(),
        "policy_id": value.policy_id,
        "components": [_market_metric_to_dict(item) for item in value.components],
    }


def _capital_structure_from_dict(data: Mapping[str, object]) -> CapitalStructure:
    return CapitalStructure(
        snapshot_id=_string(data["snapshot_id"], "snapshot_id"),
        as_of=_datetime(data["as_of"], "as_of"),
        policy_id=_string(data["policy_id"], "policy_id"),
        components=tuple(
            _market_metric_from_dict(_mapping(item, "capital component"))
            for item in _sequence(data.get("components", []), "components")
        ),
    )


def _decision_to_dict(value: NormalizationDecision) -> dict[str, object]:
    return {
        "observation_id": value.observation_id,
        "output_metric_id": value.output_metric_id,
        "raw_metric_name": value.raw_metric_name,
        "normalized_name": value.normalized_name,
        "source_unit": value.source_unit,
        "target_unit": value.target_unit.value,
        "conversion_factor": str(value.conversion_factor),
        "policy_id": value.policy_id,
        "note": value.note,
    }


def _decision_from_dict(data: Mapping[str, object]) -> NormalizationDecision:
    return NormalizationDecision(
        observation_id=_string(data["observation_id"], "observation_id"),
        output_metric_id=_string(data["output_metric_id"], "output_metric_id"),
        raw_metric_name=_string(data["raw_metric_name"], "raw_metric_name"),
        normalized_name=_string(data["normalized_name"], "normalized_name"),
        source_unit=_string(data["source_unit"], "source_unit"),
        target_unit=FinancialUnit(_string(data["target_unit"], "target_unit")),
        conversion_factor=_decimal(data["conversion_factor"], "conversion_factor"),
        policy_id=_string(data["policy_id"], "policy_id"),
        note=_none_or_string(data.get("note"), "note"),
    )


def _conflict_to_dict(value: ProfileConflict) -> dict[str, object]:
    return {
        "conflict_id": value.conflict_id,
        "field": value.field,
        "observation_ids": list(value.observation_ids),
        "reason": value.reason,
    }


def _conflict_from_dict(data: Mapping[str, object]) -> ProfileConflict:
    return ProfileConflict(
        conflict_id=_string(data["conflict_id"], "conflict_id"),
        field=_string(data["field"], "field"),
        observation_ids=tuple(
            _string(item, "observation_id")
            for item in _sequence(data.get("observation_ids", []), "observation_ids")
        ),
        reason=_string(data["reason"], "reason"),
    )


def _completeness_to_dict(value: ProfileCompleteness) -> dict[str, object]:
    return {
        "present": list(value.present),
        "missing": list(value.missing),
        "status": value.status.value,
    }


def _completeness_from_dict(data: Mapping[str, object]) -> ProfileCompleteness:
    return ProfileCompleteness(
        present=tuple(
            _string(item, "present field") for item in _sequence(data.get("present", []), "present")
        ),
        missing=tuple(
            _string(item, "missing field") for item in _sequence(data.get("missing", []), "missing")
        ),
        status=ProfileCompletenessStatus(_string(data["status"], "status")),
    )


def _issue_to_dict(value: ProfileIssue) -> dict[str, object]:
    return {
        "kind": value.kind.value,
        "message": value.message,
        "observation_ids": list(value.observation_ids),
    }


def _issue_from_dict(data: Mapping[str, object]) -> ProfileIssue:
    return ProfileIssue(
        kind=ProfileIssueKind(_string(data["kind"], "issue kind")),
        message=_string(data["message"], "issue message"),
        observation_ids=tuple(
            _string(item, "observation_id")
            for item in _sequence(data.get("observation_ids", []), "observation_ids")
        ),
    )


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{name} must be an object with string keys")
    return value


def _sequence(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value


def _string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value


def _none_or_string(value: object, name: str) -> str | None:
    return None if value is None else _string(value, name)


def _decimal(value: object, name: str) -> Decimal:
    try:
        return Decimal(_string(value, name))
    except InvalidOperation as error:
        raise ValueError(f"{name} must be a decimal string") from error


def _datetime(value: object, name: str) -> datetime:
    return datetime.fromisoformat(_string(value, name))


def _optional_datetime(value: object, name: str) -> datetime | None:
    return None if value is None else _datetime(value, name)


def _optional_date(value: object, name: str) -> date | None:
    return None if value is None else date.fromisoformat(_string(value, name))


def _positive_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value
