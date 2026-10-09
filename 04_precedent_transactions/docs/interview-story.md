# Interview story

1. **Business problem:** Bankers need to know what acquirers paid for similar companies and what
   those negotiated prices imply for the target.
2. **Methodology:** Precedent transactions use historical deal EV or equity value divided by
   transaction-date target financials, then apply peer statistics to the target.
3. **Discovery challenge:** Multiple articles can describe one bid, while competing bids, amendments,
   repeated stake purchases, and withdrawn offers must remain distinct.
4. **RAG:** Documents are ingested into transaction-aware chunks and retrieved through deterministic
   semantic and BM25 channels with page, section, source, and transaction provenance.
5. **Extraction:** A structured-output boundary sees only bounded retrieved evidence and must return
   unknown rather than invent unsupported values.
6. **Verification:** Source priority, chronology, categorical status, and multiple observations keep
   conflicts and amendments visible.
7. **EV versus equity:** Headline value, equity purchase price, and transaction EV are separate.
   Derived EV uses only compatible disclosed inputs and retains its bridge trace.
8. **Selection:** Python applies status, date, ownership, value-basis, type, and size filters; semantic
   assessment explains business, geography, and buyer comparability.
9. **Valuation:** `Decimal` arithmetic computes compatible multiples, R7 statistics, P25/median/P75
   ranges, EV-to-equity bridges, and per-share values. Negative earnings are not meaningful.
10. **Orchestration:** LangGraph coordinates existing services, typed state, conditional failures,
    bounded provider retries, and finalization.
11. **Human review:** Material conflicts and ambiguous deal structure pause through an in-memory
    checkpoint. The analyst can resolve a known observation or document an override.
12. **Evaluation:** Subsystem metrics stay separate, and ten end-to-end scenarios verify routing,
    graceful failure, override audit, and AI failure isolation.
13. **Limitations:** Coverage is fixture-heavy, persistence is process-local, and there is no
    licensed database, authentication, durable deployment, or production model evaluation.
