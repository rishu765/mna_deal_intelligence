# Project progress

## Current milestone

**M0 — Architecture and repository foundation: complete (2026-10-03)**

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

## Next review gate

Approve or revise the M1 plan before implementation. M1 should begin by selecting a small,
legally usable set of representative PDFs and defining acceptance criteria for page-aware text
extraction. No parser dependency has been selected yet.

