"""Optional structured LLM judge kept separate from deterministic metrics."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

from ma_company_intelligence.evaluation.errors import EvaluationJudgeError
from ma_company_intelligence.evaluation.models import EvaluationCase, EvidenceRecord
from ma_company_intelligence.generation.config import ReasoningEffort


@dataclass(frozen=True, slots=True)
class JudgeAssessment:
    correctness: float
    faithfulness: float
    citation_support: float
    reason: str

    def __post_init__(self) -> None:
        for name in ("correctness", "faithfulness", "citation_support"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"judge {name} must be between 0 and 1")
        if not self.reason.strip():
            raise ValueError("judge reason must not be blank")


class EvaluationJudge(Protocol):
    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    def assess(
        self,
        case: EvaluationCase,
        evidence_by_id: Mapping[str, EvidenceRecord],
    ) -> JudgeAssessment: ...


class _JudgeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correctness: float = Field(ge=0.0, le=1.0)
    faithfulness: float = Field(ge=0.0, le=1.0)
    citation_support: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1)


_JUDGE_INSTRUCTIONS = """You are a strict evaluator, not an answer generator.
Score three dimensions independently from 0 to 1:
- correctness: the answer contains the expected facts and handles unanswerable questions;
- faithfulness: every answer claim is supported by the supplied retrieved context only;
- citation_support: cited chunks support their associated claims and provenance is consistent.
Do not reward fluent wording. Do not use external knowledge. A fact can be correct but
unfaithful when the retrieved context does not support it. Return concise reasons."""


class OpenAIEvaluationJudge:
    """Optional OpenAI structured judge; never required by tests or CI."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-6-luna",
        reasoning_effort: ReasoningEffort = "low",
        client: Any | None = None,
    ) -> None:
        if not api_key.strip() or not model.strip():
            raise ValueError("judge API key and model must not be blank")
        self._model = model
        self._reasoning_effort = reasoning_effort
        self._client = client or OpenAI(api_key=api_key)

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> OpenAIEvaluationJudge | None:
        values = os.environ if environment is None else environment
        api_key = values.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            return None
        reasoning_effort = values.get("MADI_EVALUATION_JUDGE_REASONING_EFFORT", "low")
        if reasoning_effort not in {"none", "minimal", "low", "medium", "high", "xhigh"}:
            raise ValueError("invalid MADI_EVALUATION_JUDGE_REASONING_EFFORT")
        return cls(
            api_key=api_key,
            model=values.get("MADI_EVALUATION_JUDGE_MODEL", "gpt-6-luna"),
            reasoning_effort=cast(ReasoningEffort, reasoning_effort),
        )

    def assess(
        self,
        case: EvaluationCase,
        evidence_by_id: Mapping[str, EvidenceRecord],
    ) -> JudgeAssessment:
        observation = case.observation.retrieved_context_answer
        context = [
            evidence_by_id[chunk_id].text
            for chunk_id in case.observation.context_chunk_ids
            if chunk_id in evidence_by_id
        ]
        payload = {
            "question": case.question,
            "expected_facts": case.expected_facts,
            "acceptable_variants": case.acceptable_variants,
            "should_be_insufficient": case.should_be_insufficient,
            "answer": observation.answer,
            "claims": [claim.text for claim in observation.claims],
            "retrieved_context": context,
            "citations": [
                {
                    "chunk_id": citation.chunk_id,
                    "document_id": citation.document_id,
                    "page_numbers": citation.page_numbers,
                }
                for citation in observation.citations
            ],
        }
        try:
            response = self._client.responses.parse(
                model=self._model,
                reasoning={"effort": self._reasoning_effort},
                instructions=_JUDGE_INSTRUCTIONS,
                input=json.dumps(payload, ensure_ascii=False),
                max_output_tokens=500,
                text_format=_JudgeOutput,
            )
        except Exception as error:
            raise EvaluationJudgeError(
                f"evaluation judge request failed for model {self._model!r}"
            ) from error
        parsed = getattr(response, "output_parsed", None)
        if not isinstance(parsed, _JudgeOutput):
            raise EvaluationJudgeError("evaluation judge returned no valid structured output")
        return JudgeAssessment(
            correctness=parsed.correctness,
            faithfulness=parsed.faithfulness,
            citation_support=parsed.citation_support,
            reason=parsed.reason.strip(),
        )
