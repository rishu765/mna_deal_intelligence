# Repository decisions

## R-001 — One portfolio monorepo

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Keep all six AI × M&A projects in this repository under numbered directories.
- **Why:** Later projects can reuse proven capabilities while the portfolio retains a coherent
  history and a single integration branch.
- **Constraint:** Individual projects do not become nested Git repositories. Shared code is
  created only when concrete reuse appears.

## R-002 — Pull-request milestone workflow

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Develop meaningful milestones on short-lived branches, validate them, and use
  focused pull requests into `main`. Prefer squash merge after explicit approval.
- **Why:** This keeps `main` stable and creates reviewable portfolio history without permanent
  branches for each project.

## R-003 — Progressive continuous integration

- **Date:** 2026-10-03
- **Status:** Accepted
- **Decision:** Add path-scoped CI as projects acquire executable checks.
- **Why:** Project 1 already defines tests, linting, formatting, and type checking, so these
  checks now provide useful pull-request feedback without requiring monorepo-wide infrastructure.

