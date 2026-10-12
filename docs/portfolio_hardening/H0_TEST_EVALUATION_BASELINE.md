# H0 Test and Evaluation Baseline

**Audited revision:** `fdd91f8`

**Run date:** 2026-10-13

**Operating system:** Windows / PowerShell

**Supported audit runtime:** CPython 3.11.9, isolated temporary virtual environment

## Environment

The shell's default `python` resolved to Python 3.8 32-bit and did not contain the repository's dependencies. Initial `python -m pytest` attempts therefore failed during collection/import rather than revealing repository defects:

| Project | Initial unsupported-environment result |
|---|---|
| 01 | 13 collection errors |
| 02 | 9 collection errors |
| 03 | 14 collection errors |
| 04 | `conftest` import failure |
| 05 | `conftest` import failure |
| 06 | 14 collection errors |

H0 then created `%TEMP%\mna_h0_audit_env` with Python 3.11.9 and installed each project editable with its `dev` extra; Project 4 also used its `ai` extra. Installation succeeded, and `python -m pip check` reported **no broken requirements**. No repository dependency file was changed.

Representative environment commands:

```powershell
py -3.11 -m venv "$env:TEMP\mna_h0_audit_env"
& "$env:TEMP\mna_h0_audit_env\Scripts\python.exe" -m pip install -e ".\01_company_document_intelligence[dev]"
& "$env:TEMP\mna_h0_audit_env\Scripts\python.exe" -m pip install -e ".\02_target_screening_sourcing[dev]"
& "$env:TEMP\mna_h0_audit_env\Scripts\python.exe" -m pip install -e ".\03_comparable_companies_valuation[dev]"
& "$env:TEMP\mna_h0_audit_env\Scripts\python.exe" -m pip install -e ".\04_precedent_transactions[dev,ai]"
& "$env:TEMP\mna_h0_audit_env\Scripts\python.exe" -m pip install -e ".\05_ai_due_diligence[dev]"
& "$env:TEMP\mna_h0_audit_env\Scripts\python.exe" -m pip install -e ".\06_mna_deal_intelligence_super_agent[dev]"
& "$env:TEMP\mna_h0_audit_env\Scripts\python.exe" -m pip check
```

The repository has no lock/constraints file, so this records a successful resolution on the audit date rather than a guaranteed future resolution.

## Unit and integration tests

For each project, H0 ran this command from that project's directory:

```powershell
& "$env:TEMP\mna_h0_audit_env\Scripts\python.exe" -m pytest
```

| Project | Collected | Passed | Failed | Skipped | Errors | Duration |
|---|---:|---:|---:|---:|---:|---:|
| 01 Company & Document Intelligence | 133 | 133 | 0 | 0 | 0 | 9.61 s |
| 02 Target Screening & Sourcing | 96 | 96 | 0 | 0 | 0 | 7.69 s |
| 03 Comparable Companies & Valuation | 85 | 85 | 0 | 0 | 0 | 2.48 s |
| 04 Precedent Transactions | 122 | 122 | 0 | 0 | 0 | 8.40 s |
| 05 AI Due Diligence | 100 | 100 | 0 | 0 | 0 | 12.29 s |
| 06 Super-Agent | 73 | 73 | 0 | 0 | 0 | 7.38 s |
| **Total** | **609** | **609** | **0** | **0** | **0** | **47.85 s** |

Projects 2 and 3 each emitted one pytest cache permission warning caused by the temporary execution environment. The tests themselves passed; no repository defect is inferred from those warnings.

### Test-type interpretation

The suites include unit, API, graph, regression, workflow, and adapter tests. Their integration level varies:

- Project-local workflows use real project modules over controlled fixtures.
- Project 3's Project 1/2 boundaries use structural adapters and substitutes.
- Project 6 integration tests exercise real registry/graph/reconciliation behavior over fixture adapters.
- No test executed Project 6 → native Projects 1–5 as a complete repository flow.

## Static analysis and formatting

For each project, H0 ran the commands configured in its `pyproject.toml`:

```powershell
& "$env:TEMP\mna_h0_audit_env\Scripts\python.exe" -m ruff check .
& "$env:TEMP\mna_h0_audit_env\Scripts\python.exe" -m ruff format --check .
& "$env:TEMP\mna_h0_audit_env\Scripts\python.exe" -m mypy
```

