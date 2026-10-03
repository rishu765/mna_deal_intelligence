# Milestone roadmap

The boundaries below are provisional. Each milestone ends with review before the next begins.

## M0 — Architecture and repository foundation

Define V1 scope, architecture, engineering conventions, repository structure, tool
configuration, and decision/progress records.

## M1 — Document ingestion and parsing

Choose a PDF parser using representative company documents. Implement file validation,
page-aware extraction, basic document metadata input, and explicit error reporting. Include
text-based PDFs first; treat OCR as a measured follow-up if fixtures require it.

**Status:** Complete and merged into `main`.

## M2 — Canonical representation, normalization, and chunking

Define validated document/page/chunk models, stable identifiers, provenance rules,
conservative normalization, and one baseline chunking strategy. Add fixtures that exercise
headings, page boundaries, and financial tables.

**Status:** Complete and merged into `main`.

## M3 — Embeddings and local vector indexing

Define embedding and index ports, select one baseline embedding model and local store, persist
index metadata/configuration, and support reproducible index builds.

**Status:** Complete and merged into `main`.

## M4 — Retrieval baseline

Implement top-k semantic retrieval, metadata filters where supported, query/result models,
and diagnostic output. Establish retrieval metrics before considering hybrid search or a
reranker.

**Status:** Complete and merged into `main`.

## M5 — Grounded answer generation

Build token-bounded evidence context, a generation adapter, grounded prompts, and explicit
abstention behavior. Keep retrieval independently callable.

**Status:** Complete and merged into `main`.

## M6/7 — Citations, provenance, and structured company research

Render user-facing citations, validate model evidence references, and add schema-validated
company/M&A research with section-local evidence, financial qualifiers, fact/analysis
separation, and explicit unsupported sections. M6 and M7 are intentionally combined without
removing either scope.

**Status:** Complete and merged into `main`.

## M8 — Evaluation harness and curated dataset

Version a compact evaluation set and report retrieval quality, answer correctness,
faithfulness, citation correctness, and absent-evidence behavior. Evaluation contracts and
sample cases begin earlier; this milestone turns them into an end-to-end harness.

**Status:** Complete and merged into `main`.

## M9/10 — API, robustness, testing, and error handling

Expose the evaluated pipeline through a thin interface chosen from actual usage needs. Keep
business logic in the package rather than the transport layer.
Harden malformed-input handling, retries, observability, configuration validation, and test
coverage based on failures found in earlier milestones.

**Status:** M9 and M10 are intentionally combined. Implemented and locally validated on the
combined feature branch; review pending.

## M11 — Portfolio polish and deployment

Create an architecture walkthrough, reproducible demo, benchmark summary, deployment path,
and clear limitations. Publish only after secrets, sample-data rights, and reproducibility are
reviewed.

