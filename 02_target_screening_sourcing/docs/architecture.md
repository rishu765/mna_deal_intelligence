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

M0 defines only four small domain objects plus two ports. Named downstream concepts are planned
contracts, not implemented behavior.

## Planned domain concepts

| Concept | Responsibility | Planned milestone |
| --- | --- | --- |
| `AcquisitionThesis` | Canonical strategic intent and constraints | Skeleton M0; full model M1 |
| `ScreeningCriterion` | One typed hard/soft criterion, operator, value, and weight | M1 |
| `CandidateCompany` | Normalized identity, aliases, domain, country, IDs, discovery evidence | Skeleton M0; evolve M2 |
| `DiscoveryEvidence` | Where and when a candidate was observed | Skeleton M0 |
| `CandidateProfile` | Evidence-backed facts and explicit unknowns needed by screening | Boundary skeleton M0; evolve M3 |
| `ScreeningResult` | Deterministic pass/fail/unknown result per hard criterion | M4 |
| `StrategicFitAssessment` | Evidence-backed semantic fit and rationale | M5 |
| `RankedCandidate` / `Shortlist` | Stable ranking, explanations, and cited candidate set | M5 |
| Human review state | Reviewer decision and workflow transitions | M6 |

The eventual thesis can cover acquirer, strategic objective, industry/sub-industry, sought
products or capabilities, geography, revenue range, company size, ownership, growth,
technology, exclusions, qualitative fit, and optional weights. M1 will decide exact types,
operators, currencies/units, and validation. M0 deliberately does not parse prose into it.

## Deterministic and semantic separation

Deterministic components own exact geography and ownership filters, revenue/employee/founding
year thresholds, explicit exclusions, formula-based scores, deduplication where trusted keys
exist, validation, and stable ordering. They must represent missing or conflicting data rather
than ask a model to guess.

Semantic components may interpret ambiguous thesis text, assess product or capability fit,
reason about strategic adjacency, and draft qualitative rationale. Their structured outputs
must cite supplied evidence, expose uncertainty, and remain subordinate to hard criteria.

## Discovery abstraction

`DiscoveryProvider.discover(thesis)` is the initial provider-neutral port. Future adapters may
use search APIs, company databases, filings, public web sources, internal datasets, or
user-supplied lists. Adapters return canonical Project 2 objects and preserve source evidence;
provider response types never cross the port. M2 will refine pagination, query planning,
timeouts, and partial-failure semantics only when real sources are selected.

## Identity and normalization strategy

Discovery can return spelling variants, subsidiaries, former names, or similarly named
companies. The initial identity hierarchy planned for M2 is:

1. trusted external identifier match;
2. normalized website-domain match;
3. normalized name plus country, treated as a candidate match requiring caution;
4. unresolved ambiguity retained for review rather than forced into one entity.

Canonical name, aliases, domain, country, available identifiers, and every contributing source
remain attached. Fuzzy matching may propose merges but should not erase source observations.
M0 does not implement entity resolution.

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

