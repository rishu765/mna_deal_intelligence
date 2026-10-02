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

An embedding interface and a vector-index interface will isolate external providers. V1
should begin with one simple local index. Retrieval will return ranked chunks and scores in a
stable result model. Reranking will be added only if baseline evaluation shows a worthwhile
gain for tables, financial terminology, or long-document ambiguity.

### Answering and structured research

The answering layer will consume an explicit evidence bundle rather than reaching directly
into storage. Prompts will require evidence-grounded answers and abstention when support is
missing. Structured research outputs will use validated schemas and retain citations at the
field or claim level where practical.

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
- **Provider adapters** for embeddings and generation. The initial providers and models remain
  undecided until their cost, availability, and evaluation needs are clear.
- **A lightweight local vector store** for V1. FAISS, Chroma, and SQLite-backed alternatives
  will be compared in Milestone 3; no dependency is selected in Milestone 0.

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

