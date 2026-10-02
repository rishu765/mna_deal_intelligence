# M&A Company Research & Document Intelligence

This is Project 1 in the
[AI × M&A Deal Intelligence portfolio](../README.md) and lives in the canonical monorepo at
`01_company_document_intelligence/`.

A portfolio-quality Python project for extracting reliable, evidence-backed company
intelligence from annual reports, filings, investor presentations, financial statements,
and related materials.

The project will build a reusable document-intelligence and retrieval-augmented generation
(RAG) foundation for later M&A workflows. It will support free-form research questions and
structured company research while retaining document provenance such as source document,
page, section, and chunk identifier.

## Current status

Milestone 1 adds local, page-aware PDF ingestion with stable content IDs, conservative text
normalization, explicit failures, and page-level provenance. Chunking, retrieval, generation,
and user-facing interfaces are not implemented yet.

See:

- [Architecture](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [Technical decisions](docs/decisions.md)
- [Progress log](docs/progress.md)
- [PDF ingestion](docs/ingestion.md)

## V1 scope

V1 will provide a local, single-user research pipeline that:

1. ingests a deliberately limited set of company document formats, beginning with PDFs;
2. creates normalized document and chunk representations with traceable provenance;
3. indexes chunks for semantic retrieval;
4. retrieves and optionally reranks evidence for a question;
5. generates answers constrained to retrieved evidence;
6. returns human-verifiable citations;
7. produces selected structured company research outputs; and
8. measures retrieval, answer, grounding, citation, and abstention quality.

## Explicit non-goals for V1

- Autonomous deal decisions or investment recommendations
- Multi-agent orchestration
- Broad web crawling or live market-data integration
- OCR for every possible scanned or irregular document
- Fine-tuning foundation models
- Multi-tenant authentication, permissions, or enterprise deployment
- A polished frontend before the core pipeline is evaluated
- Support for every file type and vector database

## Repository layout

```text
.
├── src/ma_company_intelligence/  # Reusable application package
├── tests/                        # Automated tests
├── docs/                         # Architecture, decisions, and progress
├── data/                         # Local source and derived data (ignored)
├── artifacts/                    # Local indexes/evaluation outputs (ignored)
├── AGENTS.md                     # Instructions for future coding agents
├── pyproject.toml                # Package and tool configuration
└── .env.example                  # Configuration template; no secrets
```

## Setup at the current stage

Python 3.11 or newer is required. From the repository root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run the project checks:

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy
```

The same checks run in GitHub Actions for pull requests affecting this project and for pushes
to `main`.

Parse a local text-oriented PDF and inspect bounded output:

```powershell
madi-inspect-pdf "data/raw/example-annual-report.pdf"
```

Use `--max-pages`, `--preview-chars`, and `--max-warnings` to bound terminal output. See
[PDF ingestion](docs/ingestion.md) for the data model, page-number convention, failures, and
known limitations.

## Working principles

Evidence quality and traceability take priority over fluent output. Deterministic processing
should handle deterministic tasks. Provider-specific code will remain behind narrow
interfaces so parsing, retrieval, generation, and evaluation can evolve independently.
Architectural choices are recorded when they are made, rather than hidden inside code.

