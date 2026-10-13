# H0 Master Issue Register

**Audited revision:** `fdd91f8`

**Status:** Inventory only. No issue in this register was remediated during H0.

## Priority summary

| Priority | Count | Issue IDs |
|---|---:|---|
| P0 | 2 | H0-001, H0-002 |
| P1 | 4 | H0-003, H0-004, H0-006, H0-007 |
| P2 | 5 | H0-005, H0-008, H0-009, H0-010, H0-012 |
| P3 | 1 | H0-011 |
| **Total** | **12** | |

## Root-cause clusters

| Cluster | Issues | Root cause |
|---|---|---|
| Financial-basis enforcement | H0-001, H0-002, H0-006 | Currency, units, entity, period, and provenance are modeled in places but not enforced at every calculation/adapter boundary |
| Fixture-only pathways | H0-002, H0-003, H0-005, H0-006 | Synthetic adapters demonstrate workflow behavior without repository-composed native execution or public-data validation |
| Evaluation assurance | H0-004, H0-005, H0-007, H0-008, H0-012 | Good local suites lack portfolio gates, representative real cases, or independently executed metrics |
| Reproducibility and operating boundary | H0-009, H0-010 | Local V1 assumptions and broad dependency ranges are documented unevenly and are not deployment controls |
| Documentation drift | H0-011 | Root status text was not updated as later project CI was added |

## Register

### H0-001 — NWC analytics combine incompatible currency and units

| Field | Detail |
|---|---|
| Projects | 05 AI Due Diligence |
| Category | **DEFECT** — financial correctness |
| Severity | **P0** |
| Status | Verified and reproduced |
| H1 status | **FIXED** on `fix/portfolio-h1-critical-correctness`; mixed currency/unit histories fail closed and have deterministic regressions. Original H0 evidence retained below. |
| Observed behavior | `analyze_nwc_trend` and `calculate_nwc_peg` average numeric NWC values without checking currency or unit compatibility. The peg is labeled using the first period's basis. |
| Expected behavior | Reject incompatible periods or normalize them only with explicit unit and FX inputs, dates, and provenance. Never relabel a mixed-basis result as one input basis. |
| Reproduction | Construct FY24 NWC `10 GBP million` and FY25 NWC `100 USD thousand`; call both functions. H0 observed `trend_average=55` and `peg=55 GBP million`, with no warnings. |
| Evidence | `05_ai_due_diligence/src/ma_due_diligence/financial/analytics.py:217-295` |
| Test/diagnostic | Controlled Python reproduction in the clean H0 environment; existing 100 tests still pass, showing missing regression coverage. |
| Business impact | Can produce a materially false working-capital peg and purchase-price implication. |
| Proposed correction | Add a single basis-compatibility guard for all included periods; require explicit normalization inputs if conversion is supported; fail closed otherwise. Add mixed-currency and mixed-unit regressions. |
| Dependencies | None |
| Recommended milestone | H1 |
| Acceptance criteria | Mixed currency/unit inputs cannot yield a numeric peg without explicit, evidenced normalization; same-basis cases remain unchanged; relevant unit, integration, and evaluation tests pass. |
| Confidence | High |
| Effort / regression risk | Small / medium |

### H0-002 — Project 6 fixture adapters silently associate unrelated financials with caller entities

| Field | Detail |
|---|---|
| Projects | 06 Super-Agent; affects Project 3/5 outputs consumed by it |
| Category | **DEFECT** — evidence and financial integrity |
| Severity | **P0** |
| Status | Verified and reproduced |
| H1 status | **FIXED** on `fix/portfolio-h1-critical-correctness`; Project 3/5 fixtures are scenario-bound, specialist target IDs are immutable, and incompatible API results are excluded. Original H0 evidence retained below. |
| Observed behavior | The default Project 3 fixture adapter accepts an unrelated target, requested EUR basis, and earlier as-of date, then returns representative GBP/2025 values without warning. Project 5 similarly replaces its representative fixture target ID with the caller target ID. |
| Expected behavior | Fixture outputs must remain bound to their declared fixture identity and financial basis, or the request must be rejected. Result metadata must make fixture mode and incompatibilities impossible to miss. |
| Reproduction | Invoke the default Project 3 adapter for `entity:other`, currency EUR, as-of `2020-01-01`. H0 observed GBP, `2025-12-31`, range `900–1100`, and `warnings=[]`. Inspect the analogous Project 5 target replacement. |
| Evidence | `06_mna_deal_intelligence_super_agent/src/ma_deal_intelligence/adapters/base.py:60`; `adapters/project3.py:22-79`; `adapters/project5.py:21-82`; `registry.py:124-131` |
| Test/diagnostic | Controlled adapter reproduction; the existing 73 tests do not cover incompatible requested identity/currency/date against fixture payloads. |
| Business impact | Unrelated valuation or diligence numbers can be presented in another deal's state, creating false investment conclusions and invalid provenance. |
| Proposed correction | Bind fixtures to explicit scenario IDs and compatible requests; reject mismatches; preserve source entity; propagate requested-vs-actual basis warnings; make fixture execution conspicuous in API/synthesis. |
| Dependencies | None |
| Recommended milestone | H1 |
| Acceptance criteria | Arbitrary entity/currency/date requests cannot receive relabeled fixture finance; all fixture results preserve original identity and basis; mismatch tests pass; synthesis cannot present mismatched results as deal facts. |
| Confidence | High |
| Effort / regression risk | Medium / medium |

