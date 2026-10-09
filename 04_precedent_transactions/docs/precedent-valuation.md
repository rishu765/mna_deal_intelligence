# Comparable transaction selection and valuation

M4/5 consumes verified M3 records and produces an auditable precedent set, deterministic transaction
multiples, peer statistics, implied valuation ranges, and optional grounded commentary. It neither
orchestrates the full workflow nor exposes an API.

## Selection contract

Hard criteria are Python rules: completed status by default, announcement window, supported
transaction type, control/minority policy, usable EV or equity value, and same-currency revenue-size
band when data exists. Missing size data remains visible rather than becoming zero. Soft criteria
record business/product similarity, geography, and buyer type. The fixture provider uses token
overlap only for reproducibility; production semantic assessment can replace it through
`SoftComparabilityProvider` without changing deterministic filters.

Each deal receives `INCLUDE`, `EXCLUDE`, `SEPARATE`, or `REVIEW`, criterion-level outcomes,
rationale, missing data, evidence, and inherited M3 warnings. Default policy excludes minority and
partial-stake deals from control-acquisition statistics. An analyst can force include or exclude,
but must provide an actor, rationale, and aware timestamp. The original failed criteria remain in
the audit record.

## Numerators and denominators

The EV-based methods require disclosed or independently calculated transaction EV. Transaction P/E
requires disclosed or independently calculated equity purchase price. Headline values with an
ambiguous basis are unusable. A derived EV retains its M3 input evidence and is labeled derived.

The denominator must match the expected financial metric, preserve the exact FY/LTM and
historical/forecast label, pre-date the announcement, be no more than the configured 550 days old,
and share the numerator currency. Units are converted deterministically to millions. Reported and
adjusted metrics form separate sets. Zero or negative EBITDA, EBIT, and net income are not
meaningful multiples; missing data stays missing. No FX conversion occurs.

## Statistics and outliers

Sets are grouped by method, currency, period kind, and metric basis. The engine calculates count,
minimum, P25, median, P75, maximum, and mean with R7 linear interpolation. Exact-period differences
within an LTM or fiscal-year group create a warning. A documented 1.5×IQR rule flags extremes and
retains them by default. Configured exclusion is explicit and appears in the statistics warnings
and counts.

Sample warnings distinguish zero, one, and fewer than four valid observations. The output does not
manufacture a confidence interval or call the median fair value.

## Implied valuation and trace

Each compatible target metric is multiplied by P25, median, and P75. Methods and bases remain
separate. EV-based cases apply this bridge when the target snapshot is compatible:

`Equity value = Enterprise value - Debt - Preferred stock - NCI + Cash`

Debt and cash are required. Missing optional adjustments are identified. Currency mismatch makes
the bridge unavailable. A per-share result requires positive diluted end-of-period shares; a
weighted-average share count is intentionally rejected. Every result stores formula, policy,
inputs, evidence IDs, result, bridge trace, and warnings.

## AI boundary

An explanation provider sees structured selections, exclusions, statistics, ranges, and warnings.
The optional LangChain adapter uses model-native structured output and rejects evidence IDs outside
the deterministic result. Its prompt forbids arithmetic changes, invented facts, and invented
control premiums. Provider exceptions yield an unavailable explanation while the calculations
remain usable. Tests use deterministic fixtures and never call a model or network.

## Limitations

- Fixture business similarity is lexical and deliberately small.
- No historical FX, inflation, or market-regime normalization is supplied.
- Partial stakes are not grossed up.
- Exact-period warnings do not create artificial period equivalence.
- Sector-specific multiples, DCF, LBO, accretion/dilution, and merger models are outside scope.
- LangGraph, analyst workflow, final evaluation, and API are implemented in M6/7; frontend and
  deployment remain outside Project 4 V1.
