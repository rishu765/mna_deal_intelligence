# M&A Target Screening & Deal Sourcing Agent

## Problem

Given an acquisition thesis and strategic or quantitative criteria, this project will discover
potential target companies, enrich them with traceable research, screen them, assess strategic
fit, and produce an evidence-backed ranked shortlist for human review.

## Why This Matters in M&A

Target sourcing begins with an open universe rather than a known company. Analysts need to turn
an investment or corporate-development thesis into a defensible candidate set while retaining
the source of each company and each material fact. Separating discovery, evidence collection,
hard filters, qualitative judgment, and human review makes the process more repeatable and
auditable without pretending that software makes the deal decision.

## Project 1 vs Project 2

Project 1 starts with a known company and known documents. It turns those documents into
provenance-aware chunks, retrieval results, citations, grounded answers, and structured company
research.

Project 2 starts with an acquisition thesis and an unknown target universe. It owns candidate
discovery, identity normalization, screening, strategic-fit assessment, ranking, and shortlist
review. It may request Project 1-style research after a candidate is known, but it does not own
document-intelligence internals and does not import arbitrary Project 1 modules.

## Planned Architecture

```text
Acquisition thesis
    -> criteria parsing and normalization (M1)
    -> candidate discovery (M2)
    -> deduplication and identity resolution (M2)
    -> evidence-backed candidate enrichment (M3)
    -> deterministic screening (M4)
    -> strategic-fit reasoning (M5)
    -> ranking (M5)
    -> evidence-backed shortlist (M5)
    -> LangGraph orchestration and human review (M6)
```

Provider-specific discovery systems will sit behind `DiscoveryProvider`. A separate
`CompanyResearchProvider` port will let an adapter translate a normalized candidate into a
Project 1 research request and translate the result back into Project 2's `CandidateProfile`.
See [architecture.md](docs/architecture.md) for component ownership and data boundaries.

## Milestone Roadmap

| Milestone | Responsibility | Status |
| --- | --- | --- |
| M0 | Architecture + Project 1 integration plan | Complete |
| M1 | Acquisition thesis / screening criteria model | **Complete** |
| M2 | Company discovery / candidate sourcing | Not started |
| M3 | Candidate enrichment using Project 1 research capabilities | Not started |
| M4 | Screening engine + deterministic filters | Not started |
| M5 | Strategic-fit reasoning + ranking | Not started |
| M6 | LangGraph agentic orchestration + human-in-the-loop | Not started |
| M7 | Evaluation + API/demo + final V1 polish | Not started |

The detailed ownership map is in [milestones.md](docs/milestones.md).

## Acquisition Thesis Model

M1 provides a versioned, JSON-compatible `AcquisitionThesis` with acquirer context and typed
screening criteria. Criteria separately express their business category, hard/soft/exclusion
consequence, value type, operator, deterministic/semantic evaluation boundary, and optional
priority or normalized weight. Financial ranges retain decimal values, currency, unit, and
period and reject incompatible bounds.

The model supports incomplete theses without inventing missing constraints. See
[acquisition-thesis.md](docs/acquisition-thesis.md) and the validated examples under
[`examples/`](examples/).

## Project 1 Reuse Strategy

M0 reuses Project 1's proven engineering patterns—frozen provider-neutral domain objects,
narrow protocols, explicit provenance, deterministic validation, environment-based config,
and the same quality toolchain. It does not copy implementations or create `shared/`.

In M3, an adapter should consume a deliberately supported Project 1 application/service
boundary. Project 1 currently exposes `ProjectApplicationService` and structured
`CompanyResearchProfile` results, but the package is independently configured and has no
cross-project enrichment contract. That gap is documented rather than hidden with deep imports.
See [project-1-reuse.md](docs/project-1-reuse.md).

## Deterministic vs LLM Responsibilities

Deterministic code will own typed validation, identity keys, exact filters, numeric thresholds,
defined scoring formulae, stable sorting/tie-breaking, citation validation, and workflow state
transitions. Model-backed semantic reasoning may help interpret ambiguous thesis language,
assess strategic adjacency or capability complementarity, and produce qualitative rationales.

LLM output consumed by code must be schema-validated and evidence-linked. It must not silently
override hard constraints or manufacture missing facts. M1 classifies criteria for later
evaluation but implements no candidate screening or semantic assessment.

## Configuration

Each project remains independently installable. Project 2 uses environment variables with a
`MATS_` prefix for its future settings and may rely on provider-standard credentials such as
`OPENAI_API_KEY` through later adapters. `.env.example` documents names only; the application
will not auto-load secrets. M0 has no runtime provider dependency and requires no credentials.

## Development

From this directory, using Python 3.11 or newer:

```powershell
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest
```

## Current Status

**M1 complete — acquisition thesis and screening-criteria model.** M0 architecture and the M1
versioned schema, validation, serialization, examples, and tests are implemented. Natural-
language parsing, discovery, enrichment, candidate screening, strategic-fit assessment,
ranking, LangGraph, human review, APIs, UI, and deployment are not implemented.
