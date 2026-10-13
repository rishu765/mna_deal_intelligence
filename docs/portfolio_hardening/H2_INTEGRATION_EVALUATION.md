# H2 — Integration and Evaluation Hardening

## Scope and verdict

H2 addresses H0-003, H0-006, H0-007, H0-008, H0-010, and H0-012, plus a bounded
portion of H0-005. It adds an opt-in native-local composition, cross-project contract tests,
run-derived integration evaluation, a portfolio CI environment, broader Project 2 ranking labels,
and one primary-source public transaction validation.

This is a narrow integration layer. It does not change specialist finance logic, add live providers,
or claim that the five existing offline specialist datasets describe one deal.

## Selected worklist

| Issue | Projects | Category | Target change | Benefit | Regression risk | Acceptance evidence |
|---|---|---|---|---|---|---|
| H0-003 | 01–06 | Integration gap | Bind all five public specialist entry points into an opt-in Project 6 registry | Real specialist code can execute through Project 6 | High | Native-local contract suite invokes P1–P5 |
| H0-006 | 01–06 | Contract gap | Translate and validate identity, finance, dates, evidence, and versions | Prevents silent cross-project relabeling | High | Fail-closed identity/currency/date/document/schema tests |
| H0-007 | 01–06 | CI gap | Install all projects together and run native contract tests | Detects package and boundary drift | Low | `Portfolio Integration CI` workflow |
| H0-008 | 06 | Evaluation gap | Add a scorecard based on results produced in that run | Removes statement-based credit from native metrics | Low | Five run-derived observations |
| H0-010 | 01–06 | Reproducibility | Record tested Python 3.11 constraints | Reproduces the integrated environment | Medium | Constrained clean CI install |
| H0-012 | 02 | Evaluation gap | Add top-k/pairwise labels and denominators | Exposes ranking errors over more theses | Low | Four labeled cases and explicit counts |
| H0-005 (bounded) | 04 | Public validation | Add one primary-source precedent snapshot | Demonstrates a realistic, independently calculated case | Low | IBM/HashiCorp EV/revenue test |

## Native-local composition

`ma_deal_intelligence.native_local.build_native_local_registry` supplies native executors to the
existing five adapters. Imports are lazy, so Project 6 remains independently installable. In the
portfolio environment, each executor calls specialist-owned code:

| Project | Native code executed | Offline input boundary | Output preserved in Project 6 |
|---|---|---|---|
| P1 | PDF parsing and provenance-aware chunking | Caller-configured local document map | Entity, document IDs, chunk/page evidence, detected financial chunk IDs |
| P2 | Discovery, enrichment, screening, ranking, and LangGraph review checkpoint | Checked-in Project 2 provider fixtures | Candidate identity, rank, score, eligibility, rationale, discovery evidence |
| P3 | Complete `OfflineValuationService` | Project 3 peer and target fixtures | Target, peers, financial metrics, periods, basis, currency/unit, ranges, evidence, snapshot date |
| P4 | `PrecedentAnalysisService` selection, multiples, statistics, and valuation | Verified Project 4 transaction fixtures | Deal identity/status/value basis, target metrics, ranges, evidence, data date |
| P5 | Deterministic financial diligence services | Project 5 financial fixture | Reported/adjusted EBITDA, NWC peg, net debt, findings, conflicts, evidence, data date |

These paths are **native local with offline inputs**. They are not live-provider paths. Every P2–P5
native-local result contains `OFFLINE_SPECIALIST_FIXTURE`. Default adapter fixture mode remains
separate and contains `FIXTURE_DATA`.

The existing datasets intentionally represent different entities and currencies. H2 does not
rename or convert them into one synthetic deal. Native P3 rejects the wrong target, reporting
currency, or peer snapshot date. Native P5 rejects a request that omits any source document needed
by the returned financial evidence. Cross-specialist valuation blending therefore remains
unavailable until a common source case exists.

## Contract and compatibility decisions

Project 6's existing canonical `EvidenceReference`, `FinancialMetricReference`,
`ValuationReference`, `CanonicalEntityReference`, and `ProjectResultEnvelope` remain the portfolio
boundary. Native translators preserve specialist-owned IDs and values while mapping richer native
locators into canonical page, section, table, sheet, cell, chunk, URL, and native evidence fields.

`NativeProjectResult` now carries a schema version. Adapters accept version `1.0.0` and fail closed
before ingestion when a native executor returns an incompatible version.

No FX conversion was introduced. No period conversion or reported/adjusted flattening occurs.
Specialist values remain `Decimal` values.

## Shared-abstraction decision

