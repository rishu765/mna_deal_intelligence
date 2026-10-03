# Evaluation and quality measurement

M8 measures the existing RAG and structured-research pipeline without changing its runtime
prompts or implementation. The benchmark reports retrieval, generation correctness,
faithfulness, citations, and structured research separately. There is deliberately no
composite "project quality" score: a fluent answer can still fail because retrieval missed the
source, the answer contradicted its context, or its citation pointed to the wrong page.

## Dataset design

`evaluation/datasets/synthetic_company_v1.json` is a versioned, copyright-safe fixture about a
fictional company. It contains 13 synthetic evidence chunks, 14 question cases, and two
structured-profile cases. Questions cover business overview, products, segments, geography,
revenue, adjusted EBITDA, growth, risks, strategy, management priorities, customers/end
markets, a direct margin lookup, a multi-evidence financial question, and an intentionally
unanswerable market-share question.

Every answerable case records expected facts and one or more acceptable evidence targets with
document, canonical page, and chunk IDs. An unanswerable case records neither expected facts
nor evidence. Recorded retrieved results, context, generated claims, and citations intentionally
include several defects. This lets the deterministic baseline prove that it detects failures;
the results are not presented as a live-model quality claim.

The benchmark is small and inspectable. It is useful for regression diagnosis, but it must not
be treated as representative of all annual reports or optimized until every case passes.

## Evaluation architecture

```text
versioned evaluation cases
        |
        +--> retrieval ranks ----------> hit/recall@k, MRR, first relevant rank
        +--> retrieved-context answer -> correctness, abstention, faithfulness
        +--> gold-context answer ------> generation-attributable comparison
        +--> citations ----------------> validity, support precision, claim coverage
        +--> structured profiles ------> section, fact, qualifier, evidence metrics
        |
        +--> per-case failures + per-category/aggregate JSON and Markdown reports
```

Evaluation code stays under `ma_company_intelligence.evaluation`. Production retrieval,
generation, and research code never reads gold answers or benchmark annotations.

## Metric definitions

Retrieval metrics apply to the 13 answerable cases:

- **Hit@k** is 1 when at least one expected evidence target appears in the first `k` results,
  otherwise 0. The report averages this over answerable cases.
- **Recall@k** is the number of distinct expected evidence targets found in the first `k`
  results divided by the total expected targets. Duplicate results cannot inflate recall.
- **First relevant rank** is the one-based rank of the earliest matching target, or absent when
  none is retrieved.
- **MRR** is the mean reciprocal first relevant rank; a miss contributes zero.
- **Unanswerable no-result accuracy** is the fraction of deliberately unanswerable cases for
  which retrieval returns no evidence. It is reported separately from answerable-case recall.

Generation and grounding metrics are deterministic baselines:

- **Expected-fact recall** is the fraction of normalized gold fact strings present in the
  answer. It works best for concise facts and is not a semantic-equivalence judge.
- **Abstention accuracy** is 1 when an answerable case is answered or an unanswerable case is
  explicitly marked insufficient; otherwise 0.
- **Claim support rate** is the fraction of recorded claims whose normalized text is present in
  at least one cited context chunk. It measures faithfulness to supplied context, not external
  truth.
- **Gold-context correctness gap** is gold-context expected-fact recall minus retrieved-context
  expected-fact recall. A positive gap suggests retrieval/context selection contributed to the
  error; weak gold-context performance points to generation or scoring limitations.

Citation metrics are:

- **Validity**: fraction of citation records whose chunk was retrieved and whose document ID
  and canonical pages exactly match the evidence catalog.
- **Support precision**: fraction of valid cited chunks that support at least one associated
  claim using the deterministic normalized-text rule.
- **Claim coverage**: fraction of claims with at least one valid, supporting citation.

Structured-research metrics are averaged over expected sections:

- **Supported-section population** checks that sections with evidence are not marked
  insufficient.
- **Unsupported-section abstention** checks that sections without evidence remain empty and
  insufficient.
- **Fact recall** and **observation recall** compare expected factual and analytical strings
  within their respective fields.
- **Financial-field accuracy** compares metric name, displayed value, fiscal period, unit,
  currency, and basis independently. This exposes errors such as EUR in place of USD or annual
  figures described as quarterly.
- **Citation retention** checks expected section/metric evidence IDs against cited chunk IDs.
- **Fact/analysis separation** penalizes expected facts moved into analytical-observation
  fields.

## Failure taxonomy

Per-case results use stable labels for relevant evidence missing or ranked low, useful context
omitted, unsupported/incomplete answers, incorrect abstention, invalid/irrelevant/missing
citations, omitted or unsupported structured fields, financial qualifier mismatches, and facts
misclassified as analysis. The classifier is diagnostic; it does not prove causality in every
natural-language failure.

## Gold-context decomposition

