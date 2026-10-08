# Architecture decision record

## P3-001 — Focus V1 on public trading comps

- **Status:** Accepted in M0
- **Decision:** Project 3's valuation method is comparable public-company analysis.
- **Why:** A narrow method makes input, formula, evidence, and evaluation boundaries teachable
  and auditable. DCF and transaction/deal models have materially different assumptions.

## P3-002 — Make deterministic code authoritative for numbers

- **Status:** Accepted in M0
- **Decision:** Only deterministic services calculate EV/equity value, multiples, statistics,
  implied values, and ranges. AI remains advisory and grounded.
- **Why:** Financial arithmetic must be reproducible, testable, and traceable to source inputs.

## P3-003 — Preserve financial semantics in domain values

- **Status:** Accepted in M0
- **Decision:** Store decimals with currency, unit, typed period, actual/estimate status,
  reported/adjusted basis, evidence, and quality flags.
- **Why:** Bare numbers permit invalid comparisons and erase the meaning needed for review.

## P3-004 — Treat market timing as part of the value

- **Status:** Accepted in M0
- **Decision:** Market metrics and capital-structure snapshots require timezone-aware as-of
  timestamps. Later policy will enforce compatibility tolerances.
- **Why:** Market values move while balance-sheet components update at different frequencies;
  silently mixing dates creates a false snapshot.

## P3-005 — Make capital-structure policy explicit

- **Status:** Accepted in M0
- **Decision:** Use a documented baseline EV bridge while retaining a policy ID and component
  lineage for leases, pensions, minority interest, and other contextual treatments.
- **Why:** No single enterprise-value formula is universally correct for all datasets and uses.

## P3-006 — Retain peer and outlier decisions

- **Status:** Accepted in M0
- **Decision:** Preserve the universe, selected and rejected peers, raw values, decision
  rationales, evidence, and exclusion/treatment reasons.
- **Why:** Auditability requires answering why a company or observation affected the range.

## P3-007 — Use fixture-first, credential-free validation

- **Status:** Accepted in M0
- **Decision:** Future core tests and the default demo use controlled versioned fixtures; live
  sources are isolated adapters and never required by CI.
- **Why:** Valuation correctness must be reproducible without API keys, vendor drift, or markets
  moving during a test.

## P3-008 — Integrate Projects 1 and 2 through adapters

- **Status:** Accepted in M0
- **Decision:** Map supported public outputs into Project 3-owned models; do not import their
  private implementation modules or make either project mandatory.
- **Why:** Each project remains understandable, independently installable, and evolvable.

## P3-009 — Do not create a shared package yet

- **Status:** Accepted in M0
- **Decision:** Reuse established patterns conceptually without extracting `shared/` code.
- **Why:** Similar evidence and money objects have different consumers and invariants. Concrete
  cross-project runtime reuse has not yet justified migration risk.

## P3-010 — Do not introduce LangGraph in M0

- **Status:** Accepted in M0
- **Decision:** Begin with domain contracts, ports, and ordinary future services.
- **Why:** M0 has no implemented stateful routing, retry, tool loop, or human-review workflow.
  Orchestration must solve a demonstrated later need rather than define the architecture.

## P3-011 — Use explicit versioned serialization

- **Status:** Accepted in M0
- **Decision:** Serialize decimals as strings and enums/dates as stable textual values under a
  schema version.
- **Why:** Round trips remain precise and inspectable without making API schemas the domain
  source of truth.

## P3-012 — Separate source observations from normalized metrics

- **Status:** Accepted in M1
- **Decision:** Preserve each `FinancialObservation` and create a linked canonical metric plus
  `NormalizationDecision`; never mutate the source-aligned fact.
- **Why:** Analysts must be able to audit label mappings, scale conversion, and rejected facts.

## P3-013 — Normalize scales to millions without FX

- **Status:** Accepted in M1
- **Decision:** Convert units/thousands/billions/lakh/crore deterministically into millions while
  preserving currency. Keep EPS as per-share.
- **Why:** One scale simplifies later deterministic calculations without fabricating an exchange
  rate or date.

