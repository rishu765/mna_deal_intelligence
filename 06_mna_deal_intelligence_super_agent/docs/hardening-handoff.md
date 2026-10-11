# Portfolio-wide Hardening Handoff

This is a handoff for work after Project 6 V1. No portfolio-wide refactor is included here.

## Review and correctness

- Revisit must-fix findings recorded in Antigravity or human reviews for Projects 1–6.
- Expand real-world and adversarial datasets, expert labels, regression baselines, and failure cases.
- Validate native service injection for every specialist in one deployable environment.
- Add banker review for metric, valuation, risk, and citation presentation.

## Shared architecture

- Inventory duplicate evidence, period, currency, result, status, and API abstractions.
- Extract shared models only after confirming at least two stable consumers and a migration plan.
- Align dependency versions, package namespaces, configuration, error codes, and logging fields.
- Define cross-project compatibility tests and supported schema-version windows.

## Data, security, and operations

- Add governed document, market-data, CRM, and VDR connectors with freshness and entitlement checks.
- Add tenant isolation, authentication, authorization, encryption, retention, deletion, and audit
  policies for confidential deal data.
- Replace process-local stores with durable checkpoint, artifact, and run persistence.
- Add deployment, concurrency controls, queues, timeouts, backups, disaster recovery, and telemetry.
- Export traces and metrics to a production observability backend with redaction tests.

## User experience

- Add a reviewed analyst workspace for plans, evidence, conflicts, decisions, reruns, and progress.
- Add workflow visualization and safe export to Excel, PowerPoint, and PDF.
- Preserve specialist numbers and citations through every export format.
