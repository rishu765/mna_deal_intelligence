from __future__ import annotations

from ma_precedent_transactions.precedent import (
    LangChainValuationExplanationProvider,
    PrecedentAnalysisService,
    precedent_fixture_inputs,
)


class _Runnable:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def invoke(self, input: object) -> object:
        assert input
        return self.payload


class _Model:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.schema: object | None = None

    def with_structured_output(self, schema: object) -> _Runnable:
        self.schema = schema
        return _Runnable(self.payload)


def _payload(evidence_id: str) -> dict[str, object]:
    return {
        "precedent_set_assessment": "The set is usable with a small-sample caveat.",
        "strongest_precedents": ["txn-cash"],
        "weakest_precedents": ["txn-outlier"],
        "key_valuation_drivers": ["Target EBITDA and observed transaction multiples."],
        "outlier_commentary": ["The high multiple remains visible and flagged."],
        "recommended_multiple_focus": ["ev_revenue"],
        "valuation_caveats": ["Control pricing may differ from trading comparables."],
        "evidence_ids": [evidence_id],
    }


def test_langchain_reasoning_adapter_uses_structured_output_and_known_evidence() -> None:
    comparable, target, transactions = precedent_fixture_inputs()
    base = PrecedentAnalysisService().analyze(comparable, target, transactions)
    evidence_id = base.multiple_sets[0].multiples[0].evidence[0].evidence_id
    model = _Model(_payload(evidence_id))
    output = PrecedentAnalysisService().analyze(
        comparable,
        target,
        transactions,
        explanation_provider=LangChainValuationExplanationProvider(model),
    )

    assert model.schema is not None
    assert output.explanation is not None
    assert output.explanation.evidence_ids == (evidence_id,)


def test_unknown_ai_evidence_is_rejected_and_failure_isolated() -> None:
    comparable, target, transactions = precedent_fixture_inputs()
    provider = LangChainValuationExplanationProvider(_Model(_payload("fabricated-evidence")))
    output = PrecedentAnalysisService().analyze(
        comparable, target, transactions, explanation_provider=provider
    )

    assert output.ranges
    assert output.explanation is not None
    assert output.explanation.status.value == "unavailable"
    assert "ValuationError" in output.explanation.valuation_caveats[0]
