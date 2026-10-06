# Project 2 architecture

## Ownership boundary

Project 2 owns the path from an acquisition thesis to a reviewable target shortlist:

- acquisition thesis and screening criteria;
- candidate discovery and source provenance;
- candidate identity normalization and deduplication;
- candidate-profile requirements and enrichment coordination;
- deterministic screening results;
- strategic-fit assessments and ranking;
- shortlist state and, later, human-review state.

Project 2 does not own document parsing, chunking, embeddings, document retrieval, or citation
construction. Those are Project 1 capabilities. It also does not own external data vendors;
vendor adapters implement Project 2 ports.

## Planned flow and boundaries

```text
Human thesis
  -> Thesis normalizer
       Output: AcquisitionThesis + ScreeningCriterion[]
  -> Discovery service
       Port: DiscoveryProvider
       Output: CandidateCompany[] with DiscoveryEvidence
  -> Identity resolver
       Keys: domain, trusted identifiers, normalized name + country
       Output: canonical candidates + merge/audit record
  -> Enrichment service
       Port: EnrichmentProvider
       Output: CandidateProfile with facts, inferences, evidence, unknowns, and conflicts
  -> Deterministic screening engine
       Output: criterion evaluations + eligible/review-required/ineligible state
  -> Strategic-fit assessor
       Port: StrategicFitProvider
       Output: structured, evidence-grounded semantic evaluations
  -> Ranking service
       Output: weighted score components, RankedCandidate[] and score explanation
  -> Shortlist
       Output: evidence-backed, reviewable candidate set
  -> Human review workflow
       Output: approval/rejection/request-for-research state
```

M4/5 adds criterion-level screening, hard/exclusion gates, a structured semantic provider
boundary, transparent score aggregation, deterministic ordering, and a shortlist that retains
all candidate results for audit. Agentic orchestration remains downstream.

## Planned domain concepts

| Concept | Responsibility | Planned milestone |
| --- | --- | --- |
| `AcquisitionThesis` | Canonical strategic intent and constraints | Implemented M1 |
| `ScreeningCriterion` | Typed hard/soft/exclusion criterion, operator, value, and importance | Implemented M1 |
| `CandidateCompany` | Normalized observed identity, aliases, domain, country, tags, source evidence | Implemented M2 |
| `DiscoveryEvidence` | Provider, source, query, timestamp, excerpt, and source identifier | Implemented M2 |
| `CandidateProfile` | Facts, inferences, financials, unknowns, conflicts, evidence and status | Implemented M3 |
| `ScreeningResult` | Eligibility, per-criterion outcomes, score components and rationale | Implemented M4/5 |
| `StrategicFitAssessment` | Structured evidence-backed semantic fit and uncertainty | Implemented M4/5 |
| `RankedCandidate` / `Shortlist` | Stable ranking, explanations, and cited candidate set | Implemented M4/5 |
| Human review state | Reviewer decision and workflow transitions | Implemented M6 |

The thesis covers acquirer context and criteria for industry/sub-industry, products or
capabilities, geography, revenue, profitability, company size, employee count, founded year,
growth, ownership, customer type, technology, strategic fit, and extensions. Each criterion
separates hard/soft/exclusion consequence from typed value and deterministic/semantic
evaluation. M1 deliberately does not parse prose into the model.

## Deterministic and semantic separation

Deterministic components own exact geography and ownership filters, revenue/employee/founding
year thresholds, explicit exclusions, formula-based scores, deduplication where trusted keys
exist, validation, and stable ordering. They must represent missing or conflicting data rather
than ask a model to guess.

Semantic components may interpret ambiguous thesis text, assess product or capability fit,
reason about strategic adjacency, and draft qualitative rationale. Their structured outputs
must cite supplied evidence, expose uncertainty, and remain subordinate to hard criteria.

M4/5 implements this boundary with a credential-free fixture provider and a generic structured-
generation client adapter. Deterministic rules never call that provider. Semantic output citing
unknown evidence IDs is rejected and converted to an explicit unknown assessment.

## Discovery abstraction

`DiscoveryProvider.discover(request)` is the provider-neutral port. M2 implements a bounded
local JSON dataset adapter and user-supplied candidate adapter. Provider response types become
`DiscoveredCompanyRecord` values before normalization; providers cannot leak their native
models into the core. Future search/company-database adapters use the same request/result
contract and must translate timeout and malformed-response failures.

## Identity and normalization strategy

Discovery can return spelling variants, subsidiaries, former names, or similarly named
companies. The initial identity hierarchy planned for M2 is:

1. trusted external identifier match;
2. normalized website-domain match;
3. normalized name plus country, treated as a candidate match requiring caution;
4. unresolved ambiguity retained for review rather than forced into one entity.

Canonical name, aliases, domain, country, available identifiers, and every contributing source
remain attached. Fuzzy matching may propose merges but should not erase source observations.
M2 implements only these conservative exact rules. Fuzzy and corporate-family resolution remain
deferred.

## Project 1 integration

```text
CandidateCompany
  -> Project 2 enrichment coordinator
  -> CompanyResearchProvider port
  -> adapter using a supported Project 1 application/service boundary
  -> Project 1 evidence-backed CompanyResearchProfile
  -> adapter translation
  -> Project 2 CandidateProfile
```

The M3 adapter accepts any structurally compatible client exposing Project 1's public
`research(company_name=...)` behavior and maps its structured profile, facts, observations,
financial metrics, and citations. This avoids a package dependency or deep imports. The caller
is responsible for configuring Project 1 and indexing explicitly supplied candidate documents;
the adapter does not fetch filings or web pages.

## Configuration and errors

Core models and ports have no runtime dependencies. Future adapter configuration comes from
environment variables, uses the `MATS_` prefix for Project 2 settings, validates eagerly, and
never logs secrets. Provider errors are translated into stable Project 2 exception families.
Credentials may use provider-standard names shared by separately composed projects.

## Orchestration boundary

M6 implements LangGraph as a thin application layer after M1–M5 established independently
tested services. Nodes call the provider-neutral discovery, enrichment, and screening/ranking
ports; they do not contain query generation, profile merging, criterion comparison, semantic
reasoning, scoring, or ranking logic. The graph owns explicit state transitions, bounded retry
routing, checkpointed pause/resume, human decisions, warnings/errors, and the terminal workflow
result. See [langgraph-workflow.md](langgraph-workflow.md).
