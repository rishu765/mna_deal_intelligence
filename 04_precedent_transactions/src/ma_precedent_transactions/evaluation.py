"""Small retrieval benchmark for the M1/2 fixture corpus."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ma_precedent_transactions.errors import MalformedFixtureError
from ma_precedent_transactions.retrieval import HybridDealRetriever, RetrievalFilters


@dataclass(frozen=True, slots=True)
class RetrievalBenchmarkCase:
    case_id: str
    query: str
    transaction_id: str
    relevant_text_markers: tuple[str, ...]
    top_k: int = 3


@dataclass(frozen=True, slots=True)
class RetrievalBenchmarkResult:
    case_count: int
    hit_at_k: float
    recall_at_k: float
    mean_reciprocal_rank: float
    case_ranks: tuple[tuple[str, int | None], ...]


def load_benchmark(path: Path) -> tuple[RetrievalBenchmarkCase, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MalformedFixtureError(f"Unable to load retrieval benchmark: {path}") from error
    if not isinstance(payload, list):
        raise MalformedFixtureError("retrieval benchmark must be a JSON list")
    cases = []
    for item in payload:
        if not isinstance(item, dict):
            raise MalformedFixtureError("retrieval benchmark cases must be objects")
        data: dict[str, Any] = item
        try:
            cases.append(
                RetrievalBenchmarkCase(
                    case_id=str(data["case_id"]),
                    query=str(data["query"]),
                    transaction_id=str(data["transaction_id"]),
                    relevant_text_markers=tuple(
                        str(marker) for marker in data["relevant_text_markers"]
                    ),
                    top_k=int(data.get("top_k", 3)),
                )
            )
        except (KeyError, TypeError, ValueError) as error:
            raise MalformedFixtureError("malformed retrieval benchmark case") from error
    return tuple(cases)


def run_benchmark(
    retriever: HybridDealRetriever,
    cases: tuple[RetrievalBenchmarkCase, ...],
) -> RetrievalBenchmarkResult:
    if not cases:
        raise ValueError("benchmark requires at least one case")
    hits = 0
    recalled = 0
    total_relevant = sum(len(case.relevant_text_markers) for case in cases)
    reciprocal_rank = 0.0
    case_ranks = []
    for case in cases:
        response = retriever.retrieve(
            case.query,
            top_k=case.top_k,
            filters=RetrievalFilters(transaction_id=case.transaction_id),
        )
        found_markers: set[str] = set()
        first_rank = None
        for result in response.results:
            for marker in case.relevant_text_markers:
                if marker.casefold() in result.text.casefold():
                    found_markers.add(marker)
                    if first_rank is None:
                        first_rank = result.rank
        if first_rank is not None:
            hits += 1
            reciprocal_rank += 1 / first_rank
        recalled += len(found_markers)
        case_ranks.append((case.case_id, first_rank))
    return RetrievalBenchmarkResult(
        case_count=len(cases),
        hit_at_k=hits / len(cases),
        recall_at_k=recalled / total_relevant if total_relevant else 0.0,
        mean_reciprocal_rank=reciprocal_rank / len(cases),
        case_ranks=tuple(case_ranks),
    )
