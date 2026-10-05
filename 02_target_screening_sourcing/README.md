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
| M2 | Company discovery / candidate sourcing | **Complete** |
| M3 | Candidate enrichment using Project 1 research capabilities | **Complete** |
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

## Candidate Discovery

M2 provides deterministic thesis-to-query generation, a provider-neutral discovery contract,
a bundled fictional dataset provider, a user-supplied longlist provider, conservative identity
normalization/deduplication, and evidence-preserving results. The output is an unranked candidate
universe, not a screened shortlist.

Run the credential-free demo from this directory:

```powershell
python -m ma_target_screening.demo_discovery
```

See [candidate-discovery.md](docs/candidate-discovery.md) for provider contracts, provenance,
limits, failure semantics, and known limitations.

## Candidate Enrichment

M3 turns an M2 `CandidateCompany` into an evidence-backed `CandidateProfile`. Facts,
analytical inferences, explicit unknowns, financial metrics, and source conflicts remain
separate so later screening cannot mistake an interpretation for a verified fact. Enrichment
is thesis-aware only in deciding which fields to prioritize; it makes no pass/fail or ranking
decision.

The credential-free demo discovers the fictional PayFlow candidate and enriches it from the
bundled structured fixture:

```powershell
python -m ma_target_screening.demo_enrichment
```

See [candidate-enrichment.md](docs/candidate-enrichment.md) for the provider contract, merge
semantics, Project 1 adapter boundary, evidence model, and limitations.

## Project 1 Reuse Strategy

M3 reuses Project 1's supported application output through a narrow structural adapter. The
adapter accepts a client exposing `research(company_name=...)`, maps the public structured
research result into Project 2 profile claims, and preserves Project 1 document/chunk/page
citations. Project 2 has no runtime dependency on Project 1 and imports none of its deep
retrieval, storage, prompt, or provider modules. See
[project-1-reuse.md](docs/project-1-reuse.md).

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
`MATS_` prefix for its settings and may rely on provider-standard credentials such as
`OPENAI_API_KEY` only when a separately configured Project 1 client uses them. `.env.example`
documents names only; the application will not auto-load secrets. The bundled discovery and
enrichment demos require no credentials or network access.

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

**M3 complete — evidence-backed candidate enrichment.** M0 architecture, M1 thesis schema, M2
candidate discovery, and M3 profile models, offline enrichment, conservative multi-provider
merge, conflict/unknown handling, Project 1 output adapter, demo, and tests are implemented.
Live web research, document acquisition, candidate screening, strategic-fit assessment,
ranking, LangGraph, human review, APIs, UI, and deployment are not implemented.