No shared package was created. Project 6 is the only active cross-project consumer, and its
canonical boundary types already remove adapter ambiguity. Moving each specialist's distinct
evidence or finance models into `shared/` would couple stable local semantics to one integration
consumer and create a migration larger than the demonstrated reuse. A shared primitive should be
reconsidered only after a second non-Project-6 consumer needs the same semantics.

## Cross-project regression and evaluation

The native-local suite covers:

- P1 document parsing through P6 with document, page, chunk, and native evidence IDs;
- P2 deterministic ranking through P6 with entity and evidence references;
- P3 target metrics and valuation ranges with entity, currency, unit, period, basis, and as-of
  preservation;
- P4 selected deals and valuation ranges with transaction status, value basis, and evidence;
- P5 reported EBITDA `14`, adjusted EBITDA `15`, NWC peg
  `9.309090909090909090909090909`, adjusted net debt `20`, findings, conflicts, and evidence;
- rejection of wrong P3 entity, currency, and as-of date;
- rejection of incomplete P5 evidence document sets;
- rejection of incompatible native schema versions;
- explicit distinction between default fixture and native-local/offline-input warnings.

`evaluate_native_local` executes all five paths and emits a small report with subsystem, case ID,
metric, expected, observed, pass/fail, mode, and notes. Its five observations are calculated from
that execution. It does not replace subsystem-specific evaluations or create a composite accuracy
claim.

Project 2 now has top-k labels for four synthetic theses and pairwise labels for three. The
evaluation reports 10 top-k labels, six pairwise labels, and four labeled cases. The expanded set
shows `0.9` top-k inclusion and `0.6667` pairwise ordering accuracy, including two retained
payflow/ledgerbridge ordering failures. Deterministic stability remains `1.0`.

## Public-data validation

The checked-in IBM/HashiCorp case records:

- announcement date: 2024-04-24;
- disclosed enterprise value, net of cash: USD 6.4 billion;
- HashiCorp FY2024 reported revenue: USD 583.1 million;
- independently reproduced EV/revenue: `10.976x` after three-decimal rounding.

The transaction source is IBM's announcement and the revenue source is HashiCorp's Form 10-K on
the SEC website. URLs, access date, currency, unit, period, and basis are explicit in the fixture.
This single historical case does not establish real-world generalization, and its denominator is
not calendarized.

## Dependency and configuration changes

`constraints/portfolio-python311.txt` records the direct integration-critical versions validated
in H2. `Portfolio Integration CI` installs all six editable projects with those constraints and
runs the native-local contract suite. No project runtime range was mass-upgraded.

## Deliberately deferred work

- P1 financial observations remain IDs in the P1/P6 envelope; a value-bearing P1 → P3 handoff is
  not implemented.
- A unified P3 + P4 + P5 deal case is not created because current specialist datasets have
  incompatible entities and currencies.
- Live-provider mode has no default composition.
- Public annual-report RAG, public screening, public trading-comps, and public diligence cases
  remain open under H0-004/H0-005.
- The legacy P6 final synthetic scorecard retains some documented test-summary counts; the new
  native scorecard does not rely on them.
- Production security, durable checkpoints, final documentation diagrams, demo packaging, and
  presentation cleanup remain H3 work.

## Validation commands

The final local validation used the shared Python 3.11 environment with each project's `src`
directory selected explicitly:

| Scope | Result |
|---|---:|
| Project 1 pytest | 135 passed |
| Project 2 pytest | 96 passed |
| Project 3 pytest | 85 passed |
| Project 4 pytest, including public validation | 124 passed |
| Project 5 pytest | 102 passed |
| Project 6 pytest, including native-local integration | 84 passed |
| **Total** | **626 passed** |
| Ruff check / format check | Passed for all six projects |
| mypy | Passed for all six projects |
| `pip check` | No broken requirements |
| Fresh constrained six-project install | Succeeded; native-local integration 8 passed |

Evaluation executions:

- P1: 14 synthetic cases; H1 quality gate passed. Known failure categories remain visible.
- P2: five synthetic theses; ranking top-k inclusion `0.9`, pairwise accuracy `0.6667`,
  deterministic stability `1.0`.
- P3: eight offline cases; report passed.
- P4: nine subsystem metrics and ten scenarios passed; the separate public snapshot has two
  deterministic tests.
- P5: 14/14 scenarios passed.
- P6: 18/18 routing/planning cases passed; run-derived native-local evaluation passed 5/5.

Generated evaluation reports were written under the ignored local `work/h2-evaluation/` directory
and are not repository artifacts.

## H2 acceptance assessment

The selected native-local contracts are stable and fail closed, important specialist semantics
survive the Project 6 boundary, execution modes are explicit, evaluation observations are
reproducible, CI has one constrained portfolio environment, and no shared architecture rewrite was
introduced. The remaining gaps above limit the breadth of the integration claim and remain
explicit.
