"""OpenAI implementation of the provider-neutral embedding interface."""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from ma_company_intelligence.embeddings.errors import (
    EmbeddingProviderError,
    EmbeddingResponseError,
    InvalidEmbeddingInputError,
)


class OpenAIEmbedder:
    """Generate ordered float embeddings with the OpenAI embeddings API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimension: int = 1_536,
        client: Any | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("api_key must not be blank")
        if not model.strip():
            raise ValueError("model must not be blank")
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._model = model
        self._dimension = dimension
        self._client = client or OpenAI(api_key=api_key)

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_text(self, text: str) -> tuple[float, ...]:
        return self.embed_batch((text,))[0]

    def embed_batch(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        if not texts:
            return ()
        invalid_position = next(
            (index for index, text in enumerate(texts) if not text.strip()),
            None,
        )
        if invalid_position is not None:
            raise InvalidEmbeddingInputError(
                f"embedding input at batch position {invalid_position} is blank"
            )

        try:
            response = self._client.embeddings.create(
                input=list(texts),
                model=self._model,
                dimensions=self._dimension,
                encoding_format="float",
            )
        except Exception as error:
            raise EmbeddingProviderError(
                f"OpenAI embedding request failed for model {self._model!r}"
            ) from error

        data = sorted(response.data, key=lambda item: item.index)
        if len(data) != len(texts):
            raise EmbeddingResponseError(
                f"provider returned {len(data)} vectors for {len(texts)} texts"
            )

        vectors = tuple(tuple(float(value) for value in item.embedding) for item in data)
        for position, vector in enumerate(vectors):
            if len(vector) != self._dimension:
                raise EmbeddingResponseError(
                    f"vector at batch position {position} has dimension {len(vector)}; "
                    f"expected {self._dimension}"
                )
        return vectors