### H0-003 — No default native composition invokes Projects 1–5 from Project 6

| Field | Detail |
|---|---|
| Projects | 01–06, primarily 06 |
| Category | **INTEGRATION GAP** |
| Severity | **P1** |
| Status | Verified |
| H2 status | **FIXED FOR NATIVE LOCAL MODE** on `feat/portfolio-h2-integration-evaluation`; an opt-in Project 6 registry binds and executes public Projects 1–5 services. Live-provider mode remains unavailable and is not claimed. |
| Observed behavior | `build_default_registry` creates all adapters in `FIXTURE` mode without native executors. `NATIVE` mode calls an injected callable, but no repository composition factory supplies Projects 1–5. The default API uses the default fixture workflow. |
| Expected behavior | A supported composition entry point should bind selected native/offline specialist capabilities with explicit configuration and preserve adapter envelopes and failure isolation. |
| Reproduction | Build the default registry/API and inspect adapter modes/executors; run the final demo and observe fixture-backed outputs. |
| Evidence | `06_mna_deal_intelligence_super_agent/src/ma_deal_intelligence/adapters/base.py:60`; `registry.py:124-131`; `api/app.py:39-40,78` |
| Test/diagnostic | Project 6 demo and evaluation pass with fixtures; no native cross-package command exists. |
| Business impact | The portfolio cannot truthfully claim native end-to-end six-project execution. |
| Proposed correction | After H0-002, compose one narrow native/offline happy path using existing public entry points. Keep fixture mode for deterministic demos and label both modes. Avoid rewriting specialist modules. |
| Dependencies | H0-002; contract work in H0-006 |
| Recommended milestone | H2 |
| Acceptance criteria | At least one documented command invokes real Projects 1–5 through Project 6 adapters; outputs retain identity/basis/evidence; partial failure and retry tests exercise native calls. |
| Confidence | High |
| Effort / regression risk | Large / high |

### H0-004 — Project 1 quality failures are recorded but not enforced as release gates

| Field | Detail |
|---|---|
| Projects | 01 Company & Document Intelligence |
| Category | **TEST / EVALUATION GAP** — evidence integrity |
| Severity | **P1** |
| Status | Verified benchmark gap; live-provider behavior unconfirmed |
| H1 status | **PARTIALLY FIXED** on `fix/portfolio-h1-critical-correctness`; executable metric floors and named critical-failure gates were added. Public/live quality improvement remains H2. |
| Observed behavior | The 14-case synthetic benchmark reports unanswerable no-result rate `0`, citation support precision `0.75`, claim citation coverage `0.7857`, and structured unsupported-claim abstention `0.75`. The fixtures intentionally preserve failures, but no enforced threshold prevents regression or defines acceptable release quality. |
| Expected behavior | Evidence-critical metrics need explicit thresholds and representative regression cases; unanswerable questions must abstain reliably. |
| Reproduction | Run the installed `madi-evaluate` entry point with a temporary output directory. |
| Evidence | `01_company_document_intelligence/docs/evaluation.md`; evaluation code under `src/ma_company_intelligence/evaluation/` and `evaluation_cli.py` |
| Test/diagnostic | H0 evaluation output listed above; 133 unit tests pass. |
| Business impact | Unsupported or weakly cited research answers may appear acceptable despite known benchmark failures. |
| Proposed correction | Define non-inflated minimum gates for abstention, citation validity/support/coverage, and structured extraction; retain failure cases; add a small public-document set in H2. |
| Dependencies | None for synthetic gates; H0-005 for public cases |
| Recommended milestone | H1 for critical abstention/citation regression gates; H2 for public-data validation |
| Acceptance criteria | CI fails on agreed evidence-regression thresholds; all known failure cases are named; live/public results are reported separately from synthetic metrics. |
| Confidence | High for missing gates; medium for live business impact |
| Effort / regression risk | Medium / low |

