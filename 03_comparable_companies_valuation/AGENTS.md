# Project 3 instructions

- Work only on the approved Project 3 milestone; do not begin a later milestone implicitly.
- Keep deterministic finance logic separate from AI-assisted research and explanation.
- Preserve currency, unit, period, as-of time, metric basis, and evidence on financial values.
- Never silently mix reported and adjusted metrics, historical and forecast periods, currencies,
  units, or incompatible market-data snapshots.
- Keep domain models and ports provider-neutral. Do not import private Project 1 or Project 2
  implementation modules.
- Use Python 3.11+, a `src` layout, frozen dataclasses for core value objects, and narrow typed
  protocols at external boundaries.
- Keep live providers, secrets, caches, and generated outputs out of deterministic tests.
- Run Ruff, mypy, and pytest before reporting a milestone complete.
