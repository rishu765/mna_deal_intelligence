"""Bounded multi-provider candidate discovery orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ma_target_screening.discovery.config import DiscoveryLimits
from ma_target_screening.discovery.models import (
    CandidateDiscoveryResult,
    DiscoveredCompanyRecord,
    DiscoveryRequest,
)
from ma_target_screening.discovery.normalization import (
    candidate_from_record,
    deduplicate_candidates,
)
from ma_target_screening.discovery.query import DeterministicQueryGenerator
from ma_target_screening.errors import DiscoveryError, DiscoveryUnavailableError
from ma_target_screening.ports import DiscoveryProvider
from ma_target_screening.thesis import AcquisitionThesis

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CandidateDiscoveryService:
    providers: tuple[DiscoveryProvider, ...]
    limits: DiscoveryLimits = DiscoveryLimits()
    query_generator: DeterministicQueryGenerator = DeterministicQueryGenerator()

    def __post_init__(self) -> None:
        if not self.providers:
            raise ValueError("at least one discovery provider is required")
        names = [provider.provider_name for provider in self.providers]
        if len(set(names)) != len(names):
            raise ValueError("discovery provider names must be unique")

    def discover(self, thesis: AcquisitionThesis) -> CandidateDiscoveryResult:
        queries = self.query_generator.generate(thesis, max_queries=self.limits.max_queries)
        request = DiscoveryRequest(
            thesis_id=thesis.thesis_id,
            queries=queries,
            max_candidates_per_query=self.limits.max_candidates_per_query,
            overall_candidate_limit=self.limits.overall_candidate_limit,
        )
        raw_candidates: list[DiscoveredCompanyRecord] = []
        warnings: list[str] = []
        successful_providers: list[str] = []
        provider_failures: list[str] = []
        logger.info(
            "candidate discovery started providers=%d queries=%d", len(self.providers), len(queries)
        )
        for provider in self.providers:
            try:
                provider_result = provider.discover(request)
            except (DiscoveryError, TypeError, ValueError):
                logger.warning("discovery provider failed provider=%s", provider.provider_name)
                provider_failures.append(provider.provider_name)
                warnings.append(f"Discovery provider failed: {provider.provider_name}")
                continue
            successful_providers.append(provider.provider_name)
            raw_candidates.extend(provider_result.candidates)
            warnings.extend(provider_result.warnings)
            logger.info(
                "discovery provider completed provider=%s candidates=%d",
                provider.provider_name,
                len(provider_result.candidates),
            )
        if provider_failures and not successful_providers:
            raise DiscoveryUnavailableError("All configured discovery providers failed")

        normalized = tuple(candidate_from_record(record) for record in raw_candidates)
        deduplicated = deduplicate_candidates(normalized)
        if len(deduplicated) > self.limits.overall_candidate_limit:
            deduplicated = deduplicated[: self.limits.overall_candidate_limit]
            warnings.append("Overall candidate limit truncated the deduplicated result.")
        if not deduplicated:
            warnings.append("Discovery completed successfully but found no candidates.")
        logger.info(
            "candidate discovery completed raw=%d deduplicated=%d",
            len(raw_candidates),
            len(deduplicated),
        )
        return CandidateDiscoveryResult(
            thesis_id=thesis.thesis_id,
            queries=queries,
            candidates=deduplicated,
            provider_names=tuple(successful_providers),
            warnings=tuple(dict.fromkeys(warnings)),
            raw_candidate_count=len(raw_candidates),
            deduplicated_candidate_count=len(deduplicated),
        )
