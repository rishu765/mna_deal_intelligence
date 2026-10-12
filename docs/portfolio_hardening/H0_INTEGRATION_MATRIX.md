# H0 Integration Matrix

**Audited revision:** `fdd91f8`

**Purpose:** Record actual interfaces and distinguish native execution from adapter, mock, and synthetic-fixture behavior.

## Classification

- **Native integration:** one project invokes another project's real implementation in the tested path.
- **Adapter integration:** a typed boundary translates a specialist result, but the producer may be injected or substituted.
- **Mocked integration:** a test double supplies the producer behavior.
- **Synthetic fixture:** committed representative data is returned or processed.
- **Unavailable/untested:** no supported or H0-exercised path.

## Project entry points and integration surfaces

| Project | Package / primary entry points | API/demo | Actual upstream/downstream surface | H0 status |
|---|---|---|---|---|
| 01 Company & Document Intelligence | `ma_company_intelligence`; ingestion, retrieval, RAG, research orchestrator | FastAPI; evaluation CLI; offline PDF path | Produces facts, observations, citations, and structured company research that could feed P3/P6 | Standalone native; cross-project adapter/mock only |
| 02 Target Screening & Sourcing | `ma_target_screening`; workflow and graph entry points | FastAPI; evaluation CLI; demo workflow | Produces screened/ranked targets and evidence that could feed P3/P6 | Standalone native over local fixtures; cross-project adapter/mock only |
| 03 Comparable Companies & Valuation | `ma_comparable_valuation`; valuation workflow | FastAPI; evaluation CLI; demo | Defines structural target/screening adapters; produces valuation ranges and basis metadata for P6 | Standalone native over synthetic providers; no real P1/P2 package composition |
| 04 Precedent Transactions | `ma_precedent_transactions`; final graph/workflow | FastAPI; evaluation and demos | Produces verified precedents, multiples, and ranges for P6 | Standalone native over synthetic corpus; P6 consumes fixture envelope |
| 05 AI Due Diligence | `ma_due_diligence`; VDR and graph workflow | FastAPI; evaluation and final demo | Produces reported/adjusted EBITDA, NWC, net debt, findings, and citations for P6 | Standalone native over fixture VDR; P6 consumes representative fixture |
| 06 Super-Agent | `ma_deal_intelligence`; registry, graph, API | FastAPI; final evaluation/demo | Canonicalizes P1–P5 output envelopes, plans dependencies, reconciles and synthesizes | Default fixture integration; injected native callables available but uncomposed |

## Project 6 capability registry

| Capability family | Adapter | Default mode | Default data/execution | Native executor included? | H0 classification |
|---|---|---|---|---|---|
| Document/company research | Project 1 adapter | `FIXTURE` | Generic representative facts/evidence | No | Synthetic fixture |
| Target screening | Project 2 adapter | `FIXTURE` | Synthesized representative candidate/ranking | No | Synthetic fixture |
| Trading comps valuation | Project 3 adapter | `FIXTURE` | Representative GBP valuation state | No | Synthetic fixture; unsafe request-basis mismatch verified |
| Precedent transactions | Project 4 adapter | `FIXTURE` | Representative deal/range payload | No | Synthetic fixture |
| Due diligence | Project 5 adapter | `FIXTURE` | Representative findings and adjusted finance | No | Synthetic fixture; unsafe target relabeling verified |

`NATIVE` adapter mode is implemented as a callable injection boundary. It is useful architecture, but no default repository factory imports and supplies Projects 1–5. Therefore it was **implemented but not verified** as real portfolio integration.

## Cross-project handoff matrix

| From → To | Intended payload | Actual implementation | Tests observed | Classification | Compatibility gap |
|---|---|---|---|---|---|
| P1 → P3 | Target profile and financial observations with citations | P3 structural adapter/protocol accepts substituted research data | Adapter fakes and standalone tests | Mocked adapter | No native package call; source metric, period, currency, unit, and citation invariants not tested together |
| P2 → P3 | Selected target and peer-screening context | P3 protocol accepts substituted screening data | Adapter fakes | Mocked adapter | Cross-provider identity/freshness not validated |
| P1 → P6 | Research facts, evidence, company identity | P6 Project 1 fixture adapter | Fixture adapter tests/demo | Synthetic fixture | Generic facts are not produced by P1 in the default run |
| P2 → P6 | Candidate identity, score, explanation, sources | P6 Project 2 fixture adapter | Fixture adapter tests/demo | Synthetic fixture | Candidate is synthesized; no live/local P2 workflow invocation |
| P3 → P6 | Trading-comps range and reported financial basis | P6 Project 3 representative fixture | Fixture adapter and reconciliation tests | Synthetic fixture | Request target/currency/date can differ silently from payload (H0-002) |
| P4 → P6 | Precedent range, deal set, evidence | P6 Project 4 representative fixture | Fixture adapter and synthesis tests | Synthetic fixture | Requested target/sector/date not bound to source deal set |
| P5 → P6 | Diligence findings, adjusted EBITDA/net debt, citations | P6 Project 5 representative fixture | Fixture adapter and reconciliation tests | Synthetic fixture | Fixture target can be replaced; native VDR provenance absent (H0-002) |
| P3 + P4 → P6 | Parallel valuation views | LangGraph fan-out/fan-in over fixture adapters | Graph tests and demo | Adapter integration over fixtures | Orchestration is real; specialist execution is simulated |
| P3 + P5 → P6 | Reported vs diligence-adjusted basis | Reconciliation over representative state | Unit/graph tests and demo | Synthetic fixture | No native source linkage; compatibility depends on fixture construction |

