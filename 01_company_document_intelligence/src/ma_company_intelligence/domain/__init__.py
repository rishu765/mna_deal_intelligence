"""Provider-neutral document and chunk models."""

from ma_company_intelligence.domain.answers import RAGAnswer
from ma_company_intelligence.domain.chunks import (
    ChunkedDocument,
    ChunkPageReference,
    DocumentChunk,
    DocumentMetadata,
)
from ma_company_intelligence.domain.citations import Citation
from ma_company_intelligence.domain.documents import (
    DocumentSource,
    ParsedDocument,
    ParsedPage,
    ParsingWarning,
    ParsingWarningCode,
    SourceProvenance,
)
from ma_company_intelligence.domain.research import (
    RESEARCH_SECTION_ORDER,
    CompanyResearchProfile,
    FinancialMetric,
    ResearchFact,
    ResearchObservation,
    ResearchSection,
    ResearchSectionKey,
)
from ma_company_intelligence.domain.retrieval import (
    RetrievalFilters,
    RetrievalResult,
    VectorSearchMatch,
)
from ma_company_intelligence.domain.vectors import EmbeddingVector, VectorRecord

__all__ = [
    "ChunkedDocument",
    "Citation",
    "CompanyResearchProfile",
    "ChunkPageReference",
    "DocumentChunk",
    "DocumentMetadata",
    "DocumentSource",
    "EmbeddingVector",
    "FinancialMetric",
    "ParsedDocument",
    "ParsedPage",
    "ParsingWarning",
    "ParsingWarningCode",
    "RetrievalFilters",
    "RetrievalResult",
    "RAGAnswer",
    "RESEARCH_SECTION_ORDER",
    "ResearchFact",
    "ResearchObservation",
    "ResearchSection",
    "ResearchSectionKey",
    "SourceProvenance",
    "VectorRecord",
    "VectorSearchMatch",
]
