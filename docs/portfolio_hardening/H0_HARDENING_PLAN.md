# H0 Hardening Plan

**Audited revision:** `fdd91f8`

**Purpose:** Assign H0 findings to the locked H1–H3 roadmap. This document defines future work; it does not start remediation.

## Planning principles

1. Correct financial and evidence-integrity defects before expanding integration.
2. Build only the native handoffs needed for a credible portfolio flow.
3. Extract a shared abstraction only after two real consumers demonstrate identical semantics and adapter maintenance creates measurable drift.
4. Keep fixture demos for deterministic review, but label them explicitly and prevent cross-entity reuse.
5. Report synthetic and public-data evaluation results separately.

## Ordered milestone assignment

### H1 — Correctness and critical technical debt

| Order | Issue | Required result | Prerequisites |
|---:|---|---|---|
| 1 | H0-001 | Project 5 NWC analytics reject or explicitly normalize mixed currency/unit inputs; regression tests cover both mismatches | None |
| 2 | H0-002 | Project 6 fixture requests cannot receive or relabel finance for a different entity, currency, unit, or date; fixture mode is conspicuous | None |
| 3 | H0-004 (critical gate portion) | Project 1 known unanswerable/citation/support cases have explicit regression thresholds and named failures | None |

H1 should remain narrow. It should not add live providers, redesign models, create a shared package, or start broad portfolio integration.

### H2 — Integration, evaluation, and justified shared abstractions

| Order | Issue | Required result | Prerequisites |
|---:|---|---|---|
| 1 | H0-006 | Define and test the minimum entity/metric/period/currency/unit/evidence contracts for selected handoffs | H0-001, H0-002 |
| 2 | H0-003 | Compose one supported native/offline Projects 1–5 → Project 6 path using existing entry points | H0-006 |
| 3 | H0-007 | Add a bounded portfolio CI job for those contracts and native smoke paths | H0-003, H0-006 |
| 4 | H0-008 | Make Project 6 evaluation metrics run-derived or clearly label external test summaries | H0-003 |
| 5 | H0-012 | Expand Project 2 fully labeled ranking/exclusion cases and metric denominators | None |
| 6 | H0-004 (public validation portion) | Evaluate P1 citation/abstention on representative public documents | H0-004 H1 gate |
| 7 | H0-005 | Add the minimal public-data validation pack across the highest-value capabilities | H0-001, H0-002; native cases as applicable |
| 8 | H0-010 | Record a known-good reproducible dependency resolution for portfolio verification | H0-003 determines integrated set |

Potential shared abstraction review occurs only after items 1–2. A shared financial-basis or evidence type is justified if at least two native consumers require the same validation semantics and existing adapters duplicate those rules. Otherwise, keep translation at project boundaries.

### H3 — Cleanup and portfolio packaging

| Order | Issue | Required result | Prerequisites |
|---:|---|---|---|
| 1 | H0-009 | Make local-only API, confidentiality, checkpoint, serialization, and deployment boundaries prominent and safe | Final H1/H2 operating paths |
| 2 | H0-011 | Correct root CI/status text and align every README with verified behavior | H0-007 or explicit statement that it remains absent |
| 3 | H0-003/H0-005 documentation closure | Architecture diagrams and demos clearly distinguish native, adapter, and fixture execution and synthetic vs public results | H2 results |
| 4 | Portfolio cleanup | Remove only confirmed stale generated material, standardize commands, and prepare truthful project summaries | All checks stable |

## Effort and regression risk

