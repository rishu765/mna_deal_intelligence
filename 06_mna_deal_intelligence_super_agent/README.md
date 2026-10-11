# M&A Deal Intelligence Super-Agent

Project 6 is the capstone coordination layer for the five specialist projects in this repository.
M0 established canonical state and typed integration contracts. M1/2 adds concrete boundary
adapters, a capability registry, offline-first intent classification, deterministic dependency
planning, idempotent result ingestion, and a deliberately small sequential fixture runner. M3 adds
deterministic cross-project reconciliation and a structured unified deal intelligence snapshot.
M4/5 adds the checkpointed LangGraph runtime, dependency-aware fan-out/fan-in, bounded retries,
failure isolation, analyst interrupts and resume, and controlled specialist reruns.

## Business Problem

An acquisition question spans company research, target sourcing, trading comparables, precedent
transactions, and due diligence. Each discipline has different inputs, evidence, status vocabulary,
financial semantics, and review needs. A deal team needs one durable context that can carry those
outputs without losing ownership or source precision.

## Why a Super-Agent Is Needed

Projects 1–5 are intentionally independent specialists. Project 6 will eventually interpret a
deal-level request, invoke only the needed specialist capabilities, preserve outputs, expose
conflicts, request analyst judgment, and synthesize an evidence-linked answer. M0–M5 now cover the
contracts, selection, planning, reconciliation, and checkpointed orchestration layers.

```mermaid
flowchart LR
    U[User] --> P6[Project 6 Super-Agent]
    P6 --> P1[Project 1<br/>Company and documents]
    P6 --> P2[Project 2<br/>Target screening]
    P6 --> P3[Project 3<br/>Trading comps]
    P6 --> P4[Project 4<br/>Precedents]
    P6 --> P5[Project 5<br/>Due diligence]
    P1 & P2 & P3 & P4 & P5 --> S[(Shared Deal State)]
    S --> F[Final Synthesis Contract]
    C[M1/2: adapters and deterministic plans] -. constrains .-> P6
```

## Projects 1–5 as Specialists

- **Project 1** owns document ingestion, chunking, retrieval, citations, cited answers, and company
  research profiles.
- **Project 2** owns acquisition theses, discovery, enrichment, deterministic eligibility and
  scoring, strategic fit, ranking, and shortlist review.
- **Project 3** owns target financial profiles, peer selection, trading multiples, deterministic
  valuation ranges, calculation traces, and grounded explanations.
- **Project 4** owns transaction discovery and identity, extraction and verification, precedent
  selection, transaction multiples, valuation ranges, and transaction-specific value bases.
- **Project 5** owns VDR intelligence, financial diligence, QoE, adjusted EBITDA, working capital,
  net debt, specialist findings, compound risks, missing information, and diligence review.

The evidence-based [integration matrix](docs/integration-matrix.md) records actual public models,
outputs, dependencies, and incompatibilities found in the current repository.

## Project 6 Responsibility

Project 6 owns canonical entity references, shared deal context, specialist envelopes, cross-project
lineage, workflow and capability status, dependency and staleness metadata, analyst decisions,
reconciliation, orchestration, and final synthesis metadata.

## What Project 6 Does NOT Reimplement

Project 6 does not parse documents, run retrieval, source or score targets, select peers, calculate
trading or precedent multiples, calculate QoE or diligence bridges, or reproduce specialist
reasoning. Specialist numeric outputs are immutable references. Future adapters translate at the
boundary and retain the original record ID.

## Canonical Deal State

`DealState` is modular and strongly typed. It contains `DealContext`, canonical entities, source
documents, five separately typed specialist-result collections, financial metrics, valuations,
diligence findings, metric conflicts, evidence, lineage, analyst decisions, assumptions, warnings,
errors, status, capability executions, dependencies, artifact versions, and revision metadata.

Unknown deal facts remain `None` or an explicit `UNKNOWN` enum value. They are never converted to
zero or fabricated. The state schema is `1.0.0`; serialization rejects unsupported versions.

### State ownership

