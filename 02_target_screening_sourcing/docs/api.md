# Project 2 V1 API

## Run locally

```powershell
mats-api --host 127.0.0.1 --port 8002
```

The API composes the same offline providers and workflow used by tests and demos. It does not
require credentials or make network calls.

## Routes

- `GET /health` returns version and execution mode.
- `POST /theses/validate` validates the versioned thesis domain schema.
- `POST /discovery` returns queries, normalized candidates, provenance, warnings, and counts.
- `POST /enrichment` accepts one candidate and returns a serialized `CandidateProfile`.
- `POST /screen` accepts profiles and returns an auditable `Shortlist`.
- `POST /workflow/start` executes through ranking and pauses for review.
- `GET /workflow/{id}` inspects the current state summary.
- `POST /workflow/{id}/review` approves, rejects, or requests a bounded rerun.

FastAPI publishes the exact schemas at `/docs` and `/openapi.json`. Request models forbid unknown
top-level fields. Domain validation errors return a safe `422 invalid_request`; expected provider
failures return `503 provider_failure`. Internal Python objects and checkpoint bytes are never
returned.

## Human review flow

Start with a structured thesis:

```json
{
  "workflow_id": "review-001",
  "thesis": {"schema_version": 1, "...": "see examples/screening-ranking-demo.json"}
}
```

A successful start returns `status: awaiting_human_review`, candidate/profile counts, warnings,
trace events, and the provisional shortlist. Submit a review:

```json
{
  "decision": "approve",
  "reviewer_notes": "Evidence reviewed.",
  "approved_candidates": ["payflow.example"],
  "rejected_candidates": []
}
```

An approval can retain a subset by domain or canonical name. Rejection preserves screening audit
results but returns no approved candidates. `rerun` repeats enrichment and screening within the
configured bound and pauses again.

## Operational limitations

- Workflow IDs, state, and checkpoints live in one process and disappear on restart.
- Duplicate workflow IDs return `409` only within that process.
- There is no authentication, authorization, rate limiting, or multi-tenant isolation.
- Fixture mode is intended for local demonstration and testing, not public deployment.
