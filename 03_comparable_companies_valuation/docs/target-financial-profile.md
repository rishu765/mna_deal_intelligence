# Target financial profile and normalization

## Implemented M1 flow

```mermaid
flowchart LR
    Source[Manual fixture or Project 1 research] --> Observation[FinancialObservation]
    Observation --> Validate[Validate source semantics]
    Validate --> Name[Exact metric-name policy]
    Name --> Unit[Exact same-currency unit conversion]
    Unit --> Output[FinancialMetric or MarketMetric]
    Output --> Merge[TargetFinancialProfileService]
    Merge --> Conflicts[Conflict and duplicate metadata]
    Merge --> Completeness[Present / missing summary]
    Conflicts --> Profile[TargetFinancialProfile]
    Completeness --> Profile
```

`FinancialObservation` is the source-aligned fact. It retains the source's label, decimal value,
currency, unit text, period, as-of time, reported/adjusted basis, adjustment label, notes, quality
flags, and evidence. The observation is never overwritten by normalization.

`FinancialMetric` and `MarketMetric` are canonical internal observations. M1 records a
`NormalizationDecision` for each successful conversion, linking the source observation to the
output metric, name mapping, source and target unit, exact factor, policy version, and note.

## Target company

`TargetCompany` contains only valuation-relevant context: provider-neutral identity, optional
ticker/exchange/country, industry/sub-industry, `MM-DD` fiscal year-end, reporting currency,
short business description, customer type, business model, and source evidence. It is not a
replacement for Project 1 research or Project 2 enrichment.

## Metric-name policy

M1 uses documented exact synonyms, never fuzzy matching:

| Source labels | Canonical output | Important treatment |
| --- | --- | --- |
| Revenue, Net Revenue, Net Sales, Sales | Revenue | `Sales` records a review note |
| EBITDA | EBITDA | Source basis remains required |
| Adjusted EBITDA | EBITDA | Must be adjusted; retains adjustment label |
| EBIT | EBIT | Direct mapping |
| Operating Income | EBIT | Explicit V1 mapping with review note |
| Net Income, Net Profit | Net Income | Direct synonym policy |
| EPS, Earnings per Share | EPS | Must use `per_share` |
| Gross Profit | Gross Profit | Separate from revenue or EBITDA |
| Capex, Capital Expenditure(s) | Capex | Separate metric |
| Cash, Cash and Cash Equivalents | Cash and equivalents | Requires as-of time |
| Debt, Total Debt | Debt | Requires as-of time |
| Preferred Stock | Preferred stock | Requires as-of time |
| Minority / Non-controlling Interest | Minority interest | Requires as-of time |
| Diluted Shares Outstanding | Diluted end-of-period shares | Preferred future valuation share basis |
| Diluted Weighted Average Shares | Diluted weighted-average shares | Does not satisfy end-of-period requirement |

Unsupported labels become profile issues. They are not guessed or semantically collapsed.

## Unit and currency normalization

The canonical M1 scale is **million** for monetary metrics and share counts. Exact scale factors
are centralized:

| Source unit | Millions factor |
| --- | ---: |
| Units | 0.000001 |
| Thousand | 0.001 |
| Million | 1 |
| Billion | 1,000 |
| Lakh | 0.1 |
| Crore | 10 |

For example, INR 5 crore becomes INR 50 million. Currency never changes. M1 does not perform
FX conversion, and `per_share` values cannot be converted to monetary scales.

## Period, estimate, and basis semantics

`FinancialPeriod` validates typed FY, CY, LTM, NTM, and calendarized labels. `A` labels require
actual status; `E` labels require estimate status. Rolling periods require an end date. FY, LTM,
and NTM observations remain independent; the service does not select or replace one with another.

Reported and adjusted values remain different observations because basis is part of the
conflict key. Adjusted metrics require a label. Two different reported values for the same
metric, period, basis, and currency are both retained and flagged as conflicting.

## Capital structure and shares

M1 normalizes cash, debt, preferred stock, minority interest, and basic/diluted share counts with
their source as-of times. Share observations distinguish end-of-period from weighted-average
and basic from diluted. Later equity-value work should prefer diluted end-of-period shares;
weighted-average shares used for EPS are not silently substituted.

`TargetFinancialProfile.net_debt()` is the only M1 derived helper. It returns debt minus cash
only when exactly one non-conflicting debt and cash observation share currency, unit, and exact
as-of time. Otherwise it returns unknown (`None`). It does not calculate enterprise value.

## Missing data, conflicts, and partial results

The default completeness contract checks for revenue, EBITDA, cash, debt, and diluted
end-of-period shares. It reports named `present` and `missing` fields with `complete`, `partial`,
or `insufficient` status—never a fake confidence score. Missing observations remain absent;
zero is never inserted.

Malformed or unsupported observations become typed profile issues while valid observations
continue through the pipeline. Exact duplicate source observations are recorded and normalized
once. Conflicting values remain separate, retain their evidence, and receive the `conflicting`
quality flag.

## Evidence and serialization

Evidence retains source type/name/location, document and chunk IDs, positive page numbers,
excerpt, section/table context, publication/observation timestamps, and extraction method.
Normalized outputs retain source observation IDs. The complete profile has schema-versioned,
Decimal-safe JSON serialization and round-trips periods, enums, evidence, decisions, conflicts,
issues, and capital structure.

## Project 1 integration

`Project1TargetProfileProvider` uses structural protocols matching Project 1's public
`research(company_name=...)` result. It imports no Project 1 implementation module. It maps
structured financial-highlight metrics and citations into source observations, then calls the
same deterministic M1 service used by fixtures.

Project 1 can currently provide string-valued metric name/value, optional fiscal period, unit,
currency, basis, and document citations. It does not guarantee every valuation input, typed
period semantics, capital structure, consensus forecasts, share basis, or adjustment detail.
Incomplete Project 1 metrics become explicit issues. Fixtures/manual input therefore remain the
authoritative offline path for complete M1 examples.

## Offline fixture and demo

`data/targetco_profile.json` contains fictional source-aligned observations for FY2025A and LTM
June 2026 revenue/EBITDA plus cash, debt, and diluted end-of-period shares. The fixture provider
validates and normalizes it without credentials or network access.

Run:

```powershell
python -m ma_comparable_valuation.demo_profile
```

The demo prints raw observations, normalized metrics, capital structure, completeness, conflicts,
issues, and evidence IDs. It calculates no trading multiple or valuation.
