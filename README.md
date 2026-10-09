# AI × M&A Deal Intelligence Portfolio

This monorepo contains a progressive portfolio of six applied AI engineering projects for
mergers and acquisitions research. Each project builds a focused capability, while later
projects may reuse stable components proven in earlier work.

The portfolio emphasizes document intelligence, retrieval, evaluation, traceable evidence,
and understandable engineering decisions. It is an educational portfolio and does not provide
investment advice or autonomous deal decisions.

## Projects

| Project | Planned path | Status |
| --- | --- | --- |
| Company Research & Document Intelligence | [`01_company_document_intelligence/`](01_company_document_intelligence/) | Version 1.0 complete |
| Target Screening & Sourcing | [`02_target_screening_sourcing/`](02_target_screening_sourcing/) | **Version 1.0 complete** |
| Comparable Companies & Valuation | [`03_comparable_companies_valuation/`](03_comparable_companies_valuation/) | **Version 1.0 complete** |
| Precedent Transactions | [`04_precedent_transactions/`](04_precedent_transactions/) | **Version 1.0 complete** |
| AI Due Diligence | [`05_ai_due_diligence/`](05_ai_due_diligence/) | **M0 foundation complete** |
| Deal Intelligence System | `06_deal_intelligence_system/` | Planned |

Future project directories will be added when work on those projects begins. A `shared/`
package will be introduced only after genuinely reusable components emerge.

Project 2 Version 1.0 contains a typed acquisition thesis, credential-free discovery,
evidence-backed enrichment, deterministic screening, grounded strategic-fit assessment,
transparent ranking, checkpointed LangGraph human review, a subsystem benchmark, FastAPI, and an
offline end-to-end demo.

Project 3 Version 1.0 defines the public trading-comps workflow, normalizes the target profile,
selects an auditable peer set, ingests evidence-backed financial and timestamped market data,
calculates deterministic multiples and valuation ranges, adds grounded explanations, and exposes
an offline evaluation suite, demo, and FastAPI interface.

Project 5 M0 establishes provider-neutral, evidence-first contracts for engagements, VDR documents,
atomic facts, findings, conflicts, financial adjustments, balance-sheet items, missing information,
human review, provenance, future specialist interfaces, and future report/orchestration state.

## Portfolio foundations

[Project 1](01_company_document_intelligence/) establishes a provenance-first document
intelligence and retrieval-augmented generation foundation for company and M&A research.
It provides PDF ingestion, provenance-aware chunking, semantic retrieval, grounded answers,
citations, structured research, component-level evaluation, and a hardened FastAPI interface.

[Project 3](03_comparable_companies_valuation/) provides an auditable comparable-company
valuation V1 with strict period/basis semantics, calculation traces, subsystem evaluation, and a
callable offline API.

[Project 4](04_precedent_transactions/) begins with provider-neutral, evidence-grounded transaction
contracts that distinguish deal identity, lifecycle, consideration, ownership, headline/equity/EV
value bases, point-in-time financials, and disputed source observations. Its M1/2 research layer
adds reproducible deal discovery, document ingestion, transaction-aware chunking, semantic and BM25
retrieval, hybrid ranking, provenance, and an offline retrieval benchmark. Structured extraction
in M3 adds validated evidence-linked observations, deterministic normalization, cross-source
verification, amendment/conflict retention, and traceable derived values. M4/5 adds auditable
precedent selection, transaction multiples, peer statistics, implied valuation ranges, and grounded
explanation while preserving transaction-specific dates, ownership, and value bases.
M6/7 completes the checkpointed LangGraph workflow, focused analyst review, structured failure
routing, final subsystem evaluation, offline end-to-end demo, and FastAPI run/review interface.

## Development workflow

`main` is the stable branch. Milestones and meaningful features use short-lived branches and
focused pull requests. Automated checks run for pull requests that affect Project 1 and for
pushes to `main`. Milestone pull requests should normally use squash merge after review.

Project-specific setup and validation commands live in each project's README.

