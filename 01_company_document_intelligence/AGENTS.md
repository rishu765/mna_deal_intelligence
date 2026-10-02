# Repository instructions

## Scope and workflow

- Work one approved milestone at a time. Do not begin the next milestone automatically.
- Keep this repository focused on reusable M&A company research and document intelligence.
- Prefer the smallest understandable design that meets the current milestone.
- Do not add agents, orchestration frameworks, infrastructure, or providers without a concrete need.

## Engineering expectations

- Use Python 3.11+, the `src` layout, type hints for public boundaries, and concise docstrings
  where intent is not obvious.
- Preserve provenance through every transformation. Never fabricate missing metadata.
- Keep deterministic work deterministic; use structured schemas for LLM outputs consumed by code.
- Put provider-specific integrations behind narrow interfaces and keep domain models provider-neutral.
- Keep secrets out of source control. Update `.env.example` when configuration changes.
- Add focused tests for meaningful behavior and run the configured lint, format, type, and test checks.
- Preserve unrelated user changes and avoid broad refactors outside the active milestone.

## Documentation

- Update `docs/progress.md` when a milestone advances.
- Record consequential choices and tradeoffs in `docs/decisions.md`.
- Keep `README.md`, architecture, and setup instructions aligned with implemented behavior.