Each question stores one answer produced against the recorded retrieved context and a second
answer against known correct evidence. The runner scores both. This distinguishes a retrieval
or context problem from a generation problem more clearly than an end-to-end score alone. The
current dataset stores these observations for reproducibility; a future live benchmark can run
the same production generator twice and serialize its outputs.

## Deterministic metrics and the optional LLM judge

The normal runner is offline, deterministic, and safe for CI. String/fact checks remain easy to
audit but cannot recognize all valid paraphrases or prove entailment.

`--llm-judge` optionally adds a strict structured assessment of correctness, faithfulness, and
citation support. The OpenAI adapter defaults to `gpt-6-luna` with low reasoning effort; model
and effort are configurable through `MADI_EVALUATION_JUDGE_MODEL` and
`MADI_EVALUATION_JUDGE_REASONING_EFFORT`. No API key means the judge is skipped while the
deterministic evaluation still completes. Judge outputs are supplemental because model judges
can be inconsistent, biased toward style, and sensitive to rubric/model changes. Record the
model and configuration when comparing runs.

## Running the benchmark

From `01_company_document_intelligence/` after development installation:

```powershell
madi-evaluate
```

The default writes detailed JSON and a compact Markdown summary under
`artifacts/evaluation/`, which Git ignores. Customize the run with:

```powershell
madi-evaluate --dataset evaluation/datasets/synthetic_company_v1.json `
  --output-dir artifacts/evaluation --report-stem local-run --top-k 1,3,5
```

Optional paid judging requires `OPENAI_API_KEY`:

```powershell
madi-evaluate --llm-judge
```

The committed baseline is in `evaluation/baselines/`. JSON contains aggregate,
per-category, per-case, retrieved/expected evidence, answers, citations, and classified
failures. Markdown is a review summary.

## M8 offline baseline

Dataset `synthetic_apex_company_research` version `1.0.0` produced:

| Component | Metric | Result |
| --- | --- | ---: |
| Retrieval | Hit@1 / Hit@3 / Hit@5 | 76.92% / 84.62% / 92.31% |
| Retrieval | Recall@1 / Recall@3 / Recall@5 | 73.08% / 80.77% / 88.46% |
| Retrieval | MRR | 82.69% |
| Retrieval | Unanswerable no-result accuracy | 0.00% |
| Generation | Retrieved-context fact recall | 78.57% |
| Generation | Gold-context fact recall | 92.86% |
| Generation | Gold-context correctness gap | 14.29 points |
| Generation | Abstention accuracy | 85.71% |
| Faithfulness | Claim support rate | 85.71% |
| Citations | Validity / support precision / claim coverage | 92.86% / 75.00% / 78.57% |
| Structured | Supported population / unsupported abstention | 90.91% / 75.00% |
| Structured | Fact recall / observation recall | 86.36% / 100.00% |
| Structured | Financial field accuracy | 95.83% |
| Structured | Citation retention / fact-analysis separation | 91.67% / 86.36% |

Representative failures are intentional: geography evidence first appears at rank four and is
omitted from context; a growth answer matches the gold fact but is unsupported by retrieved
context; a product citation uses fabricated page 99; one strategy answer cites irrelevant
evidence; a multi-evidence answer omits adjusted EBITDA; and the market-share case answers when
it should abstain. These show why correctness, grounding, citation quality, and abstention must
remain separate.

## M11 final rerun

The finalization milestone reran the same dataset, top-k values, runner, and deterministic
configuration. The generated JSON was exactly equal to the committed M8 baseline, including
aggregate metrics and every per-case result. Finalization intentionally did not change runtime
prompts, recorded retrieval observations, metric definitions, or gold cases merely to improve
the displayed scores.

Therefore the table above is both the M8 baseline and the final Project 1 deterministic result.
The comparison shows zero change for every metric. This is regression evidence for the
evaluation framework, not a new live-provider quality measurement.

## Unit tests versus quality benchmarks

Unit tests verify metric arithmetic, validation, reporting, duplicate handling, safe judge
failure, and CLI behavior. They should be fast and stable. The benchmark records quality and
may expose poor scores without failing CI. Only a small, high-confidence subset should become
regression assertions; converting all benchmark scores into test thresholds would make tests
brittle and encourage overfitting.

## Limitations

- The committed baseline evaluates synthetic recorded observations, not live OpenAI calls or
  performance on a copyrighted public-company annual report.
- Normalized substring checks miss valid paraphrases and can over-credit repeated wording.
- Claim support is not full natural-language entailment and cannot reliably resolve conflicting
  evidence.
- The small dataset provides limited category and document-layout coverage.
- Citation completeness depends on explicit recorded claims; it cannot discover every implicit
  claim in prose.
- The optional judge adds cost and nondeterminism and remains subject to model drift.
- Human review remains necessary for material financial and M&A conclusions.

M9/10 exposes the evaluated services through a thin API without putting benchmark gold data
into runtime requests. Future evaluation should add representative, legally distributable
document layouts and separately recorded live-provider runs.
