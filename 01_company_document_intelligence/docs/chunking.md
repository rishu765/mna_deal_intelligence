# Document metadata and chunking

Milestone 2 converts the page-oriented output from PDF ingestion into ordered,
retrieval-ready `DocumentChunk` objects. It does not create embeddings or an index.

## Data flow

```text
ParsedDocument / ParsedPage
        |
        | optional trusted DocumentMetadata
        v
ProvenanceAwareChunker + ChunkingConfig
        |
        v
ChunkedDocument / ordered DocumentChunk objects
```

The chunker consumes M1 models directly. It does not reparse or normalize the PDF and no
PyMuPDF object crosses into the chunking or domain layers.

## Metadata model

Metadata is separated by confidence and origin:

1. **Reliably known at ingestion:** content-derived document ID, local source filename/path,
   media type, file size, source digest, physical PDF index, canonical page number, and parser
   warnings. These facts flow from M1 without caller input.
2. **Externally supplied:** `DocumentMetadata` accepts optional company, document title,
   document type, fiscal year, reporting period, source URL, and filing type. A caller must
   obtain these values from a trusted catalog, user, or later verified process.
3. **Deferred inference:** company, period, document type, printed page labels, and sections
   are never guessed from filenames or text in M2. `DocumentChunk.section` remains `None`
   because no reliable section detector exists yet.

Unknown optional values remain `None`. This avoids turning a weak guess into metadata that a
later retrieval filter or citation might incorrectly treat as fact.

## Chunk model

Each immutable `DocumentChunk` contains:

- a deterministic `chunk_id`;
- its parent `document_id`;
- a zero-based `chunk_index` and derived one-based `chunk_number`;
- the exact chunk text;
- the M1 `DocumentSource`;
- an ordered tuple of every contributing `ChunkPageReference`;
- optional externally supplied `DocumentMetadata`; and
- an optional section field, currently unset.

`ChunkedDocument` owns the ordered tuple of chunks and also retains document metadata, source,
and M1 parser warnings. Empty or image-only documents can therefore yield zero chunks without
discarding the reason recorded by ingestion.

## Baseline strategy

The baseline uses **characters** as its unit. Characters are deterministic, easy to inspect,
and require no tokenizer or embedding-model dependency before M3 selects a model. Token-based
splitting would track model context more precisely, but it would prematurely couple M2 output
to a provider tokenizer. English financial text often averages several characters per token,
so the defaults are a practical starting point that M3/M4 evaluation can tune.

| Setting | Default | Meaning |
| --- | ---: | --- |
| `max_characters` | 1,800 | Maximum characters in a chunk, including overlap |
| `overlap_characters` | 200 | Text repeated from the prior chunk |
| `min_chunk_characters` | 300 | Earliest preferred split and minimum targeted final span |

At typical English token density, 1,800 characters is roughly 400-500 tokens. This size aims
to preserve a paragraph group or financial explanation while remaining focused enough for
retrieval. The 200-character overlap carries nearby definitions, sentence continuations, and
table headers across a boundary. These estimates are guidance rather than guarantees because
token density varies by content and model.

The splitter prefers the last paragraph break before the maximum size, then a line break,
then a space. It uses a hard character boundary only when no suitable boundary exists. It also
balances a very short final span when practical. Configuration validation requires positive
size limits and overlap smaller than the minimum useful span, which guarantees forward
progress.

## Page boundaries and provenance

Nonempty pages are joined in physical order with two newline characters. Chunks may cross a
page boundary because annual-report sentences, notes, and tables often continue onto the next
page. For every chunk, interval intersection records each page that contributed actual page
text. Separator characters alone do not make a page a contributor.

`ChunkPageReference` preserves the M1 convention:

- `pdf_page_index`: zero-based physical position used by PDF software;
- `page_number`: one-based canonical number, always `pdf_page_index + 1`;
- `printed_page_label`: human-visible label, `None` unless reliably extracted elsewhere.

This supports later citations such as pages 84-85 without claiming that those canonical
numbers match labels printed inside the report.

## Stable chunk IDs

Chunk IDs use SHA-256 over the chunking algorithm version, parent document ID, complete
chunking configuration, zero-based chunk order, contributing physical-page indexes, and exact
chunk text. The ID format is `sha256:<hex digest>`.

Identical source bytes, configuration, and implementation version produce identical IDs.
Changing relevant content or chunking configuration changes the IDs, preventing an index from
silently confusing incompatible derived chunks.

## Empty and low-text pages

Whitespace-only pages are excluded from the joined text and produce no useless chunks. M1
parser warnings remain on `ChunkedDocument`. A short page with real text is retained and may
join adjacent pages; M2 has no arbitrary page-level text threshold that could discard a
material heading, footnote, or amount.

## Manual inspection

After installing the project, parse and chunk a local PDF with bounded output:

```powershell
madi-inspect-chunks "data/raw/example-annual-report.pdf"
```

The JSON summary includes counts, configuration, metadata, chunk IDs, order, character
lengths, page references, and short previews. It displays at most five chunks and 300 preview
characters per chunk by default. For example:

```powershell
madi-inspect-chunks "data/raw/example.pdf" `
  --chunk-size 1800 --overlap 200 --min-chunk-size 300 `
  --max-chunks 3 --preview-chars 200 `
  --company "Example plc" --fiscal-year 2025
```

Use supplied metadata only when its source is trustworthy.

## Known limitations and deferred work

- PyMuPDF plain-text extraction can flatten tables, reorder columns, and lose visual context.
  The chunker preserves extracted characters but is not table-aware.
- Multi-column reading order depends on M1 extraction quality.
- Scanned or image-only pages need OCR, which is not implemented.
- Boundary preferences are structural heuristics, not semantic topic detection.
- A hard split can divide a long unbroken number/string, and overlap can repeat partial rows.
- Character lengths do not guarantee a fixed embedding-model token count.
- Printed page labels and sections remain unknown.

Semantic chunking remains deferred until evaluation demonstrates a clear gain. M3 consumes
these chunks through provider-neutral embedding and index interfaces without changing
provenance semantics merely to match a vector-store schema.
