"""Structured evidence-backed company research."""

from ma_company_intelligence.research.context import (
    RESEARCH_CATEGORIES,
    ResearchCategory,
    ResearchEvidenceCollector,
    ResearchEvidenceContext,
)
from ma_company_intelligence.research.errors import InvalidResearchRequestError, ResearchError
from ma_company_intelligence.research.service import CompanyResearchService

__all__ = [
    "CompanyResearchService",
    "InvalidResearchRequestError",
    "RESEARCH_CATEGORIES",
    "ResearchCategory",
    "ResearchError",
    "ResearchEvidenceCollector",
    "ResearchEvidenceContext",
]
