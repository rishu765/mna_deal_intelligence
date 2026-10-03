"""Environment-driven configuration for grounded answer generation."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, cast

from ma_company_intelligence.generation.errors import GenerationConfigurationError

ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh", "max"]
_REASONING_EFFORTS = frozenset({"none", "low", "medium", "high", "xhigh", "max"})


@dataclass(frozen=True, slots=True)
class GenerationSettings:
    """Validated model settings that contain no provider response objects."""

    provider: str = "openai"
    model: str = "gpt-6-luna"
    reasoning_effort: ReasoningEffort = "low"
    max_output_tokens: int = 800
    timeout_seconds: float = 30.0
    max_retries: int = 2
    api_key: str | None = None

    def __post_init__(self) -> None:
        if self.provider != "openai":
            raise GenerationConfigurationError(
                f"unsupported generation provider: {self.provider!r}; expected 'openai'"
            )
        if not self.model.strip():
            raise GenerationConfigurationError("generation model must not be blank")
        if self.reasoning_effort not in _REASONING_EFFORTS:
            raise GenerationConfigurationError(
                "generation reasoning effort must be one of: none, low, medium, high, xhigh, max"
            )
        if self.max_output_tokens <= 0:
            raise GenerationConfigurationError("generation max output tokens must be positive")
        if self.timeout_seconds <= 0:
            raise GenerationConfigurationError("provider timeout must be positive")
        if self.max_retries < 0 or self.max_retries > 5:
            raise GenerationConfigurationError("provider max retries must be between 0 and 5")
        if self.api_key is not None and not self.api_key.strip():
            raise GenerationConfigurationError("OPENAI_API_KEY must not be blank")

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
        *,
        require_api_key: bool = True,
    ) -> GenerationSettings:
        """Build settings from environment variables with explicit validation."""

        values = os.environ if environment is None else environment
        try:
            max_output_tokens = int(values.get("MADI_GENERATION_MAX_OUTPUT_TOKENS", "800"))
            max_retries = int(values.get("MADI_PROVIDER_MAX_RETRIES", "2"))
        except ValueError as error:
            raise GenerationConfigurationError(
                "generation token limit and provider retries must be integers"
            ) from error
        try:
            timeout_seconds = float(values.get("MADI_PROVIDER_TIMEOUT_SECONDS", "30"))
        except ValueError as error:
            raise GenerationConfigurationError("provider timeout must be numeric") from error

        raw_effort = values.get("MADI_GENERATION_REASONING_EFFORT", "low").lower()
        if raw_effort not in _REASONING_EFFORTS:
            raise GenerationConfigurationError(
                "generation reasoning effort must be one of: none, low, medium, high, xhigh, max"
            )

        api_key = values.get("OPENAI_API_KEY")
        if require_api_key and not api_key:
            raise GenerationConfigurationError(
                "OPENAI_API_KEY is required for the OpenAI generation provider"
            )

        return cls(
            provider=values.get("MADI_GENERATION_PROVIDER", "openai").lower(),
            model=values.get("MADI_GENERATION_MODEL", "gpt-6-luna"),
            reasoning_effort=cast(ReasoningEffort, raw_effort),
            max_output_tokens=max_output_tokens,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            api_key=api_key,
        )
