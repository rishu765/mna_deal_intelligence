"""Environment-driven configuration for the M3 embedding baseline."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ma_company_intelligence.embeddings.errors import EmbeddingConfigurationError


@dataclass(frozen=True, slots=True)
class EmbeddingSettings:
    """Validated settings for embedding and local vector persistence."""

    provider: str = "openai"
    model: str = "text-embedding-3-small"
    dimension: int = 1_536
    batch_size: int = 64
    timeout_seconds: float = 30.0
    max_retries: int = 2
    api_key: str | None = None
    vector_db_path: Path = Path("artifacts/vector_index.sqlite3")

    def __post_init__(self) -> None:
        if self.provider != "openai":
            raise EmbeddingConfigurationError(
                f"unsupported embedding provider: {self.provider!r}; expected 'openai'"
            )
        if not self.model.strip():
            raise EmbeddingConfigurationError("embedding model must not be blank")
        if self.dimension <= 0:
            raise EmbeddingConfigurationError("embedding dimension must be positive")
        if self.batch_size <= 0:
            raise EmbeddingConfigurationError("embedding batch size must be positive")
        if self.timeout_seconds <= 0:
            raise EmbeddingConfigurationError("provider timeout must be positive")
        if self.max_retries < 0 or self.max_retries > 5:
            raise EmbeddingConfigurationError("provider max retries must be between 0 and 5")
        if self.api_key is not None and not self.api_key.strip():
            raise EmbeddingConfigurationError("OPENAI_API_KEY must not be blank")

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
        *,
        require_api_key: bool = True,
    ) -> EmbeddingSettings:
        """Build settings from environment variables with clear validation errors."""

        values = os.environ if environment is None else environment
        try:
            dimension = int(values.get("MADI_EMBEDDING_DIMENSION", "1536"))
            batch_size = int(values.get("MADI_EMBEDDING_BATCH_SIZE", "64"))
            max_retries = int(values.get("MADI_PROVIDER_MAX_RETRIES", "2"))
        except ValueError as error:
            raise EmbeddingConfigurationError(
                "embedding dimension, batch size, and provider retries must be integers"
            ) from error
        try:
            timeout_seconds = float(values.get("MADI_PROVIDER_TIMEOUT_SECONDS", "30"))
        except ValueError as error:
            raise EmbeddingConfigurationError("provider timeout must be numeric") from error

        api_key = values.get("OPENAI_API_KEY")
        if require_api_key and not api_key:
            raise EmbeddingConfigurationError(
                "OPENAI_API_KEY is required for the OpenAI embedding provider"
            )

        return cls(
            provider=values.get("MADI_EMBEDDING_PROVIDER", "openai").lower(),
            model=values.get("MADI_EMBEDDING_MODEL", "text-embedding-3-small"),
            dimension=dimension,
            batch_size=batch_size,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            api_key=api_key,
            vector_db_path=Path(
                values.get("MADI_VECTOR_DB_PATH", "artifacts/vector_index.sqlite3")
            ),
        )
