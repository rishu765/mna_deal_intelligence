# Trading comps valuation methodology

## Method boundary

Project 3 focuses on public comparable-company multiples. It does not implement DCF, precedent
transactions, accretion/dilution, LBO, purchase price allocation, merger modeling, or due
diligence. Multiple methods may eventually coexist elsewhere, but Project 3 does not blur them
into a generic valuation engine.

## Financial metric contract

A financial metric is not a bare float. The M0 contract, refined and implemented for target
profiles in M1, stores:

- stable metric ID and typed name;
- exact decimal value;
- three-letter ISO-style currency;
- explicit scale/unit (`units`, `thousand`, `million`, `billion`, `lakh`, `crore`, or
  `per_share`);
- a typed period with kind, label, actual/estimate status, and optional start/end dates;
- reported or adjusted basis;
- one or more evidence references;
- explicit data-quality flags.

Thus “INR 500 crore, FY2026A, reported,” “USD 45 million, LTM ending 30-Jun-2026,
adjusted,” and “INR 12.4 per share, FY2027E, forecast” are different values even before their
amounts are compared. Negative metrics are representable because they are important outlier
states; non-finite decimals are rejected.

## Period semantics

Supported contracts distinguish fiscal year (`FY`), calendar year (`CY`), last twelve months
(`LTM`), next twelve months (`NTM`), and calendarized periods. Actual and estimate status is a
separate dimension. Rolling periods require an end date; a start date, when supplied, must be
paired with an end date.

`FY2025 Revenue` is not automatically comparable with `LTM June 2026 Revenue`: the windows may
contain different months, seasonality, acquisitions, and accounting observations. A later
normalization service must either obtain compatible periods or create a documented calendarized
metric with transformation lineage. It may not relabel a value.

Likewise, `FY2025A`, `FY2026E`, and `FY2027E` must not be pooled silently. Future multiples may
be explicitly named `EV / LTM Revenue`, `EV / NTM Revenue`, or `EV / FY2027E EBITDA` only when
numerator timing and denominator semantics satisfy policy.

## Market-data as-of policy

Every share price, market capitalization, diluted share count, debt, cash, preferred stock,
minority interest, and other bridge input has a timezone-aware `as_of` timestamp and evidence.
A `CapitalStructure` and `EnterpriseValueSnapshot` also carry an as-of time and policy ID.

M2/3 snapshot ingestion enforces disclosed stale-market and capital-structure alignment
tolerances: a stock price cannot silently combine with an incompatible balance-sheet date.
“Latest” is not a stable valuation date. Stale or mismatched values remain visible and flagged;
M4/5 will decide whether a multiple is usable.

## Equity value and enterprise value

The baseline V1 convention is intended to be:

```text
Equity Value = share price × diluted shares outstanding

Enterprise Value = Equity Value
                 + debt
                 + preferred stock
                 + minority interest
                 - cash and cash equivalents
```

This is a policy, not a universal truth. Availability and transaction context may require
treatment of leases, pension deficits, investments, non-controlling interests, or other items.
The eventual calculation must name its policy, retain every included/excluded component, and
record missing items. M2/3 ingests the inputs and lineage but performs no bridge arithmetic.

## Future multiple definitions

| Multiple | Numerator | Denominator | Compatibility rule |
| --- | --- | --- | --- |
| `EV / Revenue` | Enterprise value | Revenue | Enterprise-value-compatible operating metric; explicit period/basis |
| `EV / EBITDA` | Enterprise value | EBITDA | Enterprise-value-compatible operating metric; reported/adjusted basis must be consistent |
| `EV / EBIT` | Enterprise value | EBIT | Enterprise-value-compatible operating metric; explicit period/basis |
| `P / E` | Equity value or price | Net income or EPS on the matching definition | Equity-holder metric and share basis must align |

`Market Cap / EBITDA` is conceptually mismatched because market capitalization excludes debt
and other claims while EBITDA is pre-financing. Any nonstandard multiple would require a new,
explicit definition and rationale rather than reuse one of these labels.

The `MultipleDefinition` contract binds numerator family, denominator metric, and result basis.
The future `TradingMultiple` will retain numerator and denominator IDs, raw values, calculation
policy, status, and any exclusion reason.

## Reported versus adjusted

Reported and adjusted values are separate metric bases. A peer set must not silently compare
Company A adjusted EBITDA with Company B reported EBITDA. A later normalization policy will:

1. preserve the raw disclosed values;
2. identify each adjustment and supporting evidence;
3. choose a consistent peer-set basis where possible;
4. require review for judgmental adjustments; and
5. expose residual inconsistencies as quality flags.

AI may identify likely adjustment topics from filings, but deterministic/human-approved policy
creates the normalized value.

## Currency and unit safety

No comparison or arithmetic is allowed across incompatible currencies. M1 deterministically
normalizes supported scales within the same currency to millions and records the source unit,
target unit, factor, policy, and source observation ID. Thus INR crore may become INR million,
but never USD million. A future FX conversion must additionally record source value, target
currency, FX rate, FX observation date, rate source, rounding policy, and a derived metric ID.

## Outlier and missing-data policy

Raw observations are never silently dropped. Future multiple observations will have an explicit
status and treatment reason.

- Negative or zero EBITDA makes `EV / EBITDA` non-meaningful for conventional peer statistics;
  retain the raw inputs and mark the multiple excluded.
- Negative or zero earnings similarly makes conventional `P / E` non-meaningful.
- Extreme positive multiples remain visible; policy may include, winsorize, or exclude them only
  with a recorded threshold and reason.
- Stale market data, mismatched periods/bases, missing inputs, and incompatible currencies/units
  produce explicit quality or exclusion states.
- “N/M” is a presentation state, not permission to erase the observation.

## Peer statistics

The planned deterministic summary is minimum, 25th percentile, median, 75th percentile, and
maximum, with mean only when useful and clearly labeled. Sample size, included observations,
excluded observations, interpolation convention, and policy version accompany every statistic.

Median and interquartile anchors are common because peer multiple distributions are often
skewed and small samples make the mean sensitive to extremes. They are not immune to poor peer
selection or data quality; the raw distribution and outlier decisions remain auditable.

## Implied valuation and range

An enterprise-value example is:

```text
Target LTM EBITDA × selected peer EV / LTM EBITDA = implied enterprise value
Implied enterprise value + target equity bridge = implied equity value
Implied equity value / target diluted shares = implied per-share value
```

The actual equity bridge reverses the named enterprise-value convention using target capital
structure. Every output retains the target metric ID, peer-statistic ID, formula/policy version,
bridge component IDs, and calculation time.

The 25th percentile, median, and 75th percentile can form low, midpoint, and high cases on one
consistent basis. A range communicates market dispersion and modeling uncertainty; it does not
claim that every value inside is equally likely or that the midpoint is intrinsic value.

## Evidence lineage

Source observations point to `EvidenceReference` objects containing provider/source identity,
document/chunk/page metadata where available, observation/retrieval times, and excerpts.
Derived values record their input IDs and method/policy version. For example, a future
`14.2x EV/EBITDA` must resolve to the enterprise-value snapshot, EBITDA metric, period, bases,
underlying sources, and calculation method. Narrative cites those authoritative objects rather
than restating uncited numbers.