| State area | Owner | Project 6 treatment |
| --- | --- | --- |
| Document intelligence | Project 1 | Store envelope, record IDs, and evidence references |
| Screening and sourcing | Project 2 | Store ranked candidates and specialist rationale |
| Trading-comps valuation | Project 3 | Preserve values, basis, inputs, and warnings exactly |
| Precedent analysis | Project 4 | Preserve transaction status, ownership, and value basis |
| Due diligence | Project 5 | Preserve findings, bridges, conflicts, and review state |
| Canonical identity and state | Project 6 | Own mapping, lifecycle, lineage, and revision metadata |
| Reconciliation and synthesis metadata | Project 6 | Record conflicts and decisions without mutating sources |

## Integration Contracts

`ProjectResultEnvelope[T]` wraps a capability-specific typed payload with the source project,
capability, run ID, status, evidence IDs, assumption IDs, warnings, errors, timestamps, and schema
version. `ProjectCapability` describes input/output schemas, named required inputs and outputs,
dependencies, execution nature, review needs, offline support, and version.

## Concrete Adapters and Translation

`Project1Adapter` through `Project5Adapter` implement the common M0 protocol. Each has an explicit
canonical-to-native request model and a typed native-to-envelope mapper. Fixture mode is the
default and is deterministic. Native mode accepts a specialist service callable, so later adapter
composition can bind the actual factories without importing five colliding top-level package names
at module import time. Health checks verify fixture usability or the presence of that callable.

The adapters expose only verified repository capabilities: Project 1 document research and cited
answers; Project 2 sourcing and screening; Project 3 trading-comps valuation; Project 4 precedent
valuation; and Project 5 structured diligence findings. Values and evidence locators cross the
boundary unchanged. Adapter validation checks identity, documents, currency, period, criteria, and
engagement context as applicable.

## Capability Registry

`CapabilityRegistry` owns capability-to-adapter mappings and rejects duplicate IDs. It supports
lookup by project, required input, document independence, health, and availability. Availability is
`AVAILABLE`, `UNAVAILABLE`, `DEGRADED`, `REQUIRES_INPUT`, or `UNSUPPORTED`. Planner selection always
comes from registered metadata, so an optional classifier cannot invent executable tools.

## Intent Classification and Request Normalization

The bounded taxonomy covers company research, target discovery and screening, target valuation,
trading comps, precedents, diligence, acquisition evaluation, valuation comparison, risk review,
and full deal analysis. `IntentClassifier` uses deterministic phrase rules first and supports an
optional structured model fallback for ambiguous language. Tests and demos never require an LLM.
It returns primary and secondary intents, entity mentions, constraints, requested outputs,
ambiguity, and warnings. `normalize_request` merges those results with canonical deal context and
records which inputs are actually present.

## Deterministic Planning

`ExecutionPlanner` maps known intents to registered capabilities, adds only required provider
steps, builds an acyclic dependency graph, assigns topological stages, and marks same-stage work as
parallelizable for the M4/5 runtime. It records concise selection rationale, expected outputs,
skipped capabilities, missing inputs, suggested clarification questions, and partial availability
warnings. A specified target skips Project 2. A valuation-only request does not add Project 4 or
Project 5. A target search does not add valuation or diligence.

`SequentialPlanRunner` exercises ready steps in order for offline integration tests. It records
selection, invocation, success, warning, failure, skip, and ingestion events. A failing adapter
does not remove completed results and does not stop independent steps. This runner is validation
scaffolding; M4/5 uses the LangGraph runtime described below.

`ingest_result` inserts typed envelopes, evidence, metrics, valuations, findings, warnings, and
errors into a new `DealState` revision. Reingesting the same project/capability/run ID is a no-op.
A rerun is retained and supersedes the preceding result artifact rather than deleting history.

```mermaid
flowchart LR
    U[User Request] --> I[Intent Classifier]
    I --> PL[Deterministic Planner]
    PL --> RG[Capability Registry]
    RG --> A[Typed Project 1-5 Adapters]
    A --> P[Projects 1-5 / offline fixtures]
    P --> E[ProjectResultEnvelope]
    E --> C[(Canonical DealState)]
    C --> R[Reconciliation Engine<br/>M3]
    R --> O[LangGraph Orchestration<br/>M4/5]
    O --> H[Checkpointed human review<br/>M4/5]
    H --> F[Final output<br/>M6/7]
    M[M3: reconciliation only] -. no LangGraph runtime .-> R
```

## Reconciliation Architecture

