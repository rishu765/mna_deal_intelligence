# Candidate discovery and sourcing

## Purpose and boundary

M2 turns an M1 `AcquisitionThesis` into an unranked candidate universe. It generates bounded,
transparent queries, invokes one or more provider-neutral discovery sources, normalizes observed
identities, conservatively merges obvious duplicates, and retains every discovery observation.

Discovery is not enrichment or screening. A directory description or search-like snippet is a
lead, not a verified fact. M3 will research candidates; M4 will apply deterministic criteria;
M5 will assess strategic fit and ranking.

## Architecture

```text
AcquisitionThesis
  -> DeterministicQueryGenerator
  -> DiscoveryRequest + limits
  -> DiscoveryProvider(s)
  -> DiscoveredCompanyRecord(s)
  -> conservative normalization
  -> deterministic deduplication + provenance merge
  -> CandidateDiscoveryResult
```

`CandidateDiscoveryResult` records the thesis ID, generated queries, successful providers,
warnings, raw and deduplicated counts, and unranked `CandidateCompany` values suitable for M3.

## Thesis-aware query generation

The generator reads non-exclusion criteria for:

- industry and sub-industry;
- product capability and technology;
- geography;
- customer type.

It produces small combinations such as `Fintech companies India`, capability plus geography,
or capability plus industry. It uses the objective only as a fallback when no supported typed
dimension exists. It ignores revenue, profitability, size, and exclusions because discovery
sources rarely establish these reliably and M2 prioritizes recall.

Queries are deduplicated and capped by `max_queries`. There is no LLM or autonomous query loop.

## Implemented providers

### Local dataset provider

`LocalDatasetDiscoveryProvider` searches a JSON list deterministically using transparent token
overlap. The bundled `data/discovery_companies.json` contains fictional records only and is
appropriate for tests, CI, and the demo. It deliberately includes duplicate observations and a
candidate that would likely fail a later exclusion so boundaries can be demonstrated.

### User-supplied provider

`UserSuppliedDiscoveryProvider` accepts typed `UserCandidateInput` values. It represents
banker-provided longlists, management suggestions, and previously sourced candidates. Names are
required; website, aliases, country, industry tags, description, and source URL are optional.

No live search provider is implemented or advertised in M2. A future adapter can implement the
same `DiscoveryProvider` protocol and translate API timeouts, response errors, and provider
identifiers into the existing models and exception families.

## Provenance

Every normalized candidate has at least one `DiscoveryEvidence` observation containing the
provider, source type/name, optional source URL/title/identifier, query, timestamp, excerpt,
and bounded string metadata when available. Deduplication unions evidence rather than choosing
one winning source.

This is discovery-grade provenance. It explains why a company entered the universe but does
not make snippets, dataset labels, or supplied descriptions diligence-grade evidence.

## Normalization

The normalizer:

- collapses whitespace in company display names;
- converts website URLs to lowercase IDNA domains;
- removes `www.`, paths, queries, fragments, and trailing dots from domains;
- retains aliases and observed descriptive fields;
- builds provider-scoped source identifiers.

Legal suffixes are removed only from an internal matching key. The displayed company name is
not destructively rewritten.

## Conservative deduplication

Candidates merge on the first reliable match:

1. exact provider identifier `(scheme, value)`;
2. exact normalized domain;
3. exact normalized canonical-name or alias key when countries do not conflict.

The name key recognizes common legal suffix variants but performs no fuzzy matching. Same-name
companies in explicitly different countries remain separate. A merge retains aliases,
identifiers, industry tags, and all unique evidence observations.

## Limits and failures

`DiscoveryLimits` controls maximum queries, candidates per query, and final candidates. Defaults
are 6, 10, and 50. Environment configuration uses:

- `MATS_DISCOVERY_DATASET_PATH`
- `MATS_DISCOVERY_MAX_QUERIES`
- `MATS_DISCOVERY_MAX_CANDIDATES_PER_QUERY`
- `MATS_DISCOVERY_OVERALL_CANDIDATE_LIMIT`

Provider failures become warnings when another provider succeeds. If every provider fails,
`DiscoveryUnavailableError` is raised. Successful empty results include explicit warnings.
Malformed local JSON raises a provider error. Logs record provider names and bounded counts but
not raw payloads or secrets.

## Offline demo

From `02_target_screening_sourcing/`:

```powershell
python -m ma_target_screening.demo_discovery
```

Or, after installation:

```powershell
mats-discovery-demo --max-queries 4 --max-candidates 10
```

The default demo loads `examples/fintech-payments.json`, searches the bundled fictional dataset,
and prints JSON containing queries, counts, normalized candidates, and their discovery evidence.
It requires no network or API key.

## Known limitations

- No live web/search/company-database adapter.
- Local matching is simple token overlap, not semantic search.
- No sophisticated entity resolution, corporate-family mapping, or subsidiary handling.
- No verification of descriptions, industries, geography, or domains.
- No CSV importer; supplied candidates are constructed as typed Python inputs.
- No enrichment, screening, scoring, ranking, shortlist, or orchestration.
