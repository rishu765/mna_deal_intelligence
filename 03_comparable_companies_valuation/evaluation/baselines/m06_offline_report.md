# Project 3 M6 evaluation: p03-m06-public-safe-v1

- Generated: 2026-10-07T10:00:00+00:00
- Curated cases: 8
- Overall check status: PASS

| Subsystem | Result | Passed | Failed | Representative failure | Limitation |
| --- | --- | ---: | ---: | --- | --- |
| target_financial_profile | PASS | 6 | 0 | None in fixture baseline | Gold values cover controlled INR fixtures, not arbitrary issuer disclosures. |
| comparable_selection | PASS | 5 | 0 | None in fixture baseline | The five-company benchmark is illustrative and does not establish market-wide relevance. |
| market_financial_ingestion | PASS | 5 | 0 | None in fixture baseline | Provider behavior is evaluated with deterministic fixture failures, not live outages. |
| trading_multiples | PASS | 6 | 0 | None in fixture baseline | Exact arithmetic covers four V1 multiple definitions on controlled Decimal inputs. |
| peer_statistics | PASS | 2 | 0 | None in fixture baseline | Small peer counts make quartiles sensitive even when interpolation is exact. |
| implied_valuation | PASS | 4 | 0 | None in fixture baseline | Target fixture lacks EBIT/EPS/forward metrics, so those peer sets do not imply ranges. |
| ai_explanation | PASS | 5 | 0 | None in fixture baseline | The offline explanation fixture tests grounding rules, not open-ended prose quality. |

## Limitations

- Eight synthetic cases and deterministic fixtures are a regression benchmark, not production-grade validation.
- No licensed live market-data or consensus-estimate provider is evaluated.
- The explanation rubric checks the offline structured provider; a live LLM judge is optional and not part of the correctness baseline.
