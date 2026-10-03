# API and production hardening

M9/10 exposes the evaluated Project 1 capabilities through a local FastAPI interface and adds
bounded inputs, sanitized errors, provider timeouts/retries, request correlation, and explicit
service wiring. The API is a transport layer: parsing, chunking, indexing, retrieval, grounded
answering, citations, and structured research remain in their existing application/domain
services.

## Architecture

```text
HTTP client
  -> FastAPI route and Pydantic request schema
  -> lazy ServiceContainer
  -> ProjectApplicationService
       -> M1 parser -> M2 chunker -> M3 indexer/SQLite store
       -> M4 retriever -> M5/M6 grounded RAG and citations
       -> M6/7 targeted retrieval and structured research
  -> explicit Pydantic response schema
```

Provider clients are constructed once on the first provider-dependent request. SQLite stores
are opened and closed per operation so a connection is not shared unsafely across FastAPI worker
threads. The persistent index still uses stable chunk-ID upserts, so indexing the same unchanged
document does not create duplicate rows.

## Starting the API

Install development dependencies, export configuration, and start from the Project 1 directory:

```powershell
$env:OPENAI_API_KEY = "your-key"
$env:MADI_DOCUMENT_ROOT = "data/raw"
madi-api
```

The default address is `http://127.0.0.1:8000`. Interactive OpenAPI documentation is available
at `/docs`, with the machine schema at `/openapi.json`. Bind to another host only when the local
network exposure is intentional:

```powershell
madi-api --host 0.0.0.0 --port 8000
```

Health remains available without provider credentials. Provider-dependent routes return a safe
`configuration_error` until valid credentials are supplied.

## Endpoints

### `GET /health`

Reports only process liveness and the public application version. It does not reveal provider
credentials, environment values, index paths, or document locations.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

### `POST /v1/documents/index`

Accepts a local path reference beneath `MADI_DOCUMENT_ROOT`, optional trusted metadata, and
bounded chunking parameters. This developer API intentionally uses references instead of file
uploads; it does not provide cloud storage or arbitrary filesystem access.

```powershell
$body = @{
  source_reference = "example-annual-report.pdf"
  metadata = @{
    company = "Example plc"
    document_title = "Annual Report FY2025"
    document_type = "annual_report"
    fiscal_year = 2025
  }
} | ConvertTo-Json -Depth 4

Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/v1/documents/index `
  -ContentType application/json -Body $body
```

Successful output contains the stable document ID, safe source filename, page/chunk counts,
upsert count, total index records, and parser warnings. It does not return the local source or
index path.

### `POST /v1/answers`

Uses the existing semantic retriever, context builder, generator, and citation mapper.

```powershell
$body = @{
  question = "What were the company's main revenue growth drivers?"
  top_k = 5
  filters = @{ company = "Example plc"; fiscal_year = 2025 }
} | ConvertTo-Json -Depth 3

Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/v1/answers `
  -ContentType application/json -Body $body
```

The response includes the answer, explicit `insufficient_evidence` state, generator identity,
validated citations, the bounded evidence supplied to generation, and warnings. Insufficient
evidence is a valid `200` research outcome rather than a transport failure.

### `POST /v1/research`

Invokes the existing targeted retrieval and structured research service.

```powershell
$body = @{
  company_name = "Example plc"
  filters = @{ company = "Example plc"; document_type = "annual_report" }
} | ConvertTo-Json -Depth 3

Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/v1/research `
  -ContentType application/json -Body $body
