# Acquisition thesis schema

## Purpose

An acquisition thesis translates an acquirer's intent into an inspectable specification before
candidate discovery begins. It combines business context with criteria that later milestones
can use for sourcing, enrichment, deterministic screening, and strategic-fit reasoning.

The M1 model is the structured source of truth. It supports incomplete theses because real
corporate-development work often starts before geography, budget, size, ownership, or exact
capabilities are settled.

## Top-level model

`AcquisitionThesis` contains:

- a stable `thesis_id`;
- `AcquirerIdentity` with name and optional country and industry;
- optional objective and strategic rationale;
- zero or more typed `ScreeningCriterion` values;
- optional original `source_text` for traceability;
- optional notes for unresolved assumptions.

Only the thesis ID and acquirer name are mandatory. An incomplete thesis remains valid rather
than silently inventing missing requirements.

## Criterion design

Every `ScreeningCriterion` has independent dimensions:

| Dimension | Purpose |
| --- | --- |
| `criterion_id` | Stable identifier used in later results and audit trails |
| `category` | Industry, revenue, profitability, geography, technology, strategic fit, etc. |
| `requirement` | `hard`, `soft`, or `exclusion` |
| `value_type` | Numeric, financial, categorical, boolean, geographic, semantic, or derived |
| `operator` | Typed comparison such as `between`, `in`, `is_true`, or `semantic_match` |
| `value` | Typed scalar, list, numeric range, or money range |
| `evaluation_method` | `deterministic` or `semantic` |
| `priority` / `weight` | Optional importance signal for later ranking |

This is intentionally not one untyped string and not a deep inheritance hierarchy. Requirement
consequence, value shape, and evaluation method are separate concerns.

## Hard, soft, and exclusion criteria

- **Hard:** failure may disqualify a candidate in M4. Example: FY2025 revenue of INR 100–500
  crore.
- **Soft:** failure reduces fit but does not automatically disqualify. Example: strong
  enterprise API infrastructure.
- **Exclusion:** matching the negative condition may disqualify. Example: consumer lending is
  more than 50 percent of the business.

M1 records these semantics. It does not evaluate candidates or calculate scores.

## Deterministic and semantic evaluation

Likely deterministic M4 criteria include revenue or employee ranges, founded year,
profitability flags, ownership categories, and exact geography or industry membership. Likely
semantic M5 criteria include strategic adjacency, API sophistication, product complementarity,
customer fit, proprietary technology, and distribution capability.

Semantic criteria use `semantic_match` and must explicitly declare `evaluation_method` as
`semantic`. All other M1 value types are currently deterministic. Later semantic results must
be structured, evidence-backed, and uncertainty-aware.

## Financial ranges

`MoneyAmount` retains:

- a decimal amount;
- a three-letter uppercase currency code;
- an explicit unit: unit, thousand, million, billion, lakh, or crore;
- an optional period: `FY####`, `CY####`, `LTM`, or `NTM`.

`MoneyRange` requires at least one bound. When both bounds exist, their currency, unit, and
period must match and the minimum cannot exceed the maximum. No foreign-exchange, inflation,
unit, or fiscal-period conversion occurs in M1. Later code must normalize explicitly before
comparison rather than silently comparing incompatible values.

`NumericRange` handles non-financial quantities such as employee count, founded year, or growth
rates while preserving optional unit and period labels.

## Validation and normalization

The model:

- collapses repeated whitespace in human-entered text;
- uppercases currency and supported financial-period labels;
- rejects empty ranges, inverted ranges, malformed currencies or periods, invalid
  operator/value combinations, invalid boolean combinations, duplicate list values, weights
  outside `(0, 1]`, and duplicate criterion IDs;
- detects the clear contradiction where the same geography is both a hard requirement and an
  exclusion.

It does not attempt deep semantic contradiction detection.

## Serialization

`to_dict`/`from_dict` and `to_json`/`from_json` provide a versioned, JSON-compatible boundary.
Decimals serialize as strings so values do not lose precision. Typed payload wrappers such as
`money_range`, `numeric_range`, `items`, and `boolean` make deserialization unambiguous.

Examples:

- [`fintech-payments.json`](../examples/fintech-payments.json)
- [`technology-ai-data.json`](../examples/technology-ai-data.json)
- [`partial-thesis.json`](../examples/partial-thesis.json)

## Future natural-language boundary

```text
User natural-language thesis
    -> future parser / structured extraction adapter
    -> AcquisitionThesis.from_dict(...)
    -> deterministic validation
    -> M2 discovery
```

A future parser may propose a structure, but it must not replace domain validation. Original
text can be retained in `source_text`. M1 deliberately includes no rule-based or LLM parser.

## Consumption by later milestones

- M2 uses relevant categories as discovery inputs without evaluating candidates.
- M3 enriches candidate profiles with the facts required by criteria.
- M4 evaluates deterministic hard constraints, exclusions, and measurable preferences.
- M5 evaluates evidence-backed semantic criteria and ranking importance.
- M6 coordinates the tested services and human review; it does not redefine thesis semantics.
