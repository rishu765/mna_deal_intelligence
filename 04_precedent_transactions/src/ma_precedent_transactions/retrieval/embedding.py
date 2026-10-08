"""Offline deterministic semantic vectors for reproducible tests and demos."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Protocol

from ma_precedent_transactions.errors import EmbeddingError

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_CANONICAL = {
    "acquired": "acquisition",
    "acquire": "acquisition",
    "acquisition": "acquisition",
    "bought": "acquisition",
    "closed": "completed",
    "closing": "completed",
    "completion": "completed",
    "consideration": "payment",
    "paid": "payment",
    "price": "value",
    "purchase": "acquisition",
    "shares": "stock",
    "stake": "ownership",
    "sales": "revenue",
    "withdrawal": "withdrawn",
}


class EmbeddingProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed(self, text: str) -> tuple[float, ...]: ...


@dataclass(frozen=True, slots=True)
class HashingEmbeddingProvider:
    """Feature-hashed token/bigram vectors with small finance synonym normalization."""

    dimension: int = 256

    def __post_init__(self) -> None:
        if self.dimension < 32:
            raise ValueError("embedding dimension must be at least 32")

    @property
    def provider_name(self) -> str:
        return "offline_hashing"

    @property
    def model_name(self) -> str:
        return "deal-token-bigram-v1"

    def embed(self, text: str) -> tuple[float, ...]:
        tokens = semantic_tokens(text)
        if not tokens:
            raise EmbeddingError("cannot embed blank or tokenless text")
        features = [
            *tokens,
            *(f"{left}_{right}" for left, right in zip(tokens, tokens[1:], strict=False)),
        ]
        values = [0.0] * self.dimension
        for feature in features:
            digest = hashlib.sha256(feature.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            values[index] += sign
        magnitude = math.sqrt(sum(value * value for value in values))
        if magnitude == 0:
            raise EmbeddingError("embedding has zero magnitude")
        return tuple(value / magnitude for value in values)


def semantic_tokens(text: str) -> list[str]:
    tokens = _TOKEN_PATTERN.findall(text.casefold())
    return [_CANONICAL.get(token, token) for token in tokens]


def lexical_tokens(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.casefold())
