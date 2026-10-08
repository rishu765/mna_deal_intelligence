# Portfolio and interview guide

## Portfolio summary

Comparable Companies & Valuation Copilot builds auditable public-market comparable sets,
normalizes financial and market data, calculates trading multiples and valuation ranges
deterministically, and adds evidence-grounded AI-style explanations around peer selection,
outliers, and valuation drivers.

## Resume bullets

- Built a typed Python trading-comps workflow spanning target normalization, transparent peer
  selection, provider-neutral data ingestion, deterministic multiples, peer statistics, and
  implied valuation ranges.
- Implemented auditable EV/equity bridges and EV/Revenue, EV/EBITDA, EV/EBIT, and P/E calculations
  with strict period, currency, unit, and reported/adjusted-basis controls.
- Preserved end-to-end provenance through evidence references, calculation traces, explicit
  exclusions, IQR outlier flags, provider warnings, and Decimal-safe serialization.
- Added a constrained explanation layer that consumes calculated outputs without overriding
  financial math, plus a seven-subsystem, eight-case offline evaluation benchmark.
- Exposed the complete workflow through a minimal FastAPI API and credential-free reproducible
  demo, backed by 85 Project 3 tests and static quality checks.

## Interview story

1. **Business problem:** trading comps are widely used but easy to make unauditable when peer
   judgment, time periods, accounting bases, and data gaps are hidden.
2. **Why comps:** they provide current market reference points for similar listed companies, but
   should be interpreted as ranges rather than intrinsic truth.
3. **Peer selection:** the system starts from a retained universe, scores transparent dimensions,
   keeps semantic judgment advisory, and records exclusions and analyst overrides.
4. **Financial normalization:** source observations remain intact while normalized Decimal values
   retain currency, unit, period, actual/estimate, reported/adjusted basis, and evidence.
5. **EV versus equity:** equity belongs to common shareholders; EV adjusts equity for debt, cash,
   preferred stock, and minority interest where supported. The bridge signs are explicit.
6. **Trading multiples:** EV multiples pair enterprise value with operating denominators; P/E
   pairs equity value or price with net income or EPS. Non-positive denominators are not meaningful.
7. **Period consistency:** LTM, historical fiscal years, and estimates remain exact partitions.
   The engine never relabels an old fiscal number as LTM or pools reported and adjusted EBITDA.
8. **Peer statistics:** five-number summaries use documented Decimal type-7 percentiles. IQR
   outliers are flagged and retained, and small peer counts are surfaced.
9. **Implied valuation:** target metrics are multiplied by peer quartile/median anchors; EV ranges
   are bridged to equity and divided by compatible diluted shares when available. Methods remain
   separate.
10. **AI role:** assisted reasoning explains peers, outliers, relevance, differences, and caveats
    from structured results. Deterministic code remains the only numerical authority.
11. **Evaluation:** eight synthetic cases exercise seven subsystems separately, with exact gold
    arithmetic and failure behavior. The benchmark is intentionally described as limited.
12. **Limitations:** no licensed live feed, broad forecast coverage, FX/calendarization, DCF,
    sector-specific valuation, persistent API store, auth, UI, or production deployment.

## Reusable components

- immutable finance value objects with period/basis/provenance semantics;
- structural adapters for upstream project outputs;
- provider protocols and partial-safe snapshot ingestion;
- deterministic selection, normalization, multiple, percentile, bridge, and range services;
- evidence-aware JSON presentation and safe API errors; and
- fixture-first subsystem evaluation and offline explanation contracts.

Reuse should follow contract compatibility, not copy vendor assumptions or claim a shared package
before multiple projects genuinely need one.

## Concepts to know

- enterprise value versus equity value and bridge signs;
- diluted end-of-period versus weighted-average shares;
- LTM, fiscal-year, and forward-estimate period semantics;
- reported versus adjusted metrics and denominator consistency;
- EV/Revenue, EV/EBITDA, EV/EBIT, and P/E numerator logic;
- non-meaningful negative/zero denominators;
- percentile interpolation, IQR outliers, and small-sample caveats;
- evidence lineage, as-of timing, provider failure isolation, and Decimal precision; and
- why generative explanations must be downstream of deterministic financial calculations.

## Integration and Project 4 handoff

Project 1 supplies source-backed company/document facts through adapters, but Project 3 owns
valuation semantics and completeness. Project 2 supplies a screened target identity/profile, but
Project 3 owns comparable selection and valuation. Both integrations are optional and structural,
not a deployed end-to-end product.

A future Precedent Transactions Agent may reuse target identity, evidence/provenance, financial
normalization, valuation metric definitions, and range-output concepts. Transaction screening,
deal consideration, premiums, announcement dates, and transaction multiples are not implemented
or designed in Project 3.
