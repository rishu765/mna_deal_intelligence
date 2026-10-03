"""Public grounded RAG context and orchestration interfaces."""

from ma_company_intelligence.rag.context import (
    ContextBuilder,
    EvidenceContext,
    format_evidence_result,
)
from ma_company_intelligence.rag.errors import InvalidQuestionError, RAGError
from ma_company_intelligence.rag.service import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    GroundedRAGService,
)

__all__ = [
    "ContextBuilder",
    "EvidenceContext",
    "GroundedRAGService",
    "INSUFFICIENT_EVIDENCE_MESSAGE",
    "InvalidQuestionError",
    "RAGError",
    "format_evidence_result",
]
