# AI Interview Questions

| Question | Concise answer pointer |
| --- | --- |
| Why RAG here? | Company/VDR claims change and require source evidence; retrieval bounds context and enables citations. |
| How did you choose chunks? | Preserve semantic units and provenance; page/table/clause boundaries matter more than uniform token cuts. |
| Embeddings versus BM25? | Embeddings capture semantic similarity; BM25 preserves exact names/numbers; hybrid retrieval covers both. |
| How is hybrid search evaluated? | Hit/Recall/MRR at K plus source/metadata correctness on versioned fixtures. |
| How do you reduce hallucination? | Bounded context, structured schemas, support validation, abstention, evidence gates, and HITL. |
| What is a structured output failure? | Invalid schema, missing required provenance, incompatible basis, or unsupported value; reject or review it. |
| Why agents? | Specialists map to real bounded workflows and failure domains; they do not grant the LLM authority over finance. |
| What is tool calling here? | Typed capability requests routed through adapters; provider and specialist results return versioned envelopes. |
| Where is LangChain used? | Narrow provider/structured-output boundaries; not as the portfolio orchestrator. |
| Why LangGraph? | Explicit state, conditional routing, fan-out/fan-in, checkpoints, interrupts, resume, and bounded reruns. |
| What lives in graph state? | Request, plan, specialist envelopes, reviews, warnings/errors, reconciliation, and final output references. |
| How does routing work? | Deterministic intent vocabulary and dependency planning, with optional classifier support and validation. |
| How does HITL work? | Policy creates a structured review; checkpoint pauses; a recorded analyst action resumes or reruns work. |
| How do retries work? | Bounded retries for transient failures; deterministic validation errors fail without pointless retry. |
| How is partial failure handled? | Each specialist result has status/warnings/errors; independent successful outputs survive. |
| How do you evaluate an agent? | Separate intent, tool selection, planning, state, HITL, resilience, reconciliation, and synthesis metrics. |
| How do you observe runs safely? | IDs, statuses, counts, timings, branches, error classes; exclude prompts, source text, secrets, and reasoning. |
| Fixture versus native-local? | Fixture uses P6 payloads; native-local invokes real specialist code with offline inputs; neither implies live data. |
| What would production require? | Auth, safe durable state, tenant isolation, provider SLAs, privacy controls, monitoring, and larger real datasets. |
