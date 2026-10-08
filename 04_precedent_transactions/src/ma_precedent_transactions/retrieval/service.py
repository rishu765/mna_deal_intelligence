"""Deterministic reciprocal-channel hybrid retrieval with quality warnings."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ma_precedent_transactions.errors import EmbeddingError, RetrievalError
from ma_precedent_transactions.retrieval.index import InMemoryDealIndex
from ma_precedent_transactions.retrieval.models import (
    ChannelMatch,
    DealRetrievalResult,
    RetrievalFilters,
    RetrievalResponse,
    RetrievalWarning,
    RetrievalWarningCode,
    evidence_from_chunk,
)

_MONEY_PATTERN = re.compile(
    r"(?:USD|EUR|GBP|INR|\$|€|£)\s*([0-9]+(?:\.[0-9]+)?)\s*(million|billion|crore)?",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class HybridRetrievalConfig:
    semantic_weight: float = 0.55
    lexical_weight: float = 0.45
    minimum_fused_score: float = 0.05
    low_score_threshold: float = 0.20

    def __post_init__(self) -> None:
        if abs(self.semantic_weight + self.lexical_weight - 1.0) > 1e-9:
            raise ValueError("hybrid weights must sum to 1")
        if self.semantic_weight < 0 or self.lexical_weight < 0:
            raise ValueError("hybrid weights must not be negative")


class HybridDealRetriever:
    def __init__(
        self,
        index: InMemoryDealIndex,
        config: HybridRetrievalConfig | None = None,
    ) -> None:
        self._index = index
        self._config = config or HybridRetrievalConfig()

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResponse:
        if not query.strip():
            raise RetrievalError("query must not be blank")
        if top_k <= 0:
            raise RetrievalError("top_k must be positive")
        try:
            semantic = self._index.semantic_search(query, filters=filters)
            lexical = self._index.lexical_search(query, filters=filters)
        except EmbeddingError as error:
            raise RetrievalError(f"semantic retrieval failed: {error}") from error
        semantic_scores = {item.chunk.chunk_id: max(0.0, item.score) for item in semantic}
        lexical_scores = {item.chunk.chunk_id: item.score for item in lexical}
        chunks = {item.chunk.chunk_id: item.chunk for item in (*semantic, *lexical)}
        max_lexical = max(lexical_scores.values(), default=0.0)
        ranked = []
        for chunk_id, chunk in chunks.items():
            semantic_score = semantic_scores.get(chunk_id, 0.0)
            lexical_score = lexical_scores.get(chunk_id, 0.0)
            lexical_normalized = lexical_score / max_lexical if max_lexical > 0 else 0.0
            fused = (
                self._config.semantic_weight * semantic_score
                + self._config.lexical_weight * lexical_normalized
            )
            if fused >= self._config.minimum_fused_score:
                ranked.append((fused, semantic_score, lexical_score, chunk))
        ranked.sort(key=lambda item: (-item[0], item[3].chunk_id))
        results = tuple(
            DealRetrievalResult(
                query=query,
                rank=rank,
                transaction_id=chunk.transaction_id,
                chunk_id=chunk.chunk_id,
                semantic_score=semantic_score,
                lexical_score=lexical_score,
                fused_score=fused,
                evidence=evidence_from_chunk(chunk),
                text=chunk.text,
                source_type=chunk.source.source_type,
                document_format=chunk.source.document_format,
                official_source=chunk.source.official_source,
            )
            for rank, (fused, semantic_score, lexical_score, chunk) in enumerate(
                ranked[:top_k], start=1
            )
        )
        return RetrievalResponse(query, results, self._warnings(results, semantic, lexical))

    def _warnings(
        self,
        results: tuple[DealRetrievalResult, ...],
        semantic: tuple[ChannelMatch, ...],
        lexical: tuple[ChannelMatch, ...],
    ) -> tuple[RetrievalWarning, ...]:
        warnings = []
        if not results:
            warnings.append(
                RetrievalWarning(
                    RetrievalWarningCode.NO_RESULTS, "No passage met the retrieval threshold."
                )
            )
        if not semantic or max((item.score for item in semantic), default=0.0) <= 0:
            warnings.append(
                RetrievalWarning(
                    RetrievalWarningCode.NO_SEMANTIC_RESULTS,
                    "Semantic retrieval produced no positive-similarity passage.",
                )
            )
        if not lexical or max((item.score for item in lexical), default=0.0) <= 0:
            warnings.append(
                RetrievalWarning(
                    RetrievalWarningCode.NO_LEXICAL_RESULTS,
                    "Lexical retrieval found no matching terms.",
                )
            )
        if results and results[0].fused_score < self._config.low_score_threshold:
            warnings.append(
                RetrievalWarning(
                    RetrievalWarningCode.LOW_SCORE_RESULTS,
                    "Only low-scoring passages were retrieved; analyst review is warranted.",
                )
            )
        if results and not any(result.official_source for result in results):
            warnings.append(
                RetrievalWarning(
                    RetrievalWarningCode.UNOFFICIAL_SOURCES_ONLY,
                    "All retrieved passages came from unofficial sources.",
                )
            )
        if _has_conflicting_deal_values(results):
            warnings.append(
                RetrievalWarning(
                    RetrievalWarningCode.CONFLICTING_PASSAGES,
                    "Retrieved passages contain different monetary amounts for the same "
                    "transaction.",
                )
            )
        return tuple(warnings)


def _has_conflicting_deal_values(results: tuple[DealRetrievalResult, ...]) -> bool:
    values_by_transaction: dict[str, set[tuple[str, str]]] = {}
    documents_by_transaction: dict[str, set[str]] = {}
    for result in results:
        relevant_sentences = (
            sentence
            for sentence in re.split(r"(?<=[.!?])\s+", result.text)
            if re.search(r"headline|transaction value|valued at", sentence, re.IGNORECASE)
        )
        matches: set[tuple[str, str]] = set()
        for sentence in relevant_sentences:
            matches.update(
                (value, (unit or "").casefold()) for value, unit in _MONEY_PATTERN.findall(sentence)
            )
        if not matches:
            continue
        values_by_transaction.setdefault(result.transaction_id, set()).update(matches)
        document_id = result.evidence.document_id or ""
        documents_by_transaction.setdefault(result.transaction_id, set()).add(document_id)
    return any(
        len(values) > 1 and len(documents_by_transaction.get(transaction_id, set())) > 1
        for transaction_id, values in values_by_transaction.items()
    )
