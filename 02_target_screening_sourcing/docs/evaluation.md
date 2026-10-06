# Project 2 V1 evaluation

## Purpose

The evaluation framework measures each subsystem separately so a strong deterministic filter does
not hide weak sourcing, or a good ranking hide unsupported evidence. The benchmark is offline,
versioned, small enough to inspect manually, and safe to publish.

## Dataset

`data/evaluation_cases.json` contains five cases:

1. Indian B2B payments with financial, exclusion, and semantic criteria;
2. enterprise software acquiring AI/data capability;
3. geographic expansion into Indian enterprise fintech;
4. an intentionally incomplete industrial-technology thesis; and
5. an exclusion-heavy Indian fintech thesis.

Labels cover criterion classification, relevant discovery domains, selected profile fields and
unknowns, screening outcomes, strategic-fit outcomes, top-k candidates, and pairwise ordering.
Only the payments case has complete labels across every downstream subsystem.

## Metrics

| Subsystem | Metrics |
| --- | --- |
| Thesis | Schema validity, serialization preservation, requirement classification accuracy |
| Discovery | Recall, precision, pre-dedup observation rate, provenance coverage |
| Enrichment | Gold assertion accuracy, evidence support, inference support, financial metadata completeness |
| Screening | Criterion outcome agreement, explicit UNKNOWN agreement |
| Strategic fit | Rubric outcome agreement, known-assessment grounding, unsupported-known-claim rate |
| Ranking | Expected top-k inclusion, pairwise agreement, deterministic stability |
| Workflow | Final-state accuracy, retry recovery, review checkpoint behavior across nine scenarios |

The discovery duplicate metric measures repeated raw observations across multiple queries before
normalization, not duplicates returned to downstream consumers.

## Strategic-fit rubric

The deterministic benchmark checks labeled outcome agreement and evidence grounding. A manual or
optional future LLM judge should score each dimension from 0 to 2:

| Dimension | 0 | 1 | 2 |
| --- | --- | --- | --- |
| Thesis relevance | Unrelated | Partly related | Directly answers criterion |
| Evidence grounding | Unsupported | Partly supported | Every material claim supported |
| Logical consistency | Contradictory | Some gaps | Coherent with thesis and profile |
| Specificity | Generic | Some company detail | Candidate- and criterion-specific |
| Unsupported claims | Material inventions | Minor overreach | No unsupported claim |

V1 does not enable an LLM judge by default. Human review remains the reference for explanation
quality because the fixture benchmark is too small to justify automated judging.

## Final fixture results

Run on October 7, 2026:

| Subsystem | Metric | Result |
| --- | --- | ---: |
| Thesis | Schema validity | 1.0000 |
| Thesis | Classification accuracy | 1.0000 |
| Discovery | Recall | 1.0000 |
| Discovery | Precision | 0.5556 |
| Discovery | Pre-dedup observation rate | 0.7468 |
| Discovery | Provenance coverage | 1.0000 |
| Enrichment | Gold assertion accuracy | 1.0000 |
| Enrichment | Claim evidence support | 1.0000 |
| Enrichment | Unsupported inference rate | 0.0000 |
| Enrichment | Financial metadata completeness | 1.0000 |
| Screening | Criterion outcome agreement | 1.0000 |
| Screening | UNKNOWN agreement | 1.0000 |
| Strategic fit | Labeled outcome agreement | 1.0000 |
| Strategic fit | Known-assessment grounding | 1.0000 |
| Ranking | Top-k inclusion | 1.0000 |
| Ranking | Pairwise ordering agreement | 1.0000 |
| Ranking | Deterministic stability | 1.0000 |
| Workflow | Scenario final-state accuracy | 1.0000 across 9 scenarios |

## Interpretation

Strengths:

- typed theses, labeled screening rules, and serialization are stable;
- every evaluated candidate and profile claim retains provenance/evidence;
- missing financial information remains unknown rather than being guessed;
- fixed semantic fixtures produce grounded, stable rankings; and
- graph approval, rejection, empty, partial, hard-fail, retry, and terminal-failure routes behave
  as expected.

Weaknesses and representative blind spots:

- discovery precision is deliberately modest because sourcing prioritizes recall;
- the six-company corpus cannot represent open-web noise or corporate-family ambiguity;
- the AI target is discovered but lacks a matching enrichment fixture, correctly producing gaps;
- only one thesis has complete strategic-fit and ranking labels; and
- no independent M&A professional panel labeled the benchmark.

## Running the evaluation

```powershell
mats-evaluate
mats-evaluate --output evaluation.json
```

The optional output file is a generated artifact and should not be committed.
