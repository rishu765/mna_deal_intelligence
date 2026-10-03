# Portfolio and interview guide

## Project summary

M&A Company Research & Document Intelligence is an evidence-grounded RAG system that ingests
company PDFs, preserves page-level provenance, retrieves relevant evidence, produces
citation-backed answers and typed company research, and measures retrieval, grounding,
citation, and structured-output quality separately.

It is an educational engineering portfolio project. It does not provide investment advice,
autonomous deal recommendations, live market data, or evidence beyond supplied documents.

## Resume bullet candidates

- Built a provenance-first Python RAG pipeline that parses corporate PDFs into deterministic
  page-aware chunks, embeds them with a provider-neutral interface, and persists inspectable
  vector records in SQLite.
- Implemented grounded company-document Q&A with bounded context construction, structured LLM
  output, explicit abstention, and deterministic mapping from answer evidence IDs to document
  and page citations.
- Designed typed M&A research output across 11 categories, separating extracted facts from
  analytical observations and preserving fiscal period, unit, currency, basis, and evidence
  for financial metrics.
- Created a component-level evaluation framework for retrieval, answer correctness,
  faithfulness, citation quality, abstention, and structured research using a versioned,
  copyright-safe benchmark.
- Exposed the pipeline through FastAPI with strict schemas, safe path handling, stable errors,
  request correlation, bounded provider retries, 130+ automated tests, and container-ready
  operation.

Use only bullets that fit the target role and keep the repository link nearby so every claim
can be inspected.

## Interview story

### 1. Problem

Company research requires analysts to navigate long annual reports, filings, and investor
presentations. The useful output is not merely fluent prose; analysts need the relevant fact,
its fiscal and unit context, and a path back to the source page.

### 2. Why naive PDF chat is insufficient

A single opaque PDF-to-prompt step makes it difficult to diagnose extraction errors, retrieval
misses, hallucinations, and incorrect citations. It also encourages unsupported metadata
guesses and makes quality hard to measure. This project preserves explicit boundaries and
provenance at every stage.

### 3. Architecture

PyMuPDF produces provider-neutral page objects. Conservative normalization keeps financial
symbols and approximate layout. A structural character chunker creates stable chunk IDs and
page sets. OpenAI embeddings sit behind an `Embedder` protocol; SQLite persists complete
vector records. Exact cosine retrieval returns typed results consumed by deterministic context
builders and structured generation adapters.

### 4. Parsing and chunking decisions

Physical PDF indexes are zero-based, canonical citation pages are one-based, and printed page
labels remain unknown unless reliably extracted. Chunks may cross pages and retain every
contributing page. The 1,800-character baseline is deterministic and easy to inspect; semantic
or token-aware chunking remains an evaluation-driven improvement.

### 5. Embeddings and vector search

The baseline uses `text-embedding-3-small` at 1,536 dimensions. Stable chunk IDs are SQLite
primary keys, making indexing idempotent. Exact cosine search is transparent and sufficient
for the local corpus, although it will not scale like an approximate-nearest-neighbor service.

### 6. Grounded RAG

Retrieval results are formatted into bounded, labeled evidence blocks. The generator is told
to use only that evidence, preserve financial qualifiers, and abstain when support is absent.
Provider-specific response objects do not enter the domain layer.

### 7. Citations and provenance

The model selects evidence IDs already present in context. Deterministic code validates those
IDs and resolves them to chunk, document, and canonical page provenance. Unknown evidence IDs
fail rather than becoming fabricated citations.

### 8. Structured research

Eleven fixed research categories use targeted retrieval, a deduplicated evidence catalog, and
one validated synthesis. Facts, M&A-relevant observations, and financial metrics use distinct
fields. Unsupported sections remain explicitly insufficient.

### 9. Evaluation

The benchmark reports retrieval hit/recall@k and MRR, fact recall, gold-context decomposition,
claim support, citation validity/support/coverage, and structured-field quality. It has no
single opaque quality score. The synthetic recorded baseline intentionally includes known
failures so the evaluation framework demonstrates detection rather than a perfect score.

### 10. API and robustness

FastAPI delegates to an application facade instead of duplicating pipeline logic. Pydantic
schemas reject malformed requests. Local paths are constrained to a configured root; errors
are sanitized; request IDs and durations are logged; provider calls have bounded timeouts and
retries. Offline tests use fakes, avoiding paid calls in CI.

### 11. Limitations

Plain-text PDF extraction does not solve OCR, complex tables, charts, or all multi-column
layouts. Retrieval uses a small general embedding model and exact search. The benchmark is
synthetic and small. Model output still requires human review for material M&A conclusions.
The API is local/trusted-host software without authentication.

### 12. Project 2 connection

Project 2 can consume the proven document, embedding, retrieval, evidence, provider, and
evaluation boundaries when screening acquisition targets. Code should move to `shared/` only
after Project 2 creates a second concrete consumer and exposes the exact common contract.

## Reusable foundations for Project 2

Likely reusable capabilities are:

- `ParsedDocument`, `ParsedPage`, conservative PDF ingestion, and provenance;
- `DocumentChunk`, metadata, deterministic IDs, and chunking configuration;
- `Embedder`, `VectorStore`, indexing, and retrieval protocols;
- evidence, citation, answer, and financial qualifier models;
- generator interfaces and structured-output validation;
- deterministic evaluation models, metrics, and reporting;
- application error and configuration patterns.

They remain inside Project 1 for now. Moving them before a second consumer exists would create
an abstract shared package based on predicted reuse and destabilize a completed project.
