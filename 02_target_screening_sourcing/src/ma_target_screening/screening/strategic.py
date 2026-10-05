"""Evidence-grounded strategic-fit provider contract and offline implementation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Protocol

from ma_target_screening.errors import (
    MalformedStrategicFitOutputError,
    StrategicFitError,
)
from ma_target_screening.profile import CandidateProfile
from ma_target_screening.screening.models import (
    CriterionEvaluation,
    CriterionOutcome,
    StrategicFitAssessment,
)
from ma_target_screening.thesis import (
    AcquisitionThesis,
    CriterionRequirement,
    EvaluationMethod,
    ScreeningCriterion,
)


@dataclass(frozen=True, slots=True)
class StrategicFitRequest:
    thesis: AcquisitionThesis
    profile: CandidateProfile
    criterion: ScreeningCriterion


@dataclass(frozen=True, slots=True)
class SemanticAssessmentOutput:
    criterion_id: str
    outcome: CriterionOutcome
    reason: str
    score: Decimal | None
    evidence_ids: tuple[str, ...]
    uncertainty: str | None = None

    def __post_init__(self) -> None:
        if not self.criterion_id.strip() or not self.reason.strip():
            raise ValueError("semantic criterion ID and reason must not be blank")
        if self.score is not None and (
            not self.score.is_finite() or self.score < 0 or self.score > 1
        ):
            raise ValueError("semantic score must be between 0 and 1")
        if self.outcome in {CriterionOutcome.UNKNOWN, CriterionOutcome.NOT_APPLICABLE}:
            if self.score is not None:
                raise ValueError("unknown semantic output cannot include a score")
        elif self.score is None:
            raise ValueError("known semantic output requires a score")
        if (
            self.outcome is CriterionOutcome.PASS
            and self.score is not None
            and self.score < Decimal("0.67")
        ):
            raise ValueError("pass semantic output requires score of at least 0.67")
        if (
            self.outcome is CriterionOutcome.PARTIAL
            and self.score is not None
            and (self.score < Decimal("0.34") or self.score > Decimal("0.66"))
        ):
            raise ValueError("partial semantic output requires score from 0.34 through 0.66")
        if (
            self.outcome is CriterionOutcome.FAIL
            and self.score is not None
            and self.score > Decimal("0.33")
        ):
            raise ValueError("fail semantic output requires score of at most 0.33")


class StrategicFitProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    def assess(self, request: StrategicFitRequest) -> SemanticAssessmentOutput: ...


class StructuredGenerationClient(Protocol):
    """Minimal boundary for an LLM client that guarantees a JSON object response."""

    def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class StructuredLLMStrategicFitProvider:
    """Ask a structured-generation client to assess one criterion against supplied evidence."""

    client: StructuredGenerationClient

    @property
    def provider_name(self) -> str:
        return "structured_llm_strategic_fit"

    def assess(self, request: StrategicFitRequest) -> SemanticAssessmentOutput:
        system_prompt = (
            "Assess exactly one M&A strategic-fit criterion. Use only the supplied candidate "
            "profile evidence. Do not introduce company claims or evidence IDs. Return a JSON "
            "object with criterion_id, outcome, score, reason, evidence_ids, and uncertainty. "
            "Outcome must be pass, fail, partial, unknown, or not_applicable; score is 0..1 for "
            "known outcomes and null for unknown/not_applicable. For an exclusion, pass means "
            "the prohibited condition is absent and fail means it is present."
        )
        evidence_payload = {
            "thesis": {
                "objective": request.thesis.objective,
                "strategic_rationale": request.thesis.strategic_rationale,
                "acquirer": request.thesis.acquirer.name,
            },
            "criterion": {
                "criterion_id": request.criterion.criterion_id,
                "description": request.criterion.description,
                "target": str(request.criterion.value),
                "requirement": request.criterion.requirement.value,
            },
            "candidate": request.profile.candidate.canonical_name,
            "facts": [
                {
                    "field": item.field.value,
                    "value": item.value,
                    "evidence_ids": [e.evidence_id for e in item.evidence],
                }
                for item in request.profile.facts
            ],
            "inferences": [
                {
                    "field": item.field.value,
                    "statement": item.statement,
                    "evidence_ids": [e.evidence_id for e in item.evidence],
                }
                for item in request.profile.inferences
            ],
            "financial_metrics": [
                {
                    "metric_name": item.metric_name,
                    "value": item.value,
                    "currency": item.currency,
                    "unit": item.unit,
                    "fiscal_period": item.fiscal_period,
                    "evidence_ids": [e.evidence_id for e in item.evidence],
                }
                for item in request.profile.financial_metrics
            ],
        }
        try:
            raw = self.client.generate_json(
                system_prompt=system_prompt,
                user_prompt=json.dumps(evidence_payload, ensure_ascii=False),
            )
            return _parse_semantic_output(raw)
        except MalformedStrategicFitOutputError:
            raise
        except Exception as error:
            raise StrategicFitError("Structured semantic generation failed") from error


@dataclass(frozen=True, slots=True)
class FixtureStrategicFitProvider:
    """Return curated, deterministic semantic outputs for tests and offline demos."""

    fixture_path: Path

    @property
    def provider_name(self) -> str:
        return "fixture_strategic_fit"

    def assess(self, request: StrategicFitRequest) -> SemanticAssessmentOutput:
        records = self._load()
        domain = request.profile.candidate.website_domain
        name = request.profile.candidate.canonical_name.casefold()
        record = next(
            (
                item
                for item in records
                if (domain and str(item.get("website_domain", "")).casefold() == domain.casefold())
                or str(item.get("canonical_name", "")).casefold() == name
            ),
            None,
        )
        if record is None:
            return SemanticAssessmentOutput(
                criterion_id=request.criterion.criterion_id,
                outcome=CriterionOutcome.UNKNOWN,
                reason="No offline strategic-fit assessment exists for this candidate.",
                score=None,
                evidence_ids=(),
                uncertainty="Fixture coverage is unavailable.",
            )
        assessment = next(
            (
                item
                for item in record.get("assessments", [])
                if item.get("criterion_id") == request.criterion.criterion_id
            ),
            None,
        )
        if assessment is None:
            return SemanticAssessmentOutput(
                criterion_id=request.criterion.criterion_id,
                outcome=CriterionOutcome.UNKNOWN,
                reason="The offline provider has no assessment for this criterion.",
                score=None,
                evidence_ids=(),
                uncertainty="Criterion-specific fixture coverage is unavailable.",
            )
        try:
            return _parse_semantic_output(assessment)
        except (KeyError, TypeError, ValueError, InvalidOperation) as error:
            raise MalformedStrategicFitOutputError(
                "Malformed fixture strategic-fit assessment"
            ) from error

    def _load(self) -> list[dict[str, Any]]:
        try:
            value = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise StrategicFitError(
                f"Unable to load strategic-fit fixture: {self.fixture_path}"
            ) from error
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise MalformedStrategicFitOutputError("Strategic-fit fixture must be a JSON list")
        return value


@dataclass(frozen=True, slots=True)
class StrategicFitService:
    provider: StrategicFitProvider

    def assess(
        self, thesis: AcquisitionThesis, profile: CandidateProfile
    ) -> StrategicFitAssessment:
        criteria = tuple(
            item for item in thesis.criteria if item.evaluation_method is EvaluationMethod.SEMANTIC
        )
        evaluations: list[CriterionEvaluation] = []
        warnings: list[str] = []
        for criterion in criteria:
            try:
                output = self.provider.assess(
                    StrategicFitRequest(thesis=thesis, profile=profile, criterion=criterion)
                )
                evaluations.append(self._ground(profile, criterion, output))
            except (StrategicFitError, TypeError, ValueError) as error:
                warnings.append(
                    f"Strategic-fit provider failed for {criterion.criterion_id}: "
                    f"{type(error).__name__}"
                )
                evaluations.append(
                    CriterionEvaluation(
                        criterion_id=criterion.criterion_id,
                        category=criterion.category,
                        requirement=criterion.requirement,
                        evaluation_method=criterion.evaluation_method,
                        outcome=CriterionOutcome.UNKNOWN,
                        reason="Strategic-fit assessment failed; no semantic conclusion was used.",
                        uncertainty="Provider failure or malformed structured output.",
                    )
                )
        known = [item.score for item in evaluations if item.score is not None]
        score = None
        if known:
            score = (sum(known, Decimal("0")) / Decimal(len(known)) * 100).quantize(Decimal("0.1"))
        summary = _summary(evaluations)
        return StrategicFitAssessment(
            evaluations=tuple(evaluations),
            score=score,
            summary=summary,
            warnings=tuple(warnings),
        )

    def _ground(
        self,
        profile: CandidateProfile,
        criterion: ScreeningCriterion,
        output: SemanticAssessmentOutput,
    ) -> CriterionEvaluation:
        if output.criterion_id != criterion.criterion_id:
            raise MalformedStrategicFitOutputError("Semantic output criterion ID does not match")
        catalog = {item.evidence_id: item for item in profile.evidence}
        unknown_ids = tuple(item for item in output.evidence_ids if item not in catalog)
        if unknown_ids:
            raise MalformedStrategicFitOutputError(
                "Semantic output cites evidence outside the candidate profile"
            )
        evidence = tuple(catalog[item] for item in output.evidence_ids)
        if (
            output.outcome not in {CriterionOutcome.UNKNOWN, CriterionOutcome.NOT_APPLICABLE}
            and not evidence
        ):
            raise MalformedStrategicFitOutputError(
                "Known semantic assessments require profile evidence"
            )
        return CriterionEvaluation(
            criterion_id=criterion.criterion_id,
            category=criterion.category,
            requirement=criterion.requirement,
            evaluation_method=criterion.evaluation_method,
            outcome=output.outcome,
            reason=output.reason,
            candidate_values=(str(criterion.value),),
            evidence=evidence,
            score=output.score if criterion.requirement is CriterionRequirement.SOFT else None,
            uncertainty=output.uncertainty,
        )


def _summary(evaluations: list[CriterionEvaluation]) -> str:
    if not evaluations:
        return "No semantic strategic-fit criteria were defined."
    passes = sum(item.outcome is CriterionOutcome.PASS for item in evaluations)
    partials = sum(item.outcome is CriterionOutcome.PARTIAL for item in evaluations)
    unknowns = sum(item.outcome is CriterionOutcome.UNKNOWN for item in evaluations)
    return (
        f"Strategic fit: {passes} strong, {partials} partial, and {unknowns} unknown "
        "criterion assessments."
    )


def _parse_semantic_output(data: dict[str, Any]) -> SemanticAssessmentOutput:
    try:
        score_value = data.get("score")
        uncertainty = data.get("uncertainty")
        return SemanticAssessmentOutput(
            criterion_id=str(data["criterion_id"]),
            outcome=CriterionOutcome(data["outcome"]),
            reason=str(data["reason"]),
            score=None if score_value is None else Decimal(str(score_value)),
            evidence_ids=tuple(str(item) for item in data.get("evidence_ids", [])),
            uncertainty=None if uncertainty is None else str(uncertainty),
        )
    except (KeyError, TypeError, ValueError, InvalidOperation) as error:
        raise MalformedStrategicFitOutputError(
            "Malformed structured strategic-fit output"
        ) from error
