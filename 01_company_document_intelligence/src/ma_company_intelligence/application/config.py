"""Validated environment configuration for the HTTP application layer."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class APISettings:
    """Safe operational limits that do not contain provider secrets."""

    document_root: Path = Path("data/raw")
    max_document_bytes: int = 50 * 1024 * 1024
    max_question_characters: int = 4_000
    max_top_k: int = 20
    max_request_body_bytes: int = 64 * 1024
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        if self.max_document_bytes <= 0:
            raise ValueError("API maximum document bytes must be positive")
        if self.max_question_characters <= 0:
            raise ValueError("API maximum question characters must be positive")
        if self.max_question_characters > 10_000:
            raise ValueError("API maximum question characters cannot exceed 10000")
        if self.max_top_k <= 0:
            raise ValueError("API maximum top_k must be positive")
        if self.max_top_k > 100:
            raise ValueError("API maximum top_k cannot exceed 100")
        if self.max_request_body_bytes <= 0:
            raise ValueError("API maximum request body bytes must be positive")
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("MADI_LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> APISettings:
        values = os.environ if environment is None else environment
        try:
            max_document_bytes = int(
                values.get("MADI_API_MAX_DOCUMENT_BYTES", str(50 * 1024 * 1024))
            )
            max_question_characters = int(values.get("MADI_API_MAX_QUESTION_CHARACTERS", "4000"))
            max_top_k = int(values.get("MADI_API_MAX_TOP_K", "20"))
            max_request_body_bytes = int(
                values.get("MADI_API_MAX_REQUEST_BODY_BYTES", str(64 * 1024))
            )
        except ValueError as error:
            raise ValueError("MADI_API numeric limits must be integers") from error
        return cls(
            document_root=Path(values.get("MADI_DOCUMENT_ROOT", "data/raw")),
            max_document_bytes=max_document_bytes,
            max_question_characters=max_question_characters,
            max_top_k=max_top_k,
            max_request_body_bytes=max_request_body_bytes,
            log_level=values.get("MADI_LOG_LEVEL", "INFO").upper(),
        )
