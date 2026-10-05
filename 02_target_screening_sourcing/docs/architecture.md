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
       Port: CompanyResearchProvider
       Output: CandidateProfile with evidence and explicit unknowns
  -> Deterministic screening engine
       Output: ScreeningResult per criterion, including missing-data state
  -> Strategic-fit assessor
       Output: StrategicFitAssessment with evidence-backed rationale
  -> Ranking service
       Output: RankedCandidate[] and score explanation
  -> Shortlist
       Output: evidence-backed, reviewable candidate set
  -> Human review workflow
       Output: approval/rejection/request-for-research state
```

M2 implements deterministic query generation, provider-neutral sourcing, lightweight identity
normalization, conservative deduplication, and provenance-preserving candidate results. Named
downstream enrichment and screening concepts remain planned contracts.

## Planned domain concepts

| Concept | Responsibility | Planned milestone |
| --- | --- | --- |
| `AcquisitionThesis` | Canonical strategic intent and constraints | Implemented M1 |
| `ScreeningCriterion` | Typed hard/soft/exclusion criterion, operator, value, and importance | Implemented M1 |
| `CandidateCompany` | Normalized observed identity, aliases, domain, country, tags, source evidence | Implemented M2 |
| `DiscoveryEvidence` | Provider, source, query, timestamp, excerpt, and source identifier | Implemented M2 |
| `CandidateProfile` | Evidence-backed facts and explicit unknowns needed by screening | Boundary skeleton M0; evolve M3 |
| `ScreeningResult` | Deterministic pass/fail/unknown result per hard criterion | M4 |
| `StrategicFitAssessment` | Evidence-backed semantic fit and rationale | M5 |
| `RankedCandidate` / `Shortlist` | Stable ranking, explanations, and cited candidate set | M5 |
| Human review state | Reviewer decision and workflow transitions | M6 |

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

The adapter owns configuration translation, request construction, exception mapping, and model
translation. Project 2 should not import Project 1 retrieval, prompt, store, generator, or API
schema internals. If in-process reuse proves awkward in M3, Project 1 should expose one stable
public facade or Project 2 should use its API; that decision should be based on deployment and
testing needs then, not anticipated in M0.

## Configuration and errors

Core models and ports have no runtime dependencies. Future adapter configuration comes from
environment variables, uses the `MATS_` prefix for Project 2 settings, validates eagerly, and
never logs secrets. Provider errors are translated into stable Project 2 exception families.
Credentials may use provider-standard names shared by separately composed projects.

## Future orchestration

LangGraph is reserved for M6, after M1–M5 provide independently tested services. A graph may
then coordinate retries, conditional enrichment, review checkpoints, and resumable state. It
must not contain screening mathematics or provider-specific business logic.