`ReconciliationService` reads canonical state and produces structured issues, metric and valuation
views, diligence impact insights, stale-output references, recomputation requests, scenarios, open
questions, and an analyst review queue. Specialist values remain immutable. Applying staleness
updates only Project 6 metadata and warnings.

```mermaid
flowchart LR
    P1[P1 Results] --> R[Reconciliation Engine]
    P2[P2 Results] --> R
    P3[P3 Results] --> R
    P4[P4 Results] --> R
    P5[P5 Results] --> R
    R --> M[Unified Metrics]
    R --> V[Valuation Comparison]
    R --> K[Risk Links]
    R --> S[Staleness]
    R --> Q[Review Queue]
    R --> U[Unified Deal Snapshot]
    U --> L[LangGraph Orchestration M4/5]
```

### Entity, metric, and evidence reconciliation

Entity matching uses canonical IDs, deterministic legal-name and alias normalization, ticker,
exchange, and geography. Partial or inconsistent matches remain ambiguous. Financial identity uses
metric type, entity, exact period, basis, actual/forecast state, currency, unit, source record, and
evidence. Different periods are explicitly not comparable. Reported and diligence-adjusted EBITDA
become separate scenarios rather than competing claims.

Same-currency units can be scaled across ones, thousands, millions, and billions. FX conversion is
never implicit. Values are aligned when their absolute difference is at most `0.01` base units or
their relative difference is at most `0.1%`. Valuation midpoint divergence is material above `10%`.
These thresholds are explicit in `NumericTolerancePolicy`.

Evidence references that point to the same document and locator are linked while retaining their
project IDs and native evidence IDs. Source authority remains contextual: audited history and
signed contracts may answer different questions than management adjustments.

### Staleness, valuation, and diligence impacts

A valuation that consumes reported EBITDA is marked stale only for a diligence-adjusted scenario
when a compatible adjusted metric becomes available. M3 creates an analyst-approved recomputation
request and does not rerun or recalculate the valuation. Artifact supersession and lightweight
`produced_from` lineage also mark dependent artifacts stale while unrelated outputs remain fresh.

Trading comps and precedents remain separate valuation entries with their ranges, bases, dates,
assumptions, evidence, and warnings. Their midpoint gap, percentage divergence, and range overlap
are deterministic comparison facts; no blended valuation is produced.

Project 5 EBITDA, customer concentration, net debt, and contract findings are linked to valuation
inputs, multiple confidence, equity-value context, and deal execution respectively. Quantified
deltas describe input differences only.

### Unified views, review queue, and scenarios

The unified snapshot contains all metric observations, valuation methods, risks, issues, stale
outputs, recomputation requests, thesis support and challenges, questions, evidence links, and
warnings. It selects a metric only when observations align or were explicitly resolved. Material
unresolved items enter a deduplicated review queue prioritized by blocking status, severity, and
downstream impact. Scenario contracts record metric choices and required reruns without generating
new specialist values.

## Evidence and Provenance

`EvidenceReference` supports document IDs, canonical and physical pages, section, table, spreadsheet
sheet/cell/range/row/column, chunk, URL, excerpt, and the specialist's original evidence ID. Project
6 references evidence by stable ID and does not reduce a precise spreadsheet or page locator to a
plain citation string.

`LineageGraph` connects evidence, facts, specialist outputs, reconciliation records, analyst
decisions, and future synthesis nodes. It supplies IDs and edges only; lineage construction belongs
to later milestones.

## Dependency / Staleness Model

`DependencyRequirement` records required, optional, and any-of capability or artifact inputs.
`ArtifactVersion` records schema and input versions, source artifact IDs, an optional dependency
fingerprint, stale state and reason, and supersession. M3 evaluates direct lineage and scenario
changes but does not trigger recomputation.

The representative fixture retains Project 3 reported LTM EBITDA of 100 and midpoint enterprise
value of 1,000 alongside Project 5 diligence-adjusted EBITDA of 85. The rejected recurring add-back
creates a metric conflict, marks the Project 3 valuation stale, and requires analyst review. Project
6 does not recalculate the valuation.

## Analyst Decisions

`AnalystDecision` records a stable decision ID, subject, previous state, typed action, selected
value, rationale, reviewer, and timezone-aware timestamp. It supports approvals, rejections,
modifications, selections, inclusion/exclusion, overrides, and conflict resolution. Decisions are
append-only business records; they do not overwrite specialist history.

