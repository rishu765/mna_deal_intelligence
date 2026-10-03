"""Route, wiring, safety, and application-service tests for the FastAPI interface."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from ma_company_intelligence.api import create_app
from ma_company_intelligence.application import (
    APISettings,
    DocumentAccessError,
    DocumentSizeLimitError,
    IndexDocumentCommand,
    IndexDocumentResult,
    IndexUnavailableError,
    NoIndexableTextError,
    ProjectApplicationService,
)
from ma_company_intelligence.domain import (
    RESEARCH_SECTION_ORDER,
    CompanyResearchProfile,
    RAGAnswer,
    ResearchSection,
    RetrievalFilters,
)
from ma_company_intelligence.embeddings import (
    EmbeddingConfigurationError,
    EmbeddingProviderError,
    EmbeddingSettings,
)
from ma_company_intelligence.generation import (
    GenerationConfigurationError,
    GenerationOutput,
    GenerationProviderError,
    GenerationRequest,
    GenerationSettings,
    ResearchGenerationOutput,
)
from ma_company_intelligence.ingestion import InvalidPdfError


class _FakeApplicationService:
    def __init__(self) -> None:
        self.index_command: IndexDocumentCommand | None = None
        self.answer_call: tuple[str, int, RetrievalFilters | None] | None = None
        self.research_call: tuple[str | None, RetrievalFilters | None] | None = None
        self.failure: Exception | None = None

    def index_document(self, command: IndexDocumentCommand) -> IndexDocumentResult:
        self._fail_if_requested()
        self.index_command = command
        return IndexDocumentResult(
            document_id="sha256:" + "a" * 64,
            source_filename="annual-report.pdf",
            page_count=2,
            chunk_count=3,
            records_upserted=3,
            total_index_records=3,
            warnings=("Page 2 had little text.",),
        )

    def answer(
        self,
        question: str,
        *,
        top_k: int,
        filters: RetrievalFilters | None = None,
    ) -> RAGAnswer:
        self._fail_if_requested()
        self.answer_call = (question, top_k, filters)
        return RAGAnswer(
            question=question,
            answer="I could not find sufficient evidence in the provided documents.",
            supporting_results=(),
            insufficient_evidence=True,
            generator_provider="fake",
            generator_model="fake-model",
            warnings=("No evidence was retrieved.",),
        )

    def research(
        self,
        *,
        company_name: str | None,
        filters: RetrievalFilters | None = None,
    ) -> CompanyResearchProfile:
        self._fail_if_requested()
        self.research_call = (company_name, filters)
        return _empty_profile(company_name)

    def _fail_if_requested(self) -> None:
        if self.failure is not None:
            raise self.failure


class _FakeEmbedder:
    provider_name = "fake"
    model_name = "fake-embedding"
    dimension = 2

    def embed_text(self, text: str) -> tuple[float, ...]:
        if not text.strip():
            raise ValueError("blank text")
        return (1.0, 0.0)

    def embed_batch(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple(self.embed_text(text) for text in texts)


class _FakeCombinedGenerator:
    provider_name = "fake"
    model_name = "fake-generation"

    def generate(self, request: GenerationRequest) -> GenerationOutput:
        return GenerationOutput(
            answer="FY2025 revenue was USD 125 million.",
            insufficient_evidence=False,
            cited_evidence_ids=("E1",),
        )

    def generate_research(self, request: GenerationRequest) -> ResearchGenerationOutput:
        raise AssertionError("not used in these service integration tests")


def _empty_profile(company_name: str | None) -> CompanyResearchProfile:
    return CompanyResearchProfile(
        company_name=company_name,
        sections=tuple(
            ResearchSection(
                key=key,
                summary=None,
                facts=(),
                observations=(),
                financial_metrics=(),
                citations=(),
                insufficient_evidence=True,
            )
            for key in RESEARCH_SECTION_ORDER
        ),
        citations=(),
        source_document_ids=(),
        generator_provider="fake",
        generator_model="fake-model",
        warnings=("No evidence was retrieved.",),
    )


def _write_pdf(path: Path, text: str = "FY2025 revenue was USD 125 million.") -> None:
    document = pymupdf.open()  # type: ignore[no-untyped-call]
    page = document.new_page()
    if text:
        page.insert_text((72, 72), text)
    document.save(path)  # type: ignore[no-untyped-call]
    document.close()  # type: ignore[no-untyped-call]


@pytest.fixture
def fake_service() -> _FakeApplicationService:
    return _FakeApplicationService()


@pytest.fixture
def client(fake_service: _FakeApplicationService, tmp_path: Path) -> TestClient:
    settings = APISettings(document_root=tmp_path)
    return TestClient(create_app(service=fake_service, settings=settings))


def test_health_does_not_require_provider_configuration(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ma-company-intelligence",
        "version": "1.0.0",
    }
    assert response.headers["x-request-id"]


def test_openapi_documents_the_public_endpoints(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    assert {"/health", "/v1/documents/index", "/v1/answers", "/v1/research"} <= set(schema["paths"])
    assert "ErrorResponse" in schema["components"]["schemas"]


def test_index_route_validates_and_delegates(
    client: TestClient,
    fake_service: _FakeApplicationService,
) -> None:
    response = client.post(
        "/v1/documents/index",
        json={
            "source_reference": "annual-report.pdf",
            "metadata": {"company": "Example plc", "fiscal_year": 2025},
            "chunking": {
                "max_characters": 1000,
                "overlap_characters": 100,
                "min_chunk_characters": 200,
            },
        },
    )

    assert response.status_code == 201
    assert response.json()["chunk_count"] == 3
    assert "source_path" not in response.json()
    assert fake_service.index_command is not None
    assert fake_service.index_command.metadata.company == "Example plc"
    assert fake_service.index_command.chunking.max_characters == 1000


def test_question_route_preserves_filters_and_insufficient_state(
    client: TestClient,
    fake_service: _FakeApplicationService,
) -> None:
    response = client.post(
        "/v1/answers",
        json={
            "question": "What was revenue?",
            "top_k": 3,
            "filters": {"company": "Example plc", "fiscal_year": 2025},
        },
    )

    assert response.status_code == 200
    assert response.json()["insufficient_evidence"] is True
    assert response.json()["citations"] == []
    assert fake_service.answer_call == (
        "What was revenue?",
        3,
        RetrievalFilters(company="Example plc", fiscal_year=2025),
    )


def test_research_route_returns_all_typed_sections(
    client: TestClient,
    fake_service: _FakeApplicationService,
) -> None:
    response = client.post(
        "/v1/research",
        json={"company_name": "Example plc", "filters": {"document_type": "annual_report"}},
    )

    assert response.status_code == 200
    assert len(response.json()["sections"]) == len(RESEARCH_SECTION_ORDER)
    assert all(section["insufficient_evidence"] for section in response.json()["sections"])
    assert fake_service.research_call == (
        "Example plc",
        RetrievalFilters(document_type="annual_report"),
    )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"question": "   "},
        {"question": "Valid", "top_k": 0},
        {"question": "Valid", "unknown": "rejected"},
    ],
)
def test_invalid_question_payload_uses_consistent_error_model(
    client: TestClient,
    payload: dict[str, object],
) -> None:
    response = client.post("/v1/answers", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
    assert "input" not in response.json()["error"]


def test_configured_question_and_top_k_limits_are_enforced(
    fake_service: _FakeApplicationService,
) -> None:
    test_client = TestClient(
        create_app(
            service=fake_service,
            settings=APISettings(max_question_characters=5, max_top_k=2),
        )
    )

    long_question = test_client.post("/v1/answers", json={"question": "123456"})
    large_top_k = test_client.post("/v1/answers", json={"question": "Valid", "top_k": 3})

    assert long_question.status_code == 422
    assert large_top_k.status_code == 422


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (
            InvalidPdfError(Path("C:/private/report.pdf"), "secret parser detail"),
            422,
            "document_parsing_failed",
        ),
        (EmbeddingProviderError("provider secret response"), 502, "provider_failure"),
        (GenerationProviderError("provider secret response"), 502, "provider_failure"),
        (IndexUnavailableError("private index path"), 409, "index_unavailable"),
    ],
)
def test_expected_failures_are_sanitized(
    client: TestClient,
    fake_service: _FakeApplicationService,
    error: Exception,
    status_code: int,
    code: str,
) -> None:
    fake_service.failure = error

    response = client.post("/v1/answers", json={"question": "What was revenue?"})

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == code
    assert "private" not in response.text
    assert "secret" not in response.text


def test_request_id_is_echoed_only_when_safe(client: TestClient) -> None:
    supplied = client.get("/health", headers={"X-Request-ID": "research-123"})
    rejected = client.get("/health", headers={"X-Request-ID": "unsafe id with spaces"})

    assert supplied.headers["x-request-id"] == "research-123"
    assert rejected.headers["x-request-id"] != "unsafe id with spaces"


def test_declared_oversized_request_is_rejected_before_route(
    fake_service: _FakeApplicationService,
) -> None:
    test_client = TestClient(
        create_app(
            service=fake_service,
            settings=APISettings(max_request_body_bytes=10),
        )
    )

    response = test_client.post("/v1/answers", json={"question": "What was revenue?"})

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"
    assert fake_service.answer_call is None


def test_unexpected_failures_are_sanitized(fake_service: _FakeApplicationService) -> None:
    fake_service.failure = RuntimeError("secret internal path C:/private/index")
    test_client = TestClient(
        create_app(service=fake_service, settings=APISettings()),
        raise_server_exceptions=False,
    )

    response = test_client.post("/v1/answers", json={"question": "What was revenue?"})

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "private" not in response.text
    assert "secret" not in response.text


def test_provider_configuration_is_lazy_and_missing_key_is_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    test_client = TestClient(create_app(settings=APISettings(document_root=tmp_path)))

    assert test_client.get("/health").status_code == 200
    response = test_client.post("/v1/answers", json={"question": "What was revenue?"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "configuration_error"


def test_application_service_restricts_paths_and_sizes(tmp_path: Path) -> None:
    document_root = tmp_path / "documents"
    document_root.mkdir()
    large_pdf = document_root / "large.pdf"
    large_pdf.write_bytes(b"12345")
    service = ProjectApplicationService(
        embedder=_FakeEmbedder(),
        generator=_FakeCombinedGenerator(),
        index_path=tmp_path / "index.sqlite3",
        embedding_batch_size=4,
        api_settings=APISettings(document_root=document_root, max_document_bytes=4),
    )

    with pytest.raises(DocumentAccessError):
        service.index_document(IndexDocumentCommand(source_reference="../outside.pdf"))
    with pytest.raises(DocumentSizeLimitError):
        service.index_document(IndexDocumentCommand(source_reference="large.pdf"))


def test_application_service_indexes_pdf_and_answers_with_fakes(tmp_path: Path) -> None:
    document_root = tmp_path / "documents"
    document_root.mkdir()
    _write_pdf(document_root / "annual-report.pdf")
    service = ProjectApplicationService(
        embedder=_FakeEmbedder(),
        generator=_FakeCombinedGenerator(),
        index_path=tmp_path / "index.sqlite3",
        embedding_batch_size=4,
        api_settings=APISettings(document_root=document_root),
    )

    test_client = TestClient(
        create_app(
            service=service,
            settings=APISettings(document_root=document_root),
        )
    )
    index_response = test_client.post(
        "/v1/documents/index",
        json={"source_reference": "annual-report.pdf"},
    )
    document_id = index_response.json()["document_id"]
    answer_response = test_client.post(
        "/v1/answers",
        json={
            "question": "What was FY2025 revenue?",
            "top_k": 1,
            "filters": {"document_id": document_id},
        },
    )

    assert index_response.status_code == 201
    assert index_response.json()["page_count"] == 1
    assert index_response.json()["chunk_count"] == 1
    assert answer_response.status_code == 200
    assert answer_response.json()["answer"] == "FY2025 revenue was USD 125 million."
    assert answer_response.json()["citations"][0]["canonical_page_numbers"] == [1]
    assert answer_response.json()["evidence"][0]["document_id"] == document_id

    indexed_again = test_client.post(
        "/v1/documents/index",
        json={"source_reference": "annual-report.pdf"},
    )
    assert indexed_again.json()["records_upserted"] == 1
    assert indexed_again.json()["total_index_records"] == 1


def test_application_service_rejects_documents_without_indexable_text(tmp_path: Path) -> None:
    document_root = tmp_path / "documents"
    document_root.mkdir()
    _write_pdf(document_root / "blank.pdf", text="")
    service = ProjectApplicationService(
        embedder=_FakeEmbedder(),
        generator=_FakeCombinedGenerator(),
        index_path=tmp_path / "index.sqlite3",
        embedding_batch_size=4,
        api_settings=APISettings(document_root=document_root),
    )

    with pytest.raises(NoIndexableTextError):
        service.index_document(IndexDocumentCommand(source_reference="blank.pdf"))


def test_application_service_reports_missing_index(tmp_path: Path) -> None:
    service = ProjectApplicationService(
        embedder=_FakeEmbedder(),
        generator=_FakeCombinedGenerator(),
        index_path=tmp_path / "missing.sqlite3",
        embedding_batch_size=4,
        api_settings=APISettings(document_root=tmp_path),
    )

    with pytest.raises(IndexUnavailableError):
        service.answer("What was revenue?", top_k=3)


@pytest.mark.parametrize(
    "environment",
    [
        {"MADI_API_MAX_TOP_K": "0"},
        {"MADI_API_MAX_QUESTION_CHARACTERS": "10001"},
        {"MADI_API_MAX_REQUEST_BODY_BYTES": "invalid"},
        {"MADI_LOG_LEVEL": "TRACE"},
    ],
)
def test_api_settings_reject_unsafe_environment(environment: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        APISettings.from_environment(environment)


def test_provider_timeout_and_retries_are_bounded_configuration() -> None:
    environment = {
        "OPENAI_API_KEY": "test-key",
        "MADI_PROVIDER_TIMEOUT_SECONDS": "12.5",
        "MADI_PROVIDER_MAX_RETRIES": "1",
    }

    embedding = EmbeddingSettings.from_environment(environment)
    generation = GenerationSettings.from_environment(environment)

    assert embedding.timeout_seconds == 12.5
    assert generation.timeout_seconds == 12.5
    assert embedding.max_retries == generation.max_retries == 1

    with pytest.raises(EmbeddingConfigurationError, match="between 0 and 5"):
        EmbeddingSettings.from_environment(
            {"OPENAI_API_KEY": "test", "MADI_PROVIDER_MAX_RETRIES": "6"}
        )
    with pytest.raises(GenerationConfigurationError, match="positive"):
        GenerationSettings.from_environment(
            {"OPENAI_API_KEY": "test", "MADI_PROVIDER_TIMEOUT_SECONDS": "0"}
        )
