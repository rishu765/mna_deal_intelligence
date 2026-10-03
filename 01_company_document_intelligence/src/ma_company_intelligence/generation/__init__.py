"""Public text-generation interfaces and OpenAI adapter."""

from ma_company_intelligence.generation.base import (
    GenerationOutput,
    GenerationRequest,
    Generator,
)
from ma_company_intelligence.generation.config import GenerationSettings, ReasoningEffort
from ma_company_intelligence.generation.errors import (
    GenerationConfigurationError,
    GenerationError,
    GenerationProviderError,
    GenerationResponseError,
)
from ma_company_intelligence.generation.openai_provider import OpenAIGenerator
from ma_company_intelligence.generation.research import (
    GeneratedFinancialMetric,
    GeneratedResearchItem,
    GeneratedResearchSection,
    ResearchGenerationOutput,
    ResearchGenerator,
)

__all__ = [
    "GenerationConfigurationError",
    "GenerationError",
    "GenerationOutput",
    "GenerationProviderError",
    "GenerationRequest",
    "GenerationResponseError",
    "GenerationSettings",
    "Generator",
    "GeneratedFinancialMetric",
    "GeneratedResearchItem",
    "GeneratedResearchSection",
    "OpenAIGenerator",
    "ResearchGenerationOutput",
    "ResearchGenerator",
    "ReasoningEffort",
]
