"""Concrete Project 1-5 adapters."""

from ma_deal_intelligence.adapters.base import AdapterMode, AdapterValidationError
from ma_deal_intelligence.adapters.project1 import Project1Adapter
from ma_deal_intelligence.adapters.project2 import Project2Adapter
from ma_deal_intelligence.adapters.project3 import Project3Adapter
from ma_deal_intelligence.adapters.project4 import Project4Adapter
from ma_deal_intelligence.adapters.project5 import Project5Adapter

__all__ = [
    "AdapterMode",
    "AdapterValidationError",
    "Project1Adapter",
    "Project2Adapter",
    "Project3Adapter",
    "Project4Adapter",
    "Project5Adapter",
]