| Project | Ruff check | Ruff format check | mypy | Format files checked | mypy source files |
|---|---|---|---|---:|---:|
| 01 | Pass | Pass | Pass | 106 | 87 |
| 02 | Pass | Pass | Pass | 66 | 52 |
| 03 | Pass | Pass | Pass | 58 | 46 |
| 04 | Pass | Pass | Pass | 94 | 80 |
| 05 | Pass | Pass | Pass | 86 | 73 |
| 06 | Pass | Pass | Pass | 70 | 56 |

No new analysis or formatting tool was introduced.

## Evaluation baseline

### Project 1

Command/interface: installed `madi-evaluate` entry point, equivalent to `ma_company_intelligence.evaluation_cli:main`, writing only to a temporary output directory.

Dataset: `synthetic_apex_company_research` v1.0.0, 14 cases (13 answerable, 1 unanswerable). The dataset and recorded observations are synthetic and intentionally include failure examples.

| Metric | Result |
|---|---:|
| Retrieval Hit@1 / @3 / @5 | 0.7692 / 0.8462 / 0.9231 |
| Retrieval Recall@1 / @3 / @5 | 0.7308 / 0.8077 / 0.8846 |
| MRR | 0.8269 |
| Unanswerable no-result rate | 0.0000 |
| Retrieved-fact accuracy | 0.7857 |
| Gold-context accuracy | 0.9286 |
| Abstention accuracy | 0.8571 |
| Claim support | 0.8571 |
| Citation validity | 0.9286 |
| Citation support precision | 0.7500 |
| Claim citation coverage | 0.7857 |
| Structured supported-claim accuracy | 0.9091 |
| Structured unsupported-claim abstention | 0.7500 |
| Structured financial field accuracy | 0.9583 |
| Structured citation retention | 0.9167 |

Reproducibility: deterministic for the committed recorded observations. It is not a new live-provider quality measurement.

### Project 2

Command/interface: installed `mats-evaluate` entry point (`ma_target_screening.evaluation_cli:main`) with temporary JSON output.

Dataset: five synthetic acquisition-thesis cases.

| Metric | Result |
|---|---:|
| Discovery recall | 1.0000 |
| Discovery precision | 0.5556 |
| Pre-dedup duplicate rate | 0.746835 |
| Provenance coverage | 1.0000 |
| Other labeled component metrics | 1.0000 |
| Workflow scenarios | 9 / 9 pass |

Reproducibility: deterministic. Only the payments case has complete downstream labels, so perfect downstream metrics have a narrow denominator.

### Project 3

Command:

```powershell
& "$env:TEMP\mna_h0_audit_env\Scripts\python.exe" -m ma_comparable_valuation.evaluation_cli
```

Dataset: eight curated synthetic cases using controlled INR fixtures and a five-company benchmark.

| Subsystem | Checks | Result |
|---|---:|---|
| Target profile | 6 | Pass |
| Peer selection | 5 | Pass |
| Ingestion | 5 | Pass |
| Multiples | 6 | Pass |
| Statistics | 2 | Pass |
| Implied valuation | 4 | Pass |
| AI/explanation layer | 5 | Pass |
| **Overall cases** | **8** | **Pass** |

Reproducibility: deterministic controlled fixtures; no live market/filing providers.

### Project 4

Command/interface: installed `mapt-evaluate` entry point (`ma_precedent_transactions.evaluation_final:main`).

Dataset: synthetic transaction discovery and document corpus.

| Metric | Result |
|---|---:|
| Discovery cases | 7 / 7 pass |
| Raw → resolved records | 8 → 7 |
| Retrieval Hit@3 / Recall@3 / MRR | 1.0000 / 1.0000 / 0.9167 |
| Extraction checks | Pass |
| Conflict detection | Pass |
| Selected precedents | 5 |
| R7 median | 4.46354166… |
| HITL workflow | Pass |
| Explanation cited transaction IDs | 3 |

Reproducibility: deterministic, in-memory, no licensed database or live model.

### Project 5

