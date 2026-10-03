"""Deterministic, inspectable metrics for retrieval and RAG quality."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping

from ma_company_intelligence.evaluation.models import (
    AnswerCaseMetrics,
    AnswerObservation,
    CitationCaseMetrics,
    EvaluationCase,
    EvidenceRecord,
    EvidenceTarget,
    FailureCategory,
    RetrievalCaseMetrics,
    StructuredCaseMetrics,
    StructuredEvaluationCase,
    StructuredSectionObservation,
)


def normalize_text(value: str) -> str:
    """Normalize only for transparent benchmark matching, never runtime generation."""

    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = normalized.replace("$", " usd ").replace("£", " gbp ").replace("€", " eur ")
    return " ".join(re.sub(r"[^\w%]+", " ", normalized).split())


def text_contains(container: str, expected: str) -> bool:
    return normalize_text(expected) in normalize_text(container)


def evaluate_retrieval(
    case: EvaluationCase,
    evidence_by_id: Mapping[str, EvidenceRecord],
    top_k_values: tuple[int, ...],
) -> RetrievalCaseMetrics:
    retrieved = case.observation.retrieved_chunk_ids
    if case.should_be_insufficient:
        return RetrievalCaseMetrics(
            first_relevant_rank=None,
            reciprocal_rank=0.0,
            hit_at={k: 0.0 for k in top_k_values},
            recall_at={k: 0.0 for k in top_k_values},
            unanswerable_no_result=float(not retrieved),
        )

    ranks = [
        rank
        for rank, chunk_id in enumerate(retrieved, start=1)
        if any(
            _target_matches(target, chunk_id, evidence_by_id) for target in case.expected_evidence
        )
    ]
    first_rank = min(ranks) if ranks else None
    hit_at = {k: float(any(rank <= k for rank in ranks)) for k in top_k_values}
    recall_at = {}
    for k in top_k_values:
        found = sum(
            any(_target_matches(target, chunk_id, evidence_by_id) for chunk_id in retrieved[:k])
            for target in case.expected_evidence
        )
        recall_at[k] = found / len(case.expected_evidence)
    return RetrievalCaseMetrics(
        first_relevant_rank=first_rank,
        reciprocal_rank=0.0 if first_rank is None else 1.0 / first_rank,
        hit_at=hit_at,
        recall_at=recall_at,
        unanswerable_no_result=None,
    )


def evaluate_answer(
    case: EvaluationCase,
    observation: AnswerObservation,
    context_chunk_ids: tuple[str, ...],
    evidence_by_id: Mapping[str, EvidenceRecord],
) -> AnswerCaseMetrics:
    if case.should_be_insufficient:
        expected_fact_recall = float(observation.insufficient_evidence)
    elif observation.insufficient_evidence:
        expected_fact_recall = 0.0
    else:
        matched = sum(text_contains(observation.answer, fact) for fact in case.expected_facts)
        expected_fact_recall = matched / len(case.expected_facts)

    abstention_correct = float(observation.insufficient_evidence == case.should_be_insufficient)
    if not observation.claims:
        claim_faithfulness = 1.0 if observation.insufficient_evidence else 0.0
    else:
        context_records = [
            evidence_by_id[chunk_id] for chunk_id in context_chunk_ids if chunk_id in evidence_by_id
        ]
        supported = sum(
            any(text_contains(record.text, claim.text) for record in context_records)
            for claim in observation.claims
        )
        claim_faithfulness = supported / len(observation.claims)
    return AnswerCaseMetrics(
        expected_fact_recall=expected_fact_recall,
        abstention_correct=abstention_correct,
        claim_faithfulness=claim_faithfulness,
    )


def evaluate_citations(
    observation: AnswerObservation,
    retrieved_chunk_ids: tuple[str, ...],
    evidence_by_id: Mapping[str, EvidenceRecord],
) -> CitationCaseMetrics:
    if observation.insufficient_evidence:
        return CitationCaseMetrics(validity=1.0, support_precision=1.0, claim_coverage=1.0)

    unique_citations = tuple(
        dict.fromkeys(
            (citation.chunk_id, citation.document_id, citation.page_numbers)
            for citation in observation.citations
        )
    )
    validity_by_reference: dict[tuple[str, str, tuple[int, ...]], bool] = {}
    valid_by_chunk: dict[str, bool] = {}
    for chunk_id, document_id, page_numbers in unique_citations:
        record = evidence_by_id.get(chunk_id)
        is_valid = bool(
            record is not None
            and chunk_id in retrieved_chunk_ids
            and document_id == record.document_id
            and page_numbers == record.page_numbers
        )
        validity_by_reference[(chunk_id, document_id, page_numbers)] = is_valid
        valid_by_chunk[chunk_id] = valid_by_chunk.get(chunk_id, False) or is_valid
    validity = (
        sum(validity_by_reference.values()) / len(unique_citations) if unique_citations else 0.0
    )

    supported_citations = 0
    for chunk_id, document_id, page_numbers in unique_citations:
        record = evidence_by_id.get(chunk_id)
        is_valid = validity_by_reference[(chunk_id, document_id, page_numbers)]
        if (
            is_valid
            and record is not None
            and any(
                chunk_id in claim.citation_chunk_ids and text_contains(record.text, claim.text)
                for claim in observation.claims
            )
        ):
            supported_citations += 1
    support_precision = supported_citations / len(unique_citations) if unique_citations else 0.0

    covered_claims = 0
    for claim in observation.claims:
        if any(
            valid_by_chunk.get(chunk_id, False)
            and text_contains(evidence_by_id[chunk_id].text, claim.text)
            for chunk_id in claim.citation_chunk_ids
            if chunk_id in evidence_by_id
        ):
            covered_claims += 1
    claim_coverage = covered_claims / len(observation.claims) if observation.claims else 0.0
    return CitationCaseMetrics(
        validity=validity,
        support_precision=support_precision,
        claim_coverage=claim_coverage,
    )


def classify_failures(
    case: EvaluationCase,
    retrieval: RetrievalCaseMetrics,
    answer: AnswerCaseMetrics,
    citation: CitationCaseMetrics,
    evidence_by_id: Mapping[str, EvidenceRecord],
    *,
    low_rank_cutoff: int = 3,
) -> tuple[FailureCategory, ...]:
    failures: list[FailureCategory] = []
    if not case.should_be_insufficient:
        if retrieval.first_relevant_rank is None:
            failures.append(FailureCategory.RETRIEVAL_MISS)
        elif retrieval.first_relevant_rank > low_rank_cutoff:
            failures.append(FailureCategory.RETRIEVAL_LOW_RANK)
        retrieved_relevant = _relevant_ids(
            case,
            case.observation.retrieved_chunk_ids,
            evidence_by_id,
        )
        context_relevant = _relevant_ids(case, case.observation.context_chunk_ids, evidence_by_id)
        if retrieved_relevant - context_relevant:
            failures.append(FailureCategory.CONTEXT_OMISSION)
        if case.observation.retrieved_context_answer.insufficient_evidence:
            failures.append(FailureCategory.GENERATION_FALSE_REFUSAL)
        elif answer.expected_fact_recall < 1.0:
            failures.append(FailureCategory.GENERATION_INCOMPLETE)
    elif not case.observation.retrieved_context_answer.insufficient_evidence:
        failures.append(FailureCategory.GENERATION_UNEXPECTED_ANSWER)

    if answer.claim_faithfulness < 1.0:
        failures.append(FailureCategory.GENERATION_UNSUPPORTED)
    if citation.validity < 1.0:
        failures.append(FailureCategory.CITATION_INVALID)
    if citation.support_precision < 1.0:
        failures.append(FailureCategory.CITATION_IRRELEVANT)
    if citation.claim_coverage < 1.0:
        failures.append(FailureCategory.CITATION_MISSING)
    return tuple(dict.fromkeys(failures))


def evaluate_structured_case(
    case: StructuredEvaluationCase,
    evidence_by_id: Mapping[str, EvidenceRecord],
) -> StructuredCaseMetrics:
    observed_by_key = {section.key: section for section in case.observed_sections}
    supported_population: list[float] = []
    unsupported_abstention: list[float] = []
    fact_scores: list[float] = []
    observation_scores: list[float] = []
    financial_fields: list[float] = []
    citation_scores: list[float] = []
    separation_scores: list[float] = []
    failures: list[FailureCategory] = []

    for expected in case.expected_sections:
        observed = observed_by_key.get(expected.key, _missing_section(expected.key))
        if expected.should_be_insufficient:
            clean_abstention = observed.insufficient_evidence and not (
                observed.facts or observed.observations or observed.metrics
            )
            unsupported_abstention.append(float(clean_abstention))
            if not clean_abstention:
                failures.append(FailureCategory.STRUCTURED_UNSUPPORTED)
            continue

        populated = not observed.insufficient_evidence and bool(
            observed.facts or observed.observations or observed.metrics
        )
        supported_population.append(float(populated))
        if not populated:
            failures.append(FailureCategory.STRUCTURED_OMISSION)

        for fact in expected.expected_facts:
            in_facts = any(text_contains(value, fact) for value in observed.facts)
            in_analysis = any(text_contains(value, fact) for value in observed.observations)
            fact_scores.append(float(in_facts))
            separation_scores.append(float(in_facts and not in_analysis))
            if not in_facts:
                failures.append(FailureCategory.STRUCTURED_OMISSION)
            if in_analysis and not in_facts:
                failures.append(FailureCategory.STRUCTURED_FACT_AS_ANALYSIS)

        for expected_observation in expected.expected_observations:
            found = any(
                text_contains(value, expected_observation) for value in observed.observations
            )
            observation_scores.append(float(found))
            if not found:
                failures.append(FailureCategory.STRUCTURED_OMISSION)

        for expected_metric in expected.expected_metrics:
            matching = next(
                (
                    metric
                    for metric in observed.metrics
                    if normalize_text(metric.metric_name)
                    == normalize_text(expected_metric.metric_name)
                ),
                None,
            )
            expected_values = (
                expected_metric.metric_name,
                expected_metric.value,
                expected_metric.fiscal_period,
                expected_metric.unit,
                expected_metric.currency,
                expected_metric.basis,
            )
            actual_values = (
                (
                    matching.metric_name,
                    matching.value,
                    matching.fiscal_period,
                    matching.unit,
                    matching.currency,
                    matching.basis,
                )
                if matching
                else (None,) * 6
            )
            for actual, gold in zip(actual_values, expected_values, strict=True):
                financial_fields.append(float(_optional_equal(actual, gold)))
            if matching is None:
                failures.append(FailureCategory.STRUCTURED_OMISSION)
            elif actual_values != expected_values:
                failures.append(FailureCategory.STRUCTURED_QUALIFIER)

        if populated:
            expected_ids = set(expected.expected_evidence_chunk_ids)
            observed_ids = set(observed.citation_chunk_ids)
            valid_expected_ids = {
                chunk_id
                for chunk_id in observed_ids
                if chunk_id in evidence_by_id and chunk_id in expected_ids
            }
            citation_retention = (
                len(valid_expected_ids) / len(expected_ids)
                if expected_ids
                else float(not observed_ids)
            )
            citation_scores.append(citation_retention)
            if citation_retention < 1.0 or observed_ids - expected_ids:
                failures.append(FailureCategory.CITATION_INVALID)

    return StructuredCaseMetrics(
        case_id=case.case_id,
        supported_section_population=_mean(supported_population),
        unsupported_section_abstention=_mean(unsupported_abstention),
        fact_recall=_mean(fact_scores),
        observation_recall=_mean(observation_scores),
        financial_field_accuracy=_mean(financial_fields),
        citation_retention=_mean(citation_scores),
        fact_analysis_separation=_mean(separation_scores),
        failures=tuple(dict.fromkeys(failures)),
    )


def _target_matches(
    target: EvidenceTarget,
    chunk_id: str,
    evidence_by_id: Mapping[str, EvidenceRecord],
) -> bool:
    record = evidence_by_id.get(chunk_id)
    if record is None:
        return False
    if target.chunk_id is not None:
        return target.chunk_id == chunk_id
    return target.document_id == record.document_id and bool(
        set(target.page_numbers) & set(record.page_numbers)
    )


def _relevant_ids(
    case: EvaluationCase,
    chunk_ids: Iterable[str],
    evidence_by_id: Mapping[str, EvidenceRecord],
) -> set[str]:
    return {
        chunk_id
        for chunk_id in chunk_ids
        if any(
            _target_matches(target, chunk_id, evidence_by_id) for target in case.expected_evidence
        )
    }


def _missing_section(key: str) -> StructuredSectionObservation:
    return StructuredSectionObservation(
        key=key,
        insufficient_evidence=True,
        facts=(),
        observations=(),
        metrics=(),
        citation_chunk_ids=(),
    )


def _optional_equal(actual: str | None, expected: str | None) -> bool:
    if actual is None or expected is None:
        return actual is expected
    return normalize_text(actual) == normalize_text(expected)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 1.0
