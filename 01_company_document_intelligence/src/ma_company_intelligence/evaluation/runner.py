"""Evaluation orchestration and component-level aggregation."""

from __future__ import annotations

from dataclasses import asdict

from ma_company_intelligence.evaluation.judge import EvaluationJudge
from ma_company_intelligence.evaluation.metrics import (
    classify_failures,
    evaluate_answer,
    evaluate_citations,
    evaluate_retrieval,
    evaluate_structured_case,
)
from ma_company_intelligence.evaluation.models import (
    CaseEvaluation,
    EvaluationDataset,
    EvaluationReport,
    StructuredCaseMetrics,
)


class EvaluationRunner:
    """Evaluate recorded outputs without changing production pipeline behavior."""

    def __init__(
        self,
        *,
        top_k_values: tuple[int, ...] = (1, 3, 5),
        judge: EvaluationJudge | None = None,
    ) -> None:
        if not top_k_values or any(k <= 0 for k in top_k_values):
            raise ValueError("top_k_values must contain positive integers")
        if tuple(sorted(set(top_k_values))) != top_k_values:
            raise ValueError("top_k_values must be unique and ascending")
        self._top_k_values = top_k_values
        self._judge = judge

    def run(self, dataset: EvaluationDataset) -> EvaluationReport:
        evidence = dataset.evidence_by_chunk_id
        case_results: list[CaseEvaluation] = []
        for case in dataset.cases:
            retrieval = evaluate_retrieval(case, evidence, self._top_k_values)
            retrieved_answer = evaluate_answer(
                case,
                case.observation.retrieved_context_answer,
                case.observation.context_chunk_ids,
                evidence,
            )
            gold_context_ids = tuple(
                target.chunk_id for target in case.expected_evidence if target.chunk_id is not None
            )
            gold_answer = evaluate_answer(
                case,
                case.observation.gold_context_answer,
                gold_context_ids,
                evidence,
            )
            citation = evaluate_citations(
                case.observation.retrieved_context_answer,
                case.observation.retrieved_chunk_ids,
                evidence,
            )
            failures = classify_failures(
                case,
                retrieval,
                retrieved_answer,
                citation,
                evidence,
            )
            judge_result = None
            if self._judge is not None:
                judge_result = asdict(self._judge.assess(case, evidence))
            case_results.append(
                CaseEvaluation(
                    case_id=case.case_id,
                    category=case.category,
                    retrieval=retrieval,
                    retrieved_context=retrieved_answer,
                    gold_context=gold_answer,
                    citation=citation,
                    correctness_gap=(
                        gold_answer.expected_fact_recall - retrieved_answer.expected_fact_recall
                    ),
                    failures=failures,
                    details={
                        "question": case.question,
                        "expected_facts": case.expected_facts,
                        "expected_evidence": [asdict(value) for value in case.expected_evidence],
                        "retrieved_chunk_ids": case.observation.retrieved_chunk_ids,
                        "context_chunk_ids": case.observation.context_chunk_ids,
                        "generated_answer": (case.observation.retrieved_context_answer.answer),
                        "citations": [
                            asdict(value)
                            for value in case.observation.retrieved_context_answer.citations
                        ],
                        "notes": case.notes,
                    },
                    judge=judge_result,
                )
            )

        structured = tuple(
            evaluate_structured_case(case, evidence) for case in dataset.structured_cases
        )
        return EvaluationReport(
            dataset_id=dataset.dataset_id,
            dataset_version=dataset.version,
            top_k_values=self._top_k_values,
            aggregate=_aggregate(tuple(case_results), structured, self._top_k_values),
            per_category=_per_category(tuple(case_results), self._top_k_values),
            cases=tuple(case_results),
            structured_cases=structured,
            judge_status=(
                {
                    "enabled": True,
                    "provider": self._judge.provider_name,
                    "model": self._judge.model_name,
                    "assessment_count": len(case_results),
                }
                if self._judge is not None
                else {
                    "enabled": False,
                    "reason": "Optional LLM judge was not requested or credentials were absent.",
                    "assessment_count": 0,
                }
            ),
        )


