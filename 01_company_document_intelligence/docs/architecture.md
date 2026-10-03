# V1 architecture

## Architectural goal

Build a modular pipeline that turns company documents into traceable evidence and then into
answers or structured research. Each stage should expose a small Python boundary and exchange
provider-neutral domain models. This lets later M&A projects reuse document processing and
retrieval without inheriting a particular UI, LLM, or vector database.

## Proposed data flow

```text
Source documents
    │
    ▼
Document intake and parsing
    │  page-level text + source metadata
    ▼
Normalization and document representation
    │  normalized text with provenance retained
    ▼
Chunking
    │  stable chunks with document/page/section lineage
    ▼
Embedding and vector index
    │
    ▼
Candidate retrieval ──► optional reranking
    │
    ▼
Context construction
    │  token-bounded evidence bundle
    ▼
Grounded generation
    ├──► free-form answer with citations
    └──► schema-validated company research
             │
             ▼
Evaluation across retrieval, grounding, answers, citations, and abstention
```

## Proposed components

### Domain models

Provider-neutral typed models will represent source documents, pages or logical elements,
chunks, retrieval results, evidence bundles, answers, citations, and evaluation examples.
Provenance is part of these models rather than being appended only at answer time.

Candidate metadata includes company, document title, document type, fiscal period, source,
page, section, and chunk ID. Fields remain optional unless the pipeline can derive them
reliably. Stable internal IDs will distinguish derived objects from source metadata.

### Document processing

Parsing adapters will convert supported inputs into a canonical document representation.
Normalization will make conservative, inspectable changes. Chunking will operate on that
representation and preserve lineage back to source pages. Parser and chunker choices will be
made with representative documents and measured, rather than assumed during scaffolding.

M1 implements the first part of this boundary. A PyMuPDF adapter accepts local PDFs and returns
immutable `ParsedDocument` and `ParsedPage` models. Third-party objects do not cross the
ingestion boundary. Each page carries its content-derived document ID, source reference,
zero-based physical PDF index, and one-based canonical page number. Printed page labels remain
unknown. Pages without extractable text produce explicit warnings.

M2 implements the second part with immutable `DocumentMetadata`, `DocumentChunk`, and
`ChunkedDocument` models plus a provider-neutral `ProvenanceAwareChunker`. It joins nonempty
pages in physical order and applies configurable character-based splitting that prefers
paragraph, line, and word boundaries. Chunks may cross pages and retain an ordered reference
to every page that contributed text. Stable chunk IDs include the parent document identity,
algorithm version, configuration, order, page indexes, and exact text. Optional research
metadata is accepted only from an external caller and is never guessed by the chunker.

### Indexing and retrieval

M3 adds an `Embedder` protocol, an OpenAI `text-embedding-3-small` adapter, immutable
`EmbeddingVector` and `VectorRecord` models, an atomic `ChunkIndexingService`, and a persistent
`SQLiteVectorStore`. Stable chunk IDs are vector-record primary keys. Complete M2 chunks remain
attached to vectors so source, page references, and externally supplied metadata survive
indexing. A manifest prevents provider, model, dimension, and schema mismatches.

SQLite stores inspectable JSON vectors and metadata under ignored `artifacts/`. It does not
provide similarity search or a native approximate-nearest-neighbor index in M3. Retrieval will
be introduced behind a separate boundary in M4, beginning with an exact baseline appropriate
to the measured corpus size. A specialized vector engine will be considered only if scale or
evaluation requires it. Reranking remains deferred until retrieval evaluation shows a gain.

M4 extends the existing store with exact cosine-similarity search and adds a
`SemanticRetriever` boundary. The retriever validates and embeds a query in the same embedding
space as document chunks, applies optional exact filters over stored metadata, and returns
typed `RetrievalResult` objects ordered by descending similarity. Results retain the complete
M2 chunk, so source and page provenance do not depend on a later prompt or citation stage.
Equal scores use stable chunk IDs for deterministic ordering. Search remains an exact linear
scan suitable for the current local corpus; reranking and answer generation remain deferred.

### Answering and structured research

M5 implements the first answering layer with a provider-neutral `Generator`, deterministic
`ContextBuilder`, and `GroundedRAGService`. The service consumes M4 `RetrievalResult` objects
instead of reaching into storage. It preserves rank order, includes stable source/chunk/page
identifiers, and admits only complete evidence blocks under explicit chunk and character
limits. The OpenAI adapter uses the Responses API and a schema-validated answer containing an
answer string and an insufficient-evidence flag.

No retrieval result causes deterministic abstention without an API call. If evidence is
present but weak, the prompt requires abstention and the structured flag lets application
code normalize the response to a stable insufficiency statement. The returned `RAGAnswer`
retains only the retrieval results actually placed in context. M6 will convert that preserved
evidence into polished citations and validate evidence references. Structured company
research remains deferred to M7.

### Evaluation

Evaluation will use a small versioned dataset of questions, expected evidence, expected
answers or key facts, and deliberately unanswerable questions. Retrieval and generation will
be callable independently so failures can be localized. Machine metrics will be combined
with inspectable per-example results; LLM-as-judge may supplement but will not replace
deterministic checks and human review.

## Proposed V1 stack

- **Python 3.11+** for typing support and ecosystem compatibility.
- **Frozen standard-library dataclasses** for domain schemas. They provide explicit validation,
  type checking, and immutable value objects without a runtime schema dependency at this stage.
- **PyMuPDF** for M1 PDF validation and plain-text extraction. It offers mature page-aware
  parsing with a small direct API; its AGPL/commercial licensing and layout limitations must be
  considered before commercial distribution.
- **pytest** for tests, **Ruff** for linting/formatting, and **mypy** for static type checking.
- **OpenAI `text-embedding-3-small`** behind a provider-neutral adapter, using 1,536 dimensions
  by default. It is a low-cost general retrieval baseline whose financial-domain quality will
  be measured later.
- **SQLite vector-record persistence** for V1. It is transactional, inspectable, and requires
  no service. M4 evaluation will determine whether a native vector engine is warranted.
- **OpenAI `gpt-6-luna`** with low reasoning effort behind a provider-neutral generator. It is
  a cost-conscious baseline for focused evidence synthesis; later evaluation must compare it
  with stronger models before production use.
- **Pydantic** only at the OpenAI adapter boundary for Structured Outputs response validation.
  Provider-neutral domain objects remain frozen standard-library dataclasses.

LangChain or LlamaIndex may be used later for a narrow capability if they reduce maintenance
without obscuring provenance or evaluation. The core domain models and pipeline boundaries
should not depend on them. LangGraph and multi-agent orchestration are outside V1 unless a
future requirement demonstrates a real need.

## Planned package shape

Modules will be introduced only when their milestone begins. The likely eventual boundaries
are `domain`, `ingestion`, `chunking`, `indexing`, `retrieval`, `generation`, `research`, and
`evaluation`. Avoid creating empty abstractions in advance.

## Cross-cutting constraints

- Raw source data and generated indexes remain outside Git.
- Identical input plus configuration should produce stable document and chunk identifiers.
- Page numbers must distinguish source labels from zero-based internal indexes when both exist.
- Logs and evaluation artifacts must make failures inspectable without exposing secrets.
- Absence of evidence is a supported outcome, not an invitation to fill gaps from model memory.

