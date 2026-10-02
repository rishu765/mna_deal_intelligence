"""Embedding interfaces, configuration, and baseline provider."""

from ma_company_intelligence.embeddings.base import Embedder
from ma_company_intelligence.embeddings.config import EmbeddingSettings
from ma_company_intelligence.embeddings.errors import (
    EmbeddingConfigurationError,
    EmbeddingError,
    EmbeddingProviderError,
    EmbeddingResponseError,
    InvalidEmbeddingInputError,
)
from ma_company_intelligence.embeddings.openai_provider import OpenAIEmbedder

__all__ = [
    "Embedder",
    "EmbeddingConfigurationError",
    "EmbeddingError",
    "EmbeddingProviderError",
    "EmbeddingResponseError",
    "EmbeddingSettings",
    "InvalidEmbeddingInputError",
    "OpenAIEmbedder",
]
