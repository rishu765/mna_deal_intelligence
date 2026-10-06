# Portfolio and interview guide

## Concise project description

M&A Target Screening & Deal Sourcing Agent converts an acquisition thesis into a sourced,
provenance-aware candidate universe; enriches candidates into evidence-backed profiles; applies
deterministic and semantic screening; ranks strategic fit; and orchestrates checkpointed human
review with LangGraph. A synthetic benchmark, FastAPI interface, and offline demo make the V1
reproducible without credentials.

## Resume bullet candidates

- Built a typed acquisition-thesis and criterion model covering hard constraints, preferences,
  exclusions, semantic criteria, financial units, currencies, periods, and incomplete inputs.
- Implemented provider-neutral candidate sourcing, provenance preservation, conservative identity
  deduplication, and evidence-backed enrichment with an explicit Project 1 research adapter.
- Combined deterministic financial/geographic screening with grounded semantic strategic-fit
  assessment and transparent coverage-adjusted ranking.
- Orchestrated discovery-to-shortlist execution with LangGraph checkpointing, bounded retries,
  explicit failure routes, and human approval/rejection/rerun controls.
- Added a five-case offline evaluation benchmark, nine workflow scenarios, a typed FastAPI layer,
  and reproducible credential-free demos.

## Interview story

1. **Business problem:** target sourcing begins with a thesis and an unknown universe, not a known
   company or document set.
2. **Why it is hard:** sources are noisy, identity is ambiguous, financial data is incomplete, and
   qualitative fit must remain explainable.
3. **Thesis representation:** typed criteria separate hard, soft, exclusion, deterministic, and
   semantic concerns while retaining financial comparison basis.
4. **Discovery abstraction:** providers translate their native results into one candidate and
   provenance contract; deterministic query generation stays inspectable.
5. **Enrichment:** profiles separate facts, inferences, unknowns, conflicts, and financial metrics.
6. **Project 1 reuse:** a narrow adapter consumes Project 1's supported structured research output
   without importing retrieval internals or assuming document acquisition.
7. **Deterministic screening:** hard gates, exclusions, currencies, units, and periods are handled by
   predictable code; missing data becomes review-required.
8. **Semantic strategic fit:** only qualitative criteria use the provider boundary, and known
   conclusions must cite profile evidence.
9. **Ranking:** eligibility gates precede a weighted, coverage-adjusted soft score with stable ties.
10. **LangGraph:** the graph owns state, branching, retries, checkpointing, and pause/resume—not the
    business rules.
11. **Human review:** reviewers see evidence, failures, unknowns, and rationale before approval.
12. **Evaluation:** subsystem metrics expose discovery precision separately from screening and
    ranking success; the tiny synthetic benchmark is reported honestly.
13. **Limitations:** there is no commercial data source, production auth, durable store, valuation,
    or autonomous deal decision.

## Reuse and Project 3 handoff

Potential Project 3 inputs include:

- `AcquisitionThesis` and typed financial comparison bases;
- normalized `CandidateCompany` identity and source provenance;
- evidence-backed `CandidateProfile` and financial metrics;
- shortlist eligibility, rationale, and audit results;
- evaluation report patterns; and
- typed graph state, retry, checkpoint, and review patterns.

These remain in Project 2 until Project 3 demonstrates a real second consumer. Premature extraction
into `shared/` would create coupling before the valuation domain boundary is known.
