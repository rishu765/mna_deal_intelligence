# Screening, strategic fit, and ranking

## Pipeline boundary

```text
AcquisitionThesis + CandidateProfile
  -> deterministic criterion evaluation
  -> hard/exclusion eligibility gate
  -> evidence-grounded semantic criterion evaluation
  -> soft-score aggregation and coverage adjustment
  -> deterministic ranking
  -> evidence-backed shortlist + complete audit results
```

M4/5 answers which enriched candidates best fit the thesis and why. It does not discover or
enrich companies, orchestrate agents, request human approval, or expose an API.

## Criterion evaluations

Every thesis criterion produces a `CriterionEvaluation` containing its ID, category,
requirement, deterministic/semantic method, `pass`/`fail`/`partial`/`unknown`/`not_applicable`
outcome, reason, observed values, evidence, optional score, weight, and uncertainty.

Hard criteria and exclusions are gates:

- any hard failure or triggered exclusion -> `ineligible`;
- no failures but an unknown/partial gate -> `review_required`;
- all gates pass -> `eligible`.

An exclusion evaluation passes when the prohibited predicate is not observed and fails when it
is observed. Failed candidates are not ranked as shortlist entries, but their complete results
remain in `Shortlist.screening_results`.

## Deterministic screening

The engine evaluates supported industry, sub-industry, product/capability, geography, revenue,
profitability, size, employee, founded-year, growth, ownership, customer, and technology fields.
It uses evidence-backed profile facts rather than raw discovery snippets. Missing, conflicting,
ambiguous, unsupported, or non-parseable values produce `unknown`.

Text matching is conservative case-insensitive exact/containment matching. Boolean parsing uses
explicit positive and negative signals. Numeric comparisons require parseable values and, when
specified, evidence of the requested unit and period.

## Financial safeguards

Revenue is compared only when metric name, currency, unit, and required fiscal period match the
criterion basis. There is no FX, unit, fiscal-period, or accounting-basis conversion. Conflicting
or multiple unresolved comparable metrics produce `unknown`, as do non-numeric values.

## Strategic-fit reasoning

`StrategicFitProvider` evaluates only criteria M1 marks semantic. Two implementations establish
the boundary:

- `FixtureStrategicFitProvider` supplies deterministic offline/CI outputs;
- `StructuredLLMStrategicFitProvider` accepts a generic JSON-generation client, constructs an
  evidence-only prompt, and validates the structured response.

The structured provider receives the acquirer objective, one criterion, candidate facts,
inferences, financials, and their evidence IDs. Known assessments must cite candidate-profile
evidence. Unknown IDs, missing evidence on a known claim, malformed output, or provider failure
become `unknown`; unsupported claims never enter scoring.

No concrete live LLM SDK is bundled. A separately configured client can implement the narrow
`generate_json` protocol without coupling the domain to one model vendor.

## Scoring formula

Hard criteria and exclusions do not add points; they determine eligibility. Each soft criterion
uses its explicit M1 weight, otherwise priority maps to critical=4, high=3, medium=2, low=1, and
unspecified=1. Deterministic passes score 1 and failures 0. Semantic providers return a validated
score from 0 through 1; partial outcomes can therefore retain intermediate credit.
Known semantic outcomes use explicit bands: fail=0–0.33, partial=0.34–0.66, and
pass=0.67–1.00. Inconsistent outcome/score pairs are rejected as malformed.

For known soft evaluations:

```text
raw_fit_score = 100 * sum(weight * criterion_score) / sum(known weights)
evidence_coverage = sum(known weights) / sum(all soft-criterion weights)
confidence_factor = 0.5 + 0.5 * evidence_coverage
final_score = raw_fit_score * confidence_factor
```

Scores are reported to one decimal place. Unknown soft criteria do not receive zero and do not
enter the known-score mean, but their missing weight reduces coverage and the final score. If no
soft criterion is known, scores remain `null` rather than becoming zero. The formula is a
transparent prioritization heuristic, not a valuation or probability of deal success.

## Ranking and ties

Ordering is deterministic for fixed inputs:

1. eligibility (`eligible`, then `review_required`, then `ineligible`);
2. final score descending;
3. semantic score descending;
4. deterministic soft score descending;
5. evidence coverage descending; and
6. canonical company name ascending as a stable tie-breaker.

By default, eligible and review-required candidates may appear in shortlist entries; the latter
remain visibly labeled. Ineligible candidates stay only in audit results. Callers may exclude
review-required entries or apply `top_n` without deleting underlying results.

## Offline demo

From `02_target_screening_sourcing/`:

```powershell
python -m ma_target_screening.demo_screening
```

The synthetic scenario includes a strong fit, a weaker eligible fit, an incomplete candidate,
and a consumer-lending candidate that triggers hard/exclusion failures. It requires no API key
or network access.

## Limitations

- Text matching is transparent but not ontology-backed.
- Only revenue has a defined financial metric mapping.
- There is no FX, unit, accounting-basis, or period conversion.
- The offline semantic fixture is curated; no live LLM client is configured by default.
- Evidence quality labels do not alter the score; only criterion coverage does.
- The score is a prioritization aid, not investment advice, valuation, or autonomous decision.
