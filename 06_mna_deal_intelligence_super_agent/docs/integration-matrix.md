# Projects 1–5 integration matrix

This matrix reflects the implementation re-inspected for Project 6 M1/2. Project 6 uses
adapters because each project is an independently packaged `src` application and repository rules
prohibit imports from private specialist implementation modules.

| Project | Inputs expected at future boundary | Outputs consumed by Project 6 | Evidence model | Deterministic outputs | AI-assisted outputs | Dependencies | Adapter complexity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 Company & Document Intelligence | Entity, local documents/document IDs, question or research request | `ParsedDocument`, chunks, retrieval results, `RAGAnswer`, `CompanyResearchProfile`, disclosed financial facts | `Citation` joins chunk/document IDs, canonical pages, zero-based physical indexes, printed labels, excerpt, and document metadata | PDF provenance, chunking, indexing, retrieval result structure, citation assembly | Grounded answer and structured company research | PDFs; embedding/generation providers for live paths; fixture paths available | Medium: rich page conventions and string-valued financial metrics need mapping |
| 2 Target Screening & Sourcing | `AcquisitionThesis`, discovery/enrichment inputs, review policy | `CandidateCompany`, `CandidateProfile`, `ScreeningResult`, `RankedCandidate`, `Shortlist`, workflow result | `DiscoveryEvidence` and `EnrichmentEvidence` use source URL/provider/field details; profile facts and inferences separate | Criterion evaluation, eligibility, score summaries, ranking | Strategic-fit assessment and some enrichment | Discovery and enrichment providers; Project 1 adapter already exists for research enrichment | Medium: candidate identity and evidence types differ from P1/P3; scores use project-specific types |
| 3 Comparable Companies & Valuation | Target identity/profile, evidence-backed financial and market data, universe and selection policy | `TargetFinancialProfile`, peer selection, multiples, peer statistics, `ValuationOutput`, traces | P3 `EvidenceReference` carries source/document/page/section/table/cell/chunk/URL plus timestamps | Normalization, EV/equity bridges, multiples, statistics, implied valuation ranges | Research normalization candidates and valuation explanations | Financial/market/profile/universe/forecast provider ports; existing P1/P2 adapters | High: strict period, basis, unit, timestamp, estimate, and value-family semantics must remain intact |
| 4 Precedent Transactions | Target/deal criteria, discovered transactions, transaction documents, selection and valuation inputs | Verified transaction records, selected precedents, transaction multiples, peer statistics, implied ranges, workflow result | Deal document sources and extraction evidence IDs preserve transaction, page, section, source authority/reliability, amendment, and conflict | Identity normalization, verification, selection, multiples, value ranges | Extraction and grounded valuation reasoning | Discovery/document/extraction providers; offline fixtures; LangGraph final workflow | High: headline/equity/enterprise value, partial ownership, dates, lifecycle, revisions, and disputes cannot be flattened |
| 5 AI Due Diligence | `DiligenceEngagement`, VDR manifest/documents, workstream scope, review policy | Findings, financial observations, QoE and EBITDA bridge, concentration, NWC, net debt, conflicts, missing information, report/review state | `EvidenceReference` supports VDR/external/calculation sources, pages, section, table, row/column, sheet/cells, chunk, spans, period, context | Reconciliation, adjustments, bridges, thresholds, prioritization, workflow policy | Classification/extraction candidates, specialist investigation, explanations/report narrative | VDR ingestion/retrieval, specialist services, review, checkpointed LangGraph workflow | High: broad finding and review taxonomy plus confidentiality and detailed spreadsheet provenance |

## Actual compatibility gaps

