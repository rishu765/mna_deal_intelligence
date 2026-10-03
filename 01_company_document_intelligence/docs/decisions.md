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

## D-017 — Exact cosine retrieval with stable ordering

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Extend the existing `VectorStore` boundary with exact cosine-similarity search.
  Sort descending by score and break equal-score ties with ascending stable chunk ID. Default
  to `top_k=5` with no minimum score threshold.
- **Why:** Exact scoring is transparent, deterministic, and sufficient for the current local
  corpus. An arbitrary threshold would hide evidence before evaluation establishes calibrated
  behavior.
- **Tradeoff:** Search deserializes and scores every candidate, so latency grows linearly with
  corpus size. A vector-native ANN engine remains replaceable behind the interface.

## D-018 — Retrieval results retain complete chunks

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Return provider-neutral `RetrievalResult` values containing rank, cosine score,
  and the complete M2 `DocumentChunk`.
- **Why:** M5/M6 require text, stable IDs, source metadata, and every contributing page for
  grounded evidence and citations. Keeping the original chunk avoids incomplete search shapes
  and provider-specific result objects.

## D-019 — Limited exact metadata filters

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Support AND-combined exact filters for document ID, source filename, company,
  document type, and fiscal year. Apply filters before similarity scoring.
- **Why:** These fields already exist in M2/M3 and are useful for company-document research.
  Optional fields only match when trusted metadata was supplied; retrieval never infers them.
- **Tradeoff:** Initial filtering occurs in Python and is case-sensitive. Larger corpora should
  push indexed filtering into storage without changing the public filter contract.

## D-020 — Defer reranking and answer generation

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Establish and test vector retrieval before adding reranking, context assembly,
  prompts, or an answer model.
- **Why:** Baseline retrieval must be measurable so later improvements can demonstrate value
  and retrieval failures remain distinguishable from generation failures.

## D-021 — OpenAI Luna baseline behind a structured generator boundary

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Define a provider-neutral `Generator` protocol and use OpenAI `gpt-6-luna`
  through the Responses API with low reasoning effort, an 800-token output cap, and no tools.
  Validate the provider response with a Pydantic Structured Output before converting it to a
  provider-neutral `GenerationOutput`.
- **Why:** Grounded Q&A over retrieved passages is focused evidence synthesis. Luna is the
  current cost-conscious OpenAI baseline for focused, high-volume work, while the interface
  permits later model comparison. Structured output gives downstream code a reliable boolean
  abstention signal instead of parsing prose.
- **Alternatives:** `gpt-6.1-sol` may improve difficult synthesis at higher cost and should be
  tested during evaluation. Plain JSON or free text requires fragile parsing. Multiple
  providers would add unmeasured complexity in M5.
- **Tradeoff:** Hosted generation needs credentials, network access, and API spend. A model
  alias can change over time; production should consider a tested snapshot.

## D-022 — Whole-block character-bounded context

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Preserve retrieval order and include at most five complete evidence blocks
  under a 12,000-character default budget. Stop at the first block that does not fit; never
  truncate chunk text or its provenance header.
- **Why:** Complete blocks keep financial values and source lineage together. Character counts
  are deterministic and consistent with M2 without coupling the application layer to a model
  tokenizer. The limits bound cost and prompt size while remaining easy to inspect.
- **Tradeoff:** Characters only approximate tokens, and a large high-ranked chunk can prevent
  smaller lower-ranked chunks from entering context. Evaluation may justify token accounting,
  deduplication, or evidence packing later.

## D-023 — Explicit abstention with no arbitrary retrieval threshold

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Skip generation and return a canonical insufficiency statement when retrieval
  returns nothing or no complete chunk fits. When context exists, require a structured
  insufficient-evidence decision and normalize true outcomes to the same safe statement.
- **Why:** Absence of evidence must be a supported result, especially for financial metrics.
  M4 cosine scores are not calibrated probabilities, so an unevaluated score threshold would
  create false confidence or suppress useful evidence.
- **Tradeoff:** Prompt-based support judgment can still fail. M8 must measure faithfulness and
  abstention, and later safeguards may add deterministic claim checks.

## D-024 — Preserve evidence now and render citations in M6

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Return the exact context-included `RetrievalResult` objects on `RAGAnswer`, but
  defer polished citation labels and claim-to-source validation to M6.