### H0-005 — Portfolio evaluations do not yet establish real-data readiness

| Field | Detail |
|---|---|
| Projects | 01–06 |
| Category | **TEST / EVALUATION GAP** |
| Severity | **P2** |
| Status | Verified |
| H2 status | **PARTIALLY FIXED**; one primary-source public precedent case is reproducible offline. Public document, screening, trading-comps, and diligence cases remain deferred. |
| Observed behavior | All six evaluations rely primarily on synthetic, curated, local, or representative fixture data. No small committed/reproducible public-data benchmark spans annual reports, public transaction announcements, and diligence-style exhibits. |
| Expected behavior | Each externally facing capability should have a small legally usable public-data case with source snapshot/hash, expected assertions, and separated metrics. |
| Reproduction | Inspect evaluation datasets/reports and run all six evaluation commands. |
| Evidence | Each project's `docs/evaluation*.md` and evaluation packages; H0 results in `H0_TEST_EVALUATION_BASELINE.md` |
| Test/diagnostic | All evaluation commands pass, but their documentation identifies synthetic/local inputs. |
| Business impact | Strong fixture results can be mistaken for generalization to real filings, company identities, and transaction sources. |
| Proposed correction | Add a minimal public-data validation pack in H2; do not collect a large dataset. Candidate cases: one annual report, one earnings release, two public M&A announcements, and public contract exhibits. |
| Dependencies | H0-001, H0-002 for financially safe integrated use |
| Recommended milestone | H2 |
| Acceptance criteria | Public cases are reproducible, source-attributed, license-safe, and report failure examples separately from fixture scores. |
| Confidence | High |
| Effort / regression risk | Large / low |

### H0-006 — Cross-project identity, period, currency, unit, and evidence contracts are not natively verified

| Field | Detail |
|---|---|
| Projects | 01, 02, 03, 04, 05, 06 |
| Category | **INTEGRATION GAP** |
| Severity | **P1** |
| Status | Verified gap |
| H2 status | **PARTIALLY FIXED**; native P1–P5 output translations now preserve selected entity, metric, basis, period, currency, unit, as-of, and evidence fields and fail closed on incompatible P3 identity/currency/date, P5 document sets, and schema versions. P1 financial-fact-to-P3 input remains unavailable. |
| Observed behavior | Projects use typed local contracts, while cross-project tests use protocols, fakes, or Project 6 fixtures. No test demonstrates a Project 1 financial observation becoming a Project 3 input, or native Project 3/4/5 outputs reconciling in Project 6 with invariant entity/basis/evidence fields. |
| Expected behavior | Narrow adapter contracts should validate canonical entity, metric basis, period, currency, units, source reference, and as-of time at every handoff. |
| Reproduction | Inspect Project 3 adapters and Project 6 registry/tests; run current integration tests and observe substituted data. |
| Evidence | `03_comparable_companies_valuation/src/ma_comparable_valuation/`; `06_mna_deal_intelligence_super_agent/src/ma_deal_intelligence/adapters/` and tests |
| Test/diagnostic | Existing tests pass but classify as adapter/mock/synthetic integration. |
| Business impact | Native integration could silently misinterpret otherwise correct specialist outputs. |
| Proposed correction | Specify and test only the contracts required by real handoffs. Reuse existing models or adapters before considering a shared package. |
| Dependencies | H0-001, H0-002 |
| Recommended milestone | H2 |
| Acceptance criteria | Cross-project regression tests prove entity, source value, basis, period, currency, units, provenance, and staleness remain explicit and unchanged through the selected native paths. |
| Confidence | High |
| Effort / regression risk | Large / high |

### H0-007 — CI has no portfolio-level contract or end-to-end job

