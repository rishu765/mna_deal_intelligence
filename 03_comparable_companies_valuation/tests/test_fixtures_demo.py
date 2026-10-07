from pathlib import Path

import pytest

from ma_comparable_valuation import ProfileCompletenessStatus
from ma_comparable_valuation.demo_profile import main
from ma_comparable_valuation.fixtures import FixtureTargetProfileProvider

FIXTURE = Path(__file__).resolve().parents[1] / "data" / "targetco_profile.json"


def test_fixture_builds_complete_offline_profile() -> None:
    provider = FixtureTargetProfileProvider(FIXTURE)
    target, observations = provider.load()

    profile = provider.get_target_profile(target)

    assert len(observations) == 7
    assert len(profile.metrics) == 4
    assert profile.capital_structure is not None
    assert len(profile.capital_structure.components) == 3
    assert profile.completeness is not None
    assert profile.completeness.status is ProfileCompletenessStatus.COMPLETE


def test_demo_shows_raw_normalized_completeness_and_evidence(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main()
    output = capsys.readouterr().out

    assert '"source_observations"' in output
    assert '"normalized_financial_metrics"' in output
    assert '"completeness"' in output
    assert '"evidence_ids"' in output
    assert "trading_multiple" not in output
