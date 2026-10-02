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

**Status:** Implemented on the M2 feature branch; validation and review pending.

## M3 — Embeddings and local vector indexing

Define embedding and index ports, select one baseline embedding model and local store, persist
index metadata/configuration, and support reproducible index builds.

## M4 — Retrieval baseline

Implement top-k semantic retrieval, metadata filters where supported, query/result models,
and diagnostic output. Establish retrieval metrics before considering hybrid search or a
reranker.

## M5 — Grounded answer generation

Build token-bounded evidence context, a generation adapter, grounded prompts, and explicit
abstention behavior. Keep retrieval independently callable.

## M6 — Citation and provenance validation

Render user-facing citations and validate that cited claims map to retrieved chunks and source
locations. This milestone is separate because citation correctness needs its own contracts and
tests, although provenance is preserved from M1 onward.

## M7 — Structured company and M&A research

Add schema-validated outputs for a focused research brief: company overview, segments,
geographies/end markets, products/services, key metrics, disclosed risks, and strategic
developments. Require evidence per material field and allow unknown values.

## M8 — Evaluation harness and curated dataset

Version a compact evaluation set and report retrieval quality, answer correctness,
faithfulness, citation correctness, and absent-evidence behavior. Evaluation contracts and
sample cases begin earlier; this milestone turns them into an end-to-end harness.

## M9 — API or interface

Expose the evaluated pipeline through a thin interface chosen from actual usage needs. Keep
business logic in the package rather than the transport layer.

## M10 — Robustness, testing, and error handling

Harden malformed-input handling, retries, observability, configuration validation, and test
coverage based on failures found in earlier milestones.

## M11 — Portfolio polish and deployment

Create an architecture walkthrough, reproducible demo, benchmark summary, deployment path,
and clear limitations. Publish only after secrets, sample-data rights, and reproducibility are
reviewed.

