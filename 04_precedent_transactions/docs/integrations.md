# Project 1–3 reuse and compatibility assessment

This assessment reflects the repository at Project 3 V1. Project 4 does not import earlier private
modules in M0.

## Reusable today through future adapters

### Project 1: company document intelligence

Useful capabilities already exist for PDF ingestion, parsed pages, provenance-aware chunks,
embedding/vector indexing, retrieval, citations, grounded RAG, structured research, evaluation,
and API hardening. Project 4 evidence includes compatible `document_id`, `chunk_id`, page, section,
text location, and excerpt fields.

A future adapter can translate Project 1 `DocumentSource`, `SourceProvenance`, `DocumentChunk`,
retrieval results, and citations into Project 4 document/evidence contracts. Project 1 is oriented to
company research, so deal-document classification, merger-agreement tables, and transaction-specific
queries require Project 4 behavior rather than direct reuse.

### Project 2: target screening and sourcing

Useful patterns already exist for provider-neutral discovery records, external identifiers,
evidence-backed entity profiles, deterministic hard filters, semantic judgments, result audit
trails, LangGraph typed state, conditional routing, bounded retries, checkpointing, and human
review.

Project 4 discovery concerns events and bids rather than only companies. Project 2's candidate
identity cannot uniquely represent competing bids, amended terms, repeated acquisitions, or stake
purchases. Reuse the patterns and later adapter boundaries, not the candidate model itself.

### Project 3: comparable companies and valuation

The following semantics are safe to reproduce behind a future adapter or promote to `shared/` only
after both projects consume an intentionally stable contract:

- exact `Decimal` values;
- three-letter currencies and explicit units, including crore and per-share;
- period kind, label, actual/forecast status, and exact dates;
- reported versus adjusted metric basis;
- dated capital-structure components;
- evidence-bearing financial metrics;
- explicit multiple definitions/statuses and calculation traces;
- deterministic statistics and valuation output patterns.

Project 3's concrete classes are not imported because each numbered project is independently
packaged and its modules are private implementation details. Project 4 also needs concepts absent
from trading comps: announcement/completion lifecycle, negotiated consideration, acquired stake,
headline/equity/transaction-EV ambiguity, withdrawn bids, and deal-date financial alignment.

## Compatibility risks requiring later integration work

1. Project 1 uses document/chunk citation types that do not include transaction fact status or
   source reliability. The adapter must preserve its stable locators and add Project 4 semantics.
2. Project 2 company discovery may merge records appropriately for a company universe but would
   over-merge multiple bids for the same target. Transaction resolution needs a separate key and
   analyst-visible ambiguity.
3. Project 3 calls forecast periods `estimate`; Project 4 currently calls the axis
   historical/forecast. An adapter must map this explicitly.
4. Project 3 market metrics use timestamps because share prices move intraday. Project 4 lifecycle,
   ownership, and most reported deal facts use dates, while evidence retrieval uses aware
   timestamps. Conversion rules must not discard meaningful time information.
5. Project 3 enterprise value is a current-market bridge. Transaction EV may be disclosed,
   calculated from negotiated equity consideration, or ambiguous. Its bridge policy must never
   reuse market capitalization as if it were purchase price.
6. Currency/unit code can be promoted to `shared/` only after the two projects agree on names,
   serialization, backward compatibility, and ownership. M0 avoids a premature shared refactor.

## Dependency decision

Project 4 has no runtime dependency on Projects 1–3 in M0. Later adapters should be optional at the
composition layer so core models and offline tests remain usable without installing every project.
