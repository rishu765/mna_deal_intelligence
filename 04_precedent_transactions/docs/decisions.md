# M0 architecture decisions

## Keep Project 4 independently packaged

Earlier projects contain useful semantics but no deliberately versioned cross-project library.
M0 mirrors stable concepts and documents mappings instead of importing private modules. A shared
package is deferred until at least two consumers prove an exact common contract.

## Model facts as observations

Deal values and ownership facts may be undisclosed, amended, estimated, or disputed. M0 stores
multiple source-backed observations and categorical verification status rather than one allegedly
canonical scalar. Unknown values use `None`.

## Keep valuation measures separate

Headline value, equity purchase price, transaction enterprise value, and per-share offer price are
different measures. The model cannot silently substitute one for another. Independently calculated
values require assumptions.

## Use immutable dataclasses and exact decimals

Frozen, slotted dataclasses match repository conventions and reduce accidental mutation. Financial
values use `Decimal`. Schema-versioned serialization preserves exact types.

## Defer providers and executable orchestration

M0 has no concrete discovery/retrieval request contract and no need for a provider protocol.
Protocols arrive with M1/2 integrations. LangGraph execution, retry code, checkpoint stores, and
human interrupts arrive in M6/7; M0 supplies only the state contract and architecture.

## Keep configuration conservative

M0 settings explicitly disable automatic FX conversion and partial-stake gross-up. Future policy
changes require visible code, tests, assumptions, and traces.
