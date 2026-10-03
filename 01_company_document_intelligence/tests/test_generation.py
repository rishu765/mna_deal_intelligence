"""Tests for generation configuration and the OpenAI adapter boundary."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from ma_company_intelligence.generation import (
    GenerationConfigurationError,
    GenerationProviderError,
    GenerationRequest,
    GenerationResponseError,
    GenerationSettings,
    OpenAIGenerator,
)


class _FakeResponses:
    def __init__(
        self,
        *,
        answer: str = "Revenue was $125 million.",
        insufficient_evidence: bool = False,
        fail: bool = False,
        malformed: bool = False,
    ) -> None:
        self.answer = answer
        self.insufficient_evidence = insufficient_evidence
        self.fail = fail
        self.malformed = malformed
        self.arguments: dict[str, Any] | None = None

    def parse(self, **arguments: Any) -> SimpleNamespace:
        self.arguments = arguments
        if self.fail:
            raise RuntimeError("secret provider detail")
        if self.malformed:
            return SimpleNamespace(output_parsed=None)
        output_type = arguments["text_format"]
        return SimpleNamespace(
            output_parsed=output_type(
                answer=self.answer,
                insufficient_evidence=self.insufficient_evidence,
            )
        )


def _request() -> GenerationRequest:
    return GenerationRequest(
        instructions="Use only supplied evidence.",
        input_text="QUESTION\nWhat was revenue?\n\nEVIDENCE\nRevenue was $125 million.",
        max_output_tokens=250,
    )


def test_generation_settings_are_environment_driven() -> None:
    settings = GenerationSettings.from_environment(
        {
            "OPENAI_API_KEY": "test-key",
            "MADI_GENERATION_MODEL": "test-model",
            "MADI_GENERATION_REASONING_EFFORT": "medium",
            "MADI_GENERATION_MAX_OUTPUT_TOKENS": "321",
        }
    )

    assert settings.provider == "openai"
    assert settings.model == "test-model"
    assert settings.reasoning_effort == "medium"
    assert settings.max_output_tokens == 321
    assert settings.api_key == "test-key"


def test_generation_settings_require_api_key() -> None:
    with pytest.raises(GenerationConfigurationError, match="OPENAI_API_KEY"):
        GenerationSettings.from_environment({})


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"OPENAI_API_KEY": "x", "MADI_GENERATION_REASONING_EFFORT": "extreme"}, "effort"),
        ({"OPENAI_API_KEY": "x", "MADI_GENERATION_MAX_OUTPUT_TOKENS": "0"}, "positive"),
        ({"OPENAI_API_KEY": "x", "MADI_GENERATION_MAX_OUTPUT_TOKENS": "many"}, "integer"),
    ],
)
def test_invalid_generation_settings_fail_clearly(
    environment: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(GenerationConfigurationError, match=message):
        GenerationSettings.from_environment(environment)


def test_openai_generator_uses_responses_structured_output() -> None:
    responses = _FakeResponses()
    client = SimpleNamespace(responses=responses)
    generator = OpenAIGenerator(
        api_key="test-key",
        model="test-model",
        reasoning_effort="low",
        client=client,
    )

    output = generator.generate(_request())

    assert output.answer == "Revenue was $125 million."
    assert output.insufficient_evidence is False
    assert responses.arguments is not None
    assert responses.arguments["model"] == "test-model"
    assert responses.arguments["reasoning"] == {"effort": "low"}
    assert responses.arguments["instructions"] == _request().instructions
    assert responses.arguments["input"] == _request().input_text
    assert responses.arguments["max_output_tokens"] == 250


def test_openai_generator_wraps_provider_failure_without_secret_detail() -> None:
    client = SimpleNamespace(responses=_FakeResponses(fail=True))
    generator = OpenAIGenerator(api_key="test-key", client=client)

    with pytest.raises(GenerationProviderError) as captured:
        generator.generate(_request())

    assert "secret provider detail" not in str(captured.value)


def test_openai_generator_rejects_malformed_structured_response() -> None:
    client = SimpleNamespace(responses=_FakeResponses(malformed=True))
    generator = OpenAIGenerator(api_key="test-key", client=client)

    with pytest.raises(GenerationResponseError, match="no valid structured answer"):
        generator.generate(_request())
