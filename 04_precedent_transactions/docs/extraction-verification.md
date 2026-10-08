# M3 structured extraction, normalization, and verification

## Responsibility boundary

M1/2 retrieves transaction-filtered evidence. M3 turns that evidence into auditable candidate
observations and a verified transaction record. M4/5 will decide comparability and calculate
transaction multiples. M3 does not answer valuation questions.

The flow is:

```text
retrieved chunks -> structured observations -> schema validation -> deterministic normalization
-> cross-source verification -> transaction record + conflicts + traces
```

## Structured extraction

`StructuredTransactionExtractor` consumes `ExtractionRequest`, which contains one transaction ID
and only its retrieved passages. `ExtractionBatch` supports parties and roles; announcement,
signing, completion, and termination dates; status; transaction structure; cash, shares,
contingent, earnout, liability, and other consideration; ownership; headline/equity/EV/per-share
values; Revenue, EBITDA, EBIT, Net Income; and dated capital inputs.

Each observation preserves original wording, exact evidence IDs, optional effective date, revision
context, and notes. Application validation rejects blank IDs, missing evidence, invalid enums,
incomplete quantities, adjusted metrics without labels, and duplicate observation IDs.

The optional `LangChainStructuredExtractor` calls an injected chat model through
`with_structured_output`. It uses the evidence-only prompt in `extraction/prompts.py`, passes a
bounded evidence catalog, accepts a mapping or Pydantic-style `model_dump`, and validates the
result into application contracts. It rejects invented evidence and transaction IDs. LangChain is
an optional integration extra; core M3 has no model dependency.

`FixtureStructuredExtractor` loads committed structured responses and enforces the same evidence
boundary. This keeps unit tests, CI, evaluation, and the demo fully offline.

## Normalization

`FinancialNormalizationService` owns arithmetic and validation. It parses `Decimal`, preserves
currency, applies documented unit factors, normalizes a narrow set of period labels, and maps raw
observations into M0 `ConsiderationComponent`, `OwnershipObservation`, `ValuationObservation`,
`FinancialMetric`, and capital structure contracts.

Scale conversion does not cross currencies. Per-share values cannot become aggregate money.
FY and LTM periods retain exact kind, label, dates, and actual/estimate status. Reported and
adjusted financials remain separate. Revenue cannot be negative under the M0 domain; EBITDA, EBIT,
and Net Income may be negative.

The EV bridge runs only when explicit equity value, debt, and cash share a currency. It records the
inputs, formula, evidence union, and limited assumptions. Missing preferred stock, NCI, leases, or
other adjustments are not invented.

## Verification and source priority

Verification groups like current facts, counts independent documents, retains every observation,
and emits categorical status rather than a probability. The policy ranks contractual,
regulatory, primary-company, trusted-secondary, other, and unknown reliability in that order.
Publication date and observation effective date break ties. Analysts still see conflicts and the
preferred observation ID; priority never deletes a conflicting value.

Statuses are `VERIFIED`, `SOURCE_BACKED`, `SINGLE_SOURCE`, `CONFLICTING`, `DERIVED`, `UNVERIFIED`,
and `MISSING`. Explicit non-disclosure is `MISSING` with source evidence. Two different current
values produce a `FactConflict`. A dated amendment supersedes original terms for current selection
while both observations remain in the record.

## Trace and failure handling

Every material normalized output has an `ExtractionTrace` linking final field to observation IDs
and retrieval evidence IDs. `EvidenceReference` then links to chunk, document, page/section,
publisher, URL/path, publication date, and reliability. Derived EV adds its calculation string and
all input evidence.

Invalid model output, provider failure, unknown evidence, unsupported numeric/unit/period data,
and cross-transaction context have explicit exceptions. Individual normalization failures become
warnings and allow other facts to survive. `build_partial` turns extraction-level failure into an
error-bearing partial outcome rather than raising through a batch workflow.

## Evaluation

`evaluation/extraction_cases.json` defines seven synthetic gold cases. The evaluator reports field
accuracy, numeric accuracy, missing-value correctness, evidence-link accuracy, and conflict
detection separately. The fixture result is currently 1.00 on each metric. The corpus is designed
for regression coverage and cannot estimate production accuracy.

## Reuse

Project 1's bounded-context, provider-owned schema, evidence-catalog, and citation-validation
patterns were adapted. Project 4 uses its own transaction contracts and does not import Project 1.
Project 3's Decimal, exact-unit conversion, period/basis separation, dated capital inputs, and
calculation-trace patterns were adapted. No private Project 3 code is imported.

## Limitations

The fixture extractor is deterministic and the optional LangChain adapter is provider-neutral; no
live model configuration is shipped. Period syntax is intentionally limited. Source ranking is a
policy aid, not legal truth. Complex consortium changes, conditional payments, security-class
dilution, lease adjustments, tax effects, and complete transaction EV bridges remain outside M3.
