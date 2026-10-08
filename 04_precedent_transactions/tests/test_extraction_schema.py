from __future__ import annotations

from pathlib import Path

import pytest

from conftest import FIXTURE_ROOT, ResearchHarness
from ma_precedent_transactions.errors import (
    ExtractionProviderError,
    ExtractionValidationError,
)
from ma_precedent_transactions.extraction import (
    ExtractionRequest,
    FixtureStructuredExtractor,
    LangChainStructuredExtractor,
    load_extraction_fixture,
    parse_extraction_payload,
)


def test_fixture_responses_are_validated_structured_outputs() -> None:
    batches = load_extraction_fixture(FIXTURE_ROOT / "extraction_responses.json")
    assert len(batches) == 7
    assert batches["txn-stock"].consideration[0].quantity == "0.45"
    assert batches["txn-cash"].financials[1].adjustment_label == "Adjusted EBITDA"


def test_schema_rejects_observation_without_evidence() -> None:
    with pytest.raises(ExtractionValidationError, match="evidence"):
        parse_extraction_payload(
            {
                "transaction_id": "txn-x",
                "parties": [
                    {
                        "observation_id": "party-x",
                        "evidence_ids": [],
                        "source_wording": "A acquired B",
                        "role": "acquirer",
                        "legal_name": "A",
                    }
                ],
            }
        )


def test_fixture_extractor_rejects_evidence_outside_bounded_context(
    research_harness: ResearchHarness,
) -> None:
    extractor = FixtureStructuredExtractor(FIXTURE_ROOT / "extraction_responses.json")
    with pytest.raises(ExtractionValidationError, match="bounded context"):
        extractor.extract(ExtractionRequest("txn-cash", ()))


class _Runnable:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def invoke(self, input: object) -> object:
        assert input
        return self.payload


class _FailingRunnable:
    def invoke(self, input: object) -> object:
        raise TimeoutError("fixture timeout")


class _ChatModel:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.schema: object | None = None

    def with_structured_output(self, schema: object) -> _Runnable:
        self.schema = schema
        return _Runnable(self.payload)


class _FailingChatModel:
    def with_structured_output(self, schema: object) -> _FailingRunnable:
        return _FailingRunnable()


def test_langchain_adapter_uses_structured_output_and_validates_transaction() -> None:
    model = _ChatModel({"transaction_id": "txn-empty"})
    extractor = LangChainStructuredExtractor(model)
    batch = extractor.extract(ExtractionRequest("txn-empty", ()))
    assert batch.transaction_id == "txn-empty"
    assert model.schema is not None


def test_langchain_adapter_rejects_changed_transaction_id() -> None:
    extractor = LangChainStructuredExtractor(_ChatModel({"transaction_id": "wrong"}))
    with pytest.raises(ExtractionValidationError, match="transaction ID"):
        extractor.extract(ExtractionRequest("expected", ()))


def test_langchain_provider_failure_is_wrapped() -> None:
    extractor = LangChainStructuredExtractor(_FailingChatModel())
    with pytest.raises(ExtractionProviderError, match="failed"):
        extractor.extract(ExtractionRequest("txn-x", ()))


def test_malformed_fixture_response_fails_cleanly(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("not-json", encoding="utf-8")
    with pytest.raises(ExtractionValidationError, match="unable to load"):
        load_extraction_fixture(path)
