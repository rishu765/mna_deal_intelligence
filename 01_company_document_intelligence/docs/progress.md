# Project progress

## Current milestone

**M1 — Document ingestion and parsing: complete (2026-10-03)**

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
- Passed Ruff linting, Ruff formatting, strict mypy, and 10 pytest tests in GitHub Actions.

## Next review gate

Review the M1 pull request before beginning M2.

