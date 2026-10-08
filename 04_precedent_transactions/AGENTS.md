# Project 4 instructions

- Work only on the approved Project 4 milestone; do not begin later milestones implicitly.
- Keep transaction identity, source observations, verified facts, normalization, selection, and
  valuation calculations as separate boundaries.
- Preserve transaction status, ownership, valuation basis, currency, unit, period, measurement
  date, and evidence. Unknown is never zero.
- Never treat headline value, equity purchase price, and transaction enterprise value as
  interchangeable. Never gross up partial stakes without an explicit future policy and inputs.
- Keep deterministic finance logic separate from AI-assisted extraction, comparison, and
  explanation.
- Keep domain models and ports provider-neutral. Do not import private Project 1, 2, or 3
  implementation modules; use future adapters at package boundaries.
- Use Python 3.11+, a `src` layout, frozen dataclasses for core value objects, and narrow typed
  protocols only when a concrete provider integration exists.
- Keep source documents, secrets, caches, generated indexes, and large datasets out of Git.
- Run Ruff, mypy, and pytest before reporting a milestone complete.
