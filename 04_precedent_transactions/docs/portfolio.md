# Portfolio summary

The Precedent Transactions Agent discovers historical M&A transactions, retrieves and grounds deal
evidence through hybrid RAG, extracts and verifies transaction terms through structured outputs,
selects comparable precedents, calculates transaction multiples deterministically, and orchestrates
the workflow with LangGraph checkpointing and focused human review.

## Resume-ready bullets

- Built an offline-first precedent-transactions agent spanning deal discovery, identity resolution,
  provenance-aware document ingestion, BM25/semantic hybrid retrieval, and evidence-linked results.
- Implemented schema-validated structured extraction, deterministic financial normalization,
  source-priority verification, amendment handling, and explicit conflict retention.
- Developed auditable comparable-deal selection and `Decimal`-based EV/revenue, EV/EBITDA, EV/EBIT,
  transaction P/E, percentile, EV-to-equity, and per-share calculations with complete traces.
- Orchestrated the end-to-end workflow with LangGraph conditional routing, bounded retries,
  in-memory checkpoints, analyst conflict resolution, and override audit trails.
- Exposed strict FastAPI run/review endpoints and a fixture-based subsystem evaluation covering RAG,
  extraction, verification, selection, valuation, workflow routing, and grounded explanation.
