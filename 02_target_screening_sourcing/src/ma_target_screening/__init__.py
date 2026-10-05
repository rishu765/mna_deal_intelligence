"""M&A target screening and sourcing domain foundation."""

from ma_target_screening.domain import (
    CandidateCompany,
    CandidateProfile,
    DiscoveryEvidence,
    ExternalIdentifier,
)
from ma_target_screening.thesis import (
    AcquirerIdentity,
    AcquisitionThesis,
    CriterionCategory,
    CriterionOperator,
    CriterionPriority,
    CriterionRequirement,
    CriterionValueType,
    EvaluationMethod,
    FinancialUnit,
    MoneyAmount,
    MoneyRange,
    NumericRange,
    ScreeningCriterion,
)

__all__ = [
    "AcquisitionThesis",
    "AcquirerIdentity",
    "CandidateCompany",
    "CandidateProfile",
    "CriterionCategory",
    "CriterionOperator",
    "CriterionPriority",
    "CriterionRequirement",
    "CriterionValueType",
    "DiscoveryEvidence",
    "EvaluationMethod",
    "ExternalIdentifier",
    "FinancialUnit",
    "MoneyAmount",
    "MoneyRange",
    "NumericRange",
    "ScreeningCriterion",
]

__version__ = "0.1.0"
