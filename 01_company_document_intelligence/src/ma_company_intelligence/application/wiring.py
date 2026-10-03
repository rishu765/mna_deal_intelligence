"""Small lazy dependency container for the HTTP application."""

from __future__ import annotations

import os
from collections.abc import Mapping
from threading import Lock

from ma_company_intelligence.application.config import APISettings
from ma_company_intelligence.application.service import (
    CompanyIntelligenceService,
    ProjectApplicationService,
)
from ma_company_intelligence.embeddings import EmbeddingSettings, OpenAIEmbedder
from ma_company_intelligence.generation import GenerationSettings, OpenAIGenerator


class ServiceContainer:
    """Build provider clients once, on first provider-dependent request."""

    def __init__(
        self,
        *,
        api_settings: APISettings,
        environment: Mapping[str, str] | None = None,
        service: CompanyIntelligenceService | None = None,
    ) -> None:
        self.api_settings = api_settings
        self._environment = os.environ if environment is None else environment
        self._service = service
        self._lock = Lock()

    def get_service(self) -> CompanyIntelligenceService:
        if self._service is not None:
            return self._service
        with self._lock:
            if self._service is None:
                embedding = EmbeddingSettings.from_environment(self._environment)
                generation = GenerationSettings.from_environment(self._environment)
                embedder = OpenAIEmbedder(
                    api_key=embedding.api_key or "",
                    model=embedding.model,
                    dimension=embedding.dimension,
                    timeout=embedding.timeout_seconds,
                    max_retries=embedding.max_retries,
                )
                generator = OpenAIGenerator(
                    api_key=generation.api_key or "",
                    model=generation.model,
                    reasoning_effort=generation.reasoning_effort,
                    timeout=generation.timeout_seconds,
                    max_retries=generation.max_retries,
                )
                self._service = ProjectApplicationService(
                    embedder=embedder,
                    generator=generator,
                    index_path=embedding.vector_db_path,
                    embedding_batch_size=embedding.batch_size,
                    api_settings=self.api_settings,
                    answer_max_output_tokens=generation.max_output_tokens,
                )
        return self._service
