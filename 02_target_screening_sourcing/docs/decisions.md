# Architecture decision record

## P2-001 — Separate target sourcing from document intelligence

- **Status:** Accepted in M0
- **Decision:** Keep Project 2 as an independently installable package.
- **Why:** Project 1 begins with a known company and documents; Project 2 begins with a thesis
  and must discover and compare companies. Combining them would blur ownership and release
  cycles.

## P2-002 — Discovery belongs to Project 2

- **Status:** Accepted in M0
- **Decision:** Put search/database/list adapters behind a Project 2 `DiscoveryProvider`.
- **Why:** Discovery query planning, source coverage, candidate identity, and source provenance
  are target-sourcing concerns, not document parsing or retrieval concerns.

## P2-003 — Separate deterministic screening from LLM reasoning

- **Status:** Accepted in M0
- **Decision:** Evaluate exact constraints and defined formulas in deterministic services;
  reserve model-backed components for ambiguous interpretation and qualitative fit.
- **Why:** Thresholds and exclusions must be reproducible and testable. Semantic judgments need
  evidence, structured output, uncertainty, and human review rather than control over hard
  filters.

## P2-004 — Defer LangGraph until M6

- **Status:** Accepted in M0
- **Decision:** Do not add LangGraph or agents before the underlying M1–M5 services exist.
- **Why:** Orchestration should coordinate stable capabilities. Introducing it now would encode
  speculative workflow and obscure ordinary service boundaries.

## P2-005 — Delay shared extraction until reuse is proven

- **Status:** Accepted in M0
- **Decision:** Do not create `shared/` or relocate Project 1 code in M0.
- **Why:** Patterns are reusable now, but a second concrete runtime consumer and stable common
  contract do not yet exist. Premature extraction risks destabilizing Project 1.

## P2-006 — Integrate Project 1 through an enrichment port

- **Status:** Accepted in M0
- **Decision:** Project 2 depends on `CompanyResearchProvider`; a later adapter will call a
  supported Project 1 facade or API and map results into `CandidateProfile`.
- **Why:** This preserves dependency direction, permits isolated tests, and prevents Project 2
  from importing Project 1 storage, prompts, provider adapters, or transport schemas. The exact
  in-process/API mechanism remains an M3 decision because Project 1 lacks a dedicated
  cross-project enrichment contract today.

## P2-007 — Model criterion consequence and evaluation method independently

- **Status:** Accepted in M1
- **Decision:** Give each criterion a hard/soft/exclusion requirement, a typed value and
  operator, and a separate deterministic/semantic evaluation method.
- **Why:** A qualitative criterion is commonly a soft preference but those concepts are not
  synonyms. Separate axes let M4 enforce measurable constraints while M5 evaluates qualitative
  fit without a class hierarchy or untyped strings.

## P2-008 — Preserve financial comparison basis; defer conversions

- **Status:** Accepted in M1
- **Decision:** Retain decimal amount, currency, display unit, and period on every financial
  bound and require both range bounds to share that basis.
- **Why:** Silent currency or period comparisons are unsafe. FX, unit, and period normalization
  require explicit market-data and accounting policies outside M1.

## P2-009 — Use versioned explicit JSON serialization

- **Status:** Accepted in M1
- **Decision:** Serialize decimals as strings and criterion values as typed payload objects
  under schema version 1.
- **Why:** This is precise, inspectable, dependency-free, and suitable for later API adapters
  without making transport schemas the domain source of truth.

## P2-010 — Ship credential-free providers before a live search adapter

- **Status:** Accepted in M2
- **Decision:** Implement a deterministic local JSON provider and typed user-supplied longlist
  provider behind the same discovery protocol; do not claim a live provider.
- **Why:** They provide practical sourcing paths, reproducible CI, and a stable adapter contract
  without choosing a paid API or introducing network-dependent tests prematurely.

## P2-011 — Generate transparent bounded queries without an LLM

- **Status:** Accepted in M2
- **Decision:** Combine discovery-relevant thesis industries, capabilities, geographies, and
  customer types deterministically under explicit limits.
- **Why:** Query intent stays inspectable, tests remain reproducible, and M2 does not need an
  autonomous or model-backed search loop.

## P2-012 — Deduplicate only on strong identity signals

- **Status:** Accepted in M2
- **Decision:** Merge exact provider IDs, exact normalized domains, or exact normalized
  name/alias keys without conflicting countries. Preserve all evidence.
- **Why:** Conservative merging reduces obvious duplicates without collapsing vaguely similar
  companies or pretending to solve entity resolution.

## P2-013 — Adapt Project 1 output without a runtime package dependency

- **Status:** Accepted in M3
- **Decision:** Define structural protocols for Project 1's public research output and map that
  output into Project 2 claims. Do not import Project 1's internal retrieval or provider code.
- **Why:** Project 1 remains independently configured and already exposes a stable composition
  facade and structured result. The structural boundary supports in-process composition and
  isolated tests without a monorepo-wide refactor.

## P2-014 — Keep facts, inferences, unknowns, and conflicts distinct

- **Status:** Accepted in M3
- **Decision:** Store observed claims, analytical interpretations, explicit gaps, and competing
  evidence-backed values as separate profile objects.
- **Why:** Later filters must not treat an inference as a fact or silently select one side of a
  source conflict. This preserves auditability and makes missing-data behavior explicit.

## P2-015 — Merge enrichment conservatively

- **Status:** Accepted in M3
- **Decision:** Deduplicate identical claims, retain all evidence, flag conflicting scalar or
  same-period financial values, and degrade profile completeness instead of resolving truth.
- **Why:** Source reconciliation needs policies and domain context beyond M3. Preserving the
  alternatives is safer than overwriting stronger evidence or inventing consensus.
