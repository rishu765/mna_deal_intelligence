# Trading multiples, valuation ranges, and grounded reasoning

## Implemented M4/5 flow

`ValuationEngine` consumes an M1 `TargetFinancialProfile` and an M2/3 `PeerSet`. It produces
auditable equity and enterprise values, strict-period trading multiples, peer statistics,
method-specific implied ranges, target EV-to-equity bridges, and per-share values. It performs
all arithmetic with `Decimal` and runs offline.

The output keeps methods separate. It does not average EV/Revenue, EV/EBITDA, EV/EBIT, and P/E
into a composite value.

## Equity value and enterprise value

The V1 formulas are:

```text
Equity Value = Share Price * Diluted End-of-Period Shares

Enterprise Value = Equity Value
                 + Debt
                 + Preferred Stock
                 + Minority Interest
                 - Cash and Cash Equivalents
```

Share price and diluted shares must be unique, non-conflicting, and within the configured date
tolerance. Weighted-average EPS shares are not accepted as end-of-period shares. Debt and cash
are required for EV. Preferred stock and minority interest are included when supplied; when
absent they are explicitly listed as omitted and a warning is carried into the result. Missing
required components produce an unavailable result rather than a fabricated zero.

All monetary inputs must share a currency. Supported same-currency scales are normalized before
arithmetic. No FX conversion occurs.

## Supported multiples and period semantics

V1 supports:

| Multiple | Numerator | Denominator |
| --- | --- | --- |
| EV/Revenue | deterministic enterprise value | revenue |
| EV/EBITDA | deterministic enterprise value | EBITDA |
| EV/EBIT | deterministic enterprise value | EBIT |
| P/E | share price | EPS, per share |

Every `MultipleRequest` names an exact denominator period label and reported/adjusted basis.
`LTM Jun-2026`, `FY2027E`, and any other period remain distinct. A missing forecast is an
explicit missing-input observation; historical data is never relabeled as a forecast. Reported
and adjusted observations are calculated in separate sets.

Zero or negative EBITDA, EBIT, net income, or EPS is retained as a raw denominator but marked
`not_meaningful`. Missing, duplicate, conflicting, stale, currency-incompatible, or otherwise
unusable inputs are marked `missing_input` or `excluded` with a reason.

## Statistics and outliers

Each multiple set reports valid count, excluded count and reasons, minimum, 25th percentile,
median, 75th percentile, maximum, and mean. Percentiles use Hyndman-Fan type 7 linear
interpolation:

```text
position = (n - 1) * p
result = lower_value + fractional_position * (upper_value - lower_value)
```

With at least four valid observations, the default policy flags values outside
`Q1 - 1.5 * IQR` and `Q3 + 1.5 * IQR`. Flagged observations remain in statistics by default.
An explicit policy can exclude them; the IDs, rule, count, and warning remain visible. Fewer
than three valid peers triggers a low-count warning.

## Implied valuation and target bridge

The range policy uses the 25th percentile, median, and 75th percentile as low, mid, and high:

```text
Implied EV = Target Operating Metric * Selected Peer Multiple
Implied Equity Value = Implied EV - Debt - Preferred - Minority Interest + Cash
Implied Per-Share Value = Implied Equity Value / Diluted End-of-Period Shares
```

P/E with EPS directly implies share price. P/E with net income is supported by the domain
definition as an equity-value method when requested with that definition. An incomplete target
bridge preserves the implied EV but leaves equity and per-share values unavailable.

Every result has a formula, policy ID, input IDs, evidence IDs where applicable, raw values,
dates, currency/unit semantics, and warnings.

## Deterministic versus AI-assisted behavior

`ValuationExplanationProvider` receives an already-calculated `ValuationOutput`. It may assess
peer quality, explain exclusions/outliers, discuss method relevance, interpret range dispersion,
and list risks. It cannot mutate any numeric object.

`FixtureValuationExplanationProvider` is the deterministic offline test/demo implementation.
Provider failure is caught and represented as an unavailable explanation while calculations
remain intact. A live LLM provider is not selected in M4/5.

## Demo

```powershell
python -m ma_comparable_valuation.demo_valuation
```

The fixture has five peers: ordinary observations, a high-multiple peer, a negative-profit peer,
and a missing-data peer. It demonstrates equity/EV, exclusions, historical and forecast
multiples, statistics, ranges, the target bridge, per-share value, traces, and offline
analyst-style explanation.

## Limitations

- No FX conversion or calendarization.
- No live market, consensus, or LLM provider.
- Stale price policy is conservative; an unavailable numerator is not overridden.
- Preferred stock and minority interest absence is disclosed but cannot prove the economic
  balance is zero.
- Current V1 multiple set is not designed for financial institutions or sector-specific metrics.
- The method reflects market-relative valuation and peer selection; the median is not true or
  intrinsic value.
- M6 API, evaluation framework, deployment, and final V1 polish are not implemented.
