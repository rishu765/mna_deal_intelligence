# Project 2 instructions

- Work only on the approved Project 2 milestone; do not begin a later milestone implicitly.
- Keep discovery, enrichment, deterministic screening, semantic reasoning, and orchestration as
  separate boundaries.
- Keep domain models and ports provider-neutral. Preserve source provenance without inventing
  missing company attributes.
- Do not import private implementation modules from Project 1. Integrate through an explicit
  adapter or service contract when M3 introduces enrichment.
- Use Python 3.11+, a `src` layout, frozen dataclasses for core value objects, and narrow typed
  protocols at external boundaries.
- Keep secrets, caches, datasets, and generated outputs out of Git.
- Run Ruff, mypy, and pytest before reporting a milestone complete.

