import pytest

from ma_comparable_valuation.demo_valuation import main


def test_demo_runs_complete_offline_flow(capsys: pytest.CaptureFixture[str]) -> None:
    main()
    output = capsys.readouterr().out

    assert '"peer_equity_and_enterprise_values"' in output
    assert '"multiple_sets"' in output
    assert '"valuation_ranges"' in output
    assert '"mid_equity_value"' in output
    assert '"mid_per_share"' in output
    assert '"explanation"' in output
    assert '"not_meaningful"' in output
    assert '"missing_input"' in output
