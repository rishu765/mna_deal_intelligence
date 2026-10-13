# Portfolio Evaluation Summary

No global accuracy score is calculated because retrieval, ranking, finance, orchestration, and
diligence metrics are not interchangeable.

| System | Dataset / mode | Metric or gate | Latest validated result | Limitation |
| --- | --- | --- | --- | --- |
| P1 | 14-case synthetic corpus | Evidence quality gate | Passed | Known citation/unanswerable failures remain; limited real documents |
| P2 | Five synthetic theses | Top-k, pairwise, repeatability | `0.9`, `0.6667`, `1.0` | Two payflow/ledgerbridge ordering failures; synthetic companies |
| P3 | Eight offline cases | Arithmetic, normalization, ranges, failure behavior | Passed | Fixture peers and market data; no live FX/provider |
| P4 | Synthetic subsystem and ten scenarios | Retrieval, extraction, selection, valuation, workflow | Passed | Tiny fixture corpus and selection policy |
| P4 public case | IBM/HashiCorp source snapshot | EV/revenue reproduction | Two tests passed; `10.976x` | One transaction; denominator not calendarized |
| P5 | 14 synthetic scenarios | Finance, specialists, conflicts, HITL, report | 14/14 passed | Synthetic VDR and bounded workstreams |
| P6 | 18 synthetic scenarios | Routing, planning, adapters, graph, synthesis | 18/18 passed | Predominantly fixture-backed |
| Cross-project | Native-local execution | Run-derived specialist observations | 5/5 passed | Specialist fixtures are not one compatible deal |
| Contracts | Native-local integration tests | Schema/evidence/basis/mode preservation | 8 passed | No live external provider |

## Reproduction

Each project exposes its evaluation command in its README. The final code-quality baseline is
`pytest`, `ruff check`, `ruff format --check`, and strict `mypy` from each project directory. The
portfolio workflow installs all six projects under `constraints/portfolio-python311.txt` and runs
the native-local contract file.

Model-dependent judgment is optional and excluded from deterministic CI. Results should be quoted
with their dataset and mode; for example, “0.9 top-k inclusion on ten synthetic labels,” never
“90% accurate at target screening.”
