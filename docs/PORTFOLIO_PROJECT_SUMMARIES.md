# Portfolio Project Summaries

## 1. Company & Document Intelligence

- **Problem:** Analysts need answers that remain traceable to source documents.
- **Built:** PDF ingestion, chunking, semantic retrieval, grounded RAG, citations, structured research,
  evaluation, and FastAPI.
- **Interesting:** Provenance survives ingestion through answer claims; unsupported content can abstain.
- **Concepts:** RAG, embeddings, retrieval evaluation, company/financial statement research.
- **Limit:** Small synthetic benchmark, no OCR, optional live model provider only.

## 2. Target Screening & Deal Sourcing

- **Problem:** Acquisition theses must become explainable, repeatable shortlists.
- **Built:** Discovery/enrichment ports, deterministic filters and scores, ranking, LangGraph review,
  evaluation, and API.
- **Interesting:** Hard exclusions remain separate from strategic-fit judgment.
- **Concepts:** Entity evidence, ranking, tool orchestration, acquisition criteria.
- **Limit:** Bundled candidates/providers are synthetic; ranking labels remain small.

## 3. Comparable Companies & Valuation

- **Problem:** Trading-comps work is vulnerable to basis, period, unit, and peer-selection errors.
- **Built:** Target profile, auditable peers, data snapshots, multiples, statistics, ranges, EV/equity
  bridge, explanations, evaluation, and API.
- **Interesting:** Values carry currency, unit, period, estimate status, date, and evidence.
- **Concepts:** EV/revenue, EV/EBITDA, LTM/NTM, peer selection, valuation ranges.
- **Limit:** Offline fixtures; no live market data or implicit FX.

## 4. Precedent Transactions

- **Problem:** Deal values and terms are ambiguous across announcements and amendments.
- **Built:** Discovery, document retrieval, structured extraction, conflict retention, selection,
  multiples, ranges, LangGraph review, evaluation, and API.
- **Interesting:** Headline, equity, and enterprise values are not treated as interchangeable.
- **Concepts:** Control transactions, announcement/completion dates, transaction multiples.
- **Limit:** Fixture discovery and one public validation case; no licensed database.

## 5. AI Due Diligence

- **Problem:** Large VDRs hide financial adjustments, contradictions, risks, and missing information.
- **Built:** Multi-format VDR ingestion, hybrid retrieval, four specialists, QoE/NWC/net debt,
  contradiction handling, HITL, reporting, evaluation, and API.
- **Interesting:** Candidate findings retain lineage to facts and evidence; finance remains deterministic.
- **Concepts:** QoE, add-backs, peg, debt-like items, RAG, specialist agents.
- **Limit:** Synthetic VDR, bounded workstreams, no production confidentiality controls.

## 6. M&A Deal Intelligence Super-Agent

- **Problem:** Specialist results need coordinated execution and reconciliation without losing meaning.
- **Built:** Canonical DealState, registry, routing/planning, native and fixture adapters, LangGraph,
  partial failure, HITL/rerun, reconciliation, synthesis, evaluation, observability, and API.
- **Interesting:** Adapters fail closed on incompatible entity/finance/evidence/schema data and preserve
  specialist ownership.
- **Concepts:** Multi-agent system design, tool calling, state, fan-out/fan-in, reconciliation.
- **Limit:** Native specialist fixtures are not one deal; persistence and APIs remain local.
