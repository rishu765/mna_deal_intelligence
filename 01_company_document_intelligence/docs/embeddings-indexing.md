# Embeddings and vector indexing

Milestone 3 converts M2 `DocumentChunk` objects into fixed-dimensional vectors and persists
complete vector records for M4. It deliberately does not embed user queries or perform search.

## Why embeddings are needed

An embedding represents text as a list of floating-point values. Texts with related meaning
should have vectors that are close under a suitable distance measure. RAG retrieval can later
embed a question and compare it with indexed chunk vectors to select relevant evidence.

M3 establishes the document side of that process:

```text
DocumentChunk
    |
    v
Embedder interface
    |
    v
EmbeddingVector + original DocumentChunk
    |
    v
VectorRecord
    |
    v
SQLiteVectorStore (local persistent upsert)
```

## Embedding baseline

- **Provider:** OpenAI
- **Model:** `text-embedding-3-small`
- **Default dimension:** 1,536
- **API:** OpenAI embeddings endpoint through the official Python SDK
- **Default application batch size:** 64 chunks per request

The model is a practical baseline because it offers useful general semantic-retrieval quality,
multilingual support, a large 8,192-token input limit, and low per-token cost. The official
documentation lists the default vector size as 1,536 and current input pricing as $0.02 per
million tokens. See the [OpenAI embeddings guide](https://developers.openai.com/api/docs/guides/embeddings)
and [model page](https://developers.openai.com/api/docs/models/text-embedding-3-small).

This is a general embedding model rather than a finance-specific model. Its performance on
annual-report terminology, tables, and peer-company language must be measured during M4/M8.
`text-embedding-3-large` may improve retrieval quality, but its 3,072 default dimensions,
higher storage, latency, and API cost are not justified before baseline evaluation. A local
sentence-transformer would avoid API spend and external data transfer, but adds model downloads,
runtime dependencies, and local compute requirements. The `Embedder` protocol keeps either
replacement possible without changing chunks, vector records, or indexing orchestration.

OpenAI v3 embeddings support shortened dimensions. M3 explicitly sends the configured
dimension and stores that dimension in an index manifest. Changing the model or dimension
requires a separate/rebuilt index so incompatible vectors cannot mix silently.

## Configuration

The application reads process environment variables directly:

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | required | Credential used only by the OpenAI SDK |
| `MADI_EMBEDDING_PROVIDER` | `openai` | Baseline provider selector |
| `MADI_EMBEDDING_MODEL` | `text-embedding-3-small` | Model identity |
| `MADI_EMBEDDING_DIMENSION` | `1536` | Expected and requested vector length |
| `MADI_EMBEDDING_BATCH_SIZE` | `64` | Chunks sent per API request |
| `MADI_VECTOR_DB_PATH` | `artifacts/vector_index.sqlite3` | Local SQLite file |

`.env.example` is a safe reference, but the project does not automatically load `.env` files.
For PowerShell development, export values in the current session:

```powershell
$env:OPENAI_API_KEY = "your-key"
$env:MADI_VECTOR_DB_PATH = "artifacts/vector_index.sqlite3"
```

Missing keys, unsupported providers, noninteger dimensions/batch sizes, and nonpositive values
fail with application-specific configuration errors. Secrets are never stored in vector
records or printed by the CLI.

## Provider contract and errors

The provider-neutral `Embedder` protocol exposes model/provider identity, dimension,
`embed_text`, and ordered `embed_batch`. `OpenAIEmbedder` validates nonblank input, sorts API
items by response index, verifies output count and dimension, converts provider values to
immutable tuples, and wraps provider failures without including the API key.

The official SDK is isolated in `embeddings/openai_provider.py`. Provider response objects do
not enter domain or indexing code.

## Vector records and provenance

`VectorRecord` uses the stable M2 `chunk_id` as `record_id` and contains:

- the complete immutable `DocumentChunk`, including text, document ID, order, source,
  page references, optional supplied metadata, and section;
- an `EmbeddingVector` containing provider, model, dimension, and finite float values.

Keeping the complete chunk makes a local index self-contained and debuggable. It duplicates
some source information across records, which is acceptable for the V1 scale and safer than
losing citation provenance. A production system could normalize repeated document metadata
into related tables without changing the domain contract.

## SQLite vector-record store

M3 uses standard-library SQLite because it is transactional, persistent, inspectable, easy to
test, and requires no service or additional vector-database dependency. The database contains:

- an index manifest with schema version, embedding provider, model, and dimension;
- one vector-record row per stable chunk ID;
- chunk text, source, page references, metadata, and vector values serialized as JSON.

SQLite is a vector **record store** in M3, not a native approximate-nearest-neighbor index.
This keeps storage understandable while M4 establishes the corpus size and retrieval baseline.
M4 can implement exact cosine scoring for a small portfolio corpus or replace the store behind
the `VectorStore` interface if evaluation shows a need for FAISS, pgvector, or another ANN
engine. Search methods are intentionally absent in M3.

The default database is under `artifacts/`, which Git ignores. It is reproducible from source
PDFs and should not be committed.

## Indexing and upsert behavior

`ChunkIndexingService`:

1. validates and de-duplicates the input by stable chunk ID;
2. rejects conflicting objects that claim the same ID;
3. embeds unique chunks in deterministic input order and configurable batches;
4. validates each batch count, vector dimension, and finite values;
5. constructs provider-neutral vector records; and
6. writes all records in one SQLite transaction after every embedding batch succeeds.

SQLite uses `ON CONFLICT(record_id) DO UPDATE`. Re-indexing the same chunks refreshes their
record rather than creating duplicates. The store manifest rejects records or reopened indexes
with a different model, provider, dimension, or schema version.

No SQLite write occurs until all API batches succeed. This prevents a provider failure in a
later batch from leaving a partially indexed document. API calls that succeeded before a
failure may still incur cost and must be repeated on retry because M3 does not add an embedding
cache.

## Cost, rate limits, and large reports

Embedding one string needs one input; indexing a long annual report can require hundreds of
chunk inputs and multiple requests. Batching reduces HTTP overhead, while the configurable
batch size lets developers respond to provider payload and rate limits. Charges depend on the
total input tokens, including M2 overlap text that appears in more than one chunk.

M3 is intentionally synchronous. It does not add concurrent requests, retry/backoff policy,
distributed workers, or a cache. Those should be introduced only after real indexing volumes
and failure patterns justify them.

## Build and inspect an index

After installing the package and exporting `OPENAI_API_KEY`:

```powershell
madi-build-index "data/raw/example-annual-report.pdf"
```

Optional trusted metadata and a custom path can be supplied:

```powershell
madi-build-index "data/raw/example-annual-report.pdf" `
  --index-path "artifacts/example.sqlite3" `
  --company "Example plc" --fiscal-year 2025
```

The bounded JSON summary reports document/page/chunk counts, API batch count, provider, model,
dimension, upsert and total-record counts, database path, and one provenance example. It does
not print vectors or perform retrieval. Delete the generated database and rerun the command to
rebuild it from source.

## Limitations and M4 boundary

- Embedding generation requires network access, an OpenAI API key, and incurs usage cost.
- No automatic retries, backoff, caching, or resume checkpoints exist yet.
- JSON vectors are larger and slower to scan than compact binary or native vector formats.
- SQLite provides transactional persistence but no ANN index.
- General embeddings may miss specialized financial relationships; evaluation must measure it.
- Source extraction and chunking limitations from M1/M2 still affect embedding quality.
- Index portability depends on preserving the configured model and dimension.

M4 will add query models, query embedding, similarity scoring, top-k retrieval, and retrieval
diagnostics. Those behaviors are intentionally absent from M3.