## Financial integrity traces

### P1 financial observation → P3 trading comps

**Current state:** unavailable as a native repository flow. P1 can produce typed observations with citations, and P3 can consume normalized target inputs through a protocol, but H0 found no composition command that transfers a real P1 result into P3.

**Required invariant:** original value and source reference remain immutable; metric name, period, currency, unit, reported/adjusted basis, and as-of date are explicit; P3 rejects ambiguity.

### P3 reported EBITDA → P6 valuation state

**Current state:** synthetic fixture. P6 represents reported EBITDA and valuation basis, but its default P3 adapter does not execute P3.

**Verified concern:** P6 can return its representative GBP/2025 valuation for an unrelated entity/EUR/2020 request without warning.

### P5 diligence-adjusted EBITDA → P6 reconciliation

**Current state:** synthetic fixture. Reconciliation distinguishes reported, adjusted, and selected bases, but the P5 result is not produced from the requested VDR.

**Required invariant:** adjustments retain finding IDs, evidence, period, currency, unit, review status, and no double counting.

### P4 precedent valuation → P6 unified view

**Current state:** synthetic fixture. P6 combines the range with the P3 range, but the precedent set is representative and is not selected for the requested target.

**Required invariant:** selected deals, value basis, announcement date, metric period, currency, unit, source, and exclusion rationale travel with the range.

### P5 adjusted net debt → P6 deal implications

**Current state:** synthetic fixture. Canonical fields exist; no native computation-to-state path is verified.

**Required invariant:** cash, debt, debt-like items, restricted cash, signs, currency, units, review decisions, and evidence reconcile to the final number.

## Contract compatibility

| Contract area | Current condition | Risk | H0 issue |
|---|---|---|---|
| Entity identity | Each project has typed IDs/names; no authoritative cross-provider resolution | Same company may be represented differently; fixture relabeling already fails | H0-002, H0-006 |
| Currency and units | Well modeled in P3/P6; not enforced in P5 NWC; fixture requests not bound | Material arithmetic or association error | H0-001, H0-002 |
| Financial period | P3/P4 model periods; cross-project calendarization untested | LTM/NTM or fiscal-period mismatch | H0-006 |
| Evidence/source refs | Strong local models; adapters translate representative evidence | Native lineage can be lost or fabricated by substitution | H0-002, H0-006 |
| Result envelopes | P6 has status/warnings/errors/mode/evidence | Useful boundary, but fixture warnings are insufficient | H0-002 |
| Staleness/recomputation | P6 models staleness and dependency invalidation | Tested with fixtures, not provider timestamps/native side effects | H0-003, H0-006 |
| Error model | Specialist local errors plus P6 envelope/failure isolation | Native exception mapping unverified | H0-003 |
| Versioning | Package versions are `1.0.0`; no cross-contract schema version | Future independent changes can drift | H0-006, H0-007 |
| Configuration | Six separate project configs and dependency sets | Integrated install/runtime drift | H0-010 |

## End-to-end classification

| Scenario | What H0 ran | Result | Classification |
|---|---|---|---|
| A. Document research | Generated five-page PDF → real P1 parser; P1 synthetic evaluation | Pass | Native offline ingestion + synthetic evaluation; live RAG untested |
| B. Target screening | Real P2 workflow over local candidate fixtures, including HITL resume | Pass | Native workflow over synthetic fixture data |
| C. Trading comps | Real P3 deterministic pipeline over synthetic provider data | Pass; hand arithmetic matched | Native calculation over synthetic fixtures |
| D. Precedent transactions | Real P4 graph/pipeline over synthetic deal/document corpus | Pass; hand arithmetic matched | Native workflow over synthetic fixtures |
| E. Due diligence | Real P5 VDR/graph pipeline over fixture documents | Pass; P0 NWC defect reproduced separately | Native workflow over synthetic fixtures |
| F. Integrated deal analysis | Real P6 graph with default P1–P5 fixture adapters | Pass for orchestration; unsafe basis mismatch reproduced | Adapter integration over synthetic fixtures, not native specialist integration |

## Shared-abstraction conclusion

H0 does not recommend extracting a shared package solely because projects repeat concepts such as money, periods, evidence, or entity IDs. H2 should first implement and test the narrow native handoffs. A shared abstraction is justified only if at least two real consumers require the same semantics and maintaining adapters creates demonstrated drift. Existing specialist implementations should remain owned by their projects.

## Integration verdict

Project 6 genuinely implements orchestration and reconciliation mechanics, but it does **not** currently invoke Projects 1–5 by default. The verified portfolio integration is fixture-backed adapter integration. Native integration, realistic identity resolution, and cross-project financial/evidence contract enforcement remain H2 work after the H1 P0 corrections.