| Field | Detail |
|---|---|
| Projects | 01–06 |
| Category | **TEST / EVALUATION GAP** |
| Severity | **P1** |
| Status | Verified |
| H2 status | **FIXED**; `portfolio-integration-ci.yml` installs all six projects in one constrained Python 3.11 environment and runs the native-local contract suite. |
| Observed behavior | Six path-scoped workflows validate projects independently. No workflow installs the selected integrated set and executes cross-project contract or native handoff checks. |
| Expected behavior | Once native paths exist, CI should run a bounded portfolio contract suite and fail on incompatible package or schema changes. |
| Reproduction | Inspect `.github/workflows/p01-ci.yml` through `p06-ci.yml`. |
| Evidence | `.github/workflows/` |
| Test/diagnostic | All project checks pass independently in H0. |
| Business impact | A change may keep each project green while breaking Project 6 integration. |
| Proposed correction | Add a focused portfolio workflow for contract and native smoke tests; retain project-scoped workflows. |
| Dependencies | H0-003, H0-006 |
| Recommended milestone | H2 |
| Acceptance criteria | CI runs the supported handoff matrix from a clean environment and detects schema/basis incompatibility. |
| Confidence | High |
| Effort / regression risk | Medium / low |

### H0-008 — Project 6 evaluation reports some declarative rather than executed metrics

| Field | Detail |
|---|---|
| Projects | 06 Super-Agent |
| Category | **TEST / EVALUATION GAP** |
| Severity | **P2** |
| Status | Verified |
| H2 status | **PARTIALLY FIXED**; a separate native-local scorecard reports five run-produced observations. The legacy final synthetic scorecard still contains clearly documented statement-based coverage counts and remains a cleanup candidate. |
| Observed behavior | Routing/planning cases execute, while several adapter/orchestration/numeric/citation metric counts are constructed from statements that existing tests verify the behavior. The evaluation run itself does not execute every counted behavior. |
| Expected behavior | Evaluation metrics should derive from observations produced in that evaluation run or be labeled as a test-coverage summary. |
| Reproduction | Run `FinalEvaluationHarness().evaluate()` and inspect metric construction. |
| Evidence | `06_mna_deal_intelligence_super_agent/src/ma_deal_intelligence/evaluation_final.py:226,229,360+` |
| Test/diagnostic | H0 observed 18 routing cases plus static counts such as adapter `5/5` and orchestration `4/4`. |
| Business impact | Readers may overestimate the independence and breadth of the evaluation evidence. |
| Proposed correction | Execute the measured scenarios within the harness or rename/separate inherited test evidence. |
| Dependencies | H0-003 for native metrics |
| Recommended milestone | H2 |
| Acceptance criteria | Every reported evaluation metric links to run-produced observations, or is clearly labeled as external test evidence. |
| Confidence | High |
| Effort / regression risk | Medium / low |

### H0-009 — Local-only API and checkpoint security boundaries require final hardening

| Field | Detail |
|---|---|
| Projects | 01–06, strongest exposure in 05/06 |
| Category | **SECURITY / CONFIG RISK** and **INTENTIONAL V1 LIMITATION** |
| Severity | **P2** |
| Status | Verified boundary; no credential leak found |
| Observed behavior | APIs are unauthenticated and primarily process-local. Some checkpoint serializers use pickle and assume trusted local state. This is documented in several projects but not enforced as a deployment boundary. |
| Expected behavior | Portfolio demos must bind to a safe local configuration; untrusted pickle input must be impossible; any broader deployment requires auth, durable tenant isolation, and safe serialization. |
| Reproduction | Inspect API factories, checkpoint stores/serializers, README limitations, and security tests. |
| Evidence | Project API modules; Project 5/6 checkpoint modules; `.gitignore`; security tests |
| Test/diagnostic | Secret scan found only placeholders; redaction/safe-trace tests pass. |
| Business impact | Deploying the V1 as a multi-user/confidential VDR service would expose data and unsafe deserialization risk. |
| Proposed correction | H3 should enforce/document local binding and trusted-state assumptions. Implement broader controls only if deployment scope requires them. |
| Dependencies | None |
| Recommended milestone | H3 |
| Acceptance criteria | Demo commands are local-safe; security boundary is prominent; no untrusted serialized input path exists; deployment claims match implemented controls. |
| Confidence | High |
| Effort / regression risk | Medium / medium |

### H0-010 — Dependency resolution is not locked for reproducible portfolio builds

