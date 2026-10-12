# H0 Portfolio-Wide Audit

**Milestone:** H0 — Portfolio-Wide Audit + Prioritized Issue Inventory

**Audit date:** 2026-10-13

**Audited revision:** `fdd91f8` (`origin/main`)

**Audit branch:** `audit/portfolio-h0-baseline`

**Scope:** Projects 01–06, repository controls, CI, integration, tests, evaluations, finance integrity, AI architecture, security, reliability, and documentation

**Change policy:** Audit documentation only; no application source, tests, dependencies, or business logic were changed.

## Executive summary

The portfolio is a substantial, coherent V1 implementation. All six projects install in a clean Python 3.11 environment, all 609 tests pass, and every configured Ruff, Ruff-format, and mypy check passes. The projects contain real deterministic pipelines, APIs, graph workflows, evidence models, and evaluation harnesses. The strongest areas are typed domain modeling, deterministic finance calculations, explicit provenance structures, and broad unit coverage.

Two verified P0 defects require H1 remediation:

1. Project 5 averages and labels working-capital values without checking currency or unit compatibility. A reproduced USD-thousand/GBP-million input produced a `55 GBP million` peg.
2. Project 6's default fixture adapters can return representative Project 3 and Project 5 financial outputs for an unrelated requested entity, date, and currency without a warning. This can place unrelated values in a caller's deal state.

Project 6 does not currently provide native repository composition that invokes Projects 1–5. Its default registry is fixture-backed; `NATIVE` mode is an injection boundary for supplied callables. Its current end-to-end demonstration therefore proves orchestration, adapter, reconciliation, checkpoint, and HITL behavior with synthetic data, not live cross-project execution.

The evaluation suites are useful deterministic regression fixtures, but every project remains primarily synthetic or local-fixture evaluated. Public-document and public-transaction validation is the main credibility gap for H2. This conclusion does not reduce the value of the implemented pipelines; it defines the evidence required to substantiate real-data readiness.

**H0 verdict: A — Critical issues require immediate H1 remediation.** Portfolio completion is not claimed.

## 1. Repository baseline

