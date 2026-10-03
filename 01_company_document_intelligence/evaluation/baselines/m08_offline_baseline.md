# Evaluation baseline: synthetic_apex_company_research v1.0.0

This report exposes component metrics separately; it intentionally has no composite score.

## Retrieval

- `hit_at_1`: 0.7692
- `hit_at_3`: 0.8462
- `hit_at_5`: 0.9231
- `recall_at_1`: 0.7308
- `recall_at_3`: 0.8077
- `recall_at_5`: 0.8846
- `mrr`: 0.8269
- `unanswerable_no_result_accuracy`: 0.0000

## Generation

- `retrieved_context_expected_fact_recall`: 0.7857
- `gold_context_expected_fact_recall`: 0.9286
- `gold_context_correctness_gap`: 0.1429
- `abstention_accuracy`: 0.8571

## Faithfulness

- `claim_support_rate`: 0.8571

## Citations

- `validity`: 0.9286
- `support_precision`: 0.7500
- `claim_coverage`: 0.7857

## Structured research

- `case_count`: 2
- `supported_section_population`: 0.9091
- `unsupported_section_abstention`: 0.7500
- `fact_recall`: 0.8636
- `observation_recall`: 1.0000
- `financial_field_accuracy`: 0.9583
- `citation_retention`: 0.9167
- `fact_analysis_separation`: 0.8636

## Failed cases

- `products-01` (products_services): citation.invalid_or_fabricated_provenance, citation.does_not_support_claim, citation.supporting_claim_not_cited
- `geography-01` (geographic_exposure): retrieval.correct_evidence_ranked_low, context.useful_evidence_omitted, generation.refusal_despite_sufficient_evidence
- `growth-01` (growth): retrieval.relevant_evidence_not_retrieved, generation.unsupported_claim, citation.does_not_support_claim, citation.supporting_claim_not_cited
- `risks-01` (risk_factors): generation.incomplete_answer
- `strategy-01` (strategy): citation.does_not_support_claim
- `multi-financial-01` (multi_evidence): generation.incomplete_answer
- `unanswerable-01` (unanswerable): generation.answered_unanswerable_question, generation.unsupported_claim, citation.does_not_support_claim, citation.supporting_claim_not_cited

## Failure counts

- `citation.does_not_support_claim`: 4
- `citation.invalid_or_fabricated_provenance`: 2
- `citation.supporting_claim_not_cited`: 3
- `context.useful_evidence_omitted`: 1
- `generation.answered_unanswerable_question`: 1
- `generation.incomplete_answer`: 2
- `generation.refusal_despite_sufficient_evidence`: 1
- `generation.unsupported_claim`: 2
- `retrieval.correct_evidence_ranked_low`: 1
- `retrieval.relevant_evidence_not_retrieved`: 1
- `structured.expected_field_omitted`: 1
- `structured.fact_replaced_by_analysis`: 1
- `structured.financial_qualifier_mismatch`: 1
- `structured.unsupported_field_populated`: 1

## Judge status

```json
{
  "enabled": false,
  "reason": "Optional LLM judge was not requested or credentials were absent.",
  "assessment_count": 0
}
```
