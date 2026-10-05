"""M&A target screening and sourcing domain foundation."""

from ma_target_screening.domain import CandidateCompany, DiscoveryEvidence, ExternalIdentifier
from ma_target_screening.profile import CandidateProfile
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

__version__ = "0.3.0"
