# Comparable Companies & Valuation Copilot

Project 3 is the valuation layer of the AI × M&A portfolio. Its intended question is:

> What is this company worth relative to relevant publicly traded comparable companies, and
> why?

The primary method is **Comparable Companies Analysis (trading comps)**. Public-company
enterprise-value and equity-value multiples will eventually be applied to compatible target
metrics to produce an evidence-backed valuation range. This is educational analytical software,
not investment advice.

## Milestone status

- **M0 — Architecture + valuation workflow design: ✅ complete**
- M1 — Target financial profile + normalized metrics: **NOT IMPLEMENTED**
- M2/3 — Comparable selection + market/financial ingestion: **NOT IMPLEMENTED**
- M4/5 — Trading multiples + valuation range + AI-assisted reasoning: **NOT IMPLEMENTED**
- M6 — Evaluation + API/demo + V1 polish: **NOT IMPLEMENTED**

M0 supplies architecture, provider-neutral domain contracts, provider interfaces, and contract
tests. It does **not** value a company.

## What comparable companies analysis is

Trading comps compare a target with relevant listed businesses using consistently defined
market and financial measures. Typical future multiples are `EV / Revenue`, `EV / EBITDA`,
`EV / EBIT`, and `P / E`. Peer statistics such as the 25th percentile, median, and 75th
percentile become valuation anchors; the target metric and capital structure then translate
those anchors into implied enterprise value, equity value, and—where applicable—per-share value.

The method is a range, not a single magically precise answer. Peer selection, periods,
accounting adjustments, capital structure, market timing, and outliers all affect the result.

## Planned workflow

```mermaid
flowchart TD
    Target[Target Company] --> Profile[Target Financial Profile]
    Profile --> Universe[Comparable Universe]
    Universe --> Selection[Comparable Selection]
    Selection --> Collection[Financial + Market Data Collection]
    Collection --> Normalize[Normalization]
    Normalize --> Multiples[Trading Multiples]
    Multiples --> Statistics[Peer Statistics]
    Statistics --> Implied[Implied Valuation]
    Implied --> Range[Valuation Range]
    Range --> Interpretation[AI-Assisted Interpretation]
    Interpretation --> Output[Evidence-Backed Output]
```

The complete stage contracts, responsibilities, provenance needs, and failure modes are in
[docs/architecture.md](docs/architecture.md). The finance conventions are in
[docs/valuation_methodology.md](docs/valuation_methodology.md).

## Deterministic finance, assisted reasoning

```mermaid
flowchart LR
    subgraph AI[AI-assisted research / reasoning]
        Descriptions[Business-description interpretation]
        Similarity[Strategic similarity]
        Issues[Potential normalization issues]
        Narrative[Grounded analyst narrative]
    end
    subgraph Deterministic[Deterministic finance engine]
        Validation[Compatibility validation]
        EV[Equity / enterprise value bridge]
        Multiple[Multiple calculations]
        Stats[Peer statistics]
        Value[Implied values and ranges]
    end
    Evidence[(Evidence catalog)] --> AI
    Evidence --> Deterministic
    AI --> Review[Auditable recommendation / explanation]
    Deterministic --> Output[Authoritative numerical output]
    Review --> Output
```

An LLM may later interpret descriptions, explain inclusion or exclusion, surface possible
adjustments, and narrate deterministic results. It may not invent inputs, perform authoritative
arithmetic, override formulas, or supply an untraceable valuation.

## Project relationships

```mermaid
flowchart LR
    P1[Project 1\nCompany Document Intelligence] -->|cited financial evidence\nthrough a future adapter| P3[Project 3\nComparable Companies Valuation]
    P2[Project 2\nTarget Screening & Sourcing] -->|selected candidate\nthrough a future adapter| P3
    Direct[Direct user/provider input] --> P3
```

Project 1 can support filing ingestion, retrieval, extraction, and citations, but it does not
yet guarantee every valuation metric Project 3 requires. Project 2 can pass a selected target,
but Project 3 remains independently usable. No Project 1 or Project 2 private modules are
imported.

## Scope boundary

Project 3 is designed for public trading comps. It is not a DCF, precedent-transactions,
accretion/dilution, LBO, purchase-price-allocation, merger-model, or due-diligence system.
Those methods are not hidden inside the roadmap.

## Development

```powershell
cd 03_comparable_companies_valuation
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest
```

No API keys or network access are required. M0 has no runtime dependencies outside the Python
standard library.

## Limitations

- No target extraction, normalization engine, live provider, peer-selection engine, multiple
  calculator, statistics engine, valuation range, narrative generator, API, UI, or deployment.
- Contracts prevent silent loss of key semantics; they do not prove that source data is correct.
- Calendarization, FX conversion, capital-structure policy, and accounting adjustments are
  designed but deliberately deferred.
- The initial enums cover the planned V1 methods and can be extended through reviewed schema
  changes rather than untyped strings.