- **Why:** M1–M4 already preserve complete source/page/chunk lineage. Citation rendering and
  correctness need their own contracts and tests and should not be hidden inside the prompt.
- **Tradeoff:** M5 answers are inspectable through attached evidence but do not yet contain
  production-quality inline citations.

## D-025 — Model-selected evidence IDs with deterministic citation validation

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Label supplied evidence `E1`, `E2`, and so on; require structured generation to
  return only directly supporting IDs; validate them against the exact context; deduplicate by
  chunk ID; and assign user-facing citation numbers in first-reference order.
- **Why:** This avoids listing every retrieved chunk as support and makes fabricated references
  fail deterministically. Stable application numbering remains independent of provider output.
- **Tradeoff:** The baseline maps an answer or structured item to supporting chunks. It does not
  prove clause-level entailment or isolate the exact sentence within a chunk.

## D-026 — Canonical pages drive citation display

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Display trusted document title or source filename plus one-based canonical page
  numbers. Keep physical PDF indexes and printed labels in the citation object but never use
  them as substitutes when canonical provenance is missing.
- **Why:** M1 defines canonical pages reliably, while printed labels remain unknown unless a
  future adapter extracts them. Explicit `page unavailable` output is safer than fabrication.
- **Tradeoff:** A PDF's printed page label may differ from the displayed canonical page number.

## D-027 — Fixed targeted retrieval followed by one structured synthesis

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Run one stable semantic query for each of 11 company-research categories,
  deduplicate results into a bounded catalog, then make one schema-validated synthesis call.
- **Why:** Targeted queries give each category a chance to retrieve evidence without sending the
  complete corpus. One synthesis call controls cost and keeps terminology consistent.
- **Alternatives:** One generation call per section increases cost and can create inconsistent
  profiles. Sending the full corpus ignores retrieval. An agent or LangGraph adds planning even
  though the workflow and categories are known in advance.
- **Tradeoff:** Weak category queries can miss evidence, and one large response can still omit or
  misclassify facts. M8 will measure category retrieval and structured-field accuracy.

## D-028 — Separate facts, analysis, and qualified financial strings

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Store direct facts and M&A observations in different types. Preserve each
  financial metric's displayed value as text with optional fiscal period, unit, currency, and
  basis, and require citations for every populated item.
- **Why:** Analysts must distinguish disclosure from interpretation, and premature numeric
  normalization can confuse reported and adjusted measures, periods, signs, currencies, or
  scale.
- **Tradeoff:** Values are not yet calculation-ready. A future deterministic normalization
  layer would need explicit source-aware rules and separate validation.

## D-029 — Versioned synthetic cases and recorded observations

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Commit a copyright-safe fictional-company dataset containing gold facts,
  evidence targets, recorded retrieval/context/generation observations, and deliberately flawed
  outputs. Keep generated local reports ignored while committing one reproducible baseline.
- **Why:** The benchmark can run without network access, API spend, or redistribution of annual
  reports, and failures remain directly inspectable.
- **Tradeoff:** Recorded observations measure the evaluator and diagnostic method rather than
  live provider quality. Later representative-document runs must supplement this baseline.

## D-030 — Separate component metrics without a composite score

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Report retrieval, correctness, faithfulness, citations, structured output, and
  abstention independently, with explicit definitions and per-case failure categories.
- **Why:** A single average hides whether the index, context, generator, or citation mapping
  failed and can conceal unsafe financial behavior behind strong unrelated scores.
- **Tradeoff:** Reviewers must interpret several metrics and their denominators.

## D-031 — Gold-context decomposition and deterministic-first evaluation

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Score recorded answers against retrieved context and known correct context, and
  provide normalized fact/support checks as the default. Offer a schema-validated OpenAI judge
  only as an optional supplement.
- **Why:** The correctness gap helps attribute retrieval/context failures, while deterministic
  checks keep CI reproducible and auditable. Judge output can help with paraphrases but is not
  ground truth.
- **Tradeoff:** Substring-style checks do not establish semantic entailment; the optional judge
  adds cost, nondeterminism, and model drift.

## Open decisions

- Need for hybrid retrieval or reranking, based on evaluation (M4/M8)
- Need for clause-level entailment or claim-specific excerpt selection, based on M8 evaluation
- Thin interface type: CLI, API, or minimal UI (M9)

