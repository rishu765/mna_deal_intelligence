# Candidate enrichment

## Purpose and boundary

Discovery answers “which companies might belong in the candidate universe?” Enrichment answers
“what evidence-backed information do we have about each company?” M3 converts an M2
`CandidateCompany` into a `CandidateProfile`; it does not apply acquisition criteria, reject a
candidate, calculate fit, or rank a shortlist.

## Candidate profile

A profile retains the original candidate and separates four kinds of information:

- `ProfileFact`: an observed claim with one or more evidence records;
- `ProfileInference`: an interpretation with supporting evidence and optional rationale;
- `UnknownField`: a requested field for which evidence was unavailable;
- `ProfileConflict`: competing evidence-backed values that were not silently reconciled.

Financial metrics separately retain metric name, reported value, three-letter currency when
present, unit, fiscal period, accounting basis, and evidence. The value remains a string because
M3 preserves the source representation rather than making conversions or comparisons.

`EnrichmentStatus` reports `complete_enough`, `partial`, `insufficient_evidence`, or
`provider_failure`. “Complete enough” is a workflow readiness signal based on prioritized field
coverage; it is not a statement that the company passes the thesis.

## Provider contract and workflow

`EnrichmentProvider.enrich(EnrichmentRequest)` returns a `ProviderEnrichmentResult`. The plain
Python `CandidateEnrichmentService`:

1. maps M1 thesis criterion categories to priority profile fields;
2. invokes each configured provider independently;
3. keeps useful results when another provider fails;
4. deduplicates identical claims without dropping evidence;
5. records conflicting scalar or same-period financial values;
6. retains uncovered fields as explicit unknowns; and
7. calculates a bounded completeness status.

Core business description, industry, products/services, and geography are always prioritized.
Revenue, profitability, technology, customer, ownership, growth, and other fields are added
when corresponding thesis criteria exist. Prioritization guides research only; it is not
screening.

## Project 1 integration

`Project1DocumentResearchProvider` is an adapter around a deliberately narrow structural client:

```text
CandidateCompany + explicit document references
  -> caller-configured, pre-indexed Project 1 application service
  -> public CompanyResearchProfile
  -> facts, analytical observations, financial metrics, and citations
  -> CandidateProfile claims and evidence
```

Project 1 facts remain facts. Its explicitly analytical observations become inferences. Document
IDs, chunk IDs, source filenames, page numbers, and excerpts are preserved in
`EnrichmentEvidence`. Project 2 does not import Project 1's stores, retrievers, prompts, LLM
adapters, or API schemas.

The adapter does not discover or download candidate documents. When no document references are
supplied it skips the Project 1 call, returns explicit unknowns, and adds a warning. The caller
must ingest/index appropriate documents in Project 1 before using the live adapter.

## Offline provider and demo

`StructuredFixtureEnrichmentProvider` reads the bundled fictional
`data/enrichment_profiles.json`. It implements the same contract as the Project 1 adapter and
requires no API key, proprietary document, or internet connection.

From `02_target_screening_sourcing/`:

```powershell
python -m ma_target_screening.demo_enrichment
```

The demo runs the M2 local discovery path, selects `payflow.example`, enriches it, and prints a
versioned JSON profile. An alternate discovered fixture company can be selected with
`--domain cashgrid.example`.

## Evidence and normalization

Enrichment evidence records provider, source type/title/reference, document and chunk IDs, page
numbers, excerpt, extraction method, and a coarse source-quality label. Fixture evidence is
explicitly marked supplied; mapped Project 1 document citations are marked primary. Quality is
metadata, not an automatic truth score.

Text whitespace, currency codes, domains, and enumerated values are normalized conservatively.
Raw fact values can be retained. No FX conversion, period alignment, accounting normalization,
or fuzzy truth resolution occurs in M3.

## Failure and conflict behavior

Provider, malformed-response, and mapping failures become warnings and status rather than
discarding other providers' useful output. A total provider failure is different from a
successful search with insufficient evidence. Conflicting values remain in the claims and in an
explicit conflict record with their evidence.

## Known limitations

- The fixture dataset is fictional and exists only for deterministic development and CI.
- There is no live web or company-data enrichment provider.
- Project 1 documents must already be available and indexed by the composing application.
- Conflict detection covers selected scalar fields and same-metric/same-period financial values;
  it is not full truth resolution.
- Completeness uses field coverage, not evidence recency, source corroboration, or diligence
  quality scoring.
- Financial values are preserved but not parsed, converted, compared, or screened.
