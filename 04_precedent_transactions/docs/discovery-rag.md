# Historical deal discovery and document retrieval

## Scope

M1/2 answers whether the system can generate plausible historical deal candidates and return the
exact passages needed for later analysis. It stops at evidence retrieval. M3 will decide how to
extract, normalize, reconcile, and verify facts from those passages.

## Discovery

`DealDiscoveryProvider` accepts one typed `AcquisitionContext` and returns provisional
`CandidateTransaction` objects. The context supports industry, business description, geography,
announcement range, transaction type, buyer type, same-currency size bounds, and keywords.

The implemented `FixtureDealDiscoveryProvider` reads synthetic JSON and applies deterministic hard
filters followed by token-overlap ranking. It is suitable for tests, CI, demos, and contract
development. No live provider is shipped because public web search alone is neither complete nor a
stable transaction database, while dependable commercial sources require licensed credentials.
Future news, regulatory, exchange, or database adapters can implement the one provider contract.

Discovery is candidate generation. A match does not mean the transaction is a valid precedent.

## Identity resolution

`TransactionIdentityResolver` merges candidates only when they share an external deal identifier
or an exact normalized acquirer/target/announcement-date/transaction-type fingerprint. It removes
common legal suffixes but does not rely on headlines. A shared target within 30 days with
insufficient matching signals is retained as separate candidates and flagged as ambiguous. This
protects competing bids and amendments from aggressive deduplication.

Complex amended bids, consortium changes, legal-entity reorganizations, and multi-step stake
purchases remain later resolution work.

## Source discovery and ingestion

`DealDocumentSource` records source and transaction IDs, source type, title, path/URL, publisher,
publication date, jurisdiction, format, retrieval time, reliability, official-source status, and an
optional SHA-256 checksum. `FixtureDocumentCatalog` filters by resolved transaction ID and removes
exact duplicate source/checksum records.

`DealDocumentIngestor` supports UTF-8 text and simple HTML with heading-derived sections. It
prevents local path escape and verifies checksums when present. PDF is a port: the optional
`Project1PdfParserAdapter` translates Project 1 parsed pages and warnings when that package is
installed. Project 4 does not copy the PyMuPDF stack or require Project 1 for text/HTML operation.

Document failures are isolated. The pipeline records the failure and indexes remaining documents.
Remote fetching, robots/rate-limit policy, OCR, JavaScript-rendered pages, and document caching are
not implemented.

## Chunking and metadata

`TransactionAwareChunker` follows Project 1's deterministic character-window pattern with preferred
boundaries and overlap. Project 4 owns its chunk type because deal retrieval requires transaction
ID, acquirer, target, source type, jurisdiction, official-source flag, reliability, and document
format in addition to document/page/section provenance.

Chunk IDs hash algorithm version, document, position, page, and text. Indexing treats an identical
ID/content pair as idempotent and rejects an ID mapped to different content.

## Index and retrieval

`InMemoryDealIndex` computes every vector and lexical record before mutating the index, so embedding
failure cannot leave a partial batch. It stores deterministic normalized feature-hash vectors and
BM25 term frequencies. This is an offline reference index, not a production vector database.

The semantic channel canonicalizes a small transaction vocabulary and hashes tokens plus bigrams
into a fixed-dimensional vector. The lexical channel uses BM25. Hybrid fusion is:

```text
fused = 0.55 × max(0, cosine_similarity)
      + 0.45 × (BM25 / maximum_eligible_BM25)
```

Results below `0.05` are omitted. Scores are relevance signals, not probabilities or fact
confidence. Ties use chunk ID for reproducibility.

Filters are applied before both channels and cover transaction ID, source type, publication dates,
acquirer, target, jurisdiction, and format. This prevents one deal's passage from silently
supporting another deal.

## Provenance and quality

Every result returns query, rank, transaction and chunk IDs, semantic/BM25/fused scores, text,
source metadata, official-source status, and a Project 4 `EvidenceReference`. The evidence carries
publisher, publication date, retrieval time, document, page, section, chunk, text location,
reliability, and excerpt.

Retrieval warnings cover:

- no eligible passage;
- no positive semantic match;
- no lexical term match;
- only low fused scores;
- unofficial sources only;
- differing headline transaction-value language across multiple documents.

Conflict detection is deliberately narrow. It does not label documents as conflicting merely
because they contain revenue, EBITDA, per-share price, and purchase price in the same result set.

## Project 1 reuse

Reused as design and behavior:

- page-aware provenance and deterministic source identifiers;
- character chunking with overlap and preferred boundaries;
- provider-neutral embedding protocol;
- atomic batch indexing and cosine retrieval validation;
- cited retrieval results rather than uncited answer text.

Adapted:

- PDF parsing through `Project1PdfParserAdapter`;
- document and chunk models extended with transaction metadata;
- semantic-only retrieval extended with BM25 and hybrid fusion.

Not directly reusable:

- Project 1 company/fiscal-year filters do not express transaction, buyer, target, jurisdiction,
  source-quality, or deal-document fields;
- its SQLite store persists only its own chunk type;
- its RAG answer generation crosses the M1/2 boundary because Project 4 must expose evidence to M3
  before structured extraction.

## Project 2 reuse

Project 2's multi-provider service, partial-provider failure handling, local fixture provider,
normalization, and conservative evidence merge patterns informed discovery. Its company identity
model is not reused because an M&A transaction can have competing acquirers, amendments, repeated
targets, and stake sequences.

## LangChain decision

LangChain is not used in M1/2. The implemented text/HTML parsers, Project 1 adapter, in-memory
index, BM25 scorer, filters, and fusion are concise typed code. Wrapping them in LangChain would add
dependency weight without improving behavior. A future live loader, production embedding provider,
or composed retriever may use LangChain behind the current ports when there is a concrete benefit.

## Benchmark

`evaluation/retrieval_cases.json` contains six deal questions: cash consideration, per-share offer,
stock consideration, ownership acquired, completion/withdrawal, and announcement-period EBITDA.
The evaluator reports Hit@K, Recall@K, MRR, and per-case first rank. Current fixture results are
Hit@3 `1.00`, Recall@3 `1.00`, and MRR `0.9167`.

The corpus is tiny, synthetic, and intentionally easy to inspect. These metrics catch milestone
regressions; they do not estimate performance on real filings or news.
