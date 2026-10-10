"""Capability registry for concrete specialist adapters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ma_deal_intelligence.adapters import (
    Project1Adapter,
    Project2Adapter,
    Project3Adapter,
    Project4Adapter,
    Project5Adapter,
)
from ma_deal_intelligence.adapters.base import BaseAdapter
from ma_deal_intelligence.contracts import HealthStatus, ProjectCapability
from ma_deal_intelligence.evidence import ProjectId


class CapabilityAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    REQUIRES_INPUT = "requires_input"
    UNSUPPORTED = "unsupported"


class DuplicateCapabilityError(ValueError):
    """Raised when two adapters claim the same capability ID."""


@dataclass(frozen=True, slots=True)
class CapabilityStatus:
    capability: ProjectCapability
    availability: CapabilityAvailability
    missing_inputs: tuple[str, ...] = ()
    message: str | None = None


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, ProjectCapability] = {}
        self._adapters: dict[str, BaseAdapter[Any, Any, Any]] = {}

    def register(self, adapter: BaseAdapter[Any, Any, Any]) -> None:
        for capability in adapter.capability_metadata():
            key = str(capability.capability_id)
            if key in self._capabilities:
                raise DuplicateCapabilityError(f"duplicate capability ID: {key}")
            self._capabilities[key] = capability
            self._adapters[key] = adapter

    def capability(self, capability_id: str) -> ProjectCapability:
        try:
            return self._capabilities[capability_id]
        except KeyError as exc:
            raise KeyError(f"unknown capability: {capability_id}") from exc

    def adapter(self, capability_id: str) -> BaseAdapter[Any, Any, Any]:
        self.capability(capability_id)
        return self._adapters[capability_id]

    def all(self) -> tuple[ProjectCapability, ...]:
        return tuple(self._capabilities.values())

    def for_project(self, project_id: ProjectId) -> tuple[ProjectCapability, ...]:
        return tuple(item for item in self.all() if item.project_id is project_id)

    def requiring(self, input_name: str) -> tuple[ProjectCapability, ...]:
        return tuple(item for item in self.all() if input_name in item.required_inputs)

    def without_documents(self) -> tuple[ProjectCapability, ...]:
        return tuple(item for item in self.all() if "documents" not in item.required_inputs)

    def health(self, capability_id: str) -> HealthStatus:
        return self.adapter(capability_id).health_check()

    def status(
        self, capability_id: str, available_inputs: frozenset[str] = frozenset()
    ) -> CapabilityStatus:
        if capability_id not in self._capabilities:
            placeholder = ProjectCapability(  # unreachable metadata for a useful typed result
                capability_id,
                ProjectId.PROJECT_6,
                capability_id,
                "Unregistered capability",
                _UNKNOWN_SCHEMA,
                _UNKNOWN_SCHEMA,
            )
            return CapabilityStatus(
                placeholder,
                CapabilityAvailability.UNSUPPORTED,
                message="capability is not registered",
            )
        capability = self._capabilities[capability_id]
        health = self.health(capability_id)
        if not health.healthy:
            return CapabilityStatus(
                capability, CapabilityAvailability.UNAVAILABLE, message=health.message
            )
        missing = tuple(item for item in capability.required_inputs if item not in available_inputs)
        if missing:
            return CapabilityStatus(
                capability,
                CapabilityAvailability.REQUIRES_INPUT,
                missing,
                "required inputs are missing",
            )
        if health.message and "degraded" in health.message.lower():
            return CapabilityStatus(
                capability, CapabilityAvailability.DEGRADED, message=health.message
            )
        return CapabilityStatus(
            capability, CapabilityAvailability.AVAILABLE, message=health.message
        )


from ma_deal_intelligence.contracts import SchemaReference  # noqa: E402

_UNKNOWN_SCHEMA = SchemaReference("unregistered", "Unknown", "0")


def default_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    for adapter in (
        Project1Adapter(),
        Project2Adapter(),
        Project3Adapter(),
        Project4Adapter(),
        Project5Adapter(),
    ):
        registry.register(adapter)
    return registry
