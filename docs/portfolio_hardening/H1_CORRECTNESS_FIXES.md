# H1 Correctness and Critical Technical-Debt Fixes

**Date:** 2026-10-13

**Base revision:** `9364e9b` (`origin/main`, merged H0 audit)

**Branch:** `fix/portfolio-h1-critical-correctness`

**Scope:** Verified H0 P0 defects and the H1 portion of one evidence-critical P1 gap. H2 integration and real-data evaluation work is deferred.

## Selected H1 issue set

| Issue | Project | Root cause | H1 acceptance | Regression risk | H1 status |
|---|---|---|---|---|---|
| H0-001 | 05 | NWC values were aggregated before checking currency and unit compatibility | Mixed currency/unit history cannot produce a numeric trend or peg; same-basis behavior remains unchanged | Medium | **FIXED** |
| H0-002 | 06 | Fixture adapters replaced caller identity while retaining representative financial outputs and did not bind requests to the fixture scenario | Incompatible entity, currency, date, engagement, or VDR inputs cannot return relabeled Project 3/5 fixture results; fixture mode is explicit | Medium | **FIXED** |
| H0-004, critical-gate portion | 01 | Known abstention and citation failures were measured but could regress without failing an executable check | Evidence-critical metrics have modest minimum floors and new critical failure cases fail the benchmark command | Low | **PARTIALLY FIXED**; public-data evaluation remains H2 |

No saved Antigravity issue adjudication was found in the repository. The merged and reproduced H0 shortlist therefore remained the controlling scope.

## Fixes implemented

### H0-001 — Project 5 NWC basis safety

`financial/analytics.py` now applies one basis-compatibility check to known NWC results before calculating trend statistics or a peg.

- Mixed currencies add `MIXED_CURRENCIES` and return no average, median, variance, normalized peg, current peg value, or surplus/shortfall.
- Mixed units add the new explicit `MIXED_UNITS` warning and fail closed in the same way.
- Original period results, period labels, currency, unit, warnings, and evidence-bearing calculation lines remain available for review.
- Same-currency and same-unit fixtures retain the existing Decimal calculations.

#### Before and after

| Input | Before H1 | After H1 |
|---|---|---|
| `10 GBP million`, `100 USD thousand` | Average/peg `55`, labeled `GBP million`, no warning | No numeric trend or peg; both currency and unit incompatibilities are reported |
| Same currency, mixed million/thousand | Raw numbers averaged directly | No numeric trend or peg; `MIXED_UNITS` warning |
| Existing same-basis fixture | Deterministic trend and peg | Unchanged deterministic trend and peg |

### H0-002 — Project 6 fixture identity and basis safety

`BaseAdapter` now has a shared fixture-validation hook. Fixture constraints participate in `validate_input`, so unsafe calls fail before a fixture payload is created or ingested.

Project 3 fixture execution now requires:

- exact fixture target identity;
- requested reporting currency equal to the currencies on the fixture metrics and valuations;
- requested as-of date equal to the valuation dates.

Project 5 fixture execution now requires:

- exact fixture target identity;
- exact fixture engagement;
- exact fixture VDR document set.

Both adapters now return their specialist fixture payload unchanged. The previous `replace(..., target_entity_id=request.target_entity_id)` mutations were removed.

Every fixture adapter result also carries a low-severity `FIXTURE_DATA` warning. This makes fixture execution visible even when a caller supplies its own execution ID.

The planning and API demo fixture context now uses the representative Northstar entity, GBP basis, and 2025-12-31 valuation date. This aligns the request with the source fixture instead of weakening validation.

#### Before and after

| Request | Before H1 | After H1 |
|---|---|---|
| Other entity, EUR, 2020 through Project 3 adapter | Northstar GBP/2025 range returned under caller target, no warning | Validation failure naming target, currency, and date mismatches |
| Other entity/engagement/VDR through Project 5 adapter | Northstar diligence payload retagged to caller target | Validation failure; original payload is never returned |
| Incompatible API valuation request | Could present the Project 3 fixture as caller finance | Project 3 capability is failed and trading-comps fixture valuation is excluded |
| Compatible offline demo | Successful fixture result could look native | Successful-with-warnings result includes `FIXTURE_DATA` |

