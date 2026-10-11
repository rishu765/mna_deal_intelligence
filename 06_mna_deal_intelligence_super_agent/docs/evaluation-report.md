# Final V1 Evaluation Report

The final benchmark contains 18 deterministic synthetic cases: company research, target screening,
trading comps, precedents, diligence, valuation comparison, full acquisition evaluation, ambiguous
intent, missing target, missing VDR, unavailable Project 4, transient Project 3 failure, material
EBITDA mismatch, multiple reviews, no material risk, entity conflict, mixed currencies, and stale
valuation requiring rerun.

| Subsystem | Metric | Result | Interpretation |
| --- | --- | ---: | --- |
| Intent | Exact fixture intent accuracy | 18/18 (100%) | Bounded rules match the synthetic request set, including ambiguity. |
| Routing | Required capability precision | 32/34 (94.1%) | Two Project 1 calls are explicit dependency providers for missing financial/sector context. |
| Routing | Required capability recall | 32/32 (100%) | Every expected specialist capability is selected. |
| Planning | Missing prerequisite detection | 2/2 (100%) | Missing target and VDR are disclosed as clarification requirements. |
| Planning | Dependency, cycle, and parallel stage checks | 2/2 (100%) | Existing contract tests verify ordering, cycle rejection, and P3/P4 fan-out. |
| Adapters | Translation and provenance suites | 5/5 (100%) | Each specialist adapter retains native values and evidence IDs in fixtures. |
| Orchestration | Branch, retry, and partial-failure fixtures | 4/4 (100%) | Fan-out/fan-in, bounded retry, exhaustion, and independent-result survival are covered. |
| Reconciliation | Conflict, staleness, and impact checks | 5/5 (100%) | Rich fixtures cover basis mismatch, staleness, valuation divergence, risk, and evidence linking. |
| HITL | Trigger, checkpoint, resume, and decision checks | 4/4 (100%) | Decisions are validated, appended, and applied to the same checkpointed run. |
| Synthesis | Required section coverage | 16/16 (100%) | All required structured sections are present. |
| Synthesis | Numeric fidelity | 6/6 (100%) | Surfaced valuations and material metrics equal canonical sources. |
| Synthesis | Citation reference integrity | 100% | Every rendered evidence ID exists in canonical state. |
| Resilience | State preservation and terminal correctness | 4/4 (100%) | Existing graph invariants retain completed state and honest terminal status. |
| End to end | Offline component path | 6/6 (100%) | Routing through validated synthesis is exercised without network or live models. |

There is no composite score. These results validate deterministic fixtures, not production quality.
Live provider accuracy, latency, security, market-data freshness, concurrency, and real-deal analyst
outcomes remain unevaluated.
