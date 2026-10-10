"""Structured, offline-first M&A intent classification."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from ma_deal_intelligence.requests import UserDealRequest


class DealIntent(StrEnum):
    COMPANY_RESEARCH = "company_research"
    FIND_TARGETS = "find_targets"
    SCREEN_TARGETS = "screen_targets"
    VALUE_TARGET = "value_target"
    RUN_TRADING_COMPS = "run_trading_comps"
    RUN_PRECEDENTS = "run_precedents"
    RUN_DUE_DILIGENCE = "run_due_diligence"
    EVALUATE_ACQUISITION = "evaluate_acquisition"
    COMPARE_VALUATION_METHODS = "compare_valuation_methods"
    INVESTIGATE_RISK = "investigate_risk"
    FULL_DEAL_ANALYSIS = "full_deal_analysis"


@dataclass(frozen=True, slots=True)
class ExtractedEntity:
    role: str
    name: str


@dataclass(frozen=True, slots=True)
class IntentClassification:
    primary_intent: DealIntent | None
    secondary_intents: tuple[DealIntent, ...] = ()
    extracted_entities: tuple[ExtractedEntity, ...] = ()
    extracted_constraints: tuple[tuple[str, str], ...] = ()
    requested_outputs: tuple[str, ...] = ()
    ambiguous: bool = False
    warnings: tuple[str, ...] = ()
    classifier: str = "rules"

    @property
    def intents(self) -> tuple[DealIntent, ...]:
        if self.primary_intent is None:
            return self.secondary_intents
        return (self.primary_intent, *self.secondary_intents)


class IntentModel(Protocol):
    def classify(self, request: UserDealRequest) -> IntentClassification: ...


_RULES: tuple[tuple[DealIntent, tuple[str, ...]], ...] = (
    (DealIntent.FULL_DEAL_ANALYSIS, (r"\bfull deal analysis\b", r"\bcomplete deal review\b")),
    (
        DealIntent.COMPARE_VALUATION_METHODS,
        (r"\bcompare\b.*\b(comps?|comparables?)\b.*\bprecedents?\b",),
    ),
    (
        DealIntent.EVALUATE_ACQUISITION,
        (r"\bshould (?:we|i) acquire\b", r"\bevaluate (?:the )?acquisition\b"),
    ),
    (DealIntent.RUN_DUE_DILIGENCE, (r"\bdue diligence\b", r"\bvdr\b", r"\bred flags?\b")),
    (
        DealIntent.RUN_PRECEDENTS,
        (r"\bprecedent transactions?\b", r"\bhistorically paid\b", r"\bprevious deals?\b"),
    ),
    (
        DealIntent.RUN_TRADING_COMPS,
        (r"\btrading comps?\b", r"\bcomparable compan(?:y|ies)\b"),
    ),
    (DealIntent.SCREEN_TARGETS, (r"\bscreen (?:the )?targets?\b", r"\brank (?:the )?targets?\b")),
    (DealIntent.FIND_TARGETS, (r"\bfind\b.*\btargets?\b", r"\bsource\b.*\btargets?\b")),
    (DealIntent.INVESTIGATE_RISK, (r"\binvestigate\b.*\brisks?\b", r"\brisk review\b")),
    (DealIntent.COMPANY_RESEARCH, (r"\bresearch\b", r"\bcompany intelligence\b")),
    (DealIntent.VALUE_TARGET, (r"\bvalue\b", r"\bvaluation\b")),
)


class IntentClassifier:
    def __init__(self, model: IntentModel | None = None) -> None:
        self._model = model

    def classify(self, request: UserDealRequest) -> IntentClassification:
        query = request.user_query.strip()
        lowered = query.lower()
        matches: list[DealIntent] = []
        for intent, patterns in _RULES:
            if any(re.search(pattern, lowered) for pattern in patterns):
                matches.append(intent)

        # Specific valuation methods subsume generic valuation wording.
        if DealIntent.COMPARE_VALUATION_METHODS in matches:
            matches = [
                item
                for item in matches
                if item not in {DealIntent.RUN_TRADING_COMPS, DealIntent.VALUE_TARGET}
            ]
        elif DealIntent.RUN_TRADING_COMPS in matches and DealIntent.VALUE_TARGET in matches:
            matches.remove(DealIntent.VALUE_TARGET)

        matches = list(dict.fromkeys(matches))
        if not matches and self._model is not None:
            result = self._model.classify(request)
            if any(not isinstance(item, DealIntent) for item in result.intents):
                raise ValueError("intent model returned an unsupported intent")
            return result

        entities = self._entities(request, query)
        constraints = self._constraints(lowered)
        if not matches:
            return IntentClassification(
                None,
                extracted_entities=entities,
                extracted_constraints=constraints,
                ambiguous=True,
                warnings=("No supported M&A intent could be determined deterministically.",),
            )
        return IntentClassification(
            matches[0],
            tuple(matches[1:]),
            entities,
            constraints,
            tuple(item.value for item in matches),
        )

    @staticmethod
    def _entities(request: UserDealRequest, query: str) -> tuple[ExtractedEntity, ...]:
        entities: list[ExtractedEntity] = []
        if request.target is not None:
            entities.append(
                ExtractedEntity(
                    "target",
                    request.target.display_name
                    or request.target.legal_name
                    or request.target.canonical_entity_id,
                )
            )
        if request.buyer is not None:
            entities.append(
                ExtractedEntity(
                    "buyer",
                    request.buyer.display_name
                    or request.buyer.legal_name
                    or request.buyer.canonical_entity_id,
                )
            )
        if request.target is None:
            match = re.search(
                r"(?:for|of|acquire|acquisition of)\s+([A-Z][\w.-]*(?:\s+[A-Z][\w.-]*){0,3})",
                query,
            )
            if match:
                entities.append(ExtractedEntity("target", match.group(1).strip(" .?!")))
        return tuple(entities)

    @staticmethod
    def _constraints(query: str) -> tuple[tuple[str, str], ...]:
        values: list[tuple[str, str]] = []
        for geography in ("india", "united kingdom", "uk", "united states", "us", "europe"):
            if re.search(rf"\b{re.escape(geography)}\b", query):
                values.append(("geography", geography.title()))
        for sector in ("b2b fintech", "fintech", "b2b saas", "saas", "software"):
            if re.search(rf"\b{re.escape(sector)}\b", query):
                values.append(("sector", sector.upper() if sector == "saas" else sector.title()))
                break
        return tuple(values)