### H0-004 — Project 1 evidence quality gate

The deterministic Project 1 evaluation now runs a small evidence-quality gate after producing its report. The CLI exits nonzero when the gate fails and includes structured violations in its JSON summary.

Minimum floors are intentionally close to the existing synthetic baseline:

| Metric | Minimum |
|---|---:|
| Generation abstention accuracy | 0.85 |
| Citation validity | 0.90 |
| Citation support precision | 0.75 |
| Claim citation coverage | 0.75 |
| Structured unsupported-section abstention | 0.75 |

The gate also maintains named allowlists for existing critical failure cases. Fixing an existing case is allowed; introducing the same failure category in a new case fails the gate.

This prevents quality regression without pretending the current zero unanswerable no-result score or known citation failures are resolved. Real-document validation remains H2.

## Regression tests added or strengthened

### Project 1

- Baseline evidence metrics and named critical failures pass the gate.
- A citation-support drop from `0.75` to `0.74` fails.
- A new answered-unanswerable failure outside `unanswerable-01` fails.
- The CLI reports gate status and returns success only when it passes.

### Project 5

- Mixed currencies fail closed in both trend and peg calculations.
- Mixed units fail closed in both trend and peg calculations.
- Existing same-basis NWC, missing-input, EBITDA, net-debt, concentration, and finding tests remain unchanged and pass.

### Project 6

- Project 3 fixture validation rejects incompatible target, currency, and date.
- Project 5 fixture validation rejects incompatible target, engagement, and VDR documents.
- All fixture envelopes expose `FIXTURE_DATA`.
- Compatible adapter results preserve evidence references.
- API regression proves an incompatible Project 3 fixture cannot appear in final valuation output.
- Graph/evaluation expectations now correctly distinguish fixture-backed completion as completed-with-warnings.

## Numerical regression results

| Area | Result |
|---|---|
| Project 3 EV/equity, multiple, statistics, and range suite | 85 project tests pass; no Project 3 calculation changed |
| Project 4 transaction multiple and precedent range suite | 122 project tests pass; no Project 4 calculation changed |
| Project 5 reported/adjusted EBITDA, bridge, NWC, peg, net debt, and concentration | 102 project tests pass, including two new NWC basis regressions |
| Project 6 specialist number preservation and valuation reconciliation | Project 6 suite passes; compatible fixture values remain 900–1100 and 850–1050 GBP million |

The existing simple Project 3 and Project 4 hand checks recorded in H0 remain valid because those implementations were not modified.

## Evidence and provenance results

- Project 1 gate protects citation validity, support precision, claim coverage, abstention, and named critical failure cases.
- Project 5 retains period-level calculation results and evidence-bearing lines even when aggregate NWC output is blocked.
- Project 6 adapter tests confirm evidence objects and `evidence_refs` remain identical after fixture validation.
- Project 6 no longer changes specialist-owned target IDs in Project 3 or Project 5 outputs.
- Project 6 API excludes incompatible Project 3 valuation output rather than synthesizing it under a caller identity.

## Cross-project regression classification

| Path | H1 result | Classification |
|---|---|---|
| P1 → P3 financial handoff | Existing Project 3 adapter tests pass; no native handoff added | Mocked/adapter; native path deferred H2 |
| P3 + P4 → P6 valuation reconciliation | Compatible GBP fixture paths pass; incompatible P3 basis is rejected | Fixture-backed adapter integration |
| P5 adjusted EBITDA → P6 reconciliation | Existing reported/adjusted-basis and scenario tests pass | Fixture-backed adapter integration |
| P5 finding → P6 risk view | Existing evidence and synthesis tests pass | Fixture-backed adapter integration |
| P6 HITL → rerun → reconciliation | Existing checkpoint, decision, rerun, and synthesis tests pass | Fixture-backed graph integration |

No native Projects 1–5 composition was added; that remains H0-003/H2.

## LangGraph, HITL, and security

