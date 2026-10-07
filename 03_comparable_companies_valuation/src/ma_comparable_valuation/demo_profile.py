"""Offline M1 demonstration of source observations becoming a normalized profile."""

from __future__ import annotations

import json
from pathlib import Path

from ma_comparable_valuation.fixtures import FixtureTargetProfileProvider


def main() -> None:
    fixture_path = Path(__file__).resolve().parents[2] / "data" / "targetco_profile.json"
    provider = FixtureTargetProfileProvider(fixture_path)
    target, observations = provider.load()
    profile = provider.get_target_profile(target)
    output = {
        "target": target.identity.name,
        "source_observations": [
            {
                "id": item.observation_id,
                "name": item.raw_metric_name,
                "value": str(item.value),
                "currency": item.currency,
                "unit": item.unit,
                "period": None if item.period is None else item.period.label,
                "evidence_ids": [evidence.evidence_id for evidence in item.evidence],
            }
            for item in observations
        ],
        "normalized_financial_metrics": [
            {
                "id": item.metric_id,
                "name": item.name.value,
                "value": str(item.value),
                "currency": item.currency,
                "unit": item.unit.value,
                "period": item.period.label,
                "basis": item.basis.value,
                "evidence_ids": [evidence.evidence_id for evidence in item.evidence],
            }
            for item in profile.metrics
        ],
        "capital_structure": [
            {
                "id": item.metric_id,
                "name": item.kind.value,
                "value": str(item.value),
                "currency": item.currency,
                "unit": item.unit.value,
                "as_of": item.as_of.isoformat(),
                "share_basis": None if item.share_basis is None else item.share_basis.value,
                "evidence_ids": [evidence.evidence_id for evidence in item.evidence],
            }
            for item in (
                () if profile.capital_structure is None else profile.capital_structure.components
            )
        ],
        "completeness": (
            None
            if profile.completeness is None
            else {
                "status": profile.completeness.status.value,
                "present": list(profile.completeness.present),
                "missing": list(profile.completeness.missing),
            }
        ),
        "conflicts": [item.reason for item in profile.conflicts],
        "issues": [item.message for item in profile.issues],
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
