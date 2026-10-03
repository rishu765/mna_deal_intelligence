# Final Project 1 validation

Date: 2026-10-04

This record captures the M11 release checks for version 1.0.0. It distinguishes verified
behavior from checks that require external infrastructure or paid credentials.

## Automated quality

| Check | Result |
| --- | --- |
| Complete pytest suite | 133 passed |
| Ruff lint | Passed |
| Ruff format verification | 106 files formatted |
| Strict MyPy | 87 source files passed |
| Editable package installation | Passed as `ma-company-intelligence==1.0.0` |
| Dependency consistency (`pip check`) | No broken requirements |
| Console entry-point smoke tests | Demo and API help passed |
| Synthetic document flow | Five pages parsed, five demo-config chunks, no warnings |

GitHub Actions repeats dependency consistency, lint, format, type, and test checks on the final
pull request. The pull request result is the authoritative clean-environment CI evidence.

## Evaluation rerun

`madi-evaluate --top-k 1,3,5` produced JSON exactly equal to
`evaluation/baselines/m08_offline_baseline.json`, including aggregate and per-case values. The
M11 result therefore has zero metric change from M8. See `evaluation.md` for the full metric
table and interpretation.

This is an offline recorded-observation benchmark. No optional LLM judge or paid live-provider
evaluation was run.

## Reproducibility and demo

- The synthetic company PDF is generated locally from fictional text; no third-party report is
  committed.
- Two independent generations produced identical PDF bytes during automated testing.
- The generated PDF passes the production parser and chunker.
- Existing offline HTTP integration tests exercise PDF parsing, chunking, fake embedding,
  SQLite indexing, retrieval, fake generation, citation responses, and idempotent re-indexing.
- The container definition installs the release package, runs as non-root, uses mounted data,
  and exposes a health check.

Docker was not installed in the M11 development environment, so the image was not built
locally. The Dockerfile and `.dockerignore` were reviewed, and CI continues to validate the
same packaged Python application. A reviewer with Docker should run the build command in
`deployment.md` before publishing an image.

## Configuration and security hygiene

- No committed `.env`, API key, raw PDF, SQLite database, cache, or generated evaluation output
  was found.
- `.env.example` contains placeholders and every supported setting.
- Provider keys remain environment-only and provider clients initialize lazily.
- Input paths stay beneath `MADI_DOCUMENT_ROOT`, including resolved symlinks.
- Request, question, retrieval-count, and document-size limits are configured and tested.
- Public errors omit stack traces, provider details, local paths, prompts, and secrets.
- Operational logs omit request bodies, document text, vectors, prompts, and credentials.
- Provider timeouts and retries are finite; invalid deterministic inputs are not retried.
- Runtime dependencies are all used by implemented capabilities; `pip check` passed.

This is portfolio-level hygiene, not a formal penetration test or software-composition audit.

## Release boundary

The release is suitable for local development and a single container on a trusted host. It is
not ready for unauthenticated public exposure, multiple writable replicas, or high-concurrency
production use. The README and deployment guide state those limits directly.
