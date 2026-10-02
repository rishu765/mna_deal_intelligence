# Repository instructions

## Repository structure

- This is the canonical monorepo for the six-project AI × M&A portfolio.
- Keep each project's implementation and documentation in its numbered directory.
- Add code to `shared/` only after at least two concrete consumers demonstrate reuse.
- Follow the nearest nested `AGENTS.md` for project-specific instructions.

## Git workflow

- Treat `main` as stable. Use a short-lived branch for each approved milestone or feature.
- Synchronize `main` before branching. Do not force-push or commit routine work directly to `main`.
- Keep pull requests focused, inspect their final diff, and report validation accurately.
- Prefer squash merge. Never merge a pull request without explicit user authorization.
- Do not delete branches until their changes are safely integrated and deletion is authorized.

## Engineering expectations

- Work only within the approved project and milestone scope.
- Keep secrets, local environments, caches, generated indexes, and large datasets out of Git.
- Add CI checks as executable behavior appears; keep workflows proportionate to the project.
- Preserve unrelated work and resolve conflicts by understanding both intended changes.
- Keep root documentation aligned with actual portfolio status.

