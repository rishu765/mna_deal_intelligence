# Portfolio Summary, Resume Bullets, and Interview Story

## Portfolio summary

Built an M&A Deal Intelligence Super-Agent that routes high-level deal requests across five
specialist systems for document intelligence, target screening, trading comps, precedent
transactions, and due diligence; preserves typed evidence and specialist-owned finance; reconciles
cross-project outputs; runs checkpointed LangGraph workflows with analyst review and selective
reruns; and produces validated deal-level synthesis through a local API and offline benchmark.

## Resume bullets

- Designed a typed canonical `DealState` and adapters that integrate five independent M&A AI
  systems while preserving source ownership, evidence locators, schema versions, and exact finance.
- Built deterministic intent routing and dependency planning with capability discovery, missing-input
  detection, cycle checks, explicit skips, and parallelizable execution stages.
- Implemented checkpointed LangGraph fan-out/fan-in, bounded retry, failure isolation, human review,
  resume, and selective specialist reruns with append-only decisions and output history.
- Created basis-, period-, currency-, and lineage-aware reconciliation for financial metrics,
  valuation methods, diligence impacts, staleness, scenarios, and analyst review priorities.
- Added evidence-backed final deal synthesis with policy-based assessment, citation rendering,
  specialist numeric fidelity validation, and an optional narrative numeric-claim guard.
- Delivered a typed FastAPI interface, safe operational observability, a three-scenario offline demo,
  and an 18-case subsystem evaluation without live model or network dependencies.

## Interview story

1. **Problem:** a deal question spans documents, sourcing, valuation, precedents, and diligence, but
   each discipline has different data and review semantics.
2. **Specialists:** Projects 1–5 retain ownership of their business logic and calculations.
3. **Adapters:** narrow typed boundaries translate canonical requests and preserve native results.
4. **State:** one immutable canonical state stores identities, envelopes, finance, evidence,
   decisions, warnings, errors, dependencies, and versions.
5. **Routing:** bounded natural-language rules choose known intents; the registry prevents invented
   tools.
6. **Planning:** a deterministic DAG adds required providers, detects missing input and cycles, and
   marks independent work for parallel execution.
7. **Reconciliation:** deterministic comparisons respect entity, basis, period, currency, unit,
   source, and evidence semantics.
8. **Conflict example:** Project 3 uses reported EBITDA of 100 while Project 5 supports adjusted
   EBITDA of 85; Project 6 flags staleness and asks an analyst rather than silently recalculating.
9. **LangGraph:** typed nodes make state transitions, routing, fan-out/fan-in, and failure paths
   explicit.
10. **Parallelism:** independent Project 3 and Project 4 steps dispatch together and join before
    reconciliation.
11. **HITL:** material issues interrupt with bounded options, source values, and evidence IDs.
12. **Resume:** the same checkpoint resumes; decisions and reruns are auditable and idempotent.
13. **Synthesis:** structured output comes first; narrative is explanatory, methods remain separate,
    and numeric values are validated against sources.
14. **Evaluation:** metrics remain separate by subsystem across 18 deterministic scenarios.
15. **Observability:** safe traces and run summaries expose IDs, counts, timings, retries, reviews,
    failures, and outcome without source content or hidden reasoning.
16. **Limitations:** fixture-heavy integrations, local persistence, no auth or cloud deployment, and
    no full legal, tax, cyber, or advanced modeling engines.
