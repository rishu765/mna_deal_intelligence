# Configuration and security review

- Offline fixture mode requires no credentials or environment variables.
- Root `.gitignore` excludes `.env`, virtual environments, caches, raw/processed data, and artifacts.
- `.env.example` contains comments only and no secret-shaped placeholder value.
- Source, fixtures, tests, and documentation were scanned for API keys, passwords, and committed
  credentials; none are required or present.
- FastAPI runs with `debug=False`, maps known validation/provider failures, and returns a generic
  message for unexpected exceptions while logging the server-side exception.
- API responses use compact evidence locators and do not return full ingested documents or model
  prompts.
- Operational logs contain node names, statuses, counts, timings, and retry events, not document
  bodies, secrets, or hidden model reasoning.
- The default checkpoint serializer uses pickle only for bytes written and read inside the same
  trusted process. It is unsuitable for untrusted, shared, or durable storage.
- V1 has no authentication, authorization, rate limiting, durable persistence, multi-process run
  coordination, or production deployment hardening.