| Issue | Priority | Effort | Regression risk | Affected projects | Prerequisite IDs |
|---|---|---|---|---|---|
| H0-001 | P0 | Small | Medium | 05 | None |
| H0-002 | P0 | Medium | Medium | 06; P3/P5 fixture outputs | None |
| H0-003 | P1 | Large | High | 01–06 | H0-002, H0-006 |
| H0-004 | P1 | Medium | Low | 01 | H0-005 for public portion |
| H0-006 | P1 | Large | High | 01–06 | H0-001, H0-002 |
| H0-007 | P1 | Medium | Low | 01–06 | H0-003, H0-006 |
| H0-005 | P2 | Large | Low | 01–06 | H0-001, H0-002 |
| H0-008 | P2 | Medium | Low | 06 | H0-003 |
| H0-009 | P2 | Medium | Medium | 01–06, mainly 05/06 | None |
| H0-010 | P2 | Medium | Medium | 01–06 | H0-003 |
| H0-012 | P2 | Medium | Low | 02 | H0-005 for public cases |

H0-011 is P3, small effort, and low regression risk.

## H1 acceptance gate

H1 passes only when all of the following are true:

- No verified P0 defect remains unresolved.
- Project 5 mixed-currency and mixed-unit NWC inputs fail closed or use explicit, evidenced normalization.
- Project 6 cannot associate representative fixture finance with an incompatible entity, currency, unit, period, or as-of date.
- Critical Project 1 abstention and citation regressions have explicit, non-inflated thresholds.
- All directly affected unit, integration, API, evaluation, Ruff, format, and mypy checks pass.
- Documentation identifies any remaining suspected or unverified evidence risk.

H0 does not declare this gate passed.

## H2 acceptance gate

H2 passes only when all of the following are true:

- Cross-project contracts for selected paths validate entity identity, source value, metric basis, period, currency, units, provenance, and timestamps.
- At least one documented Project 6 run invokes real specialist project entry points rather than all-default fixtures.
- Native partial failure, retry, staleness, and recomputation behavior is regression tested.
- Portfolio CI runs the supported contract/native smoke matrix from a clean environment.
- Evaluation metrics are reproducible and linked to run-produced observations.
- A small public-data pack validates the most credible document, screening, valuation, transaction, and diligence cases; synthetic and real metrics remain separate.
- Any shared abstraction has at least two proven consumers and reduces an observed contract inconsistency; otherwise no extraction occurs.
- A known-good dependency resolution is reproducible.

H0 does not declare this gate passed.

## H3 acceptance gate

H3 passes only when all of the following are true:

- The full configured test, lint, format, type, evaluation, and portfolio contract checks pass from documented commands.
- Root and project documentation accurately distinguish implemented, native, fixture, unverified, and intentional V1 behavior.
- Reproducible demos start from a clean environment and disclose their data/provider mode.
- Security and confidentiality boundaries match the actual deployment scope; local-only and trusted-checkpoint assumptions are explicit.
- Architecture diagrams reflect the final supported paths.
- Resume/project summaries make truthful claims about finance calculations, RAG, LangGraph/HITL, evaluation, and integration.
- Known limitations and any deferred issues are explicit.

H0 does not declare this gate passed.

## H2 public-data validation candidates

Keep this set deliberately small:

1. **Document research:** one public annual report with narrative, financial table, and an unanswerable query; assert page/claim provenance.
2. **Target screening:** a small frozen set of public company profiles with known identity collisions and dated financial sources.
3. **Trading comps:** one public peer set with a documented as-of date, currencies, units, periods, and hand-calculated EV/equity bridge.
4. **Precedents:** two public acquisition announcements with announcement/completion distinction, consideration, and independently verified deal value.
5. **Due diligence:** public contract exhibits or synthetic-redacted filings that permit evidence-based adjustment/review tests without confidential data.
6. **Integrated run:** one selected target whose specialist outputs share explicit identity and financial bases through Project 6.

## Deferred learning emphasis after H3

The later finance study should go deepest on calendarization, transaction-value basis, QoE adjustment evidence, working-capital peg design, net-debt/debt-like classifications, and deal-basis reconciliation. The later AI study should go deepest on retrieval evaluation, citation support, structured-output failure recovery, graph state semantics, secure durable HITL, native tool execution, and evaluation design. The full curriculum remains outside H0 scope.

## Stop condition

This plan completes H0 planning only. No H1 source-code correction, refactor, dependency change, or feature implementation is included in the audit branch.
