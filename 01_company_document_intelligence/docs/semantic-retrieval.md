# Semantic retrieval

Milestone 4 retrieves the most relevant M2 chunks from the persistent M3 vector store. It
returns ranked evidence with complete provenance and does not generate an answer.

## Data flow

```text
User query
    |
    v
SemanticRetriever validation
    |
    v
M3 Embedder (same provider, model, and dimension as document vectors)
    |
    v
SQLiteVectorStore exact cosine similarity
    |
    v
VectorSearchMatch objects
    |
    v
Ranked RetrievalResult objects with complete DocumentChunk provenance
```

Query and document vectors must share the same embedding provider, model, and dimension. The
retriever checks this when it is constructed and validates the query vector again before
search. Blank queries, nonpositive `top_k`, dimension mismatches, non-finite values, and
zero-magnitude query vectors fail explicitly.

## Retrieval interface

`SemanticRetriever.retrieve(query, top_k=5, filters=None)` returns an immutable ordered tuple
of `RetrievalResult` objects. Every result contains:

- a one-based rank;
- a cosine-similarity score;
- the complete M2 `DocumentChunk`, including stable chunk ID, text, document ID, source,
  ordered page references, optional trusted metadata, and section.

Convenience properties expose chunk ID, document ID, and text without converting the result
to a provider-specific or prompt-specific object. M5 can therefore build evidence context from
the same result type without depending on SQLite or OpenAI response classes.

## Exact cosine similarity

The SQLite store loads candidate vector records and calculates cosine similarity:

```text
cosine_similarity = dot(query, chunk) / (norm(query) * norm(chunk))
```

Scores range from -1 to 1:

- values nearer 1 indicate vectors pointing in a similar semantic direction;
- values near 0 indicate little angular similarity;
- values nearer -1 indicate opposing vector directions.

Results are sorted by descending score. Equal scores use ascending stable chunk ID as a
deterministic tie-breaker. Rank is assigned after sorting and begins at 1.

OpenAI v3 embeddings are normally unit-normalized, but the implementation calculates both
norms so the store also works correctly with compatible alternative providers and test
embeddings. Scores are useful for ordering results within one query. Their absolute values
should not be treated as calibrated probabilities or compared blindly across different
queries and corpora.

M4 does not impose a minimum score threshold. An arbitrary threshold could hide relevant
evidence before representative retrieval evaluation establishes a defensible value. Callers
receive up to `top_k` results; an empty store or filters with no matches return an empty tuple.

## Top-k baseline

The default `top_k` is 5. This is large enough to expose several potentially relevant passages
for inspection while remaining small enough for a later evidence context. It is configurable
per request and must be positive. M5 will decide how many returned chunks fit its context
budget; that concern does not change M4 ranking.

## Exact metadata filters

`RetrievalFilters` supports exact matching on fields that already exist reliably in M2/M3:

- `document_id`;
- source filename;
- company;
- document type;
- fiscal year.

All supplied filters are combined with AND semantics and applied before similarity scoring.
Filters do not improve semantic relevance; they restrict the candidate set. Optional company,
document type, and fiscal year values only match when trusted metadata was supplied during
chunking/indexing. Missing values remain missing and are never inferred during retrieval.

The initial SQLite implementation filters in Python because M3 stores metadata as inspectable
JSON and V1 corpora are small. Production-scale storage would push indexed filters into the
database while preserving the same `RetrievalFilters` contract.

## Provenance

M3 stores the complete immutable chunk alongside every vector. Search returns that original
chunk rather than reconstructing an incomplete search-result shape. Consequently each
`RetrievalResult` retains:

- stable chunk and document IDs;
- source filename, path, digest, and media type;
- zero-based physical PDF indexes;
- one-based canonical page numbers;
- printed page labels when reliably available;
- every page contributing to a cross-page chunk;
- optional externally supplied company-document metadata.

This is the evidence M5–M7 use for grounded context, citations, and structured research.

## Lightweight quality check

The automated suite contains a tiny deterministic company-research corpus with separate
chunks for revenue, employees, and disclosed risks. Handcrafted vectors verify that:

- `What was FY25 revenue?` ranks the revenue chunk first;
- `Which risks were disclosed?` ranks the risk chunk first;
- `top_k` truncates in rank order;
- exact company/year filters exclude a more similar chunk from another company;
- ties resolve by stable chunk ID.

This makes ranking behavior inspectable without network calls or API spend. It is a smoke test
of retrieval mechanics, not the formal retrieval evaluation dataset planned for M8.

## Manual retrieval

After installing the project and exporting `OPENAI_API_KEY`:

```powershell
madi-retrieve "data/raw/example-annual-report.pdf" `
  "What were the main growth drivers?" `
  --top-k 3 --preview-chars 250
```

Optional trusted metadata can be supplied during indexing, and exact retrieval filters can be
added separately:

```powershell
madi-retrieve "data/raw/example-annual-report.pdf" `
  "What was FY25 revenue?" `
  --company "Example plc" --fiscal-year 2025 `
  --filter-company "Example plc" --filter-fiscal-year 2025
```

The command runs PDF parsing, chunking, document embedding/upsert, query embedding, and
retrieval. Its bounded JSON output includes rank, score, chunk and document IDs, source
filename, page numbers, trusted metadata, and a short text preview. It never prints vectors or
generates an answer.

Example shape:

```text
Query: What was FY25 revenue?
1. score=0.9986, report.pdf, page 1
   FY25 revenue increased to $125 million due to subscription growth.
2. score=0.0526, report.pdf, page 3
   Material risks include foreign exchange and customer concentration.
```

The displayed values above illustrate the deterministic synthetic quality fixture rather than
a claim about a real annual report.

## Limitations and deferred work

- Exact search deserializes and scores every candidate in Python, so latency grows linearly
  with index size.
- SQLite JSON vectors are optimized for clarity rather than numeric scan performance.
- General semantic embeddings can miss exact financial terminology, identifiers, or tabular
  relationships.
- No lexical/BM25 retrieval, hybrid fusion, query expansion, or reranking exists.
- No minimum relevance threshold or calibrated confidence exists.
- Metadata filters are exact and case-sensitive.
- Provider requests still have the M3 network, cost, retry, and rate-limit constraints.
- PDF extraction and chunking errors can reduce retrieval quality.

Reranking is deferred until evaluation shows that the vector baseline returns useful evidence
but orders ambiguous candidates poorly. M5 will consume retrieval results to construct bounded
evidence context and generate a grounded answer; that generation behavior is not implemented
in M4.
