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
| Comparable Companies & Valuation | [`03_comparable_companies_valuation/`](03_comparable_companies_valuation/) | **M0 architecture complete** |
| Precedent Transactions | `04_precedent_transactions/` | Planned |
| Due Diligence | `05_due_diligence/` | Planned |
| Deal Intelligence System | `06_deal_intelligence_system/` | Planned |

Future project directories will be added when work on those projects begins. A `shared/`
package will be introduced only after genuinely reusable components emerge.

Project 2 Version 1.0 contains a typed acquisition thesis, credential-free discovery,
evidence-backed enrichment, deterministic screening, grounded strategic-fit assessment,
transparent ranking, checkpointed LangGraph human review, a subsystem benchmark, FastAPI, and an
offline end-to-end demo.

Project 3 M0 defines the public trading-comps workflow, deterministic-versus-AI boundary,
valuation-safe domain contracts, provider interfaces, evidence lineage, and offline testing
strategy. It does not yet calculate multiples or valuations.

## Portfolio foundations

[Project 1](01_company_document_intelligence/) establishes a provenance-first document
intelligence and retrieval-augmented generation foundation for company and M&A research.
It provides PDF ingestion, provenance-aware chunking, semantic retrieval, grounded answers,
citations, structured research, component-level evaluation, and a hardened FastAPI interface.

[Project 3](03_comparable_companies_valuation/) establishes the architecture for evidence-backed
comparable-company valuation. M1 and all calculation/data-ingestion milestones remain pending.

## Development workflow

`main` is the stable branch. Milestones and meaningful features use short-lived branches and
focused pull requests. Automated checks run for pull requests that affect Project 1 and for
pushes to `main`. Milestone pull requests should normally use squash merge after review.

Project-specific setup and validation commands live in each project's README.

