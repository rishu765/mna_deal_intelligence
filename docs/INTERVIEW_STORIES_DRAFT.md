# Interview Story Drafts

These are preparation aids. Explain tradeoffs in your own words and be ready to open the cited
modules.

## Project 1 — Company & Document Intelligence

**30 seconds:** I built a provenance-first research system that parses company PDFs, chunks them
with page metadata, retrieves lexical and semantic evidence, and produces cited answers or
structured research. The design goal was to make every material claim traceable and let the system
abstain when evidence is insufficient.

**Two minutes:** Start with the analyst problem, then trace ingestion → normalized pages → chunks →
embeddings/index → hybrid retrieval → bounded context → answer/citations. Explain why provider
interfaces are optional, why citation validation is separate from generation, and why the evidence
quality gate preserves known failures instead of claiming perfect accuracy.

**Deep dive:** chunk boundaries; reciprocal/weighted retrieval; evidence models; prompt/context
limits; citation support metrics; table and OCR limits; production document security.

## Project 2 — Target Screening & Sourcing

**30 seconds:** I converted an acquisition thesis into explicit filters, explainable scores, and a
ranked shortlist, then used LangGraph for checkpointed human review. Deterministic exclusions stay
separate from semantic strategic-fit reasoning.

**Two minutes:** Explain discovery and enrichment ports, evidence freshness, identity, hard filters,
scoring, stable ranking, and review. Discuss the expanded labels and why two retained ordering
failures are more credible than an inflated score.

**Deep dive:** criteria modeling; missing data; score weights; tie-breaking; ranking metrics;
checkpoint state; external data freshness and entity resolution.

## Project 3 — Comparable Companies & Valuation

**30 seconds:** I built a deterministic trading-comps engine that makes peer decisions and every
multiple auditable. Finance values carry basis, period, currency, unit, date, and evidence so the
system fails rather than mix incompatible inputs.

**Two minutes:** Trace target profile → peer universe → exclusions → market/financial snapshot →
multiples → statistics → implied EV → equity bridge. Explain Decimal use, negative/missing
denominators, LTM/NTM discipline, and why the AI explanation cannot calculate value.

**Deep dive:** EV versus equity value; denominator alignment; median/quartile policy; outliers;
snapshot dates; FX; production data-provider contracts.

## Project 4 — Precedent Transactions

**30 seconds:** I built a transaction-research and valuation workflow that preserves deal identity,
dates, consideration, control, and value basis across conflicting sources. It pauses for analyst
review rather than treating headline value as enterprise value.

**Two minutes:** Walk through discovery/deduplication, document retrieval, extraction, verification,
selection, multiples, ranges, and review. Use the IBM/HashiCorp public snapshot to explain primary
sources and an independently reproduced EV/revenue multiple.

**Deep dive:** announcement versus completion date; amendments; equity purchase price versus EV;
partial stakes; control context; period alignment; selection bias and licensed data limits.

## Project 5 — AI Due Diligence

**30 seconds:** I built an evidence-linked VDR diligence workflow with financial, commercial,
legal/contractual, and operational specialists. AI proposes findings, deterministic services own
QoE/NWC/net-debt arithmetic, and an analyst resolves material conflicts.

**Two minutes:** Trace VDR ingestion, classification, table/clause chunks, hybrid retrieval,
financial observations, specialists, consolidation, review, and report. Explain lineage from report
finding to fact to evidence and why adjustment recurrence/support matters.

**Deep dive:** reported-to-adjusted EBITDA bridge; add-back tests; working-capital peg; restricted
cash/debt-like items; contradiction/version handling; confidentiality and workstream limits.

## Project 6 — Deal Intelligence Super-Agent

**30 seconds:** I coordinated five specialist systems through typed adapters and a canonical
DealState. LangGraph handles dependency-aware execution, partial failures, HITL reruns, and resume;
deterministic reconciliation checks identity and finance basis before grounded synthesis.

**Two minutes:** Explain why specialists keep domain ownership, adapters isolate translations,
DealState records versioned outputs, and reconciliation retains method differences. Walk through
planning, fan-out/fan-in, compatibility checks, a review interrupt, approved rerun, staleness, and
final synthesis. Distinguish fixture mode from native-local execution.

**Deep dive:** capability registry; dependency DAG; envelope/schema versions; idempotency; retry
classification; checkpoint/thread isolation; evidence fidelity; observability; durable production
state and authentication gaps.

## Project 6 system-design decisions

- **Specialists:** isolate bounded expertise, tests, and failure domains.
- **Adapters:** translate public contracts without importing private modules or copying logic.
- **Canonical DealState:** provides one versioned record of requests, outputs, reviews, and warnings.
- **Reconciliation:** compares compatible bases while retaining disagreements and lineage.
- **LangGraph:** makes state transitions, fan-out/fan-in, interrupts, and resume explicit.
- **HITL:** assigns material ambiguity to an analyst and records the decision.
- **Deterministic finance:** makes arithmetic reproducible and interview-auditable.
- **Evaluation:** tests each subsystem in its own terms and exposes failure examples.
