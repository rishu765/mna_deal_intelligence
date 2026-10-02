# Technical decision log

This lightweight log records decisions that constrain later work. Add a dated entry when a
choice has meaningful alternatives or downstream effects.

## D-001 — Python package with a `src` layout

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Use Python 3.11+ and package code under `src/ma_company_intelligence`.
- **Why:** Python has the strongest practical document/ML ecosystem. A `src` layout prevents
  tests from accidentally importing the working directory instead of the installed package.
- **Alternatives:** A flat module layout is simpler initially but becomes easier to misuse as
  the project grows.

## D-002 — Provider-neutral core with narrow adapters

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Keep document, chunk, evidence, answer, and evaluation models independent of
  parsing, embedding, vector-store, and LLM vendors.
- **Why:** Later portfolio projects should reuse the pipeline, and evaluation must be able to
  compare implementations without rewriting domain logic.
- **Tradeoff:** Interfaces add a small amount of structure. They will be introduced alongside
  real implementations rather than created speculatively.

## D-003 — Provenance is an invariant

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Every derived chunk and retrieval result must retain lineage to its source
  document and the most precise reliable location available.
- **Why:** Evidence-backed M&A research requires users and evaluators to verify claims.
- **Tradeoff:** Parsing and transformations need stricter contracts and more metadata tests.

## D-004 — Defer RAG framework and provider selection

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Do not add LangChain, LlamaIndex, LangGraph, parser, embedding, LLM, or vector
  database dependencies in Milestone 0.
- **Why:** Representative documents and baseline evaluation should drive these choices. Early
  selection would add coupling without implemented behavior.
- **Alternatives:** A batteries-included framework speeds up a demo but can conceal retrieval
  and provenance behavior that this project is intended to teach and evaluate.

## D-005 — Evaluation seams from the start

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Keep parsing, chunking, retrieval, context construction, and generation callable
  independently, with serializable inputs and outputs where practical.
- **Why:** This enables stage-specific metrics and makes errors attributable instead of treating
  the system as an opaque end-to-end chat application.

## D-006 — Project lives in the canonical portfolio monorepo

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Place Project 1 under `01_company_document_intelligence/` in
  `rishu765/mna_deal_intelligence`; do not retain nested Git metadata.
- **Why:** The six projects form a progressive portfolio and later projects may reuse proven
  components. One repository supports integrated history and shared CI while numbered paths
  keep project boundaries clear.
- **Tradeoff:** Tooling and workflows must be path-aware as additional projects are introduced.

## D-007 — PyMuPDF is the M1 PDF parser

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Use PyMuPDF directly for local PDF validation, physical-page iteration, and
  plain-text extraction.
- **Why:** It provides a mature, fast page-aware API and clear corrupt-file behavior without
  adding an orchestration framework. The adapter prevents PyMuPDF objects from leaking into
  domain code.
- **Alternatives:** `pdfplumber` offers stronger layout/table primitives but adds complexity not
  required for the M1 baseline. `pypdf` has a permissive license and pure-Python implementation,
  but PyMuPDF was selected for extraction maturity and performance on long reports.
- **Tradeoffs:** PyMuPDF uses AGPL or commercial licensing. Plain-text extraction does not solve
  tables, columns, OCR, charts, or printed page-label recovery.

## D-008 — Content-derived IDs and explicit page-number semantics

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Identify documents as `sha256:<file digest>`. Store the zero-based physical PDF
  index and a one-based canonical page number on every page; leave printed page labels unset.
- **Why:** File-content hashes are deterministic and independent of local filenames. Explicit
  page concepts prevent later citations from confusing PDF positions with printed labels.
- **Tradeoff:** Any byte change creates a new ID, even when visible content is equivalent.

## D-009 — Conservative text normalization

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Normalize line endings and remove non-text control characters while preserving
  all visible characters and whitespace.
- **Why:** Financial meaning and approximate layout can depend on symbols, parentheses, tabs,
  and spacing. Aggressive cleanup would destroy evidence before evaluation.

