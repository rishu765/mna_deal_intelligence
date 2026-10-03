# Citations and structured company research

Milestone M6/7 turns preserved M1–M5 provenance into user-facing citations and adds a typed,
M&A-oriented company research profile. Both capabilities follow the same rule: generated
content is accepted only when it points to evidence actually supplied to the model.

## Citation flow

```text
RAG answer
    -> generated evidence IDs (for example E2, E4)
    -> deterministic CitationBuilder validation
    -> numbered Citation objects ([1], [2])
    -> RetrievalResult
    -> DocumentChunk
    -> source document and contributing page(s)
```

Every M5 context block now has an ID such as `E1`. The structured model response returns only
the IDs that directly support its answer. Application code rejects unknown IDs, deduplicates
repeated chunks, and assigns contiguous citation numbers in first-reference order. It does not
automatically cite every retrieved chunk.

`Citation` contains the citation number, stable chunk and document IDs, trusted title when
available, source filename, one-based canonical page numbers, zero-based physical PDF indexes,
printed page labels when known, a bounded exact-source excerpt, and trusted M2 metadata. The
underlying `RAGAnswer.supporting_results` still records every chunk supplied to generation;
`RAGAnswer.citations` records only the chunks selected as support.

The analyst-facing format is deterministic:

```text
[1] Annual Report FY2025 — p. 84
[2] Investor Presentation — pp. 17–18
[3] filing.pdf — page unavailable
```

Consecutive canonical pages are displayed as a range. Nonconsecutive pages are listed. The
formatter never substitutes physical indexes or guesses printed labels. If page provenance is
unavailable to a future source adapter, it says `page unavailable`.

This is an answer-level baseline. It validates that every citation maps to supplied evidence
but does not run natural-language entailment for every clause. M8 measures citation correctness
and faithfulness using curated expected evidence.

## Structured research flow

```text
Company corpus
    -> 11 fixed category-specific semantic queries
    -> unique bounded evidence catalog + category map
    -> one schema-validated research synthesis request
    -> application-owned generated research models
    -> deterministic evidence-ID validation and citation mapping
    -> CompanyResearchProfile
```

`ResearchEvidenceCollector` retrieves up to three results per category by default. It
deduplicates chunks across categories and gives each included chunk one global evidence ID.
The default 40,000-character budget applies to complete provenance-rich blocks; an oversized
result is omitted rather than truncated. These defaults are configurable.

The fixed categories are:

1. company/source context;
2. business overview;
3. products and services;
4. business segments;
5. geographic exposure;
6. customers and end markets;
7. financial highlights;
8. major risks;
9. strategic developments;
10. management outlook and stated priorities;
11. M&A-relevant observations.

One synthesis call keeps cross-section terminology consistent and avoids 11 generation calls,
while targeted retrieval prevents sending the entire corpus to the model. This is a fixed
deterministic workflow; LangGraph and agents would add orchestration without a planning problem.

## Structured schema

`CompanyResearchProfile` contains an optional company name, all 11 sections in canonical order,
a global deduplicated citation catalog, contributing document IDs, generator identity, and
warnings.

Each `ResearchSection` contains an optional summary, directly supported `ResearchFact` values,
explicitly analytical `ResearchObservation` values, section-local citations, and an
`insufficient_evidence` flag. An insufficient section must have no claims or citations. A
supported section must contain content and citations.

`financial_highlights` may additionally contain `FinancialMetric` values with metric name,
displayed value retained as text, fiscal period, unit or scale, currency, basis or qualifier,
and metric-specific citations. Optional qualifiers remain `None` when the source does not
establish them. Domain validation prohibits financial metrics in other sections.

## Facts and M&A synthesis

Facts and analytical observations use different domain types and output fields.

```text
Fact: North America represented 62% of disclosed revenue. [1]
Analysis: This concentration may matter when evaluating geographic diversification. [1]
```

Facts must be directly stated by evidence. Observations may reason about M&A relevance, but
must cite the facts supporting the interpretation and remain visibly separate from source
disclosures. The system does not produce autonomous acquisition or investment recommendations.

## Financial safeguards

Financial values are strings rather than application-normalized numbers in this milestone.
This preserves signs, parentheses, scale words, percentages, and source formatting. Period,
unit, currency, and basis are separate optional fields. Prompt and schema rules prohibit:

- equating revenue with net revenue;
- equating EBITDA with adjusted EBITDA;
- mixing annual and quarterly periods;
- changing currencies or unit scales;
- treating percentage changes as percentage points;
- calculating missing values unless the document explicitly states the calculation and result.

Every metric requires a valid citation. Deterministic normalization and financial calculation
remain outside this milestone.

## Insufficient evidence

Targeted retrieval returning no evidence skips generation and returns every section as
insufficient. During synthesis, an unsupported category must be empty and marked
`insufficient_evidence=true`. Unknown customer concentration, market share, acquisition
history, financial measures, and strategic claims remain absent rather than inferred.

Malformed structured output becomes `GenerationResponseError`. Unknown evidence IDs become
`CitationReferenceError`; neither case is silently converted into supported output.

## Manual validation

Free-form cited Q&A:

```powershell
madi-answer "data/raw/example-annual-report.pdf" `
  "What were the main revenue growth drivers?" `
  --company "Example plc" --document-title "Annual Report FY2025"
```

Structured company research:

```powershell
madi-research "data/raw/example-annual-report.pdf" `
  --company "Example plc" `
  --document-title "Annual Report FY2025" `
  --document-type "annual_report" `
  --fiscal-year 2025 `
  --top-k-per-section 3 `
  --preview-chars 300
```

The research command prints all sections, separate fact and analysis fields, financial
qualifiers, section citation markers, and a bounded global citation catalog. It does not print
prompts, vectors, credentials, or full documents. Both commands require `OPENAI_API_KEY` for
live embeddings and generation; automated tests use fakes and incur no API cost.

A shortened output shape is:

```json
{
  "company_name": "Example plc",
  "sections": [
    {
      "key": "financial_highlights",
      "summary": "FY2025 revenue was $125 million.",
      "financial_metrics": [
        {
          "metric_name": "Revenue",
          "value": "$125 million",
          "fiscal_period": "FY2025",
          "unit": "million",
          "currency": "USD",
          "basis": "reported revenue",
          "citations": ["[1]"]
        }
      ],
      "insufficient_evidence": false
    }
  ],
  "citations": [
    {"id": "1", "reference": "[1] Annual Report FY2025 — p. 84"}
  ]
}
```

## Known limitations

- Evidence-ID validation proves that a cited chunk was supplied, not that every generated
  clause is entailed by the excerpt.
- Citation excerpts are deterministic bounded chunk prefixes, not claim-specific sentences.
- One structured synthesis call can still omit or misclassify evidence.
- Character budgets approximate tokens and semantic retrieval can miss relevant text.
- Exact vector retrieval has no reranker or lexical component.
- Table structure, multicolumn reading order, charts, and scanned PDFs inherit M1/M2 limits.
- Research covers the indexed local corpus only; there is no web search or company discovery.
- Formal M8 scores are reported in `evaluation.md`; clause-level entailment remains a
  limitation of the deterministic baseline.

## Evaluation hooks retained for M8

Stable question, answer, evidence ID, chunk ID, document ID, page, section, factual/analytical
type, financial qualifier, abstention state, and citation objects can be inspected separately.
M8 measures retrieval recall, answer correctness, grounding, citation validity, citation page
correctness, structured-field accuracy, and absent-evidence behavior without parsing terminal
prose.
