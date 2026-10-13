# AI versus Deterministic Logic

The portfolio uses AI where language ambiguity matters and ordinary Python where correctness must
be auditable.

| AI-assisted responsibility | Deterministic responsibility |
| --- | --- |
| Semantic retrieval and query interpretation | Document IDs, chunk IDs, evidence locators |
| Candidate structured extraction from text | Schema validation and missing-value handling |
| Strategic-fit and diligence issue spotting | Eligibility filters, thresholds, ranking arithmetic |
| Comparing narrative claims across documents | Currency, unit, period, and basis compatibility |
| Drafting evidence-grounded explanations | EV/equity bridges, multiples, statistics, valuation ranges |
| Optional intent classification | QoE bridges, NWC, peg, net debt, concentration |
| Optional answer/research generation | Dependency plans, state transitions, retry limits, review policy |

AI output consumed by code must enter through a typed contract and remain linked to evidence.
Missing support produces abstention, a warning, or review rather than a fabricated value.

LangGraph coordinates stateful workflows in Projects 2, 4, 5, and 6. It does not perform finance.
LangChain/provider integrations are narrow and optional; offline evaluations replace network/model
calls with deterministic implementations. HITL records the reviewer, decision, rationale, prior
state, and result so approval cannot be confused with model confidence.

The core interview principle is simple: an LLM can propose meaning; deterministic code validates
and calculates; an analyst owns material judgment.