## D-010 — Character-based structural chunking baseline

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Split with configurable character counts, defaulting to 1,800 maximum, 200
  overlap, and a 300-character minimum preferred span. Prefer paragraph, line, and space
  boundaries in that order.
- **Why:** Character counts are deterministic and inspectable without selecting an embedding
  tokenizer in M2. The defaults approximate 400-500 English tokens while retaining enough
  context for financial explanations. Evaluation will determine later tuning.
- **Alternatives:** Token splitting couples output to a tokenizer before M3. Semantic splitting
  adds model cost and nondeterminism before a baseline exists.

## D-011 — Cross-page chunks with explicit page sets

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Permit chunks to cross physical page boundaries and store an ordered
  `ChunkPageReference` for every contributing page.
- **Why:** Sentences, tables, and notes frequently continue across annual-report pages. Page
  sets preserve citation lineage without forcing context-breaking page cuts.
- **Tradeoff:** A cited chunk may refer to a page span, and extraction errors can still affect
  reading order.

## D-012 — Versioned content-derived chunk IDs and explicit metadata origin

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Hash the algorithm version, document ID, full configuration, chunk order, page
  indexes, and exact text. Keep source facts separate from optional caller-supplied research
  metadata; do not infer optional fields in M2.
- **Why:** Derived IDs must change when index-relevant output changes. Explicit metadata origin
  prevents filenames or weak heuristics from becoming trusted retrieval filters.
- **Tradeoff:** Retuning chunk configuration invalidates chunk IDs and requires re-indexing.

## D-013 — OpenAI small embedding model behind an interface

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Use the official OpenAI SDK with `text-embedding-3-small` at 1,536 dimensions
  as the baseline implementation of a provider-neutral `Embedder` protocol.
- **Why:** The model offers practical general retrieval quality, low current input cost, simple
  hosted operation, and explicit dimension control. The interface keeps provider response
  types outside domain and indexing code.
- **Alternatives:** The large OpenAI model has higher benchmark quality but doubles default
  dimensions and costs more. Local sentence transformers remove API dependency but add model
  downloads, runtime weight, and local compute requirements.
- **Tradeoff:** Index builds require a key, network access, and external API spend. Financial
  retrieval quality is not assumed and must be evaluated.

## D-014 — SQLite stores self-contained vector records

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Persist vectors, complete M2 chunks, and an embedding manifest in a local SQLite
  database under `artifacts/`. Store vector values as inspectable JSON in M3.
- **Why:** SQLite is transactional, debuggable, dependency-free, and suitable for a local
  educational corpus. Complete chunks guarantee that citation provenance survives indexing.
- **Alternatives:** FAISS offers efficient numeric search but weak metadata persistence. Chroma
  provides vector-native features but adds a larger dependency and abstraction before M4 has
  defined retrieval requirements. Production-scale systems may use pgvector or a managed
  vector database.
- **Tradeoff:** JSON vectors use more space and SQLite has no native approximate-nearest-neighbor
  index. M4 may use exact scoring for small corpora or replace the store behind its interface.

## D-015 — Atomic stable-ID upserts

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Embed and validate every batch before one transactional SQLite upsert keyed by
  M2 `chunk_id`. Reject conflicting objects with the same ID and incompatible index manifests.
- **Why:** Rebuilding an unchanged document is idempotent, and provider failure cannot leave a
  partially persisted indexing run. Model or dimension changes cannot silently mix vectors.
- **Tradeoff:** Successful API calls before a later failure may still incur cost and must be
  repeated because M3 does not add an embedding cache or checkpointing.

## D-016 — Retrieval remains a separate milestone

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** M3 stores document vectors but exposes no query embedding, similarity search,
  filtering, or ranking behavior.
- **Why:** Storage integrity and retrieval quality need separate contracts and tests. M4 can
  evaluate an exact baseline before selecting more infrastructure.

## Open decisions

- Need for hybrid retrieval or reranking, based on evaluation (M4)
- Generation provider and citation representation (M5–M6)
- Thin interface type: CLI, API, or minimal UI (M9)