| Field | Detail |
|---|---|
| Projects | 01–06 |
| Category | **SECURITY / CONFIG RISK** |
| Severity | **P2** |
| Status | Verified |
| H2 status | **FIXED FOR PORTFOLIO CI**; `constraints/portfolio-python311.txt` records the known-good integrated resolution used by the portfolio workflow. |
| Observed behavior | Each project has bounded but broad `pyproject.toml` dependencies. No lock or constraints file captures the tested portfolio resolution. |
| Expected behavior | A reproducible portfolio/demo environment should pin or constrain a known-good Python 3.11 resolution while preserving maintainable update workflow. |
| Reproduction | Search dependency manifests and lock files; build a clean environment. |
| Evidence | Six project `pyproject.toml` files; no repository lock/constraints file |
| Test/diagnostic | Fresh H0 installation succeeded and `pip check` reported no broken requirements, so this is a drift risk rather than a current break. |
| Business impact | Future dependency releases may change behavior or make CI/demo reproduction inconsistent. |
| Proposed correction | Adopt the repository's preferred constraints/lock approach for the portfolio verification environment; document update procedure. |
| Dependencies | H0-003 may determine the integrated dependency set |
| Recommended milestone | H2 |
| Acceptance criteria | Clean install resolves the recorded versions and all configured checks/evaluations pass from that definition. |
| Confidence | High |
| Effort / regression risk | Medium / medium |

### H0-011 — Root README CI statement is stale

| Field | Detail |
|---|---|
| Projects | Repository documentation |
| Category | **DOCUMENTATION GAP** |
| Severity | **P3** |
| Status | Verified |
| Observed behavior | Root README says automated checks are available only for Project 1, while six workflows exist. |
| Expected behavior | Root status accurately lists project CI and portfolio-level limitations. |
| Reproduction | Compare `README.md:85` with `.github/workflows/`. |
| Evidence | `README.md:85`; `.github/workflows/p01-ci.yml` through `p06-ci.yml` |
| Test/diagnostic | File inspection |
| Business impact | Understates repository quality controls and confuses reviewers. |
| Proposed correction | Update the root README during final packaging after H1/H2 gates settle. |
| Dependencies | H0-007 |
| Recommended milestone | H3 |
| Acceptance criteria | Root README matches actual workflows and does not overclaim portfolio integration. |
| Confidence | High |
| Effort / regression risk | Small / low |

### H0-012 — Project 2 ranking evaluation has insufficient complete labels

| Field | Detail |
|---|---|
| Projects | 02 Target Screening & Sourcing |
| Category | **TEST / EVALUATION GAP** |
| Severity | **P2** |
| Status | Verified |
| H2 status | **PARTIALLY FIXED**; four synthetic theses now carry top-k labels, three carry pairwise labels, denominators are reported, and ranking failures remain visible. Public candidate labels and complete full-order labels remain unavailable. |
| Observed behavior | The five-case evaluation has complete downstream labels for only the payments case. Perfect downstream labeled metrics therefore have very small effective sample support. |
| Expected behavior | Ranking, exclusions, and explanations should be evaluated across several varied, fully labeled acquisition theses and candidate universes. |
| Reproduction | Run the Project 2 evaluation CLI and inspect its dataset/documentation. |
| Evidence | `02_target_screening_sourcing/docs/evaluation.md` and evaluation dataset |
| Test/diagnostic | Five synthetic cases pass; discovery precision is `0.5556`; downstream metrics are `1.0` on the limited labeled subset. |
| Business impact | Ranking consistency and false recommendations may be overstated. |
| Proposed correction | Add diverse fully labeled cases, entity conflicts, stale data, exclusion edge cases, and ranking ties; keep discovery and downstream metrics separate. |
| Dependencies | H0-005 for public candidates |
| Recommended milestone | H2 |
| Acceptance criteria | Metric reports disclose denominators and include multiple fully labeled theses with failure examples. |
| Confidence | High |
| Effort / regression risk | Medium / low |

## Observations intentionally not classified as defects

- Project 1 lacks OCR, dedicated table reconstruction, and lexical/hybrid retrieval: explicit V1 limitations.
- Project 2 uses a local candidate universe: explicit offline V1 scope.
- Projects 4 and 5 use deterministic token-hash embeddings in offline paths: fixture/local fallback, not a claim of production embedding quality.
- APIs do not provide production multi-tenant infrastructure: acceptable for a local portfolio V1 when stated accurately.
- Two pytest cache warnings in Projects 2 and 3 were caused by temporary-directory permissions; all tests passed and repository behavior was unaffected.
