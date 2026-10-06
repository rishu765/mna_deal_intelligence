# Project 1 reuse analysis

This classification was established in M0 and updated after concrete M3 integration work.

## A — Reuse directly now

| Capability | M0 action |
| --- | --- |
| Python 3.11 `src` package and quality-tool configuration | Reuse the established project structure and Ruff/mypy/pytest settings. |
| Provider-neutral narrow protocols | Use the same structural pattern for discovery and company research ports. |
| Frozen dataclass domain objects with invariant checks | Use for foundational Project 2 value objects. |
| Provenance-first design | Require `DiscoveryEvidence` on sourced candidates and preserve unknowns. |
| Environment configuration and secret hygiene | Use `.env.example`; no auto-loading or committed values. |
| Stable exception families | Establish Project 2 base, discovery, and enrichment error types. |
| Public structured research output | M3 maps Project 1 facts, observations, financial metrics, and citations into Project 2 profile objects through a structural adapter. |

These are patterns, not copied runtime code. Project 2 has no package dependency on Project 1
in M0.

## B — Reuse conceptually but do not extract yet

| Capability | Reason to defer |
| --- | --- |
| `ProjectApplicationService` implementation | The composing application may supply it to the M3 adapter, but Project 2 does not import, configure, or own the facade. |
| `CompanyResearchService` internals | Project 2 consumes the public result shape instead of assembling Project 1's service pipeline. |
| Citation model implementation | M3 preserves its public page/chunk semantics through mapping; shared extraction is still unnecessary. |
| `Retriever`, `Generator`, and `Embedder` protocols | Useful internal patterns; Project 2 should consume research output, not assemble Project 1's pipeline. |
| Structured-output validation | M4/5 applies the approach to evidence-grounded semantic provider output. |
| Evaluation runner, metrics, reports, and failure taxonomy | Adopt compatible ideas in M7 after Project 2 tasks and gold cases exist. |
| Logging and bounded provider behavior | Apply when executable providers/application layers arrive. |

No `shared/` extraction is justified yet. The structural adapter proves concrete reuse while
keeping both projects independently installable; moving Project 1 types would add churn without
reducing meaningful duplication.

## C — Reimplement differently in Project 2

| Capability | Project 2 need |
| --- | --- |
| Evidence model | Project 2 owns enrichment/discovery provenance and maps Project 1 document citations into it. |
| Company profile | M3 shapes facts, inferences, financials, conflicts, and missing-data states around later screening needs rather than Project 1's fixed sections. |
| Configuration | Use Project 2 namespaces and discovery settings while allowing provider-standard credentials. |
| Errors | Express discovery, identity, enrichment, screening, and ranking failures at Project 2 boundaries. |
| Evaluation | Measure discovery recall, identity resolution, filter correctness, ranking quality, evidence coverage, and reviewer outcomes. |

## D — Not relevant to Project 2 core

Project 1's PDF parser, text normalizer, character chunker, SQLite vector-store implementation,
CLI commands, FastAPI transport schemas, demo PDF generator, and container packaging are not
Project 2 core responsibilities. Project 2 may benefit from their outputs through the research
boundary but should not reuse their implementations directly.

## M3 integration boundary

`Project1DocumentResearchProvider` depends only on structural protocols matching the supported
`research(company_name=...)` result. A composed application may pass Project 1's
`ProjectApplicationService` after it has been configured and candidate documents have been
ingested. The adapter translates output and exceptions; it does not reach into retrieval,
storage, prompts, ingestion, or LLM provider internals.