Command/interface: installed `madd-evaluate` entry point (`ma_due_diligence.evaluation_final:main`).

Dataset: synthetic VDR and deterministic specialist findings.

| Metric / artifact | Result |
|---|---:|
| Evaluation cases | 14 / 14 pass |
| Documents | 25 |
| Warnings | 5 |
| Retrieval results | 20 |
| Citations | 22 |
| EBITDA checks | 15 |
| Largest customer | 42% |
| Findings / conflicts | 14 / 5 |
| HITL and report consistency | Pass |

Reproducibility: deterministic fixture VDR. The passing evaluation does not cover mixed-currency/mixed-unit NWC; H0 independently reproduced H0-001.

### Project 6

Command/interface: `FinalEvaluationHarness().evaluate()` from `ma_deal_intelligence.evaluation_final`; the final demo also invokes it.

An initial exploratory call used a nonexistent `.run()` method and raised `AttributeError`; using the documented `.evaluate()` interface passed. This was an audit invocation correction, not a product defect.

| Metric | Result |
|---|---:|
| Intent cases | 18 / 18 |
| Routing precision | 32 / 34 = 0.9412 |
| Routing recall | 32 / 32 = 1.0000 |
| Missing-prerequisite checks | 2 / 2 |
| Adapter contract summary | 5 / 5 |
| Orchestration summary | 4 / 4 |
| State/numeric checks | 6 / 6 |
| Citation checks | 6 / 6 |
| End-to-end fixture scenarios | 6 / 6 |

Reproducibility: deterministic. Routing/planning observations execute directly; several other counts are declarative summaries of coverage in existing tests. All specialist outputs use the default fixture registry.

## Demo and controlled integration checks

| Project | Command/interface exercised | Result | Classification |
|---|---|---|---|
| 01 | Demo PDF generation plus real parser/ingestion path | Five pages parsed with correct page metadata and no warnings | Native offline ingestion |
| 02 | `mats-workflow-demo` | Five candidates; deterministic ranks; HITL pause/resume; two approved | Native workflow over synthetic candidates |
| 03 | `macv-valuation-demo` | Completed; independent EV/equity arithmetic matched | Native deterministic calculation over fixtures |
| 04 | `mapt-precedent-valuation-demo`, `mapt-agent-demo` | Completed; inclusion/exclusion, ranges, and HITL worked | Native workflow over synthetic deals/documents |
| 05 | `madd-agent-demo` | Paused then completed with warnings; 25 docs, 14 findings, 9 review actions, 12 trace entries | Native workflow over fixture VDR |
| 06 | `python demo_final.py` | Screening, P3/P4 fan-out, review, rerun, and fixture valuation completed | Real orchestration over fixture adapters |

No external model, market-data, transaction-data, or document provider was called. This avoids cost and nondeterminism, but leaves those paths unverified.

## Independent finance checks

### Project 3

The demo's revenue-low and EBITDA-median valuation paths were recomputed by hand:

- `4.915625 × 5,400 = 26,544.375 EV`.
- `26,544.375 - (1,000 debt - 400 cash) = 25,944.375 equity value`.
- `42.5 × 820 = 34,850 EV`.
- `34,850 - 600 = 34,250 equity value`.

All matched the application output.

### Project 4

The compact demo's median `4.4635416666… × 100 revenue = 446.3541666… EV`; subtracting `28` net debt gives `418.3541666…` equity value, divided by `50` shares gives `8.3670833…`. All matched.

### Project 5

The mixed-basis NWC check failed as described in H0-001: `10 GBP million` and `100 USD thousand` were averaged to `55` and labeled `GBP million` without warning.

### Project 6

An incompatible fixture request failed integrity expectations as described in H0-002: an unrelated EUR/2020 request received representative GBP/2025 valuation data without warning.

## Reproducibility limitations

- No dependency lock captures the exact successful resolution.
- All evaluations are synthetic/local or representative fixtures.
- Live model/provider behavior, rate limits, drift, and credentials were not exercised.
- Project 6 does not execute Projects 1–5 natively by default.
- Temporary evaluation outputs were kept outside the repository and are not committed audit artifacts.
- Duration figures are wall-clock observations on one machine and should not be treated as performance benchmarks.
