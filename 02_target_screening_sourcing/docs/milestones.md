# Locked milestone responsibility map

| Milestone | Owns | Explicitly deferred |
| --- | --- | --- |
| M0 — Architecture + Project 1 integration plan ✅ | Boundaries, minimal domain/port skeletons, reuse analysis, configuration/test foundation, decisions | All production workflow behavior |
| M1 — Acquisition thesis / screening criteria model ✅ | Full typed thesis and criteria, deterministic normalization, validation, JSON serialization, examples and tests | Natural-language parsing and candidate discovery |
| M2 — Company discovery / candidate sourcing ✅ | Offline and user-list providers, deterministic queries, provenance, conservative normalization/deduplication, bounded workflow and demo | Live providers, research enrichment and screening |
| M3 — Candidate enrichment using Project 1 research capabilities ✅ | Project 1 output adapter, evidence-backed profiles, offline provider, gaps/conflicts and demo | Screening decisions |
| M4/5 — Screening + strategic fit + ranking ✅ | Hard/exclusion gates, missing-data semantics, qualitative fit, transparent scoring, ranking, shortlist and audit trail | Agentic workflow and human-review orchestration |
| M6 — LangGraph agentic orchestration + human-in-the-loop | Graph state, conditional steps, resumability, approval/review checkpoints | API/demo and final V1 polish |
| M7 — Evaluation + API/demo + final V1 polish | Project 2 benchmark, metrics, hardened interface/demo, documentation and release validation | Post-V1 integrations |

Milestone names and order are locked. Finishing one milestone does not authorize starting the
next.
