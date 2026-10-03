# Reproducible Project 1 demo

This walkthrough demonstrates Project 1 with a fictional five-page company report generated
locally. It does not download or commit a third-party annual report. OpenAI credentials are
needed for embeddings and generation; PDF creation, parsing, tests, and deterministic
evaluation remain available without them.

## 1. Install and configure

From `01_company_document_intelligence/`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

The application deliberately does not load `.env` itself. Export at least the key in the
current shell before provider-backed steps:

```powershell
$env:OPENAI_API_KEY = "your-key"
```

## 2. Create the copyright-safe sample

```powershell
madi-create-demo-pdf
```

This creates `data/raw/apex-industrial-analytics-demo.pdf`. The fictional report covers a
business overview, products, segments, geography, financial highlights, risks, strategy, and
management priorities. The generator refuses to overwrite an existing file unless
`--overwrite` is provided.

Parsing can be inspected without an API key:

```powershell
madi-inspect-pdf data/raw/apex-industrial-analytics-demo.pdf
madi-inspect-chunks data/raw/apex-industrial-analytics-demo.pdf
```

## 3. Start the API

```powershell
madi-api
```

Open `http://127.0.0.1:8000/docs` for the interactive OpenAPI interface or verify liveness:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## 4. Index the sample

```powershell
$indexBody = @{
  source_reference = "apex-industrial-analytics-demo.pdf"
  metadata = @{
    company = "Apex Industrial Analytics"
    document_title = "FY2025 Synthetic Annual Report"
    document_type = "annual_report"
    fiscal_year = 2025
  }
  chunking = @{
    max_characters = 600
    overlap_characters = 80
    min_chunk_characters = 200
  }
} | ConvertTo-Json -Depth 4

Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/v1/documents/index `
  -ContentType application/json -Body $indexBody
```

The index is written to ignored local storage at `artifacts/vector_index.sqlite3` by default.
Stable chunk IDs make repeat indexing an upsert rather than an uncontrolled duplicate insert.

## 5. Ask an evidence-grounded question

```powershell
$questionBody = @{
  question = "What were FY2025 revenue and adjusted EBITDA?"
  top_k = 5
  filters = @{ company = "Apex Industrial Analytics"; fiscal_year = 2025 }
} | ConvertTo-Json -Depth 3

Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/v1/answers `
  -ContentType application/json -Body $questionBody
```

A typical response states that FY2025 reported revenue was USD 125 million and adjusted
EBITDA was USD 18 million, then resolves its evidence references to the synthetic report and
the chunk's canonical page span. With the demo chunk settings, the financial evidence spans
pages 2–3 because overlap preserves the transition into the financial section. Exact prose can
vary by model; the financial facts, qualifiers, and citations should remain grounded in
retrieved evidence.

## 6. Generate structured research

```powershell
$researchBody = @{
  company_name = "Apex Industrial Analytics"
  filters = @{ company = "Apex Industrial Analytics"; document_type = "annual_report" }
} | ConvertTo-Json -Depth 3

Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/v1/research `
  -ContentType application/json -Body $researchBody
```

The response contains 11 typed sections. Facts, analytical M&A observations, financial metric
qualifiers, insufficiency states, and citations remain separate and inspectable.

## 7. Run deterministic evaluation

Stop the API or open another shell, then run:

```powershell
madi-evaluate --report-stem demo-evaluation
```

The runner writes JSON and Markdown under `artifacts/evaluation/`. It measures retrieval,
generation correctness, grounding, citations, and structured research independently. The
default benchmark uses recorded synthetic observations and requires no provider call.

## Using a public filing instead

Place a legally obtained text-oriented PDF under `data/raw/` and substitute its filename in
the indexing request. Raw documents and generated indexes are ignored by Git. Scanned filings
need OCR before this V1 parser can extract their contents reliably.