## AI vs Deterministic Responsibilities

Future AI-assisted work may interpret user intent, assist planning, explain conflicts, produce
qualitative synthesis, and draft the final narrative. Deterministic code invokes projects, validates
schemas, maps IDs, tracks dependencies and state transitions, enforces numeric integrity, detects
stale artifacts, and retains evidence lineage. An LLM may explain Project 3, 4, or 5 numbers but may
never silently rewrite them. M3 uses no LLM: comparison, tolerance, staleness, review priority, and
scenario construction are deterministic.

## LangGraph Super-Agent Runtime

M4/5 implements an explicit typed `StateGraph`. Request validation, intent classification, plan
construction, plan validation, dependency-stage dispatch, adapter invocation, result collection,
M3 reconciliation, review detection, analyst interruption, approved reruns, and terminal handling
are separate workflow boundaries.

```mermaid
flowchart TD
    U[User Request] --> I[Intent Classifier and Planner]
    I --> E[Validated Execution Plan]
    E --> D[LangGraph Dispatcher]
    D -->|Send| P1[Project 1]
    D -->|Send| P2[Project 2]
    D -->|Send| P3[Project 3]
    D -->|Send| P4[Project 4]
    D -->|Send| P5[Project 5]
    P1 & P2 & P3 & P4 & P5 --> C[Result Collection]
    C --> R[M3 Reconciliation]
    R --> H{Review needed?}
    H -->|no| F[Structured terminal state]
    H -->|yes| X{{HITL interrupt}}
    X --> A[Analyst decision]
    A --> Q{Approved rerun?}
    Q -->|yes| D2[Affected specialist only]
    D2 --> R
    Q -->|no| R
```

The dispatcher reads M1/2 topological stages and invokes only selected capabilities. Ready steps in
the same stage use LangGraph `Send`, then join at typed result ingestion. Missing required input
enters `WAITING_FOR_INPUT`; it does not fabricate a target, VDR, financial profile, currency, or
sector. Retryable provider failures use a bounded counter, while deterministic validation errors
are not retried. Independent successful results survive another specialist's failure.

M3 review items and policy-triggered material diligence findings create concise review payloads.
LangGraph checkpoints before `interrupt`; resume uses the same thread ID and an append-only decision
and audit record. An approved EBITDA scenario reruns only Project 3, retains its prior envelope, and
reconciles again. The default process-local checkpointer and trusted serializer are suitable for
offline tests and a single trusted process only.

See [orchestration.md](docs/orchestration.md) for state fields, nodes, routing, retry policy,
checkpointing, review payloads, invariants, and the milestone evaluation harness.

LangChain remains available for structured model interactions inside intent interpretation or
specialists. LangGraph is the sole Project 6 orchestration layer.

## Roadmap

1. **M0 — Architecture + Canonical Deal State + Integration Contracts** ✅
2. **M1/2 — Project Adapters + Tool Registry + Intent Routing / Planning** ✅
3. **M3 — Cross-Agent Reconciliation + Unified Deal Intelligence** ✅
4. **M4/5 — LangGraph Super-Agent Orchestration + HITL + Resilience** ✅
5. **M6/7 — Final Synthesis + Evaluation + Observability + API/Demo + Final V1**

## Development

```powershell
cd 06_mna_deal_intelligence_super_agent
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest
python demo_routing.py
python demo_reconciliation.py
python demo_orchestration.py
```

All tests and fixtures are offline. The package has no runtime dependency on Projects 1–5.

## Limitations

- Entity matching is deterministic and bounded; ambiguous identities require analyst review.
- Native specialist factories must be injected; repository package-name collisions prevent safe
  eager imports of every project in one interpreter.
- Rules cover a bounded English intent vocabulary; ambiguous requests need the optional classifier
  or later clarification flow.
- The M1/2 runner remains sequential scaffolding; M4/5 uses the checkpointed LangGraph runtime.
- Dependency staleness follows explicit metric IDs and `produced_from` metadata; it does not infer
  undocumented specialist dependencies.
- Native scenario reruns depend on the specialist adapter accepting the approved scenario input.
- Final synthesis defines the future output shape; M0 creates no generated synthesis content.
- The included checkpointer is process-local; no production database or distributed worker exists.
- No final synthesis, production API, frontend, authentication, or deployment exists.