| Item | Observed state |
|---|---|
| Initial checkout | Clean `feat/p06-m06-m07-final-v1` at `13dacc8`; its tree matched the completed Project 6 content later squash-merged to main |
| Remote main | `origin/main` at `fdd91f8`; live remote inspection and fetch confirmed it contains the completed six-project tree |
| Local main | Stale at `d6be61a`; left unchanged to preserve local branch state |
| Audit branch | Created as `audit/portfolio-h0-baseline`, then safely rebased to `origin/main`; current base `fdd91f8` |
| Working tree at audit start | Clean; no tracked or untracked user work |
| Open pull requests | None when queried |
| Remote feature state | The initial Project 6 feature branch had already been deleted remotely after merge |
| Existing ignored material | Local virtual environments, caches, coverage/evaluation artifacts; inspected, not deleted |
| Latest main CI | Project 6 CI succeeded for `fdd91f8` ([run 38165821464](https://github.com/rishu765/mna_deal_intelligence/actions/runs/38165821464)) |
| Dependency manifests | Six `pyproject.toml` files; no lock or constraints file |
| CI | Six project-scoped GitHub Actions workflows (`p01-ci.yml` through `p06-ci.yml`) |

A zero-byte stale `.git/index.lock` appeared after an interrupted ignored-file enumeration. Process inspection showed no active Git process; only that lock was removed. No repository content or user work was deleted.

## 2. Evidence classification

The project assessments use these meanings:

- **Implemented and verified:** inspected in code and exercised by a test, evaluation, demo, or independent check during H0.
- **Implemented but not verified:** code exists, but H0 did not exercise its external or provider-dependent path.
- **Partially implemented:** useful implementation exists with a material boundary or missing supported path.
- **Fixture/mock only:** behavior is exercised with deterministic local or injected substitutes.
- **Documented but not implemented:** a material claim lacks a corresponding implementation.

## 3. Project 1 — Company & Document Intelligence

### Business problem and architecture

Project 1 ingests company documents, normalizes and chunks page-aware text, embeds chunks, retrieves evidence, generates grounded answers and structured research, and exposes these capabilities through a FastAPI service. Its principal components are under `src/ma_company_intelligence/`: ingestion and parsing, chunking, embeddings, SQLite vector storage, retrieval, RAG, structured extraction, research orchestration, provenance, evaluation, and API modules.

### Capability status

| Status | Capabilities |
|---|---|
| Implemented and verified | PyMuPDF PDF ingestion; canonical page metadata; normalization; page-aware chunking; SQLite vector storage; exact cosine semantic retrieval; citation/evidence structures; grounded RAG validation; structured extraction controls; FastAPI contracts; 133 tests; synthetic evaluation; offline PDF parse |
| Implemented but not verified | Live OpenAI embedding and generation provider calls; H0 intentionally made no paid/network model call |
| Partially implemented | Table content is retained as extracted text but has no dedicated table reconstruction; confidence is represented through evidence and validation outcomes rather than calibrated probabilities |
| Fixture/mock only | Evaluation retrieval/generation observations and provider-independent tests |
| Documented but not implemented | None found among the project's scoped V1 claims |

### Strengths

- Page numbering preserves canonical page and zero-based PDF index, reducing citation ambiguity.
- Research facts, observations, citations, and unsupported claims are distinct types.
- The evaluation fixture deliberately retains retrieval and citation failures instead of masking them.
- Offline ingestion was reproduced using a generated five-page PDF with correct page provenance and no warnings.

### Weaknesses and limitations

- The committed synthetic benchmark reports zero unanswerable-query no-result rate, 75% citation support precision, and 78.57% claim citation coverage. This is a test/evaluation gap until quality thresholds and representative cases are enforced; it is not proof that the current live provider path fails identically.
- Retrieval is semantic exact-cosine V1. Lexical/hybrid retrieval, OCR, and robust table reconstruction are explicit V1 limitations.
- Live model behavior, rate limits, provider drift, and realistic annual-report tables were not verified in H0.

### Technical verdict

The document intelligence core is real and well tested for its stated offline scope. Evidence quality is not yet demonstrated on realistic public documents, and the known synthetic failure cases need measurable release gates.

## 4. Project 2 — Target Screening & Sourcing

### Business problem and architecture

Project 2 converts acquisition criteria into a deterministic sourcing and screening workflow. It includes local candidate discovery, enrichment, identity and deduplication, hard exclusion rules, scoring, strategic-fit explanations, ranking, LangGraph orchestration, HITL review, and a FastAPI interface under `src/ma_target_screening/`.

### Capability status

| Status | Capabilities |
|---|---|
| Implemented and verified | Typed acquisition thesis; local JSON discovery; candidate identity/deduplication; enrichment; hard filters; deterministic scoring/ranking; evidence-bearing explanations; LangGraph workflow; pause/resume HITL; API; 96 tests; five-case synthetic evaluation; offline workflow demo |
| Implemented but not verified | Fresh external company discovery or financial-data provider integration |
| Partially implemented | Evaluation is broad at component level but has complete downstream labels for only one of five cases |
| Fixture/mock only | Candidate universe, source freshness, financial values, and evaluation labels are local synthetic fixtures |
| Documented but not implemented | No material scoped claim found; documentation describes local data boundaries |

### Strengths

- Eligibility and ranking are separated, so excluded companies do not receive misleading ranks.
- Deterministic scores and traceable rule contributions make rankings reproducible.
- HITL pause/resume was reproduced, including approval of the top two candidates.

### Weaknesses and limitations

- The evaluation's pre-dedup duplicate rate is high by design (`0.746835`), and its discovery precision is `0.5556`; deduplication and downstream metrics pass on synthetic data.
- Entity freshness and company identity are not validated against authoritative live sources.
- With one fully labeled downstream case, perfect labeled metrics cannot support a general ranking-quality claim.

### Technical verdict

The screening engine is a credible deterministic prototype over a controlled candidate universe. Live sourcing accuracy, freshness, and broader ranking labels remain H2 validation work.

## 5. Project 3 — Comparable Companies & Valuation

### Business problem and architecture

Project 3 normalizes target and peer financial data, selects comparable companies, computes enterprise/equity metrics and trading multiples with `Decimal`, calculates peer statistics and implied valuation ranges, and exposes the workflow through an API. Modules under `src/ma_comparable_valuation/` cover domain models, normalization, adapters, selection, calculations, statistics, valuation, explanations, evaluation, and API delivery.

### Capability status

| Status | Capabilities |
|---|---|
| Implemented and verified | Target and peer normalization; period/currency/unit checks; peer selection; EV/equity bridge; LTM/NTM multiple definitions; peer statistics; valuation ranges; deterministic precision; API; 85 tests; eight-case evaluation; demo; independent hand calculation |
| Implemented but not verified | Real market/filing provider ingestion |
| Partially implemented | Project 1 and Project 2 integration is represented by structural adapter protocols and test fakes, not repository-composed native calls |
| Fixture/mock only | Financial providers, peer universe, and evaluation data |
| Documented but not implemented | No material scoped arithmetic claim found |

### Independent arithmetic check

For the demo target, revenue `5,400 INRm`, EBITDA `820 INRm`, cash `400`, debt `1,000`, and `50` shares were independently recomputed:

- Revenue low EV: `4.915625 × 5,400 = 26,544.375`.
- Revenue low equity value: `26,544.375 - 600 net debt = 25,944.375`.
- EBITDA median EV: `42.5 × 820 = 34,850`.
- EBITDA median equity value: `34,850 - 600 = 34,250`.

These values match the demo output.

### Strengths

- EV and equity value are modeled separately and bridged explicitly through debt and cash.
- Currency, units, financial period, and denominator basis are typed and validated.
- Decimal arithmetic and explicit rounding reduce silent precision drift.

### Weaknesses and limitations

- The system has not been validated against market-data restatements, differing fiscal calendars, provider FX conventions, or real peer exclusions.
- Cross-project target and screening adapters are interfaces, not verified native Project 1/2 handoffs.

### Technical verdict

The controlled-fixture arithmetic is deterministic and correct for the cases checked. The main remaining risk is data-contract and real-provider validation, rather than an observed valuation-formula defect.

## 6. Project 4 — Precedent Transactions

### Business problem and architecture

Project 4 discovers and resolves transaction records, ingests supporting documents, performs lexical/semantic hybrid retrieval, extracts and verifies deal facts, detects conflicts, selects relevant precedents, calculates transaction multiples and ranges, and runs a LangGraph/HITL workflow. The implementation is under `src/ma_precedent_transactions/`.

### Capability status

| Status | Capabilities |
|---|---|
| Implemented and verified | Transaction discovery; target/acquirer identity resolution; deduplication; announcement/completion status; consideration and value fields; token-hash semantic plus BM25 hybrid retrieval; extraction/verification; conflict handling; precedent selection; multiples and ranges; provenance; LangGraph/HITL; API; 122 tests; final evaluation; two demos |
| Implemented but not verified | Licensed transaction database or live model/provider paths |
| Partially implemented | Financial periods and transaction bases are guarded, but real source disagreement and complex consideration structures have only fixture coverage |
| Fixture/mock only | Deal universe, documents, embeddings, extraction observations, and evaluation |
| Documented but not implemented | None found within V1 boundaries |

### Independent arithmetic check

The compact demo's EV/revenue median of `4.4635416666…`, target EV `446.3541666…`, equity value `418.3541666…`, and per-share value `8.3670833…` reconcile using target revenue `100`, net debt `28`, and `50` shares.

### Strengths

- Transaction identity resolution and source conflicts are explicit stages.
- Withdrawn and partial transactions are excluded in the tested selection path.
- The workflow surfaces small-sample and period-alignment warnings rather than silently overstating precision.

### Weaknesses and limitations

- Evaluation uses seven synthetic discovery records and an in-memory corpus; it does not establish source completeness or real announcement-date accuracy.
- Deterministic token-hash embeddings are a local fallback, not evidence of production semantic retrieval quality.

### Technical verdict

The project has a real, layered precedent workflow with correct checked arithmetic. Source realism, complex deal terms, and authoritative transaction reconciliation remain unverified.

## 7. Project 5 — AI Due-Diligence Agent

### Business problem and architecture

Project 5 ingests a VDR, classifies and chunks documents, retrieves evidence, performs deterministic financial analytics and specialist commercial/legal/operational analysis, detects contradictions and duplicate findings, composes compound risks, supports HITL, and generates a diligence report. The implementation is under `src/ma_due_diligence/`.

### Capability status

| Status | Capabilities |
|---|---|
| Implemented and verified | Multi-document VDR ingestion; classification; document-aware token-hash/BM25 retrieval; source/version metadata; QoE and EBITDA adjustments; NWC and net-debt analytics; rule-based specialist agents; evidence citations; contradictions; deduplication; compound risks; LangGraph/HITL; reporting; API; 100 tests; 14-case evaluation; final demo |
| Implemented but not verified | Live LLM specialist augmentation and realistic confidential VDR operation |
| Partially implemented | Spreadsheet evidence is parsed for supported fixture layouts; legal conclusions remain rules and review-required findings, not legal advice |
| Fixture/mock only | VDR corpus, model responses, reported company facts, and evaluation |
| Documented but not implemented | None found within the project's stated local V1 boundary |

### Verified critical defect

`financial/analytics.py` collects `WorkingCapitalPeriod` NWC values and averages them without validating or converting their currencies and units, then labels the result using the first period's basis. The reproduction used `10 GBP million` and `100 USD thousand`; `analyze_nwc_trend` and `calculate_nwc_peg` returned `55`, and the peg was labeled `GBP million`, with no warning. Evidence: `src/ma_due_diligence/financial/analytics.py:217-295`.

### Strengths

- Financial analytics and narrative specialist findings are kept separate.
- EBITDA add-backs, net debt, debt-like items, restricted cash, evidence, and review decisions have explicit models.
- The final demo paused for review and completed with warnings, 25 documents, 14 findings, 22 citations, and report consistency checks.

### Weaknesses and limitations

- The NWC basis defect can create materially incorrect pegs.
- The evaluation corpus is synthetic and cannot substantiate real VDR confidentiality, spreadsheet diversity, or legal/commercial generalization.
- Pickle checkpoint serializers are safe only within the documented trusted, local process boundary.

### Technical verdict

The diligence workflow is extensive and substantively implemented, but the verified cross-basis NWC arithmetic defect is a financial blocker for H1.

## 8. Project 6 — M&A Deal Intelligence Super-Agent

### Business problem and architecture

Project 6 defines a canonical `DealState`, entity/evidence/financial contracts, a capability registry, intent routing and dependency planning, project adapters, output envelopes, reconciliation and staleness logic, LangGraph fan-out/fan-in execution, retry and failure isolation, checkpoint/resume, HITL, synthesis, observability, and an API. Its implementation is under `src/ma_deal_intelligence/`.

### Capability status

| Status | Capabilities |
|---|---|
| Implemented and verified | Canonical state; entity registry; evidence refs; financial basis models; capability registry; intent routing; dependency planning; adapter envelopes; reconciliation; staleness/recomputation flags; LangGraph `Send` fan-out/fan-in; retries; failure isolation; checkpoint/resume; HITL; synthesis; traces; API; 73 tests; 18-case routing/planning evaluation; final fixture demo |
| Implemented but not verified | Injected `NATIVE` callable execution with actual Projects 1–5 functions |
| Partially implemented | Native mode is an adapter extension point, but the repository has no composition factory that binds Projects 1–5 to the default registry |
| Fixture/mock only | The default registry and API execution, representative project outputs, financial reconciliation demonstration, and end-to-end evaluation |
| Documented but not implemented | A genuinely native, default end-to-end invocation of Projects 1–5 |

### Critical integration answer

Project 6 primarily simulates integration with representative fixtures. `adapters/base.py:60` defaults adapters to fixture mode, and `registry.py:124-131` builds all five default adapters without native executors. `NATIVE` mode is genuine callable dispatch when a caller injects an executor, but no repository-level composition supplies those executors.

The default API creates the default workflow and registry, so API runs are also fixture-backed unless custom services are constructed outside the provided application factory.

### Verified critical defect

The Project 3 fixture adapter accepts a request with an unrelated target entity, requested EUR basis, and an earlier as-of date, then returns representative GBP/2025 valuation data without a warning. The Project 5 fixture adapter likewise replaces the representative payload's target identifier with the caller's identifier. This is more severe than an honest fixture limitation because incompatible finance can silently enter a different deal state. Evidence: `src/ma_deal_intelligence/adapters/project3.py:22-79`; `project5.py:21-82`.

### Strengths

- The orchestration mechanics are real: planning, graph dispatch, retry, partial failure, state reconciliation, review interrupts, and resume are implemented and tested.
- Project output envelopes carry status, warnings, errors, evidence, timestamps, and adapter mode.
- Reconciliation models distinguish reported, diligence-adjusted, and selected valuation bases.

### Weaknesses and limitations

- No default native execution path invokes Projects 1–5.
- Fixture identity and financial-basis compatibility are not enforced.
- Parts of the final evaluation assign passing counts based on statements that existing tests cover a capability, instead of executing those capabilities in the evaluation harness.

### Technical verdict

Project 6 is a real orchestration prototype over adapter fixtures, not a native integrated application. Its graph and state architecture are credible, but its fixture safety defect and absent repository composition must be stated and addressed in sequence.

## 9. Cross-project architecture and financial integrity

### Verified interfaces

- Projects 1–5 expose independent Python packages and FastAPI applications.
- Project 3 defines structural adapters for target research and screening inputs.
- Project 6 defines canonical envelopes and adapters for Projects 1–5.
- Each package owns its domain models; there is no shared package and no demonstrated need to extract one during H0.

### Compatibility assessment

| Flow | H0 classification | Finding |
|---|---|---|
| Project 1 observation → Project 3 comps | Adapter/fixture only | Structural protocol exists; no native package-composed run verified |
| Project 2 target → Project 3 peer context | Adapter/fixture only | Protocol/fakes exist; identity and freshness across real providers untested |
| Project 3 reported EBITDA/valuation → Project 6 | Synthetic fixture | Canonical state stores results, but default adapter uses representative fixture data |
| Project 5 adjusted EBITDA → Project 6 reconciliation | Synthetic fixture | Basis concepts reconcile; source VDR and entity identity are not native-linked |
| Project 4 precedent valuation → Project 6 unified view | Synthetic fixture | Range synthesis works over fixture envelope |
| Project 5 adjusted net debt → Project 6 implications | Synthetic fixture | State fields exist; no native Project 5 invocation |

No H0 evidence shows source numbers being altered in the Project 3 and Project 4 standalone calculations. The Project 6 fixture relabeling defect, however, can associate unchanged numbers with the wrong entity and requested basis, which is an evidence-integrity failure.

## 10. LangChain, LangGraph, and AI architecture

| Topic | Actual use |
|---|---|
| LangGraph | Real state graphs in Projects 2, 4, 5, and 6; routing, interrupts/HITL, and resume are exercised |
| LangChain | Used where package integrations support graph/model abstractions; it is not a substitute for the deterministic finance engines |
| Retrieval | Project 1 exact-cosine semantic retrieval; Projects 4 and 5 local token-hash semantic plus BM25 hybrid retrieval |
| Structured outputs | Typed Pydantic/dataclass models and validation across all projects; live model structured-output behavior remains unverified |
| Tool/capability calling | Project 6 dispatches registered capabilities; default calls resolve to fixture adapters |
| Arithmetic | Core finance computations are deterministic Python/Decimal logic; no observed LLM-authored valuation arithmetic |
| HITL | Real graph interrupt/resume mechanics exist; local/process-limited persistence is an explicit V1 boundary |
| Checkpointing | Implemented in graph workflows; some serializers use pickle and require trusted local state |
| Observability | Structured traces and warnings exist, especially in Projects 5 and 6; no external telemetry backend is required for V1 |

No unbounded graph loop was observed in the inspected paths. Model-output validation is strongest at typed boundaries; realistic adversarial provider outputs have not been evaluated.

## 11. Security, confidentiality, and reliability

- No hardcoded live credential was found. Secret-like matches were documentation or test placeholders; values are not reproduced here.
- `.env` files, raw/processed data, artifacts, caches, and virtual environments are ignored.
- APIs are unauthenticated and use local/process-level persistence. This is acceptable only under the documented local V1 boundary and must be prominent in portfolio demos.
- Project 5 and Project 6 pickle checkpoint loads must never accept untrusted serialized input.
- Input validation and evidence-safe logging are covered by tests, including Project 1 redaction and Project 6 safe trace fields.
- Retry, partial failure, and resume are strongest in Project 6. Cross-process durability, concurrent-worker state, and idempotency against external providers are not demonstrated.
- Missing and malformed fixture inputs have meaningful test coverage; corrupted external documents and large real VDRs do not.

## 12. Documentation accuracy

| Claim | Classification | Evidence |
|---|---|---|
| Hybrid RAG | VERIFIED for Projects 4/5 local BM25 + token-hash retrieval; INACCURATE if applied to Project 1 | Project-specific retrieval modules and tests |
| LangGraph orchestration | VERIFIED | Projects 2/4/5/6 graph implementations and graph tests |
| Human review | VERIFIED within local graph workflows | Pause/resume demos and tests |
| Real project integration | PARTIAL/MOCKED | Project 6 default registry is fixture-only; native callable boundary is not composed |
| Deterministic valuations | VERIFIED on controlled fixtures | Project 3/4 tests, evaluations, and independent arithmetic checks |
| Grounded reports | VERIFIED on fixtures; NOT VERIFIED on real corpora | Evidence/citation models and synthetic evaluations |
| Cross-project reconciliation | VERIFIED on synthetic envelopes; MOCKED end to end | Project 6 reconciliation tests and fixture demo |
| Root README: automated checks only for Project 1 | INACCURATE | Six active workflow files exist |

## 13. Implemented finance learning inventory

| Concept | Project/module evidence | Later study emphasis |
|---|---|---|
| Financial-statement interpretation | P1 structured research; P3 normalization; P5 financial analytics | Restatements, fiscal calendars, source hierarchy |
| Target screening | P2 criteria, exclusions, scorecards, ranking | Acquisition-thesis design and bias in scoring |
| EV vs equity value | P3/P4 valuation bridges; P6 basis state | Minority interests, pensions, leases, noncontrolling interests |
| LTM/NTM | P3 metric/period models | Stub periods and calendarization |
| Trading multiples and peer selection | P3 selection, statistics, valuation | Sector-specific metrics and peer judgment |
| Precedent transactions | P4 selection, consideration, multiples | Complex consideration and unaffected-price premiums |
| QoE and EBITDA adjustments | P5 financial analytics | Evidence standards, run-rate adjustments, double counting |
| Working capital and NWC peg | P5 analytics | Basis consistency, seasonality, normalized mechanisms; especially deep study required |
| Net debt and debt-like items | P5/P6 | Restricted cash, leases, contingent liabilities |
| Deal-level reconciliation | P6 canonical state and synthesis | Basis waterfalls and source-of-truth governance; especially deep study required |

## 14. Implemented AI and engineering learning inventory

| Concept | Project/module evidence | Later mastery gap |
|---|---|---|
| PDF parsing/chunking | P1 ingestion and chunking; P4/P5 document pipelines | OCR, tables, layouts, scanned documents |
| Embeddings/retrieval | P1 provider embeddings; P4/P5 deterministic semantic + BM25 | Retrieval calibration and realistic corpora |
| RAG/citations | P1 RAG/research; P4/P5 evidence workflows | Claim-level support metrics and adversarial grounding |
| Structured extraction | P1/P4/P5 typed extraction | Provider variability and schema recovery |
| Agents/tool calling | P5 specialists; P6 capability dispatch | Clear boundary between workflow and autonomous decisions |
| LangGraph/state/routing | P2/P4/P5/P6 | Durable distributed execution and concurrency |
| Fan-out/fan-in | P6 graph | Failure semantics under native side effects |
| HITL/checkpointing | P2/P4/P5/P6 | Secure durable storage and multi-user authorization |
| Reconciliation | P6 | Data lineage and compatibility contracts |
| Evaluation | All projects | Real datasets, statistical uncertainty, release thresholds |
| Observability | P5/P6 traces | External tracing, privacy, operational SLOs |
| FastAPI | All projects | Authentication, deployment, rate limits, durable state |

## 15. Overall technical verdict

The six projects demonstrate meaningful finance and AI engineering work rather than README-only prototypes. The standalone controlled calculations and graph mechanics are generally strong. The portfolio is not ready to claim native six-project integration or real-world validation. H1 must first correct the two verified P0 integrity defects. H2 should then establish safe native handoffs, portfolio-level contract tests, and reproducible public-data evaluations. H3 should make the final presentation explicitly reflect those verified boundaries.

**Final verdict: A — Critical issues require immediate H1 remediation.**
