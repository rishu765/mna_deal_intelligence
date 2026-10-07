"""Credential-free JSON fixture provider for target financial profiles."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ma_comparable_valuation.domain import (
    FinancialObservation,
    TargetCompany,
    TargetFinancialProfile,
)
from ma_comparable_valuation.errors import MalformedFixtureError
from ma_comparable_valuation.profile_service import TargetFinancialProfileService
from ma_comparable_valuation.serialization import (
    financial_observation_from_dict,
    target_company_from_dict,
)


@dataclass(frozen=True, slots=True)
class FixtureTargetProfileProvider:
    fixture_path: Path
    service: TargetFinancialProfileService = TargetFinancialProfileService()

    @property
    def provider_name(self) -> str:
        return "structured_fixture"

    def get_target_profile(self, target: TargetCompany) -> TargetFinancialProfile:
        fixture_target, observations = self.load()
        if fixture_target.identity.company_id != target.identity.company_id:
            raise MalformedFixtureError("fixture target does not match requested target")
        return self.service.build(fixture_target, observations)

    def load(self) -> tuple[TargetCompany, tuple[FinancialObservation, ...]]:
        try:
            raw = json.loads(self.fixture_path.read_text(encoding="utf-8"))
            data = _mapping(raw, "fixture")
            target = target_company_from_dict(_mapping(data["target"], "target"))
            observations = tuple(
                financial_observation_from_dict(_mapping(item, "observation"))
                for item in _sequence(data["observations"], "observations")
            )
            return target, observations
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise MalformedFixtureError(
                f"Unable to load target profile fixture: {error}"
            ) from error


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{name} must be an object with string keys")
    return value


def _sequence(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value