| Gap | Repository evidence | M1/2 treatment | Later owner |
| --- | --- | --- | --- |
| Entity identity | P2 `CandidateCompany`, P3 `CompanyIdentity`, P4 transaction parties, and P5 `EntityReference` use different IDs and fields; P1 often carries a company name only | `CanonicalEntityReference` retains canonical ID, names, aliases, market fields, external IDs, source projects, and evidence | M1/2 adapter mappings; M3 reconciliation policy |
| Evidence shape | P1 distinguishes canonical page and physical PDF index; P3 has finance-oriented locators and timestamps; P4 evidence is transaction/document scoped; P5 includes spreadsheet and span locators | Superset `EvidenceReference` plus original `project_evidence_id` and `source_record_id` | M1/2 adapters |
| Financial metric types | P1 research metrics store values as source strings; P2 profile metrics use screening units; P3 and P5 use different metric enums, period kinds, bases, and units; P4 has deal-specific financial facts | `FinancialMetricReference` is a cross-project reference, not a replacement calculator; it retains project record ID, basis, period, estimate state, evidence, and verification | M1/2 adapters and M3 reconciliation |
| Period semantics | P3 has historical/forecast and strict period models; P4 ties financials to transaction dates; P5 has LTM/NTM/as-of periods | Canonical period carries label and optional date bounds; specialist source ID remains authoritative | M1/2 adapters |
| Currency and units | P1 may have nullable strings, P2 screening units, P3 strict currency/unit/value-family rules, P4 transaction money bases, P5 finance units | Currency/unit are explicit on canonical financial and valuation references; no conversion occurs | M3 reconciliation or a later explicit conversion capability |
| Valuation basis | P3 separates EV/equity families; P4 distinguishes headline, equity purchase price, and transaction EV | `ValuationBasis`, source record, method, metric basis, and input metric IDs retained | M1/2 adapters |
| Status vocabularies | Each workflow has distinct states (`awaiting_review`, `waiting_for_information`, `completed_with_warnings`, and others) | Project 6 owns a small orchestration status and a separate capability execution status; source payload remains available | M1/2 status mapping |
| Warning/error shape | P1/P2 often expose strings or local issue objects; P4/P5 use distinct structured failure codes | Project 6 envelope uses `DealWarning`/`DealError`, including project and capability, without raw stack traces | M1/2 adapters |
| Human review | P2 shortlist actions and P4/P5 workflow decisions have different subjects/actions | Project 6 `AnalystDecision` records general subject/action/reviewer/time while keeping specialist source records | M3 reconciliation and M4/5 HITL |
| Serialization | P3, P4, and P5 have separate tagged serializers and schema constants; P1/P2 mainly expose dataclasses/API schemas | Project 6 has an independent tagged state serializer and rejects unknown schema versions | Each adapter at its boundary |
| Package boundaries | Five separate distributions reuse top-level package names such as `src` and expose different service/factory shapes | Concrete adapters use explicit native request models and injectable service callables; fixture mode remains import-safe | Native composition in M4/5 |

## M1/2 adapter bindings

| Adapter | Canonical capability | Verified native seam | Current binding |
| --- | --- | --- | --- |
| Project 1 | Company intelligence and cited Q&A | `ProjectApplicationService`, `CompanyIntelligenceService`, `ServiceContainer` | Explicit request/output translation; fixture callable by default; native callable injection |
| Project 2 | Target sourcing and screening | `build_offline_services`, discovery/profile/screening services | Acquisition criteria mapping with typed candidate and evidence envelope |
| Project 3 | Trading-comps valuation | Public valuation request/output models and offline fixtures | Target profile, currency, and as-of validation; specialist valuation retained unchanged |
| Project 4 | Precedent valuation | Discovery/selection/valuation workflow services and fixtures | Search criteria mapping; transaction basis and evidence retained |
| Project 5 | Structured diligence | Final workflow services and `DiligenceWorkflowResult` | VDR/workstream mapping; findings and finance references remain structured |

The registry exposes these bindings without importing specialist internals. A host application can
provide a project-native callable after loading the relevant distribution. This is required because
the repository projects are independently packaged and are not safe to import eagerly together.

## Compatibility expectation

An adapter must preserve the specialist payload or a stable source record ID, map only fields it
understands, emit a warning for partial mappings, and never coerce unknown values to zero. A schema
version change requires an explicit adapter update and contract test. Project 6 state may add
backward-compatible optional fields within `1.x`; breaking serialized-state changes require a new
major schema version.
