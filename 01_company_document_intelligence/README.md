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

Milestone 5 completes the first grounded RAG loop. It retrieves M4 evidence, builds a bounded
and provenance-rich context, calls a provider-neutral generation boundary, and returns a typed
answer with the exact supporting results. Empty or inadequate evidence produces an explicit
insufficient-evidence result. Polished citations remain an M6 responsibility.

See:

- [Architecture](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [Technical decisions](docs/decisions.md)
- [Progress log](docs/progress.md)
- [PDF ingestion](docs/ingestion.md)
- [Metadata and chunking](docs/chunking.md)
- [Embeddings and vector indexing](docs/embeddings-indexing.md)
- [Semantic retrieval](docs/semantic-retrieval.md)
- [Grounded RAG generation](docs/grounded-rag.md)

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

Parse and chunk a local PDF while displaying only a bounded sample:

```powershell
madi-inspect-chunks "data/raw/example-annual-report.pdf"
```

The default strategy uses a maximum of 1,800 characters, 200 characters of overlap, and a
300-character minimum preferred span. These values and the output limits are configurable.
See [metadata and chunking](docs/chunking.md) for the model, provenance rules, rationale, and
limitations.

After exporting `OPENAI_API_KEY`, build a local persistent vector-record store:

```powershell
madi-build-index "data/raw/example-annual-report.pdf"
```

The default OpenAI model produces 1,536-dimensional vectors in batches of 64 and stores them
under `artifacts/vector_index.sqlite3`, which Git ignores. The summary is bounded and does not
print vectors or run retrieval. See
[embeddings and vector indexing](docs/embeddings-indexing.md) for configuration, costs,
idempotency, persistence, and limitations.

Run the complete document-to-retrieval developer pipeline without generating an answer:

```powershell
madi-retrieve "data/raw/example-annual-report.pdf" `
  "What were the main growth drivers?" --top-k 3
```

Results include cosine score, stable IDs, source document, page provenance, trusted metadata,
and a bounded text preview. See [semantic retrieval](docs/semantic-retrieval.md) for score
semantics, filters, deterministic ordering, quality checks, and limitations.

Run the complete local PDF-to-answer pipeline:

```powershell
madi-answer "data/raw/example-annual-report.pdf" `
  "What were the main revenue growth drivers?" `
  --top-k 5 --company "Example plc" --fiscal-year 2025
```

This command requires `OPENAI_API_KEY` for both embedding and generation. It displays one
answer plus bounded evidence previews and does not print vectors, prompts, or credentials.
Generation defaults to OpenAI `gpt-6-luna` with low reasoning effort, an 800-token output cap,
at most five evidence chunks, and a 12,000-character evidence budget. See
[grounded RAG generation](docs/grounded-rag.md) for configuration, grounding rules, and
limitations.

## Working principles

Evidence quality and traceability take priority over fluent output. Deterministic processing
should handle deterministic tasks. Provider-specific code will remain behind narrow
interfaces so parsing, retrieval, generation, and evaluation can evolve independently.
Architectural choices are recorded when they are made, rather than hidden inside code.

