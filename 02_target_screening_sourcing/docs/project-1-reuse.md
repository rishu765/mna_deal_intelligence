# Project 1 reuse analysis

This classification reflects Project 1 version 1.0 as inspected during Project 2 M0.

## A — Reuse directly now

| Capability | M0 action |
| --- | --- |
| Python 3.11 `src` package and quality-tool configuration | Reuse the established project structure and Ruff/mypy/pytest settings. |
| Provider-neutral narrow protocols | Use the same structural pattern for discovery and company research ports. |
| Frozen dataclass domain objects with invariant checks | Use for foundational Project 2 value objects. |
| Provenance-first design | Require `DiscoveryEvidence` on sourced candidates and preserve unknowns. |
| Environment configuration and secret hygiene | Use `.env.example`; no auto-loading or committed values. |
| Stable exception families | Establish Project 2 base, discovery, and enrichment error types. |

These are patterns, not copied runtime code. Project 2 has no package dependency on Project 1
in M0.

## B — Reuse conceptually but do not extract yet

| Capability | Reason to defer |
| --- | --- |
| `ProjectApplicationService` composition facade | Promising M3 entry point, but it is configured for Project 1 workflows rather than a cross-project enrichment request. |
| `CompanyResearchService` and `CompanyResearchProfile` | Directly relevant to enrichment, but candidate-profile mapping and document availability are not defined until M3. |
| Citation and document provenance models | Their page/chunk semantics are valuable evidence, but discovery evidence also includes web/database observations with different locations. |
| `Retriever`, `Generator`, and `Embedder` protocols | Useful internal patterns; Project 2 should consume research output, not assemble Project 1's pipeline. |
| Structured-output validation | Reuse the approach when M1/M5 add model-backed parsing/reasoning. |
| Evaluation runner, metrics, reports, and failure taxonomy | Adopt compatible ideas in M7 after Project 2 tasks and gold cases exist. |
| Logging and bounded provider behavior | Apply when executable providers/application layers arrive. |

No `shared/` extraction is justified yet: there is only one concrete runtime consumer and
moving Project 1 code now would create churn without proving a stable common abstraction.

## C — Reimplement differently in Project 2

| Capability | Project 2 need |
| --- | --- |
| Evidence model | Add discovery/database/web provenance and observation time, then map document citations during enrichment. |
| Company profile | Shape fields around screening criteria and conflict/missing-data states, not Project 1's fixed document-research sections alone. |
| Configuration | Use Project 2 namespaces and discovery settings while allowing provider-standard credentials. |
| Errors | Express discovery, identity, enrichment, screening, and ranking failures at Project 2 boundaries. |
| Evaluation | Measure discovery recall, identity resolution, filter correctness, ranking quality, evidence coverage, and reviewer outcomes. |

## D — Not relevant to Project 2 core

Project 1's PDF parser, text normalizer, character chunker, SQLite vector-store implementation,
CLI commands, FastAPI transport schemas, demo PDF generator, and container packaging are not
Project 2 core responsibilities. Project 2 may benefit from their outputs through the research
boundary but should not reuse their implementations directly.