```

All 11 canonical research sections are returned. Each section explicitly reports whether its
evidence is insufficient and retains typed facts, separately labeled observations, qualified
financial metrics, and citations.

## Error model

Every handled failure uses one envelope:

```json
{
  "error": {
    "code": "document_parsing_failed",
    "message": "Document could not be parsed.",
    "request_id": "0dc8d661e06e46d8a6947fa47b77093a"
  }
}
```

Relevant mappings include:

| Status | Code | Meaning |
| ---: | --- | --- |
| 403 | `document_access_denied` | Reference escapes the configured document root |
| 404 | `document_not_found` | Referenced document does not exist |
| 409 | `index_unavailable` | Q&A/research requested before any index exists |
| 413 | `document_too_large` / `request_too_large` | Configured size limit exceeded |
| 415 | `unsupported_document` | Input is not a PDF |
| 422 | `invalid_request`, `document_parsing_failed`, `no_indexable_text` | Invalid or unusable input |
| 502 | `provider_failure`, `provider_response_invalid`, `generation_failure` | Provider or synthesis failure |
| 503 | `configuration_error`, `indexing_failure`, `retrieval_failure` | Required service is unavailable |
| 500 | `internal_error` | Unexpected server failure |

Client messages never include exception strings, stack traces, local paths, prompts, or secrets.
Expected failures are logged by request ID and error type. Unexpected failures include a
server-side traceback for diagnosis without logging request bodies or document text.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `MADI_DOCUMENT_ROOT` | `data/raw` | Only directory from which the path API may ingest documents |
| `MADI_API_MAX_DOCUMENT_BYTES` | `52428800` | Maximum referenced PDF size (50 MiB) |
| `MADI_API_MAX_REQUEST_BODY_BYTES` | `65536` | Maximum declared JSON body size |
| `MADI_API_MAX_QUESTION_CHARACTERS` | `4000` | Runtime question-length limit |
| `MADI_API_MAX_TOP_K` | `20` | Runtime retrieval-result limit |
| `MADI_PROVIDER_TIMEOUT_SECONDS` | `30` | Timeout passed to OpenAI clients |
| `MADI_PROVIDER_MAX_RETRIES` | `2` | Bounded OpenAI SDK retries; accepted range 0–5 |
| `MADI_LOG_LEVEL` | `INFO` | Application logging threshold |

Embedding/generation provider, model, dimension, token, API-key, and index-path variables retain
their documented meanings. Configuration is validated before constructing provider clients.
Health does not construct those clients, allowing orchestrators to distinguish process liveness
from provider readiness.

Retries live in provider adapters. The API never retries parsing, invalid requests, malformed
structured output, or application validation errors. Provider adapters use a 30-second timeout
and at most two SDK retries by default, both configurable within validated bounds.

## Logging and observability

Each request receives an `X-Request-ID`. A safe caller-supplied ID is preserved; otherwise the
server creates one. Logs record method, route path, response status, operation duration, major
pipeline completion, document ID, counts, and insufficient-evidence state. They intentionally
exclude request bodies, full document text, prompts, vectors, API keys, and local paths.

This is observability plumbing rather than a monitoring platform. Metrics export, tracing
backends, dashboards, and alerting remain deployment concerns.

## Security and robustness choices

- Only `.pdf` ingestion is supported by the existing parser.
- Paths are resolved and must remain beneath `MADI_DOCUMENT_ROOT`, including through symlinks.
- The API uses strict schemas and rejects unknown fields.
- Questions, retrieval counts, metadata strings, chunking values, JSON bodies, and document
  sizes are bounded.
- No unsafe deserialization, shell execution, remote URL fetching, or upload storage is used.
- Generated evidence IDs still pass through the M6/7 deterministic citation validator.
- Empty or image-only documents produce `no_indexable_text` rather than an empty successful
  index.
- Provider clients are lazy and reused; the SQLite index is not reloaded during a single
  operation.

## Known limitations

- The API has no authentication or TLS and should not be exposed publicly as-is.
- The path-based ingestion endpoint is intended for a controlled local deployment with a
  preconfigured document directory.
- `Content-Length` is enforced when supplied; deployment infrastructure should also enforce a
  request-body limit for chunked requests.
- Synchronous provider calls occupy worker threads. High concurrency requires measured worker,
  queue, or async-provider design in a later deployment stage.
- SQLite similarity search remains a linear scan and concurrent writes are limited by SQLite.
- Structured research uses one bounded synthesis call. A provider failure fails that request;
  evidence-absent sections still return safely as insufficient.
- Scanned PDFs still require a future OCR capability.
- No live paid-provider end-to-end validation is part of CI.
