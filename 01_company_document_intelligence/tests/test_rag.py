"""Tests for bounded context construction and grounded RAG orchestration."""

from __future__ import annotations

import json
from pathlib import Path

import pymupdf
import pytest

from ma_company_intelligence.domain import (
    ChunkPageReference,
    DocumentChunk,
    DocumentMetadata,
    DocumentSource,
    RetrievalFilters,
    RetrievalResult,
)
from ma_company_intelligence.generation import (
    GenerationOutput,
    GenerationProviderError,
    GenerationRequest,
)
from ma_company_intelligence.rag import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    ContextBuilder,
    GroundedRAGService,
    InvalidQuestionError,
)
from ma_company_intelligence.rag_cli import main as rag_cli_main


def _result(
    tmp_path: Path,
    *,
    rank: int,
    text: str,
    score: float = 0.9,
    first_page: int | None = None,
) -> RetrievalResult:
    page = rank if first_page is None else first_page
    source_path = (tmp_path / "annual-report.pdf").resolve()
    source_path.write_bytes(b"synthetic")
    chunk = DocumentChunk(
        chunk_id=f"sha256:{rank:064x}",
        document_id="sha256:" + "a" * 64,
        chunk_index=rank - 1,
        text=text,
        source=DocumentSource(
            filename="annual-report.pdf",
            path=source_path,
            media_type="application/pdf",
            size_bytes=source_path.stat().st_size,
            sha256="a" * 64,
        ),
        page_references=(
            ChunkPageReference(pdf_page_index=page - 1, page_number=page),
            ChunkPageReference(pdf_page_index=page, page_number=page + 1),
        ),
        metadata=DocumentMetadata(
            company="Example plc",
            document_title="Annual Report FY2025",
            document_type="annual_report",
            fiscal_year=2025,
            reporting_period="FY2025",
        ),
        section="Revenue",
    )
    return RetrievalResult(rank=rank, score=score, chunk=chunk)


class _FakeRetriever:
    def __init__(self, results: tuple[RetrievalResult, ...]) -> None:
        self.results = results
        self.call: tuple[str, int, RetrievalFilters | None] | None = None

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> tuple[RetrievalResult, ...]:
        self.call = (query, top_k, filters)
        return self.results[:top_k]


class _FakeGenerator:
    provider_name = "test"
    model_name = "grounded-test-model"

    def __init__(
        self,
        output: GenerationOutput | None = None,
        *,
        fail: bool = False,
    ) -> None:
        self.output = output or GenerationOutput(
            answer="FY25 revenue was $125.0 million, with a 17.5% margin.",
            insufficient_evidence=False,
        )
        self.fail = fail
        self.requests: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> GenerationOutput:
        self.requests.append(request)
        if self.fail:
            raise GenerationProviderError("synthetic generation failure")
        return self.output


def test_context_preserves_order_provenance_metadata_and_financial_text(tmp_path: Path) -> None:
    results = (
        _result(
            tmp_path,
            rank=1,
            first_page=84,
            text="FY25 revenue was $125.0 million; margin was 17.5% (FY24: 16.2%).",
        ),
        _result(tmp_path, rank=2, first_page=90, text="EBITDA was not disclosed here."),
    )

    context = ContextBuilder(max_characters=5_000, max_chunks=5).build(results)

    assert context.included_results == results
    assert context.omitted_result_count == 0
    assert context.text.index(results[0].chunk_id) < context.text.index(results[1].chunk_id)
    assert "canonical_page_numbers: 84, 85" in context.text
    assert "physical_pdf_page_indexes: 83, 84" in context.text
    assert "printed_page_labels: unknown, unknown" in context.text
    assert "company: Example plc" in context.text
    assert "FY25 revenue was $125.0 million; margin was 17.5% (FY24: 16.2%)." in context.text


def test_context_budget_uses_only_complete_ranked_prefix(tmp_path: Path) -> None:
    first = _result(tmp_path, rank=1, text="First evidence.")
    second = _result(tmp_path, rank=2, text="Second evidence is too much.")
    first_context = ContextBuilder(max_characters=5_000, max_chunks=5).build((first,))
    budget = first_context.character_count

    context = ContextBuilder(max_characters=budget, max_chunks=5).build((first, second))

    assert context.included_results == (first,)
    assert context.omitted_result_count == 1
    assert "[/EVIDENCE 1]" in context.text
    assert "Second evidence" not in context.text


def test_context_does_not_cut_oversized_first_chunk(tmp_path: Path) -> None:
    result = _result(tmp_path, rank=1, text="Revenue evidence " * 100)

    context = ContextBuilder(max_characters=100, max_chunks=5).build((result,))

    assert context.text == ""
    assert context.included_results == ()
    assert context.omitted_result_count == 1


