# Portfolio Capability Matrix

Status terms:

- **Implemented** — production code exists and deterministic tests exercise it.
- **Implemented in offline/native mode** — real specialist code runs with local inputs.
- **Fixture-driven** — behavior is real, but the supplied data/provider response is synthetic.
- **Mocked external dependency** — external network/model boundary is replaced in tests.
- **Planned / not implemented** — no V1 implementation claim.

| Capability | Project | Status | Evidence and boundary |
| --- | --- | --- | --- |
| PDF/text ingestion and normalization | P1 | Implemented | Local PDF parser; no OCR |
| Provenance-aware chunking | P1 | Implemented | Page and chunk IDs retained |
| Embeddings/vector index | P1 | Implemented; mocked external dependency | SQLite index; deterministic tests; optional OpenAI embeddings |
| Semantic retrieval | P1 | Implemented | Vector retrieval with a deterministic benchmark |
| Lexical/semantic hybrid retrieval | P4, P5 | Implemented | Local deterministic benchmarks |
| Grounded RAG and citations | P1 | Implemented; mocked external dependency | Provider-neutral generation; synthetic evidence gate |
| Structured company research | P1 | Implemented | Evidence-linked sections and abstention |
| Candidate discovery/enrichment | P2 | Fixture-driven | Credential-free provider fixtures |
| Deterministic screening/ranking | P2 | Implemented | Explicit criteria, exclusions, score traces |
| Strategic-fit explanation | P2 | Fixture-driven | Grounded fixture provider; optional model boundary |
| Trading comps | P3 | Implemented in offline/native mode | Real normalization, multiples, statistics, ranges over fixtures |
| Precedent transactions | P4 | Implemented in offline/native mode | Real selection/valuation over fixtures plus one public snapshot |
| QoE and EBITDA bridge | P5 | Implemented in offline/native mode | Deterministic finance fixture |
| NWC, peg, and net debt | P5 | Implemented in offline/native mode | Currency/unit guards and regression tests |
| Specialist diligence agents | P5 | Implemented; fixture-driven evidence | Financial, commercial, legal/contractual, operational |
| LangGraph orchestration | P2, P4, P5, P6 | Implemented | Typed graphs, conditional routing, bounded retries |
| Human review | P2, P4, P5, P6 | Implemented | Real interrupt/resume within process-local checkpoints |
| Checkpoint/resume | P2, P4, P5, P6 | Implemented locally | In-memory trusted-process serializer; not durable or multi-user |
| P1–P5 Project 6 adapters | P6 | Implemented in offline/native mode | Lazy native-local registry and fixture registry |
| Cross-project reconciliation | P6 | Implemented | Basis, period, currency, lineage, staleness, conflicts |
| Final synthesis | P6 | Implemented; fixture/native inputs | Structured, evidence-linked, bounded assessment |
| FastAPI | P1–P6 | Implemented locally | Typed local APIs; no authentication/deployment |
| Safe observability | P6 | Implemented | Counts, IDs, status, duration; no source text or secrets |
| Live market/deal/VDR connectors | Portfolio | Planned / not implemented | Provider ports exist; no default live composition |
| Production persistence/auth | Portfolio | Planned / not implemented | Local proof-of-concept boundary only |
| DCF/LBO/accretion-dilution | Portfolio | Planned / not implemented | Outside V1 scope |
| Banker-grade Excel/PPT output | Portfolio | Planned / not implemented | No claim made |

The authoritative mode distinction is: **fixture mode** uses Project 6-owned payloads;
**native-local mode** executes specialist code with offline inputs; **live-provider mode** requires
a separately supplied provider and is not a portfolio default.
