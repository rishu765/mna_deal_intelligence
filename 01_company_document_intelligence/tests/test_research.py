"""Tests for targeted retrieval and cited structured company research."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pymupdf
import pytest

from ma_company_intelligence.citations import CitationReferenceError
from ma_company_intelligence.domain import (
    RESEARCH_SECTION_ORDER,
    ChunkPageReference,
    DocumentChunk,
    DocumentMetadata,
    DocumentSource,
    ResearchSectionKey,
    RetrievalFilters,
    RetrievalResult,
)
from ma_company_intelligence.generation import (
    GeneratedFinancialMetric,
    GeneratedResearchItem,
    GeneratedResearchSection,
    GenerationRequest,
    GenerationResponseError,
    OpenAIGenerator,
    ResearchGenerationOutput,
)
from ma_company_intelligence.research import (
    RESEARCH_CATEGORIES,
    CompanyResearchService,
    ResearchEvidenceCollector,
)
from ma_company_intelligence.research_cli import main as research_cli_main


def _result(tmp_path: Path, *, rank: int, text: str, page: int) -> RetrievalResult:
    source_path = (tmp_path / "annual-report.pdf").resolve()
    source_path.write_bytes(b"synthetic")
    return RetrievalResult(
        rank=rank,
        score=0.95 - rank / 100,
        chunk=DocumentChunk(
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
            page_references=(ChunkPageReference(pdf_page_index=page - 1, page_number=page),),
            metadata=DocumentMetadata(
                company="Example plc",
                document_title="Annual Report FY2025",
                document_type="annual_report",
                fiscal_year=2025,
                reporting_period="FY2025",
            ),
        ),
    )


class _FakeRetriever:
    def __init__(self, results: tuple[RetrievalResult, ...]) -> None:
        self.results = results
        self.calls: list[tuple[str, int, RetrievalFilters | None]] = []

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> tuple[RetrievalResult, ...]:
        self.calls.append((query, top_k, filters))
        return self.results[:top_k]


def _generated_profile(*, invalid_reference: bool = False) -> ResearchGenerationOutput:
    sections: list[GeneratedResearchSection] = []
    for key in RESEARCH_SECTION_ORDER:
        if key is ResearchSectionKey.BUSINESS_OVERVIEW:
            evidence_id = "E99" if invalid_reference else "E1"
            sections.append(
                GeneratedResearchSection(
                    key=key,
                    summary="Example plc provides subscription software.",
                    summary_evidence_ids=(evidence_id,),
                    facts=(
                        GeneratedResearchItem(
                            text="The company provides subscription software.",
                            evidence_ids=(evidence_id,),
                        ),
                    ),
                    observations=(),
                    financial_metrics=(),
                    insufficient_evidence=False,
                )
            )
        elif key is ResearchSectionKey.FINANCIAL_HIGHLIGHTS:
            sections.append(
                GeneratedResearchSection(
                    key=key,
                    summary="FY2025 revenue was $125 million.",
                    summary_evidence_ids=("E2",),
                    facts=(),
                    observations=(),
                    financial_metrics=(
                        GeneratedFinancialMetric(
                            metric_name="Revenue",
                            value="$125 million",
                            fiscal_period="FY2025",
                            unit="million",
                            currency="USD",
                            basis="reported revenue",
                            evidence_ids=("E2",),
                        ),
                    ),
                    insufficient_evidence=False,
                )
            )
        elif key is ResearchSectionKey.MA_RELEVANT_OBSERVATIONS:
            sections.append(
                GeneratedResearchSection(
                    key=key,
                    summary=None,
                    summary_evidence_ids=(),
                    facts=(),
                    observations=(
                        GeneratedResearchItem(
                            text=(
                                "The subscription model may matter when assessing revenue "
                                "recurrence."
                            ),
                            evidence_ids=("E1",),
                        ),
                    ),
                    financial_metrics=(),
                    insufficient_evidence=False,
                )
            )
        else:
            sections.append(
                GeneratedResearchSection(
                    key=key,
                    summary=None,
                    summary_evidence_ids=(),
                    facts=(),
                    observations=(),
                    financial_metrics=(),
                    insufficient_evidence=True,
                )
            )
    return ResearchGenerationOutput(company_name="Example plc", sections=tuple(sections))


def _single_evidence_profile() -> ResearchGenerationOutput:
    sections = tuple(
        GeneratedResearchSection(
            key=key,
            summary=(
                "Example plc provides subscription software."
                if key is ResearchSectionKey.BUSINESS_OVERVIEW
                else None
            ),
            summary_evidence_ids=("E1",) if key is ResearchSectionKey.BUSINESS_OVERVIEW else (),
            facts=(
                (
                    GeneratedResearchItem(
                        text="The company provides subscription software.",
                        evidence_ids=("E1",),
                    ),
                )
                if key is ResearchSectionKey.BUSINESS_OVERVIEW
                else ()
            ),
            observations=(),
            financial_metrics=(),
            insufficient_evidence=key is not ResearchSectionKey.BUSINESS_OVERVIEW,
        )
        for key in RESEARCH_SECTION_ORDER
    )
    return ResearchGenerationOutput(company_name="Example plc", sections=sections)


class _FakeResearchGenerator:
    provider_name = "test"
    model_name = "research-test-model"

    def __init__(self, output: ResearchGenerationOutput | None = None) -> None:
        self.output = output or _generated_profile()
        self.requests: list[GenerationRequest] = []

    def generate_research(self, request: GenerationRequest) -> ResearchGenerationOutput:
        self.requests.append(request)
        return self.output


def test_targeted_collector_queries_every_category_and_deduplicates_chunks(tmp_path: Path) -> None:
    results = (
        _result(tmp_path, rank=1, text="Subscription software business.", page=4),
        _result(tmp_path, rank=2, text="FY2025 revenue was $125 million.", page=84),
    )
    retriever = _FakeRetriever(results)
    filters = RetrievalFilters(company="Example plc")

    context = ResearchEvidenceCollector(retriever, top_k_per_section=2).collect(
        company_name="Example plc",
        filters=filters,
    )

    assert len(retriever.calls) == len(RESEARCH_CATEGORIES)
    assert all(call[1:] == (2, filters) for call in retriever.calls)
    assert tuple(context.evidence_by_id) == ("E1", "E2")
    assert all(ids == ("E1", "E2") for ids in context.evidence_ids_by_section.values())
    assert context.text.count("[EVIDENCE E1]") == 1
    assert context.text.count("[EVIDENCE E2]") == 1


def test_structured_profile_preserves_citations_financial_qualifiers_and_fact_analysis_split(
    tmp_path: Path,
) -> None:
    results = (
        _result(tmp_path, rank=1, text="Subscription software business.", page=4),
        _result(tmp_path, rank=2, text="FY2025 revenue was $125 million.", page=84),
    )
    retriever = _FakeRetriever(results)
    generator = _FakeResearchGenerator()

    profile = CompanyResearchService(
        ResearchEvidenceCollector(retriever, top_k_per_section=2),
        generator,
    ).research(company_name="Example plc")

    assert profile.company_name == "Example plc"
    assert len(profile.citations) == 2
    overview = profile.section(ResearchSectionKey.BUSINESS_OVERVIEW)
    assert overview.facts[0].statement.startswith("The company")
    assert overview.observations == ()
    assert overview.citations[0].canonical_page_numbers == (4,)
    financials = profile.section(ResearchSectionKey.FINANCIAL_HIGHLIGHTS)
    metric = financials.financial_metrics[0]
    assert (metric.value, metric.fiscal_period, metric.unit, metric.currency, metric.basis) == (
        "$125 million",
        "FY2025",
        "million",
        "USD",
        "reported revenue",
    )
    assert metric.citations[0].canonical_page_numbers == (84,)
    analysis = profile.section(ResearchSectionKey.MA_RELEVANT_OBSERVATIONS)
    assert analysis.facts == ()
    assert analysis.observations[0].observation.startswith("The subscription model may")
    assert profile.section(ResearchSectionKey.MAJOR_RISKS).insufficient_evidence is True
    assert len(generator.requests) == 1
    assert "FACT" not in generator.requests[0].input_text
    assert "facts" in generator.requests[0].instructions.lower()


def test_no_result_research_returns_all_sections_insufficient_without_generation() -> None:
    retriever = _FakeRetriever(())
    generator = _FakeResearchGenerator()

    profile = CompanyResearchService(
        ResearchEvidenceCollector(retriever),
        generator,
    ).research(company_name="Example plc")

    assert all(section.insufficient_evidence for section in profile.sections)
    assert profile.citations == ()
    assert profile.source_document_ids == ()
    assert generator.requests == []


def test_unknown_research_evidence_reference_is_rejected(tmp_path: Path) -> None:
    retriever = _FakeRetriever(
        (_result(tmp_path, rank=1, text="Subscription software business.", page=4),)
    )
    generator = _FakeResearchGenerator(_generated_profile(invalid_reference=True))

    with pytest.raises(CitationReferenceError, match="E99"):
        CompanyResearchService(ResearchEvidenceCollector(retriever), generator).research()


def test_malformed_openai_research_response_is_rejected() -> None:
    client = SimpleNamespace(
        responses=SimpleNamespace(
            parse=lambda **_arguments: SimpleNamespace(output_parsed=object())
        )
    )
    generator = OpenAIGenerator(api_key="test-key", client=client)

    with pytest.raises(GenerationResponseError, match="structured research profile"):
        generator.generate_research(
            GenerationRequest(
                instructions="Use evidence.",
                input_text="Evidence E1.",
                max_output_tokens=100,
            )
        )


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


def test_research_cli_runs_complete_pipeline_with_bounded_cited_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pdf_path = tmp_path / "report.pdf"
    index_path = tmp_path / "research.sqlite3"
    _write_pdf(pdf_path, "Subscription software business. FY2025 revenue was $125 million.")
    generator = _FakeResearchGenerator(_single_evidence_profile())
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "ma_company_intelligence.research_cli.OpenAIEmbedder",
        lambda **_arguments: _PipelineEmbedder(),
    )
    monkeypatch.setattr(
        "ma_company_intelligence.research_cli.OpenAIGenerator",
        lambda **_arguments: generator,
    )

    exit_code = research_cli_main(
        [
            str(pdf_path),
            "--index-path",
            str(index_path),
            "--top-k-per-section",
            "1",
            "--preview-chars",
            "24",
            "--company",
            "Example plc",
            "--document-title",
            "Annual Report FY2025",
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["company_name"] == "Example plc"
    assert len(output["sections"]) == len(RESEARCH_SECTION_ORDER)
    assert output["sections"][1]["facts"][0]["citations"] == ["[1]"]
    assert output["citations"][0]["reference"] == "[1] Annual Report FY2025 — p. 1"
    assert len(output["citations"][0]["excerpt"]) == 24
