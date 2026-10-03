"""OpenAI Responses API implementation of the generation interface."""

from __future__ import annotations

from typing import Any

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

from ma_company_intelligence.generation.base import (
    GenerationOutput,
    GenerationRequest,
)
from ma_company_intelligence.generation.config import ReasoningEffort
from ma_company_intelligence.generation.errors import (
    GenerationProviderError,
    GenerationResponseError,
)


class _OpenAIGroundedAnswer(BaseModel):
    """Provider-side schema used only to validate the model response."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)
    insufficient_evidence: bool


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
        )
