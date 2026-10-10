from datetime import date

from ma_deal_intelligence.requests import FinalDealIntelligence, SynthesisSection


def test_final_synthesis_contract_is_structure_only_in_m0() -> None:
    sections = tuple(
        SynthesisSection(f"section:{index}", title, None)
        for index, title in enumerate(
            (
                "Deal overview",
                "Strategic rationale",
                "Company intelligence",
                "Target screening",
                "Trading comps",
                "Precedents",
                "Due diligence",
                "Reconciled metrics",
                "Valuation summary",
                "Key risks",
                "Analyst decisions",
                "Open questions",
                "Limitations",
            )
        )
    )
    contract = FinalDealIntelligence(
        synthesis_id="synthesis:1",
        deal_id="deal:1",
        as_of_date=date(2026, 1, 1),
        deal_overview=sections[0],
        strategic_rationale=sections[1],
        company_intelligence=sections[2],
        target_screening=sections[3],
        trading_comps=sections[4],
        precedents=sections[5],
        due_diligence=sections[6],
        reconciled_metrics=sections[7],
        valuation_summary=sections[8],
        key_risks=sections[9],
        analyst_decisions=sections[10],
        open_questions=sections[11],
        limitations=sections[12],
        evidence_refs=(),
        assumption_ids=(),
    )
    assert len(contract.sections) == 13

    assert all(section.content is None for section in contract.sections)
