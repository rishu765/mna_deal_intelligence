# Project 4 V1 evaluation report

| Subsystem | Metric | Result | Interpretation |
| --- | --- | --- | --- |
| Deal discovery | Candidate recall | 7/7 | Pass on fixture universe |
| Deal discovery | Duplicate resolution | 8 observations → 7 deals | Pass |
| Hybrid RAG | Hit@3 / Recall@3 / MRR | 1.0000 / 1.0000 / 0.9167 | Pass on six cases |
| Extraction | Field / numeric / missing / evidence accuracy | 1.0000 each | Pass on seven cases |
| Verification | Conflict detection | 1.0000 | Pass |
| Selection | Expected include/exclude behavior | 5 selected | Pass |
| Valuation | R7 statistics and traced ranges | 5 ranges | Pass |
| Workflow | Pause / resume / terminal routing | Pass | Checkpointed in one process |
| Explanation | Evidence IDs grounded in calculation inputs | 3/3 valid | Pass |

All ten end-to-end scenarios pass: clean set, duplicate discovery, ambiguous value, partial stake,
conflicting sources, negative EBITDA, weak retrieval, no valid precedents, analyst override, and AI
explanation failure.

Representative safe failures include retrieval warnings instead of invented evidence, not-meaningful
earnings multiples, structured no-precedent termination, and preserved deterministic valuation when
commentary fails.

This is a regression suite over a tiny synthetic corpus. It does not establish production deal
coverage, legal completeness, model quality, source licensing, or market valuation accuracy. No
licensed transaction database, production embedding model, or live LLM is evaluated.
