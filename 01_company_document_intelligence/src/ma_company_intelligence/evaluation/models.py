"""Typed, provider-neutral evaluation dataset and report models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class FailureCategory(StrEnum):
    RETRIEVAL_MISS = "retrieval.relevant_evidence_not_retrieved"
    RETRIEVAL_LOW_RANK = "retrieval.correct_evidence_ranked_low"
    CONTEXT_OMISSION = "context.useful_evidence_omitted"
    GENERATION_UNSUPPORTED = "generation.unsupported_claim"
    GENERATION_INCOMPLETE = "generation.incomplete_answer"
    GENERATION_UNEXPECTED_ANSWER = "generation.answered_unanswerable_question"
    GENERATION_FALSE_REFUSAL = "generation.refusal_despite_sufficient_evidence"
    CITATION_INVALID = "citation.invalid_or_fabricated_provenance"
    CITATION_IRRELEVANT = "citation.does_not_support_claim"
    CITATION_MISSING = "citation.supporting_claim_not_cited"
    STRUCTURED_OMISSION = "structured.expected_field_omitted"
    STRUCTURED_UNSUPPORTED = "structured.unsupported_field_populated"
    STRUCTURED_QUALIFIER = "structured.financial_qualifier_mismatch"
    STRUCTURED_FACT_AS_ANALYSIS = "structured.fact_replaced_by_analysis"


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    chunk_id: str
    document_id: str
    source_filename: str
    page_numbers: tuple[int, ...]
    text: str

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (self.chunk_id, self.document_id, self.source_filename, self.text)
        ):
            raise ValueError("evidence record text identifiers must not be blank")
        if not self.page_numbers or any(page < 1 for page in self.page_numbers):
            raise ValueError("evidence record pages must be positive and nonempty")


@dataclass(frozen=True, slots=True)
class EvidenceTarget:
    chunk_id: str | None
    document_id: str
    page_numbers: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.chunk_id is not None and not self.chunk_id.strip():
            raise ValueError("target chunk_id must be non-blank when supplied")
        if not self.document_id.strip():
            raise ValueError("target document_id must not be blank")
        if not self.page_numbers or any(page < 1 for page in self.page_numbers):
            raise ValueError("target page_numbers must be positive and nonempty")


@dataclass(frozen=True, slots=True)
class ClaimObservation:
    text: str
    citation_chunk_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("observed claim must not be blank")
        if any(not chunk_id.strip() for chunk_id in self.citation_chunk_ids):
            raise ValueError("claim citation chunk IDs must not be blank")


@dataclass(frozen=True, slots=True)
class CitationObservation:
    chunk_id: str
    document_id: str
    page_numbers: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.chunk_id.strip() or not self.document_id.strip():
            raise ValueError("observed citation IDs must not be blank")
        if any(page < 1 for page in self.page_numbers):
            raise ValueError("observed citation pages must be positive")


@dataclass(frozen=True, slots=True)
class AnswerObservation:
    answer: str
    insufficient_evidence: bool
    claims: tuple[ClaimObservation, ...]
    citations: tuple[CitationObservation, ...]

    def __post_init__(self) -> None:
        if not self.answer.strip():
            raise ValueError("observed answer must not be blank")
        if self.insufficient_evidence and (self.claims or self.citations):
            raise ValueError("an insufficient observation cannot contain claims or citations")


@dataclass(frozen=True, slots=True)
class CaseObservation:
    retrieved_chunk_ids: tuple[str, ...]
    context_chunk_ids: tuple[str, ...]
    retrieved_context_answer: AnswerObservation
    gold_context_answer: AnswerObservation


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    case_id: str
    question: str
    category: str
    expected_facts: tuple[str, ...]
    expected_evidence: tuple[EvidenceTarget, ...]
    should_be_insufficient: bool
    acceptable_variants: tuple[str, ...]
    notes: str
    observation: CaseObservation

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.case_id, self.question, self.category)):
            raise ValueError("evaluation case identifiers must not be blank")
        if self.should_be_insufficient and (self.expected_facts or self.expected_evidence):
            raise ValueError("unanswerable cases cannot declare expected facts or evidence")
        if not self.should_be_insufficient and (
            not self.expected_facts or not self.expected_evidence
        ):
            raise ValueError("answerable cases require expected facts and evidence")


@dataclass(frozen=True, slots=True)
class ExpectedFinancialMetric:
    metric_name: str
    value: str
    fiscal_period: str | None
    unit: str | None
    currency: str | None
    basis: str | None


@dataclass(frozen=True, slots=True)
class StructuredSectionExpectation:
    key: str
    should_be_insufficient: bool
    expected_facts: tuple[str, ...]
    expected_observations: tuple[str, ...]
    expected_metrics: tuple[ExpectedFinancialMetric, ...]
    expected_evidence_chunk_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ObservedFinancialMetric:
    metric_name: str
    value: str
    fiscal_period: str | None
    unit: str | None
    currency: str | None
    basis: str | None
    citation_chunk_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StructuredSectionObservation:
    key: str
    insufficient_evidence: bool
    facts: tuple[str, ...]
    observations: tuple[str, ...]
    metrics: tuple[ObservedFinancialMetric, ...]
    citation_chunk_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StructuredEvaluationCase:
    case_id: str
    company_name: str
    expected_sections: tuple[StructuredSectionExpectation, ...]
    observed_sections: tuple[StructuredSectionObservation, ...]


@dataclass(frozen=True, slots=True)
class EvaluationDataset:
    dataset_id: str
    version: str
    description: str
    evidence: tuple[EvidenceRecord, ...]
    cases: tuple[EvaluationCase, ...]
    structured_cases: tuple[StructuredEvaluationCase, ...]

    def __post_init__(self) -> None:
        if not self.dataset_id.strip() or not self.version.strip():
            raise ValueError("dataset ID and version must not be blank")
        chunk_ids = tuple(record.chunk_id for record in self.evidence)
        if len(set(chunk_ids)) != len(chunk_ids):
            raise ValueError("evaluation evidence chunk IDs must be unique")
        case_ids = tuple(case.case_id for case in self.cases)
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("evaluation case IDs must be unique")

    @property
    def evidence_by_chunk_id(self) -> dict[str, EvidenceRecord]:
        return {record.chunk_id: record for record in self.evidence}


@dataclass(frozen=True, slots=True)
class RetrievalCaseMetrics:
    first_relevant_rank: int | None
    reciprocal_rank: float
    hit_at: dict[int, float]
    recall_at: dict[int, float]
    unanswerable_no_result: float | None


@dataclass(frozen=True, slots=True)
class AnswerCaseMetrics:
    expected_fact_recall: float
    abstention_correct: float
    claim_faithfulness: float


@dataclass(frozen=True, slots=True)
class CitationCaseMetrics:
    validity: float
    support_precision: float
    claim_coverage: float


@dataclass(frozen=True, slots=True)
class CaseEvaluation:
    case_id: str
    category: str
    retrieval: RetrievalCaseMetrics
    retrieved_context: AnswerCaseMetrics
    gold_context: AnswerCaseMetrics
    citation: CitationCaseMetrics
    correctness_gap: float
    failures: tuple[FailureCategory, ...]
    details: dict[str, Any]
    judge: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class StructuredCaseMetrics:
    case_id: str
    supported_section_population: float
    unsupported_section_abstention: float
    fact_recall: float
    observation_recall: float
    financial_field_accuracy: float
    citation_retention: float
    fact_analysis_separation: float
    failures: tuple[FailureCategory, ...]


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    dataset_id: str
    dataset_version: str
    top_k_values: tuple[int, ...]
    aggregate: dict[str, Any]
    per_category: dict[str, dict[str, float]]
    cases: tuple[CaseEvaluation, ...]
    structured_cases: tuple[StructuredCaseMetrics, ...]
    judge_status: dict[str, Any]
