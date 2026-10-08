"""Configuration that is meaningful at M0 without implying live providers."""

from dataclasses import dataclass

from ma_precedent_transactions.serialization import SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    schema_version: int = SCHEMA_VERSION
    require_timezone_aware_retrieval: bool = True
    allow_automatic_fx_conversion: bool = False
    allow_partial_stake_gross_up: bool = False
