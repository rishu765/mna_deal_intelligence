import pytest

from ma_comparable_valuation.demo_valuation import main


def test_demo_runs_complete_offline_flow(capsys: pytest.CaptureFixture[str]) -> None:
    main()
    output = capsys.readouterr().out

    assert '"target_profile"' in output
    assert '"universe"' in output
    assert '"selection"' in output
    assert '"peer_set"' in output
    assert '"multiple_sets"' in output
    assert '"ranges"' in output
    assert '"implied_equity_value"' in output
    assert '"implied_per_share"' in output
    assert '"explanation"' in output
    assert '"not_meaningful"' in output
    assert '"missing_input"' in output
    assert '"mode": "offline_fixture"' in output