No separate verified graph, HITL, secret, logging, path, stack-trace, or run-state isolation defect survived the H0 shortlist for H1. No graph or checkpoint implementation was rewritten. Existing graph, retry, partial-failure, review, resume, rerun, and safe API error tests pass.

Fixture mode is now surfaced as a warning, closing the critical configuration ambiguity directly related to H0-002. Broader authentication, durable persistence, and trusted-pickle boundaries remain H0-009/H3.

## Files changed

### Project 1

- `src/ma_company_intelligence/evaluation/gates.py` — new quality-gate model and evaluator.
- `src/ma_company_intelligence/evaluation/__init__.py` — public gate exports.
- `src/ma_company_intelligence/evaluation_cli.py` — execute and report the gate.
- `tests/test_evaluation.py` — gate regressions.
- `docs/evaluation.md`, `docs/progress.md`, `docs/decisions.md` — gate scope and rationale.

### Project 5

- `src/ma_due_diligence/financial/models.py` — `MIXED_UNITS` warning code.
- `src/ma_due_diligence/financial/analytics.py` — shared NWC basis guard.
- `tests/test_qoe_and_financial_analysis.py` — mixed-basis regressions.

### Project 6

- `src/ma_deal_intelligence/adapters/base.py` — fixture validation hook and explicit fixture warning.
- `src/ma_deal_intelligence/adapters/project3.py` — immutable fixture payload and basis validation.
- `src/ma_deal_intelligence/adapters/project5.py` — immutable fixture payload and scenario validation.
- `src/ma_deal_intelligence/planning_fixtures.py` — request/source scenario alignment.
- `tests/test_adapters_registry.py`, `tests/test_api_final.py`, `tests/test_orchestration_evaluation.py`, `tests/test_orchestration_graph.py` — adapter, API, provenance, and status regressions.

### Portfolio documentation

- `docs/portfolio_hardening/H0_ISSUE_REGISTER.md` — appended H1 statuses without removing audit evidence.
- `docs/portfolio_hardening/H1_CORRECTNESS_FIXES.md` — this report.

## Test and check baseline

| Project | Tests | Result |
|---|---:|---|
| 01 | 135 | Pass |
| 02 | 96 | Pass |
| 03 | 85 | Pass |
| 04 | 122 | Pass |
| 05 | 102 | Pass |
| 06 | 76 | Pass |
| **Total** | **616** | **Pass** |

Ruff lint, Ruff format check, and strict mypy pass for all six projects. The checks covered 481 formatted files and 395 mypy source files across the project configurations.

## Deferred issues

### H2

- H0-003 native Project 6 composition.
- H0-004 public-document evaluation and actual quality improvement beyond the regression gate.
- H0-005 public-data readiness.
- H0-006 native cross-project contracts.
- H0-007 portfolio CI.
- H0-008 run-derived Project 6 evaluation metrics.
- H0-010 dependency reproducibility.
- H0-012 broader Project 2 labels.

### H3

- H0-009 final local-security and checkpoint boundary packaging.
- H0-011 root README CI correction and final documentation alignment.

## Remaining limitations

- Project 1's known synthetic unanswerable and citation failures remain visible; the H1 gate prevents regression rather than claiming they are solved.
- Project 6 remains fixture-backed by default and still lacks native Projects 1–5 composition.
- The Project 6 fixture safety checks cover the verified P0 Project 3/5 pathways. Public/provider identity resolution remains H2.
- Evaluations remain synthetic/local; no public dataset or paid provider was added.
- APIs remain local V1 services without production authentication or durable multi-user state.

## H1 acceptance gate

- Verified P0 H0-001: fixed with deterministic regressions.
- Verified P0 H0-002: fixed with adapter and API regressions.
- Selected P1 H0-004 critical gate: implemented; broader evaluation work explicitly deferred.
- Financial and evidence regressions: pass.
- Affected and portfolio project suites: pass.
- Specialist ownership: preserved; P6 contains no copied specialist finance logic.
- Unresolved verified P0 issues: none.

**H1 verdict: B — the correctness gate is satisfied and the portfolio can proceed to H2 after independent review and merge authorization. H2 has not started.**