## P3-014 — Preserve conflicts and partial profiles

- **Status:** Accepted in M1
- **Decision:** Keep different same-basis values, flag them, and continue processing unrelated
  valid observations. Report named missing fields rather than filling zeros.
- **Why:** Source disagreement and missing data are valuation risks, not parsing failures or
  evidence for a default value.

## P3-015 — Distinguish share-count bases

- **Status:** Accepted in M1
- **Decision:** Represent basic/diluted and end-of-period/weighted-average share observations
  explicitly. Completeness requires diluted end-of-period shares by default.
- **Why:** Weighted-average EPS shares are not automatically suitable for point-in-time equity
  value.

## P3-016 — Adapt Project 1 through structural public output

- **Status:** Accepted in M1
- **Decision:** Map Project 1 research metrics/citations through a structural protocol into M1
  observations, then use the same normalization service as fixtures.
- **Why:** This reuses evidence-backed document research without deep imports or assuming Project
  1 emits complete valuation-ready data.

## P3-017 — Keep selection scoring transparent and non-authoritative

- **Status:** Accepted in M2/3
- **Decision:** Use versioned, weighted criterion results with visible pass/fail/unknown outcomes.
  Required deterministic failures control exclusion; semantic scores are advisory inputs.
- **Why:** A user must be able to reconstruct why one peer was included and another was not.

## P3-018 — Make analyst overrides explicit records

- **Status:** Accepted in M2/3
- **Decision:** Force-include and force-exclude actions require analyst, time, and rationale and
  retain the underlying automated evaluation.
- **Why:** Judgment is legitimate in comps, but an override must not erase the original evidence.

## P3-019 — Prefer partial snapshots to provider-wide failure

- **Status:** Accepted in M2/3
- **Decision:** Isolate financial, forecast, and market provider failures per peer and record
  missingness, conflicts, staleness, and period alignment as typed flags/issues.
- **Why:** One missing source should not discard otherwise reviewable peer data.

## P3-020 — Defer a live provider until a responsible source is available

- **Status:** Accepted in M2/3
- **Decision:** Ship provider ports and offline implementations, but no brittle unauthenticated
  scraper or hidden-key dependency.
- **Why:** Reproducibility, licensing, rate limits, and time-consistent data matter more than a
  nominal demo integration that cannot support reliable valuation inputs.
## P3-014 — Keep deterministic arithmetic authoritative

- **Status:** Accepted in M4/5
- **Decision:** Only `ValuationEngine` calculates values, multiples, percentiles, bridges, and
  ranges. Explanation providers receive immutable calculated output and cannot alter it.
- **Why:** Narrative generation must not rewrite reproducible math.

## P3-015 — Distinguish required and optional EV bridge fields

- **Status:** Accepted in M4/5
- **Decision:** Share price and diluted end-of-period shares are required for equity value; debt
  and cash are required for EV. Preferred stock and minority interest are included when sourced,
  while absence is explicitly disclosed as omitted.
- **Why:** Required claims cannot be silently assumed to be zero; optional V1 fields remain
  visible without making every otherwise-complete snapshot unusable.

## P3-016 — Partition multiples by exact semantics

- **Status:** Accepted in M4/5
- **Decision:** Partition observations by exact period label, denominator metric, and
  reported/adjusted basis. Never relabel historical values or pool bases.
- **Why:** LTM, fiscal-year estimates, and accounting bases are different observations.

## P3-017 — Use transparent percentiles and outliers

- **Status:** Accepted in M4/5
- **Decision:** Use Decimal Hyndman-Fan type 7 interpolation. Flag Tukey 1.5-IQR outliers when
  at least four observations exist and retain them by default. Optional exclusion is versioned
  and auditable.
- **Why:** The policy is deterministic and avoids silently deleting extreme market observations.

## P3-018 — Keep valuation methods separate

- **Status:** Accepted in M4/5
- **Decision:** Use the 25th percentile, median, and 75th percentile as low, mid, and high for
  each method independently. Do not average methods automatically.
- **Why:** Interquartile anchors communicate dispersion without claiming a single true value.
