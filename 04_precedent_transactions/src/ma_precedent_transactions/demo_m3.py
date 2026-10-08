"""Reproducible offline M3 retrieval-to-verification demonstration."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date

from ma_precedent_transactions.demo import PROJECT_ROOT, build_fixture_pipeline
from ma_precedent_transactions.discovery import AcquisitionContext
from ma_precedent_transactions.extraction import (
    FixtureStructuredExtractor,
    StructuredTransactionService,
    load_extraction_benchmark,
    retrieve_extraction_context,
    run_extraction_benchmark,
)
from ma_precedent_transactions.retrieval import HybridDealRetriever


def run_demo() -> dict[str, object]:
    research = build_fixture_pipeline()
    corpus = research.build(
        AcquisitionContext(
            "m3-demo",
            "B2B fintech infrastructure",
            "Payments, ledger, banking API, and compliance infrastructure",
            ("United States", "United Kingdom"),
            date(2020, 1, 1),
            date(2025, 12, 31),
        )
    )
    retriever = HybridDealRetriever(research.index)
    service = StructuredTransactionService(
        FixtureStructuredExtractor(PROJECT_ROOT / "data" / "fixtures" / "extraction_responses.json")
    )
    outputs = {}
    for candidate in corpus.discovery.transactions:
        evidence = retrieve_extraction_context(retriever, candidate.candidate_id)
        outputs[candidate.candidate_id] = service.build(candidate, evidence)
    benchmark = run_extraction_benchmark(
        outputs,
        load_extraction_benchmark(PROJECT_ROOT / "evaluation" / "extraction_cases.json"),
    )
    return {
        "pipeline": "retrieval -> structured extraction -> normalization -> verification",
        "transactions": {
            transaction_id: _record_summary(result) for transaction_id, result in outputs.items()
        },
        "evaluation": asdict(benchmark),
        "scope_guard": "No transaction multiples, comparable selection, or valuation range.",
    }


def _record_summary(result: object) -> dict[str, object]:
    from ma_precedent_transactions.extraction import VerifiedTransactionRecord

    assert isinstance(result, VerifiedTransactionRecord)
    record = result.record
    return {
        "acquirer": record.acquirer.legal_name,
        "target": record.target.legal_name,
        "status": record.lifecycle.status.value,
        "consideration": [item.kind.value for item in record.consideration],
        "ownership_acquired": [
            str(item.acquired_percent)
            for item in record.ownership
            if item.acquired_percent is not None
        ],
        "valuations": [
            {
                "measure": item.measure.value,
                "value": None if item.amount is None else str(item.amount.value),
                "currency": None if item.amount is None else item.amount.currency,
                "unit": None if item.amount is None else item.amount.unit.value,
                "basis": item.basis.value,
            }
            for item in record.valuations
        ],
        "financials": [
            {
                "name": item.name.value,
                "value": str(item.value),
                "period": item.period.label,
                "basis": item.basis.value,
            }
            for item in record.target_financials
        ],
        "conflicts": [item.field for item in result.conflicts],
        "missing": [item.field for item in result.verification if item.status.value == "missing"],
        "warnings": list(result.warnings),
        "trace_count": len(result.traces),
    }


def main() -> None:
    print(json.dumps(run_demo(), indent=2, default=str))


if __name__ == "__main__":
    main()
