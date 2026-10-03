"""OpenAI Responses API implementation of the generation interface."""

from __future__ import annotations

from typing import Any

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

from ma_company_intelligence.domain import ResearchSectionKey
from ma_company_intelligence.generation.base import (
    GenerationOutput,
    GenerationRequest,
)
from ma_company_intelligence.generation.config import ReasoningEffort
from ma_company_intelligence.generation.errors import (
    GenerationProviderError,
    GenerationResponseError,
)
from ma_company_intelligence.generation.research import (
    GeneratedFinancialMetric,
    GeneratedResearchItem,
    GeneratedResearchSection,
    ResearchGenerationOutput,
)


class _OpenAIGroundedAnswer(BaseModel):
    """Provider-side schema used only to validate the model response."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)
    insufficient_evidence: bool
    cited_evidence_ids: list[str] = Field(default_factory=list)


class _OpenAIResearchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    evidence_ids: list[str]


class _OpenAIFinancialMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_name: str = Field(min_length=1)
    value: str = Field(min_length=1)
    fiscal_period: str | None
    unit: str | None
    currency: str | None
    basis: str | None
    evidence_ids: list[str]


class _OpenAIResearchSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: ResearchSectionKey
    summary: str | None
    summary_evidence_ids: list[str]
    facts: list[_OpenAIResearchItem]
    observations: list[_OpenAIResearchItem]
    financial_metrics: list[_OpenAIFinancialMetric]
    insufficient_evidence: bool


class _OpenAIResearchProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str | None
    sections: list[_OpenAIResearchSection]


class OpenAIGenerator:
    """Generate schema-validated grounded answers with the Responses API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-6-luna",
        reasoning_effort: ReasoningEffort = "low",
        client: Any | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("api_key must not be blank")
        if not model.strip():
            raise ValueError("model must not be blank")
        self._model = model
        self._reasoning_effort = reasoning_effort
        self._client = client or OpenAI(api_key=api_key)

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    def generate(self, request: GenerationRequest) -> GenerationOutput:
        try:
            response = self._client.responses.parse(
                model=self._model,
                reasoning={"effort": self._reasoning_effort},
                instructions=request.instructions,
                input=request.input_text,
                max_output_tokens=request.max_output_tokens,
                text_format=_OpenAIGroundedAnswer,
            )
        except Exception as error:
            raise GenerationProviderError(
                f"OpenAI generation request failed for model {self._model!r}"
            ) from error

        parsed = getattr(response, "output_parsed", None)
        if not isinstance(parsed, _OpenAIGroundedAnswer):
            raise GenerationResponseError(
                f"OpenAI model {self._model!r} returned no valid structured answer"
            )
        if not parsed.answer.strip():
            raise GenerationResponseError(f"OpenAI model {self._model!r} returned a blank answer")
        return GenerationOutput(
            answer=parsed.answer.strip(),
            insufficient_evidence=parsed.insufficient_evidence,
            cited_evidence_ids=tuple(parsed.cited_evidence_ids),
        )

    def generate_research(self, request: GenerationRequest) -> ResearchGenerationOutput:
        """Generate and validate the application-owned structured research schema."""

        try:
            response = self._client.responses.parse(
                model=self._model,
                reasoning={"effort": self._reasoning_effort},
                instructions=request.instructions,
                input=request.input_text,
                max_output_tokens=request.max_output_tokens,
                text_format=_OpenAIResearchProfile,
            )
        except Exception as error:
            raise GenerationProviderError(
                f"OpenAI research request failed for model {self._model!r}"
            ) from error

        parsed = getattr(response, "output_parsed", None)
        if not isinstance(parsed, _OpenAIResearchProfile):
            raise GenerationResponseError(
                f"OpenAI model {self._model!r} returned no valid structured research profile"
            )
        try:
            return ResearchGenerationOutput(
                company_name=parsed.company_name,
                sections=tuple(self._convert_section(section) for section in parsed.sections),
            )
        except ValueError as error:
            raise GenerationResponseError(
                f"OpenAI model {self._model!r} returned an invalid research profile"
            ) from error

    @staticmethod
    def _convert_section(section: _OpenAIResearchSection) -> GeneratedResearchSection:
        return GeneratedResearchSection(
            key=section.key,
            summary=section.summary,
            summary_evidence_ids=tuple(section.summary_evidence_ids),
            facts=tuple(
                GeneratedResearchItem(text=item.text, evidence_ids=tuple(item.evidence_ids))
                for item in section.facts
            ),
            observations=tuple(
                GeneratedResearchItem(text=item.text, evidence_ids=tuple(item.evidence_ids))
                for item in section.observations
            ),
            financial_metrics=tuple(
                GeneratedFinancialMetric(
                    metric_name=metric.metric_name,
                    value=metric.value,
                    fiscal_period=metric.fiscal_period,
                    unit=metric.unit,
                    currency=metric.currency,
                    basis=metric.basis,
                    evidence_ids=tuple(metric.evidence_ids),
                )
                for metric in section.financial_metrics
            ),
            insufficient_evidence=section.insufficient_evidence,
        )
