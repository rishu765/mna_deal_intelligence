# V1 API

## Boundary

FastAPI is a thin delivery layer over `OfflineValuationService`. Domain models and valuation math
do not depend on HTTP. V1 accepts Decimal values serialized as strings and requires explicit
currency, unit, period, basis, and evidence fields in supplied profiles.

## Start the service

```powershell
.\.venv\Scripts\macv-api.exe
```

The server binds to `127.0.0.1:8003`, disables debug/reload, and exposes OpenAPI at `/docs`.

## Endpoints

`GET /health` reports version and offline mode.

`POST /target/profile` round-trips a versioned `TargetFinancialProfile`, applying domain
validation without inventing missing values.

`POST /valuation/run` runs the complete M1–M6 workflow. The smallest request is:

```json
{
  "provider_mode": "offline_fixture",
  "include_explanation": true
}
```

Optional `target_profile` accepts the same versioned object emitted by the profile serializer.
Optional `methods` must contain exact, period-aware labels from the offline fixture catalog, for
example:

```json
{
  "provider_mode": "offline_fixture",
  "methods": ["LTM Jun-2026 EV/EBITDA (reported)"],
  "include_explanation": false
}
```

The response contains a generated `valuation_id`, provider mode, target profile, universe,
selection decisions, peer snapshots, multiple sets, peer statistics, ranges, bridges, traces,
warnings, and optional explanation. `GET /valuation/{valuation_id}` retrieves that result while
the process remains alive.

## Error behavior

- Schema violations and unknown fields use FastAPI''s readable `422` validation response.
- Unsupported/duplicate method labels return `422 invalid_request`.
- A valid request with no compatible positive target metric returns
  `422 no_meaningful_valuation`.
- Unknown valuation IDs return `404`.
- Unexpected failures are logged server-side and return a generic `500 internal_error`; stack
  traces are not returned to clients.

Incomplete capital structure is not filled with zero. It is represented by warnings and may
prevent an EV-derived equity range while allowing other deterministic output to remain usable.

## Operational limits

The result store is in-memory and process-local. The API has no authentication, persistent
database, concurrency controls, rate limiting, live market data, or deployment configuration.
It is a callable portfolio interface, not a production service.
