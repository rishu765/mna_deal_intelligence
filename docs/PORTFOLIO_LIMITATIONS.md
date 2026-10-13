# Portfolio Limitations

## Data and evaluation

- Most tests and evaluations use small synthetic fixtures designed for deterministic regression.
- Public-data validation covers one IBM/HashiCorp precedent snapshot; it does not establish broad
  real-world accuracy.
- Project 1 retains known synthetic citation/abstention failure cases under a regression gate.
- Project 2's expanded synthetic ranking labels expose two ordering failures.
- No licensed market-data, deal, company, or VDR dataset is included.

## Integration

- Native-local mode executes real specialist code, but supplied specialist datasets describe
  different entities and currencies.
- P1 currently passes evidence/fact identifiers to P6; a value-bearing P1-to-P3 financial feed is
  not implemented.
- P6 does not silently blend trading comps and precedents or perform implicit FX conversion.
- Live provider composition is not included by default.

## Document and diligence scope

- Complex OCR, handwriting, scanned-table recovery, and arbitrary spreadsheet layouts are outside
  the tested V1 boundary.
- Diligence specialists cover financial, commercial, legal/contractual, and operational signals.
  They are not full legal, tax, cyber, HR, regulatory, ESG, or technical diligence.
- Legal observations are issue-spotting aids and not legal opinions.

## Operating and security boundary

- APIs are local, unauthenticated demonstrations with process-local state.
- Checkpoint serializers use pickle only inside trusted in-memory stores. External or untrusted
  checkpoint bytes must never be deserialized.
- There is no tenant isolation, enterprise authorization, durable database, distributed worker,
  disaster recovery, production secrets manager, or compliance certification.
- Safe traces exclude prompts, source excerpts, credentials, and VDR contents, but production
  privacy controls have not been implemented.

## Product scope

- No DCF, LBO, accretion/dilution, merger model, synergy model, or fairness opinion is included.
- No production deployment, frontend, real-time market-data guarantee, or autonomous investment
  decision exists.
- No banker-grade Excel model, PowerPoint deck, or data-room export is generated.

These limits are accepted for an educational V1 and define the starting point for
[POST_V1_BACKLOG.md](POST_V1_BACKLOG.md).
