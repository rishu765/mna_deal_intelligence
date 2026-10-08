# Project 1–3 reuse and compatibility assessment

This assessment reflects the repository at Project 3 V1 and Project 4 M3. Project 4 remains
standalone; the optional PDF adapter resolves Project 1 dynamically only when installed.

## Reusable today through future adapters

### Project 1: company document intelligence

Useful capabilities already exist for PDF ingestion, parsed pages, provenance-aware chunks,
embedding/vector indexing, retrieval, citations, grounded RAG, structured research, evaluation,
and API hardening. Project 4 evidence includes compatible `document_id`, `chunk_id`, page, section,
text location, and excerpt fields.

`Project1PdfParserAdapter` now translates Project 1 parsed pages and warnings into Project 4
documents. Project 1's provenance, chunking, embedding, atomic-indexing, and cosine-retrieval
patterns were adapted. Its company/fiscal-year metadata and chunk/store types cannot directly
support transaction, acquirer, target, jurisdiction, and source-quality filters, so Project 4 owns
those contracts plus BM25 and hybrid fusion.

### Project 2: target screening and sourcing

Useful patterns already exist for provider-neutral discovery records, external identifiers,
evidence-backed entity profiles, deterministic hard filters, semantic judgments, result audit
trails, LangGraph typed state, conditional routing, bounded retries, checkpointing, and human
review.

Project 4 reused these service and failure-handling patterns in its fixture discovery and identity
resolver. Discovery concerns events and bids rather than only companies. Project 2's candidate
identity cannot uniquely represent competing bids, amended terms, repeated acquisitions, or stake
purchases. Reuse the patterns and later adapter boundaries, not the candidate model itself.

### Project 3: comparable companies and valuation

M3 adapts the following semantics locally; they may be promoted to `shared/` only
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

Project 4 has no required runtime dependency on Projects 1–3. The optional Project 1 PDF adapter is
resolved at execution time. The optional LangChain adapter accepts an injected model and adds no
dependency to offline extraction. Core models, ingestion, retrieval, extraction, verification,
tests, and demos work without installing every project.
