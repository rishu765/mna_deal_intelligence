# Project 5 handoff: AI Due-Diligence Agent

Project 5 can reuse proven patterns rather than importing Project 4 private modules:

- provider-neutral document catalogs and ingestion adapters;
- transaction/document-aware chunk metadata;
- semantic plus BM25 hybrid retrieval and provenance-complete evidence results;
- bounded-context structured extraction and second-stage validation;
- explicit missing/conflicting observations and source-priority verification;
- typed LangGraph state, conditional routes, bounded retries, and operational trace events;
- checkpointed analyst review with rationale and selected evidence;
- subsystem metrics plus representative end-to-end failure scenarios;
- strict FastAPI run/status/review transport and safe error mapping.

Due diligence needs a different domain: diligence workstreams, requests, red flags, materiality,
responsible parties, and issue resolution. Those models and Project 5 functionality are not part of
Project 4.
