"""Conservative preliminary identity resolution for discovered transactions."""

from __future__ import annotations

import re
from dataclasses import replace
from hashlib import sha256

from ma_precedent_transactions.discovery.models import (
    CandidateTransaction,
    IdentityResolutionDecision,
    IdentityResolutionResult,
    ResolutionDisposition,
)

_LEGAL_SUFFIX = re.compile(
    r"(?:,?\s+(?:holdings|inc\.?|llc|limited|ltd\.?|plc|corp\.?|corporation))+$",
    re.IGNORECASE,
)


class TransactionIdentityResolver:
    """Merge only strong matches and surface near-match ambiguity."""

    def resolve(self, candidates: tuple[CandidateTransaction, ...]) -> IdentityResolutionResult:
        groups: list[list[CandidateTransaction]] = []
        warnings: list[str] = []
        ambiguous_ids: set[str] = set()
        for candidate in candidates:
            match = next(
                (group for group in groups if self._same_transaction(group[0], candidate)), None
            )
            if match is None:
                near = next(
                    (group for group in groups if self._ambiguous_pair(group[0], candidate)),
                    None,
                )
                if near is not None:
                    ambiguous_ids.update((near[0].candidate_id, candidate.candidate_id))
                    warnings.append(
                        "Ambiguous transaction identity retained separately: "
                        f"{near[0].candidate_id} and {candidate.candidate_id}."
                    )
                groups.append([candidate])
            else:
                match.append(candidate)

        transactions: list[CandidateTransaction] = []
        decisions: list[IdentityResolutionDecision] = []
        for group in groups:
            merged = self._merge(group)
            transactions.append(merged)
            if len(group) > 1:
                disposition = ResolutionDisposition.MERGED
                rationale = "Matched external deal ID or acquirer/target/date/type fingerprint."
            elif group[0].candidate_id in ambiguous_ids:
                disposition = ResolutionDisposition.AMBIGUOUS
                rationale = "Near-match signals were insufficient for an automatic merge."
            else:
                disposition = ResolutionDisposition.UNIQUE
                rationale = "No duplicate candidate met the conservative merge threshold."
            decisions.append(
                IdentityResolutionDecision(
                    tuple(item.candidate_id for item in group),
                    (merged.candidate_id,),
                    disposition,
                    rationale,
                )
            )
        return IdentityResolutionResult(
            tuple(transactions),
            tuple(decisions),
            tuple(dict.fromkeys(warnings)),
        )

    @classmethod
    def _same_transaction(cls, left: CandidateTransaction, right: CandidateTransaction) -> bool:
        left_ids = {
            source.external_deal_id.casefold()
            for source in left.discovery_sources
            if source.external_deal_id
        }
        right_ids = {
            source.external_deal_id.casefold()
            for source in right.discovery_sources
            if source.external_deal_id
        }
        if left_ids and right_ids:
            return bool(left_ids & right_ids)
        return cls._fingerprint(left) == cls._fingerprint(right)

    @classmethod
    def _ambiguous_pair(cls, left: CandidateTransaction, right: CandidateTransaction) -> bool:
        if cls._name_key(left.target_name) != cls._name_key(right.target_name):
            return False
        if left.announcement_date is None or right.announcement_date is None:
            return False
        return abs((left.announcement_date - right.announcement_date).days) <= 30

    @classmethod
    def _fingerprint(cls, item: CandidateTransaction) -> tuple[object, ...]:
        return (
            cls._name_key(item.acquirer_name),
            cls._name_key(item.target_name),
            item.announcement_date,
            item.transaction_type,
        )

    @staticmethod
    def _name_key(value: str) -> str:
        normalized = " ".join(value.split()).casefold()
        normalized = _LEGAL_SUFFIX.sub("", normalized)
        return re.sub(r"[^a-z0-9]+", " ", normalized).strip()

    @classmethod
    def _merge(cls, group: list[CandidateTransaction]) -> CandidateTransaction:
        first = group[0]
        external_ids = sorted(
            {
                source.external_deal_id
                for candidate in group
                for source in candidate.discovery_sources
                if source.external_deal_id
            }
        )
        if len(external_ids) == 1:
            transaction_id = external_ids[0]
        else:
            digest = sha256(repr(cls._fingerprint(first)).encode()).hexdigest()[:16]
            transaction_id = f"discovered:{digest}"
        sources = tuple(
            {
                source.reference_id: source
                for candidate in group
                for source in candidate.discovery_sources
            }.values()
        )
        rationale = " ".join(dict.fromkeys(candidate.discovery_rationale for candidate in group))
        return replace(
            first,
            candidate_id=transaction_id,
            discovery_rationale=rationale,
            discovery_sources=sources,
        )
