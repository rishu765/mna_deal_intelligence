# AI Engineering Summary

| Concept | Where it appears | Implemented boundary |
| --- | --- | --- |
| Parsing and normalization | P1, P4, P5 | PDFs/text/HTML and VDR formats; bounded table/spreadsheet handling |
| Chunking | P1, P4, P5 | Page, transaction, clause, and table-aware chunks with evidence IDs |
| Embeddings | P1, P4, P5 | Provider-neutral interfaces; local deterministic substitutes; optional OpenAI in P1 |
| Semantic and hybrid retrieval | P1; P4/P5 | P1 vector retrieval; P4/P5 weighted lexical/semantic retrieval |
| RAG | P1, P5 | Bounded contexts, grounded answers/findings, abstention behavior |
| Structured extraction | P1, P4, P5 | Typed schemas, missing fields, validation, conflicts, source priority |
| Specialist agents | P5 | Financial, commercial, legal/contractual, operational analyzers |
| Tool/adaptor calls | P6 | Typed capability registry and specialist adapters |
| LangChain | Narrow provider integrations | No portfolio-wide LangChain agent architecture |
| LangGraph | P2, P4, P5, P6 | State, conditional routing, checkpointing, review, resume, rerun |
| Reconciliation | P6 | Entity/metric/evidence compatibility, conflicts, staleness |
| Evaluation | P1–P6 | Subsystem metrics and deterministic scenario suites |
| Observability | P6 | Safe run counters, statuses, IDs, timings, and error classes |
| FastAPI | P1–P6 | Local typed APIs with explicit errors and no production auth claim |

The architecture keeps provider interfaces narrow and domain models provider-neutral. Structured
model output is treated as candidate data until schema, evidence, and business rules accept it.
The principal conceptual gaps for later mastery are retrieval evaluation on diverse real corpora,
model calibration, production prompt/version management, durable distributed LangGraph state,
provider failure engineering, and privacy controls for confidential VDR data.
