# Finance Modeling Summary

This file maps implemented finance concepts to their owning modules. It is an implementation map,
not a finance textbook.

| Concept | Implementation | Project |
| --- | --- | --- |
| Enterprise versus equity value | Debt/cash bridge, explicit value basis, traced results | P3 `valuation.py`; P4 precedent models/valuation |
| Trading comps | Peer eligibility, normalized market/financial data, EV/revenue and EV/EBITDA, statistics, implied ranges | P3 selection, multiples, statistics, valuation |
| Precedent transactions | Control/status/value-basis filters, transaction multiples, ranges | P4 `precedent/` |
| Reported versus adjusted EBITDA | Explicit metric basis and bridge inputs | P5 `financial/qoe.py`; P6 reconciliation |
| Quality of earnings | Supported/rejected adjustments, recurrence and evidence | P5 financial services |
| Working capital | Component classification and period-aware NWC | P5 `financial/analytics.py` |
| NWC peg | Historical basis checks and deterministic peg calculation | P5 analytics |
| Net debt | Debt, cash, restricted cash, and debt-like classifications | P5 `financial/net_debt.py` |
| Customer concentration | Deterministic revenue concentration calculations | P5 financial analytics |
| Valuation reconciliation | Method ranges retained separately; no automatic blending | P6 reconciliation/finance |
| Diligence impact | Links adjusted EBITDA, net debt, and findings to affected valuation inputs | P6 reconciliation/synthesis |

Financial values preserve currency, unit, period, estimate status, reported/adjusted basis,
measurement date, and evidence where the specialist exposes them. Cross-currency outputs are not
converted implicitly. Unknown values remain unknown.

The deepest later-study areas are: enterprise-to-equity bridges, LTM/NTM calendarization, peer and
precedent selection judgment, defensible QoE adjustments, normalized working capital and peg
negotiation, debt-like items, and how diligence changes price mechanics without double counting.
