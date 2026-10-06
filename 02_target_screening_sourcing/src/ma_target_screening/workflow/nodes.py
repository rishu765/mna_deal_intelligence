"""Thin LangGraph nodes that orchestrate existing Project 2 services."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from time import perf_counter
from typing import cast

from langgraph.types import interrupt

from ma_target_screening.errors import (
    DiscoveryError,
    DiscoveryUnavailableError,
    EnrichmentError,
    StrategicFitError,
)
from ma_target_screening.profile import EnrichmentStatus
from ma_target_screening.screening.models import RankedCandidate, Shortlist
from ma_target_screening.thesis import AcquisitionThesis
from ma_target_screening.workflow.models import (
    HumanReviewDecision,
    HumanReviewInput,
    RetryPolicy,
    ReviewDecision,
    WorkflowIssue,
    WorkflowResult,
    WorkflowState,
    WorkflowStatus,
    WorkflowTraceEvent,
)
from ma_target_screening.workflow.ports import (
    DiscoveryWorkflowService,
    EnrichmentWorkflowService,
    ScreeningWorkflowService,
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WorkflowNodes:
    discovery: DiscoveryWorkflowService
    enrichment: EnrichmentWorkflowService
    screening: ScreeningWorkflowService
    retry_policy: RetryPolicy = RetryPolicy()

    def validate_thesis(self, state: WorkflowState) -> WorkflowState:
        started = perf_counter()
        try:
            thesis = state["thesis"]
            validated = AcquisitionThesis.from_dict(thesis.to_dict())
        except (KeyError, TypeError, ValueError) as error:
            issue = WorkflowIssue("validate_thesis", str(error), False, 1)
            return self._update(
                state,
                status=WorkflowStatus.FAILED,
                errors=(*state.get("errors", ()), issue),
                retry_stage=None,
                trace=self._trace(
                    state,
                    "validate_thesis",
                    WorkflowStatus.FAILED,
                    started,
                    "Thesis validation failed.",
                ),
            )
        return self._update(
            state,
            thesis=validated,
            status=WorkflowStatus.VALIDATED,
            warnings=state.get("warnings", ()),
            errors=state.get("errors", ()),
            retry_counts=dict(state.get("retry_counts", {})),
            retry_stage=None,
            trace=self._trace(
                state,
                "validate_thesis",
                WorkflowStatus.VALIDATED,
                started,
                "Acquisition thesis validated.",
            ),
        )

    def discover_candidates(self, state: WorkflowState) -> WorkflowState:
        started = perf_counter()
        stage = "discovery"
        attempt = self._retry_count(state, stage) + 1
        try:
            result = self.discovery.discover(state["thesis"])
        except (DiscoveryUnavailableError, TimeoutError, ConnectionError) as error:
            return self._recoverable_failure(
                state,
                stage=stage,
                node="discover_candidates",
                attempt=attempt,
                maximum=self.retry_policy.discovery,
                error=error,
                started=started,
            )
        except (DiscoveryError, KeyError, TypeError, ValueError) as error:
            issue = WorkflowIssue(stage, str(error), False, attempt)
            return self._update(
                state,
                candidates=(),
                status=WorkflowStatus.FAILED,
                errors=(*state.get("errors", ()), issue),
                retry_stage=None,
                trace=self._trace(
                    state,
                    "discover_candidates",
                    WorkflowStatus.FAILED,
                    started,
                    "Candidate discovery failed with a non-retryable error.",
                    attempt - 1,
                ),
            )
        warnings = (*state.get("warnings", ()), *result.warnings)
        return self._update(
            state,
            discovery_result=result,
            candidates=result.candidates,
            status=WorkflowStatus.DISCOVERY_COMPLETE,
            warnings=tuple(dict.fromkeys(warnings)),
            retry_stage=None,
            trace=self._trace(
                state,
                "discover_candidates",
                WorkflowStatus.DISCOVERY_COMPLETE,
                started,
                f"Discovered {len(result.candidates)} deduplicated candidates.",
                attempt - 1,
            ),
        )

    def enrich_candidates(self, state: WorkflowState) -> WorkflowState:
        started = perf_counter()
        stage = "enrichment"
        attempt = self._retry_count(state, stage) + 1
        profiles = []
        issues: list[WorkflowIssue] = []
        candidates = state.get("candidates", ())
        for candidate in candidates:
            try:
                profiles.append(self.enrichment.enrich(candidate, state["thesis"]))
            except (EnrichmentError, TimeoutError, ConnectionError, TypeError, ValueError) as error:
                issues.append(
                    WorkflowIssue(
                        stage,
                        f"{candidate.canonical_name}: {error}",
                        True,
                        attempt,
                    )
                )
        provider_failures = tuple(
            profile for profile in profiles if profile.status is EnrichmentStatus.PROVIDER_FAILURE
        )
        all_failed = bool(candidates) and (not profiles or len(provider_failures) == len(profiles))
        if all_failed:
            issues.append(
                WorkflowIssue(
                    stage,
                    "All candidate enrichment attempts failed.",
                    attempt <= self.retry_policy.enrichment,
                    attempt,
                )
            )
        if all_failed and attempt <= self.retry_policy.enrichment:
            return self._retry_update(
                state,
                stage=stage,
                node="enrich_candidates",
                attempt=attempt,
                started=started,
                message="All candidate enrichment attempts failed; retry scheduled.",
                errors=(*state.get("errors", ()), *issues),
            )
        warnings = list(state.get("warnings", ()))
        warnings.extend(warning for profile in profiles for warning in profile.warnings)
        if issues:
            warnings.append("Some candidates could not be enriched; partial results were kept.")
        if all_failed:
            warnings.append("Enrichment retry limit exhausted; failed profiles were retained.")
        return self._update(
            state,
            profiles=tuple(profiles),
            status=WorkflowStatus.ENRICHMENT_COMPLETE,
            warnings=tuple(dict.fromkeys(warnings)),
            errors=(*state.get("errors", ()), *issues),
            retry_stage=None,
            trace=self._trace(
                state,
                "enrich_candidates",
                WorkflowStatus.ENRICHMENT_COMPLETE,
                started,
                f"Enriched {len(profiles)} of {len(candidates)} candidates.",
                attempt - 1,
            ),
        )

    def screen_and_rank(self, state: WorkflowState) -> WorkflowState:
        started = perf_counter()
        stage = "screening"
        attempt = self._retry_count(state, stage) + 1
        try:
            shortlist = self.screening.build_shortlist(state["thesis"], state.get("profiles", ()))
        except (StrategicFitError, TimeoutError, ConnectionError) as error:
            return self._recoverable_failure(
                state,
                stage=stage,
                node="screen_and_rank",
                attempt=attempt,
                maximum=self.retry_policy.screening,
                error=error,
                started=started,
            )
        except (KeyError, TypeError, ValueError) as error:
            issue = WorkflowIssue(stage, str(error), False, attempt)
            return self._update(
                state,
                status=WorkflowStatus.FAILED,
                errors=(*state.get("errors", ()), issue),
                retry_stage=None,
                trace=self._trace(
                    state,
                    "screen_and_rank",
                    WorkflowStatus.FAILED,
                    started,
                    "Screening failed with a non-retryable error.",
                    attempt - 1,
                ),
            )
        semantic_failure = any(
            "Strategic-fit provider failed" in warning
            for result in shortlist.screening_results
            for warning in result.warnings
        )
        semantic_issue = (
            WorkflowIssue(
                stage,
                "One or more semantic assessments failed.",
                attempt <= self.retry_policy.screening,
                attempt,
            )
            if semantic_failure
            else None
        )
        if semantic_failure and attempt <= self.retry_policy.screening:
            return self._retry_update(
                state,
                stage=stage,
                node="screen_and_rank",
                attempt=attempt,
                started=started,
                message="Semantic assessment failure detected; screening retry scheduled.",
                errors=(
                    *state.get("errors", ()),
                    *(() if semantic_issue is None else (semantic_issue,)),
                ),
            )
        warnings = (*state.get("warnings", ()), *shortlist.warnings)
        if semantic_failure:
            warnings = (
                *warnings,
                "Screening retry limit exhausted; unknown semantic assessments were retained.",
            )
        return self._update(
            state,
            provisional_shortlist=shortlist,
            status=WorkflowStatus.SCREENING_COMPLETE,
            warnings=tuple(dict.fromkeys(warnings)),
            errors=(
                *state.get("errors", ()),
                *(() if semantic_issue is None else (semantic_issue,)),
            ),
            retry_stage=None,
            trace=self._trace(
                state,
                "screen_and_rank",
                WorkflowStatus.SCREENING_COMPLETE,
                started,
                f"Ranked {len(shortlist.ranked_candidates)} shortlist candidates.",
                attempt - 1,
            ),
        )

    def prepare_human_review(self, state: WorkflowState) -> WorkflowState:
        started = perf_counter()
        return self._update(
            state,
            status=WorkflowStatus.AWAITING_HUMAN_REVIEW,
            trace=self._trace(
                state,
                "prepare_human_review",
                WorkflowStatus.AWAITING_HUMAN_REVIEW,
                started,
                "Workflow paused for shortlist review.",
            ),
        )

    def human_review(self, state: WorkflowState) -> WorkflowState:
        started = perf_counter()
        response = interrupt(self._review_payload(state), response_schema=HumanReviewInput)
        try:
            review = HumanReviewDecision(
                decision=ReviewDecision(response["decision"]),
                reviewer_notes=response.get("reviewer_notes"),
                approved_candidates=tuple(response.get("approved_candidates", [])),
                rejected_candidates=tuple(response.get("rejected_candidates", [])),
            )
            self._validate_review_candidates(state, review)
        except (KeyError, TypeError, ValueError) as error:
            issue = WorkflowIssue("human_review", str(error), False, 1)
            return self._update(
                state,
                status=WorkflowStatus.FAILED,
                errors=(*state.get("errors", ()), issue),
                trace=self._trace(
                    state,
                    "human_review",
                    WorkflowStatus.FAILED,
                    started,
                    "Human review response was invalid.",
                ),
            )
        if review.decision is ReviewDecision.RERUN:
            current = self._retry_count(state, "human_rerun")
            next_count = current + 1
            if next_count > self.retry_policy.human_reruns:
                issue = WorkflowIssue(
                    "human_review",
                    "Human-requested rerun limit exceeded.",
                    False,
                    next_count,
                )
                return self._update(
                    state,
                    human_review=review,
                    status=WorkflowStatus.FAILED,
                    errors=(*state.get("errors", ()), issue),
                    trace=self._trace(
                        state,
                        "human_review",
                        WorkflowStatus.FAILED,
                        started,
                        "Human-requested rerun limit exceeded.",
                        next_count,
                    ),
                )
            counts = dict(state.get("retry_counts", {}))
            counts["human_rerun"] = next_count
            return self._update(
                state,
                human_review=review,
                retry_counts=counts,
                status=WorkflowStatus.ENRICHMENT_COMPLETE,
                trace=self._trace(
                    state,
                    "human_review",
                    WorkflowStatus.ENRICHMENT_COMPLETE,
                    started,
                    "Reviewer requested a bounded enrichment and screening rerun.",
                    next_count,
                ),
            )
        status = (
            WorkflowStatus.APPROVED
            if review.decision is ReviewDecision.APPROVE
            else WorkflowStatus.REJECTED
        )
        return self._update(
            state,
            human_review=review,
            status=status,
            trace=self._trace(
                state,
                "human_review",
                status,
                started,
                f"Reviewer decision recorded: {review.decision.value}.",
            ),
        )

    def finalize(self, state: WorkflowState) -> WorkflowState:
        started = perf_counter()
        thesis = state["thesis"]
        status = state.get("status", WorkflowStatus.FAILED)
        provisional = state.get("provisional_shortlist")
        if provisional is None:
            provisional = Shortlist(
                thesis.thesis_id,
                (),
                (),
                ("No provisional shortlist was produced.",),
            )
        review = state.get("human_review")
        if status is WorkflowStatus.APPROVED and review is not None:
            final_shortlist = self._approved_shortlist(provisional, review)
        else:
            final_shortlist = Shortlist(
                thesis_id=provisional.thesis_id,
                ranked_candidates=(),
                screening_results=provisional.screening_results,
                warnings=provisional.warnings,
            )
        if status not in {
            WorkflowStatus.APPROVED,
            WorkflowStatus.REJECTED,
            WorkflowStatus.FAILED,
        }:
            status = WorkflowStatus.FAILED
        trace = self._trace(
            state,
            "finalize",
            status,
            started,
            f"Workflow finalized with status {status.value}.",
        )
        result = WorkflowResult(
            thesis=thesis,
            final_shortlist=final_shortlist,
            human_review=review,
            status=status,
            warnings=state.get("warnings", ()),
            errors=state.get("errors", ()),
            trace=trace,
        )
        return self._update(state, final_result=result, status=status, trace=trace)

    @staticmethod
    def _update(state: WorkflowState, **values: object) -> WorkflowState:
        return cast(WorkflowState, values)

    @staticmethod
    def _retry_count(state: WorkflowState, stage: str) -> int:
        return state.get("retry_counts", {}).get(stage, 0)

    def _recoverable_failure(
        self,
        state: WorkflowState,
        *,
        stage: str,
        node: str,
        attempt: int,
        maximum: int,
        error: Exception,
        started: float,
    ) -> WorkflowState:
        issue = WorkflowIssue(stage, str(error), attempt <= maximum, attempt)
        if attempt <= maximum:
            return self._retry_update(
                state,
                stage=stage,
                node=node,
                attempt=attempt,
                started=started,
                message=f"Recoverable {stage} failure; retry scheduled.",
                errors=(*state.get("errors", ()), issue),
            )
        return self._update(
            state,
            status=WorkflowStatus.FAILED,
            errors=(*state.get("errors", ()), issue),
            retry_stage=None,
            trace=self._trace(
                state,
                node,
                WorkflowStatus.FAILED,
                started,
                f"{stage.capitalize()} retry limit exhausted.",
                attempt,
            ),
        )

    def _retry_update(
        self,
        state: WorkflowState,
        *,
        stage: str,
        node: str,
        attempt: int,
        started: float,
        message: str,
        errors: tuple[WorkflowIssue, ...] | None = None,
    ) -> WorkflowState:
        counts = dict(state.get("retry_counts", {}))
        counts[stage] = attempt
        return self._update(
            state,
            retry_counts=counts,
            retry_stage=stage,
            errors=state.get("errors", ()) if errors is None else errors,
            trace=self._trace(
                state,
                node,
                state.get("status", WorkflowStatus.INITIALIZED),
                started,
                message,
                attempt,
            ),
        )

    @staticmethod
    def _trace(
        state: WorkflowState,
        node: str,
        status: WorkflowStatus,
        started: float,
        message: str,
        retry_count: int = 0,
    ) -> tuple[WorkflowTraceEvent, ...]:
        duration_ms = max(0, round((perf_counter() - started) * 1000))
        event = WorkflowTraceEvent(
            node=node,
            status=status,
            duration_ms=duration_ms,
            message=message,
            occurred_at=datetime.now(UTC).isoformat(),
            retry_count=retry_count,
        )
        LOGGER.info(
            "workflow node completed node=%s status=%s duration_ms=%d retry_count=%d",
            node,
            status.value,
            duration_ms,
            retry_count,
        )
        return (*state.get("trace", ()), event)

    @staticmethod
    def _review_payload(state: WorkflowState) -> dict[str, object]:
        shortlist = state["provisional_shortlist"]
        return {
            "instruction": "Review and approve, reject, or request one bounded rerun.",
            "shortlist": shortlist.to_dict(),
            "audit_results": [
                {
                    "candidate": result.profile.candidate.canonical_name,
                    "domain": result.profile.candidate.website_domain,
                    "eligibility": result.eligibility.value,
                    "rationale": result.rationale,
                    "criteria": [
                        {
                            "criterion_id": item.criterion_id,
                            "outcome": item.outcome.value,
                            "reason": item.reason,
                            "evidence_ids": [e.evidence_id for e in item.evidence],
                        }
                        for item in result.evaluations
                    ],
                    "warnings": list(result.warnings),
                }
                for result in shortlist.screening_results
            ],
            "workflow_warnings": list(state.get("warnings", ())),
            "workflow_errors": [
                {
                    "stage": item.stage,
                    "message": item.message,
                    "recoverable": item.recoverable,
                    "attempt": item.attempt,
                }
                for item in state.get("errors", ())
            ],
        }

    @staticmethod
    def _validate_review_candidates(state: WorkflowState, review: HumanReviewDecision) -> None:
        if review.decision is ReviewDecision.RERUN and (
            review.approved_candidates or review.rejected_candidates
        ):
            raise ValueError("rerun decisions cannot approve or reject individual candidates")
        ranked = state["provisional_shortlist"].ranked_candidates
        identifiers = {
            value.casefold()
            for item in ranked
            for value in (
                item.result.profile.candidate.canonical_name,
                item.result.profile.candidate.website_domain or "",
            )
            if value
        }
        requested = {
            item.casefold() for item in (*review.approved_candidates, *review.rejected_candidates)
        }
        unknown = sorted(requested - identifiers)
        if unknown:
            raise ValueError(
                "review references unknown shortlist candidates: " + ", ".join(unknown)
            )

    @staticmethod
    def _approved_shortlist(provisional: Shortlist, review: HumanReviewDecision) -> Shortlist:
        approved = {item.casefold() for item in review.approved_candidates}
        rejected = {item.casefold() for item in review.rejected_candidates}

        def keep(item: RankedCandidate) -> bool:
            identifiers = {
                item.result.profile.candidate.canonical_name.casefold(),
                (item.result.profile.candidate.website_domain or "").casefold(),
            }
            if identifiers & rejected:
                return False
            return not approved or bool(identifiers & approved)

        retained = tuple(item for item in provisional.ranked_candidates if keep(item))
        reranked = tuple(replace(item, rank=index) for index, item in enumerate(retained, start=1))
        return Shortlist(
            thesis_id=provisional.thesis_id,
            ranked_candidates=reranked,
            screening_results=provisional.screening_results,
            warnings=provisional.warnings,
        )
