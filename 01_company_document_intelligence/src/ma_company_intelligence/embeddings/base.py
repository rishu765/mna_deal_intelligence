"""Provider-neutral embedding interface."""

from __future__ import annotations

from typing import Protocol


class Embedder(Protocol):
    """Convert text to fixed-dimensional floating-point vectors."""

    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed_text(self, text: str) -> tuple[float, ...]: ...

    def embed_batch(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]: ...
