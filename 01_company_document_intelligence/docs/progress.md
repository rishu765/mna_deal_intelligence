# Project progress

## Current milestone

**M5 — Grounded RAG generation: implemented and locally validated (2026-10-03)**

## Milestone log

### 2026-10-03 — M0 completed

- Defined project purpose, V1 scope, and explicit non-goals.
- Proposed a provenance-first, provider-neutral pipeline architecture.
- Established a Python `src` package and development-tool configuration.
- Added repository guidance, roadmap, technical decision log, and setup instructions.
- Added local data/artifact directories whose generated contents are ignored by Git.
- Added a minimal package test to verify installation/import plumbing.
- Integrated the project into the canonical portfolio monorepo under
  `01_company_document_intelligence/`.
- Added path-scoped GitHub Actions checks for tests, linting, formatting, and type checking.

### 2026-10-03 — M1 implementation

- Added local PDF validation and page-aware parsing with PyMuPDF.
- Added immutable document, page, provenance, and warning models.
- Added content-derived IDs and explicit physical/canonical page-number semantics.
- Added conservative text normalization and application-specific failures.
- Added deterministic synthetic-PDF tests and a bounded inspection CLI.
- Documented parser selection, licensing, behavior, and known limitations.
- Passed Ruff linting, Ruff formatting, strict mypy, and 15 pytest tests in GitHub Actions.

### 2026-10-03 — M2 implementation

- Added immutable, provider-neutral metadata, chunk, page-reference, and chunked-document
  models.
- Added deterministic character chunking with configurable size, overlap, and minimum span.
- Preserved source identity, all contributing physical pages, and M1 parser warnings.
- Kept optional company-document metadata caller-supplied and left unknown values unset.
- Added invariant-focused tests for ordering, IDs, overlap, boundaries, empty pages, metadata,
  configuration failures, and bounded CLI output.
- Added a bounded parse-to-chunk inspection command and documented strategy limitations.
- Passed Ruff linting, Ruff formatting, strict mypy across 16 source files, and all 29 tests
  in GitHub Actions.

### 2026-10-03 — M3 implementation

- Added a provider-neutral synchronous embedding interface and environment-driven settings.
- Added the OpenAI `text-embedding-3-small` baseline with 1,536-dimensional vectors.
- Added immutable embedding/vector-record models that retain complete M2 chunks.
- Added atomic batch indexing with output-count, dimension, and finite-value validation.
- Added an inspectable SQLite store with a compatibility manifest and stable-ID upserts.
- Added a bounded PDF-to-index command without query retrieval or vector output.
- Added offline tests for ordering, mapping, provenance, upserts, persistence, configuration,
  provider failures, malformed inputs, dimensions, and partial-write prevention.
- Passed Ruff linting, Ruff formatting, strict mypy, and all automated tests in GitHub Actions.

### 2026-10-03 — M4 implementation

- Added typed retrieval filters, vector matches, and ranked retrieval results.
- Added validated query embedding through the existing M3 provider interface.
- Extended the existing SQLite store with exact cosine similarity and stable tie-breaking.
- Added exact filters for document ID, source filename, company, document type, and fiscal year.
- Preserved complete M2 chunk text, source metadata, page spans, and trusted metadata in every
  result.
- Added a bounded PDF-to-ranked-evidence CLI without answer generation.
- Added a deterministic company-research quality corpus and tests for ranking, scores, top-k,
  filters, empty indexes, invalid queries/vectors, provider failures, provenance, and the full
  pipeline.
- Passed Ruff linting, Ruff formatting across 44 files, strict mypy across 35 source files, and
  all 55 tests in GitHub Actions.

### 2026-10-03 — M5 implementation

- Added a provider-neutral retrieval protocol and generation request/output interface.
- Added environment-driven OpenAI generation configuration and a Responses API adapter using
  schema-validated structured output.
- Selected `gpt-6-luna` with low reasoning effort and a bounded 800-token default response as
  the cost-conscious focused-synthesis baseline.
- Added deterministic evidence blocks containing retrieval rank, score, stable IDs, source,
  physical and canonical pages, printed-label status, trusted metadata, and unchanged text.
- Added configurable five-chunk and 12,000-character context limits that admit only complete
  ranked evidence blocks.
- Added a grounded company-research prompt with explicit financial safeguards and no external
  knowledge or web fallback.
- Added deterministic abstention when evidence is absent or cannot fit, plus structured
  insufficient-evidence handling when context is weak.
- Added typed `RAGAnswer` objects retaining exactly the evidence used for generation.
- Added a bounded PDF-to-answer CLI and offline full-pipeline validation using fake providers.
- Passed Ruff linting, Ruff formatting across 60 files, strict mypy across 50 source files, and
  all 75 tests locally. No live paid API call was run.

## Next review gate

Review and merge the M5 pull request before beginning M6.

