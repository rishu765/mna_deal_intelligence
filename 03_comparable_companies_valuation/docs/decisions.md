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

