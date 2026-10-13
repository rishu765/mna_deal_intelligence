# Demo Guide

Run commands from the project directory after `python -m pip install -e ".[dev]"` on Python 3.11.

| Project | Command | Data and mode | Demonstrates |
| --- | --- | --- | --- |
| P1 | `madi-create-demo-pdf`, then follow `docs/demo.md` | Copyright-safe synthetic PDF; offline or optional model provider | Ingestion, indexing, retrieval, citations, research |
| P2 | `mats-workflow-demo` | Synthetic discovery/enrichment providers; fixture-driven | Thesis, shortlist, ranking, checkpoint, approval |
| P3 | `python -m ma_comparable_valuation.demo_valuation` | Offline company/peer fixtures | Peer selection, multiples, ranges, EV/equity bridge |
| P4 | `python -m ma_precedent_transactions.demo_final` | Offline deal/doc fixtures | Retrieval, extraction, conflict review, precedents, ranges |
| P5 | `madd-agent-demo` | Synthetic Northstar VDR | Specialist diligence, finance, review/resume, report |
| P6 | `python demo_final.py` | Project 6 fixture mode | Routing, fan-out/fan-in, review, rerun, synthesis, evidence |

External network access is not required for these commands. P1 can optionally use configured
OpenAI embedding/generation providers, but the documented deterministic tests do not.

## Portfolio native-local proof

The native-local composition is exercised by the integration suite rather than presented as one
fictional unified deal:

```powershell
python -m pytest -q 06_mna_deal_intelligence_super_agent/tests/test_native_local_integration.py
```

It calls real P1–P5 code through Project 6 adapters. Inputs remain each specialist's offline
fixture and may describe different companies or currencies.

## Project 6 presentation sequence

`demo_final.py` prints:

1. the analyst request, classified intent, selected capabilities, and run status;
2. a valuation fan-out/fan-in with trading-comps and precedent ranges;
3. a full-deal graph run with an EBITDA conflict;
4. the analyst decision, approved specialist rerun, and resumed reconciliation;
5. final sections, assessment, citations, safe run metrics, and evaluation summary.

The command uses fixture mode and must be described that way in demonstrations. Native-local mode
proves adapter composition; it does not yet provide a single compatible P3/P4/P5 TargetCo case.

## APIs

Each README lists its local API command. APIs are unauthenticated, process-local demonstrations.
Bind them to `127.0.0.1`, do not expose them to untrusted networks, and do not load checkpoint
bytes from external sources.