def _aggregate(
    cases: tuple[CaseEvaluation, ...],
    structured: tuple[StructuredCaseMetrics, ...],
    top_k_values: tuple[int, ...],
) -> dict[str, object]:
    answerable = tuple(case for case in cases if case.retrieval.unanswerable_no_result is None)
    unanswerable = tuple(
        case for case in cases if case.retrieval.unanswerable_no_result is not None
    )
    structured_values = structured
    retrieval = {
        f"hit_at_{k}": _mean([case.retrieval.hit_at[k] for case in answerable])
        for k in top_k_values
    }
    retrieval.update(
        {
            f"recall_at_{k}": _mean([case.retrieval.recall_at[k] for case in answerable])
            for k in top_k_values
        }
    )
    retrieval["mrr"] = _mean([case.retrieval.reciprocal_rank for case in answerable])
    retrieval["unanswerable_no_result_accuracy"] = _mean(
        [case.retrieval.unanswerable_no_result or 0.0 for case in unanswerable]
    )
    return {
        "case_count": len(cases),
        "answerable_case_count": len(answerable),
        "unanswerable_case_count": len(unanswerable),
        "retrieval": retrieval,
        "generation": {
            "retrieved_context_expected_fact_recall": _mean(
                [case.retrieved_context.expected_fact_recall for case in cases]
            ),
            "gold_context_expected_fact_recall": _mean(
                [case.gold_context.expected_fact_recall for case in cases]
            ),
            "gold_context_correctness_gap": _mean([case.correctness_gap for case in cases]),
            "abstention_accuracy": _mean(
                [case.retrieved_context.abstention_correct for case in cases]
            ),
        },
        "faithfulness": {
            "claim_support_rate": _mean(
                [case.retrieved_context.claim_faithfulness for case in cases]
            )
        },
        "citations": {
            "validity": _mean([case.citation.validity for case in cases]),
            "support_precision": _mean([case.citation.support_precision for case in cases]),
            "claim_coverage": _mean([case.citation.claim_coverage for case in cases]),
        },
        "structured_research": (
            {
                "case_count": len(structured_values),
                "supported_section_population": _mean(
                    [case.supported_section_population for case in structured_values]
                ),
                "unsupported_section_abstention": _mean(
                    [case.unsupported_section_abstention for case in structured_values]
                ),
                "fact_recall": _mean([case.fact_recall for case in structured_values]),
                "observation_recall": _mean(
                    [case.observation_recall for case in structured_values]
                ),
                "financial_field_accuracy": _mean(
                    [case.financial_field_accuracy for case in structured_values]
                ),
                "citation_retention": _mean(
                    [case.citation_retention for case in structured_values]
                ),
                "fact_analysis_separation": _mean(
                    [case.fact_analysis_separation for case in structured_values]
                ),
            }
            if structured_values
            else {"case_count": 0}
        ),
        "failure_counts": _failure_counts(cases, structured_values),
    }


def _per_category(
    cases: tuple[CaseEvaluation, ...],
    top_k_values: tuple[int, ...],
) -> dict[str, dict[str, float]]:
    categories = sorted({case.category for case in cases})
    result: dict[str, dict[str, float]] = {}
    maximum_k = max(top_k_values)
    for category in categories:
        selected = tuple(case for case in cases if case.category == category)
        answerable = tuple(
            case for case in selected if case.retrieval.unanswerable_no_result is None
        )
        metrics = {
            "expected_fact_recall": _mean(
                [case.retrieved_context.expected_fact_recall for case in selected]
            ),
            "faithfulness": _mean([case.retrieved_context.claim_faithfulness for case in selected]),
            "citation_support_precision": _mean(
                [case.citation.support_precision for case in selected]
            ),
        }
        if answerable:
            metrics[f"hit_at_{maximum_k}"] = _mean(
                [case.retrieval.hit_at[maximum_k] for case in answerable]
            )
        else:
            metrics["unanswerable_no_result_accuracy"] = _mean(
                [case.retrieval.unanswerable_no_result or 0.0 for case in selected]
            )
        result[category] = metrics
    return result


def _failure_counts(
    cases: tuple[CaseEvaluation, ...],
    structured: tuple[StructuredCaseMetrics, ...],
) -> dict[str, int]:
    values = [str(failure) for case in cases for failure in case.failures]
    for case in structured:
        values.extend(str(failure) for failure in case.failures)
    return {value: values.count(value) for value in sorted(set(values))}


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 1.0
