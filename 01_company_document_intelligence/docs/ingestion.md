# PDF ingestion and parsing

## Supported input

Milestone 1 supports local files with a `.pdf` extension whose contents are recognized as PDF.
The parser targets text-oriented annual reports, filings, financial reports, and investor
presentations. Other formats, URLs, password-protected PDFs, and OCR are not supported.

```python
from ma_company_intelligence.ingestion import parse_pdf

document = parse_pdf("data/raw/example-annual-report.pdf")
```

`PdfParser` provides the equivalent object-oriented entry point.

## Parser choice

M1 uses PyMuPDF directly. It provides deterministic physical-page iteration, mature plain-text
extraction, useful PDF validation errors, and a small API without an orchestration framework.
PyMuPDF is available under GNU AGPL or a commercial Artifex license; future distribution or
commercial deployment must review its licensing obligations.

`pdfplumber` was considered because it exposes layout and table primitives. It was not selected
because M1 needs page-aware plain text rather than table reconstruction. `pypdf` was considered
for its permissive license and pure-Python design, but PyMuPDF was selected for extraction
maturity and performance on long reports. Parser quality should be revisited with a
representative corpus rather than adding several parsers speculatively.

## Internal representation

The parser returns immutable, provider-neutral dataclasses:

- `DocumentSource` records filename, resolved absolute path, PDF media type, byte size, and
  SHA-256 digest.
- `ParsedDocument` contains a stable content-derived ID, its source, ordered pages, and
  recoverable warnings.
- `ParsedPage` contains extracted text and `SourceProvenance`.
- `SourceProvenance` keeps a page traceable after later transformations.

The document identifier is `sha256:<file digest>`. Identical bytes produce the same ID,
regardless of filename or location. M1 does not infer company, document type, fiscal year,
financial period, or section metadata.

## Page-number convention

| Field | Meaning |
| --- | --- |
| `pdf_page_index` | Zero-based physical position used by PDF libraries. |
| `page_number` | One-based canonical page number used by this project: index + 1. |
| `printed_page_label` | Human-visible label printed in the document; always `None` in M1. |

The first physical PDF page has `pdf_page_index=0` and `page_number=1`. A cover page can shift
this canonical number relative to a number printed inside the report. M1 never claims that
canonical page numbers are printed page labels.

## Normalization and warnings

Normalization standardizes CRLF and CR line endings to LF and removes non-text Unicode control
characters. It preserves spaces, tabs, newlines, punctuation, currency symbols, percentages,
parentheses, and visible Unicode characters.

A page with no extractable text remains in the ordered page list and emits an
`empty_page_text` warning. It is not silently dropped and OCR is not attempted.

## Failure behavior

Expected failures use subclasses of `DocumentIngestionError` for missing paths, unsupported
extensions, invalid sources, corrupt/non-PDF content, password-protected PDFs, zero-page PDFs,
and page-level extraction failures. Failures do not return empty documents.

## Manual validation

After installing the project, inspect a local PDF with bounded output:

```powershell
madi-inspect-pdf "data/raw/example-annual-report.pdf"
madi-inspect-pdf "C:\path\report.pdf" --max-pages 5 --preview-chars 500 --max-warnings 20
```

The command parses the complete file but prints only bounded page previews and warnings, plus
the document ID, resolved source, page count, provenance, total warning count, and whether the
warning list was truncated.

## Known limitations

- Plain text follows encoded PDF order and may not match natural reading order in columns.
- Tables remain text; rows, columns, merged cells, and visual alignment are not reconstructed.
- Image-only and scanned pages require OCR, which is deferred.
- Printed page labels are not extracted.
- Forms, annotations, charts, images, and styling are not represented.
- Byte-level changes produce a new document ID even when visible content is unchanged.

Chunking, enriched metadata, and layout-aware representation remain M2 concerns. Embeddings,
retrieval, and generation remain later milestones.
