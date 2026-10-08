# M6 evaluation framework

## Purpose

The evaluation suite is a small regression benchmark for Project 3 V1. It measures distinct
subsystems rather than hiding strengths and weaknesses in one score. The cases and expected
behaviors are synthetic/public-safe; passing them does not prove production or market accuracy.

## Curated cases

`evaluation/datasets/m06_cases.json` defines eight scenarios:

1. profitable software with meaningful EV and equity methods;
2. high-growth software with negative EBITDA;
3. an industrial company with debt and an EV/equity bridge;
4. mixed reported and adjusted EBITDA that must not be pooled;
5. stale or missing market data;
6. incomplete target capital structure;
7. forward estimates with exact forecast labels; and
8. negative earnings with no meaningful P/E.

Each record describes expected behavior, not a claimed real-company valuation.

## Subsystem checks

| Subsystem | What is checked |
| --- | --- |
| Target financial profile | gold Revenue, EBITDA, EBIT, Net Income, EPS, Cash, Debt, and Shares; normalization; periods/basis; conflicts; evidence |
| Comparable selection | strong-peer overlap, obvious exclusion, insufficient-data treatment, rationale, manual override |
| Data ingestion | timestamps, sources, periods, currency/unit consistency, missing fields, provider failure isolation |
| Trading multiples | exact EV/Revenue, EV/EBITDA, EV/EBIT, P/E arithmetic; non-positive denominator; semantic partitioning |
| Peer statistics | min, type-7 quartiles, median, max, and transparent IQR flags |
| Implied valuation | implied EV, equity bridge signs, per-share value, and separate multi-method output |
| AI explanation | evidence references, number consistency, peer/outlier discussion, weak-set caveats, and non-authority |

The AI rubric is deterministic in CI. A live LLM judge can be added outside the correctness
baseline, but V1 neither requires nor trusts one to validate arithmetic.

## Percentile reference

For sorted values `x` and percentile `p`, V1 uses Hyndman–Fan type 7: index
`h = (n - 1) × p`, then linearly interpolates between `floor(h)` and `ceil(h)` using Decimal
arithmetic. Outliers use Tukey fences `Q1 - 1.5 × IQR` and `Q3 + 1.5 × IQR` with at least four
valid observations. Outliers remain in statistics unless an explicit policy says otherwise.

## Running and artifacts

```powershell
.\.venv\Scripts\python.exe -m ma_comparable_valuation.evaluation_cli
```

The command validates the dataset, runs all checks, rewrites
`evaluation/baselines/m06_offline_report.json` and `.md`, and exits nonzero on failure. The JSON
contains individual expected/actual results; the Markdown is the concise review report.

Current baseline: 8 cases and 33/33 passing checks across seven independently reported
subsystems. Representative failures are empty because the baseline passes; each subsystem still
states its principal limitation.

## Known evaluation limits

- Controlled INR fixtures do not cover arbitrary issuer disclosures, currencies, or accounting
  regimes.
- Five candidate peers do not establish general peer-selection quality.
- Provider failures are simulated, not live outages.
- Exact arithmetic coverage does not validate source-data correctness.
- Small peer sets make quartiles sensitive even when interpolation is correct.
- The target fixture cannot produce every method because it intentionally lacks some target
  metrics.
- The offline explanation fixture tests structure and grounding, not stylistic quality.