def test_grounded_service_passes_question_and_evidence_to_generator(tmp_path: Path) -> None:
    results = (_result(tmp_path, rank=1, text="FY25 revenue was $125.0 million."),)
    retriever = _FakeRetriever(results)
    generator = _FakeGenerator()
    filters = RetrievalFilters(company="Example plc", fiscal_year=2025)

    answer = GroundedRAGService(
        retriever,
        ContextBuilder(max_characters=5_000),
        generator,
        max_output_tokens=400,
    ).answer("What was FY25 revenue?", top_k=3, filters=filters)

    assert retriever.call == ("What was FY25 revenue?", 3, filters)
    assert len(generator.requests) == 1
    request = generator.requests[0]
    assert "What was FY25 revenue?" in request.input_text
    assert results[0].chunk_id in request.input_text
    assert "FY25 revenue was $125.0 million." in request.input_text
    assert "Use no external knowledge" in request.instructions
    assert request.max_output_tokens == 400
    assert answer.answer == "FY25 revenue was $125.0 million, with a 17.5% margin."
    assert answer.supporting_results == results
    assert answer.supporting_chunk_ids == (results[0].chunk_id,)
    assert answer.insufficient_evidence is False


def test_empty_retrieval_returns_safe_answer_without_generation() -> None:
    retriever = _FakeRetriever(())
    generator = _FakeGenerator()

    answer = GroundedRAGService(retriever, ContextBuilder(), generator).answer("What was EBITDA?")

    assert answer.answer == INSUFFICIENT_EVIDENCE_MESSAGE
    assert answer.insufficient_evidence is True
    assert answer.supporting_results == ()
    assert generator.requests == []
    assert "generation was skipped" in answer.warnings[0]


def test_model_insufficiency_is_normalized_to_safe_message(tmp_path: Path) -> None:
    retriever = _FakeRetriever(
        (_result(tmp_path, rank=1, text="The document discusses employee headcount."),)
    )
    generator = _FakeGenerator(
        GenerationOutput(answer="There is not enough support.", insufficient_evidence=True)
    )

    answer = GroundedRAGService(retriever, ContextBuilder(), generator).answer("What was EBITDA?")

    assert answer.answer == INSUFFICIENT_EVIDENCE_MESSAGE
    assert answer.insufficient_evidence is True
    assert len(answer.supporting_results) == 1
    assert "classified" in answer.warnings[-1]


def test_context_budget_failure_skips_generation(tmp_path: Path) -> None:
    retriever = _FakeRetriever((_result(tmp_path, rank=1, text="A" * 1_000),))
    generator = _FakeGenerator()

    answer = GroundedRAGService(
        retriever,
        ContextBuilder(max_characters=50),
        generator,
    ).answer("What was revenue?")

    assert answer.insufficient_evidence is True
    assert generator.requests == []
    assert "context budget" in answer.warnings[0]


@pytest.mark.parametrize("question", ["", "   ", "\n\t"])
def test_blank_question_is_rejected(question: str) -> None:
    with pytest.raises(InvalidQuestionError, match="non-whitespace"):
        GroundedRAGService(_FakeRetriever(()), ContextBuilder(), _FakeGenerator()).answer(question)


def test_generation_provider_failure_propagates_with_evidence_context(tmp_path: Path) -> None:
    retriever = _FakeRetriever((_result(tmp_path, rank=1, text="Revenue was $125 million."),))
    generator = _FakeGenerator(fail=True)

    with pytest.raises(GenerationProviderError, match="synthetic"):
        GroundedRAGService(retriever, ContextBuilder(), generator).answer("What was revenue?")

    assert len(generator.requests) == 1


def _write_pdf(path: Path, text: str) -> None:
    document = pymupdf.open()  # type: ignore[no-untyped-call]
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)  # type: ignore[no-untyped-call]
    document.close()  # type: ignore[no-untyped-call]


class _PipelineEmbedder:
    provider_name = "test"
    model_name = "retrieval-test-model"
    dimension = 3

    def embed_text(self, _text: str) -> tuple[float, ...]:
        return (1.0, 0.0, 0.0)

    def embed_batch(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple((1.0, 0.0, 0.0) for _text in texts)


def test_rag_cli_runs_complete_pipeline_with_bounded_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pdf_path = tmp_path / "report.pdf"
    index_path = tmp_path / "rag.sqlite3"
    _write_pdf(pdf_path, "FY25 revenue increased to $125 million due to subscriptions.")
    generator = _FakeGenerator(
        GenerationOutput(
            answer="FY25 revenue increased to $125 million due to subscriptions.",
            insufficient_evidence=False,
        )
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "ma_company_intelligence.rag_cli.OpenAIEmbedder",
        lambda **_arguments: _PipelineEmbedder(),
    )
    monkeypatch.setattr(
        "ma_company_intelligence.rag_cli.OpenAIGenerator",
        lambda **_arguments: generator,
    )

    exit_code = rag_cli_main(
        [
            str(pdf_path),
            "What drove FY25 revenue?",
            "--index-path",
            str(index_path),
            "--top-k",
            "1",
            "--preview-chars",
            "24",
            "--company",
            "Example plc",
        ]
    )
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["answer"] == ("FY25 revenue increased to $125 million due to subscriptions.")
    assert summary["insufficient_evidence"] is False
    assert summary["generator"] == {
        "provider": "test",
        "model": "grounded-test-model",
    }
    assert summary["chunks_indexed"] == 1
    assert summary["evidence_used"] == 1
    assert summary["evidence"][0]["page_numbers"] == [1]
    assert summary["evidence"][0]["company"] == "Example plc"
    assert len(summary["evidence"][0]["text_preview"]) == 24
    assert "embedding" not in summary["evidence"][0]
