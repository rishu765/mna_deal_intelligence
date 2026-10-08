"""Structured extraction, normalization, and verification public API."""

from ma_precedent_transactions.extraction.evaluation import (
    ExtractionBenchmarkResult,
    ExtractionGoldCase,
    load_extraction_benchmark,
    run_extraction_benchmark,
)
from ma_precedent_transactions.extraction.models import (
    CapitalFactObservation,
    ConsiderationObservation,
    DateObservation,
    DealDateKind,
    ExtractionBatch,
    ExtractionTrace,
    FactConflict,
    FieldVerification,
    FinancialFactObservation,
    OwnershipFactObservation,
    PartyObservation,
    PartyRole,
    RawMoney,
    RevisionKind,
    StatusObservation,
    StructureObservation,
    ValuationFactObservation,
    VerificationStatus,
    VerifiedTransactionRecord,
)
from ma_precedent_transactions.extraction.normalization import (
    FinancialNormalizationService,
    NormalizationDecision,
    convert_unit,
    derive_enterprise_value,
    normalize_money,
    normalize_period,
    parse_decimal,
    parse_unit,
)
from ma_precedent_transactions.extraction.pipeline import retrieve_extraction_context
from ma_precedent_transactions.extraction.ports import (
    ExtractionRequest,
    StructuredTransactionExtractor,
)
from ma_precedent_transactions.extraction.providers import (
    FixtureStructuredExtractor,
    LangChainStructuredExtractor,
)
from ma_precedent_transactions.extraction.schema import (
    EXTRACTION_JSON_SCHEMA,
    load_extraction_fixture,
    parse_extraction_payload,
)
from ma_precedent_transactions.extraction.service import (
    ExtractionOutcome,
    StructuredTransactionService,
)
from ma_precedent_transactions.extraction.verification import (
    SourcePriorityPolicy,
    TransactionVerificationService,
    VerificationResult,
)

__all__ = [
    "EXTRACTION_JSON_SCHEMA",
    "CapitalFactObservation",
    "ConsiderationObservation",
    "DateObservation",
    "DealDateKind",
    "ExtractionBatch",
    "ExtractionBenchmarkResult",
    "ExtractionGoldCase",
    "ExtractionOutcome",
    "ExtractionRequest",
    "ExtractionTrace",
    "FactConflict",
    "FieldVerification",
    "FinancialFactObservation",
    "FinancialNormalizationService",
    "FixtureStructuredExtractor",
    "LangChainStructuredExtractor",
    "NormalizationDecision",
    "OwnershipFactObservation",
    "PartyObservation",
    "PartyRole",
    "RawMoney",
    "RevisionKind",
    "SourcePriorityPolicy",
    "StatusObservation",
    "StructureObservation",
    "StructuredTransactionExtractor",
    "StructuredTransactionService",
    "TransactionVerificationService",
    "ValuationFactObservation",
    "VerificationResult",
    "VerificationStatus",
    "VerifiedTransactionRecord",
    "convert_unit",
    "derive_enterprise_value",
    "load_extraction_benchmark",
    "load_extraction_fixture",
    "normalize_money",
    "normalize_period",
    "parse_decimal",
    "parse_extraction_payload",
    "parse_unit",
    "retrieve_extraction_context",
    "run_extraction_benchmark",
]
