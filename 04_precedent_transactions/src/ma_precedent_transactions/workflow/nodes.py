"""Thin LangGraph nodes around the existing Project 4 services."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from time import perf_counter
from typing import cast

from langgraph.types import interrupt

from ma_precedent_transactions.domain import MultipleStatus, TransactionType, ValuationBasis
from ma_precedent_transactions.errors import (
    DiscoveryError,
    EmbeddingError,
    ExtractionError,
    IndexingError,
)
from ma_precedent_transactions.extraction import (
    VerifiedTransactionRecord,
    retrieve_extraction_context,
)
from ma_precedent_transactions.precedent import ManualOverride, OverrideAction
from ma_precedent_transactions.retrieval import HybridDealRetriever
from ma_precedent_transactions.workflow.models import (
    FailureCode,
    HumanReviewDecision,
    HumanReviewInput,
    ObservationResolution,
    PrecedentWorkflowResult,
    RetryPolicy,
    ReviewAction,
    ReviewOverride,
    ReviewPolicy,
    ReviewRequest,
    RunEvaluationMetadata,
    TransactionEvidenceBundle,
    WorkflowIssue,
    WorkflowState,
    WorkflowStatus,
    WorkflowTraceEvent,
)
from ma_precedent_transactions.workflow.services import WorkflowServices

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WorkflowNodes:
    services: WorkflowServices
    retry_policy: RetryPolicy = RetryPolicy()

    def validate_input(self, state: WorkflowState) -> WorkflowState:
        started = perf_counter()
        try:
            request = state["request"]
            request.__post_init__()
        except (KeyError, TypeError, ValueError) as error:
            return self._fail(
                state,
                FailureCode.INVALID_INPUT,
                "validate_input",
                str(error),
                1,
                started,
            )
        return self._update(
            status=WorkflowStatus.VALIDATED,
            warnings=state.get("warnings", ()),
            errors=state.get("errors", ()),
            retry_counts=dict(state.get("retry_counts", {})),
            retry_stage=None,
            failure_code=None,
            trace=self._trace(
                state,
                "validate_input",
                WorkflowStatus.VALIDATED,
                started,
                "Target and acquisition context validated.",
            ),
        )

    def research_deals(self, state: WorkflowState) -> WorkflowState:
        started = perf_counter()
        attempt = self._attempt(state, "research")
        try:
            corpus = self.services.research.build(state["request"].acquisition_context)
        except (
            DiscoveryError,
            EmbeddingError,
            IndexingError,
            TimeoutError,
            ConnectionError,
        ) as error:
            return self._recoverable(
                state,
                FailureCode.RETRIEVAL_INSUFFICIENT,
                "research",
                "research_deals",
                error,
                attempt,
                self.retry_policy.research,
                started,
            )
        if not corpus.discovery.transactions:
            return self._fail(
                state,
                FailureCode.NO_DEALS_FOUND,
                "research_deals",
                "No historical transactions matched the acquisition context.",
                attempt,
                started,
            )
        if not corpus.chunks:
            return self._recoverable(
                state,
                FailureCode.RETRIEVAL_INSUFFICIENT,
                "research",
                "research_deals",
                RuntimeError("No usable document chunks were indexed."),
                attempt,
                self.retry_policy.research,
                started,
            )
        warnings = tuple(dict.fromkeys((*state.get("warnings", ()), *corpus.warnings)))
        return self._update(
            research=corpus,
            status=WorkflowStatus.RESEARCH_COMPLETE,
            warnings=warnings,
            retry_stage=None,
            trace=self._trace(
                state,
                "research_deals",
                WorkflowStatus.RESEARCH_COMPLETE,
                started,
                f"Resolved {len(corpus.discovery.transactions)} transactions and indexed "
                f"{len(corpus.chunks)} evidence chunks.",
                attempt - 1,
            ),
        )

    def extract_and_verify(self, state: WorkflowState) -> WorkflowState:
        started = perf_counter()
        attempt = self._attempt(state, "extraction")
        try:
            corpus = state["research"]
            retriever = HybridDealRetriever(self.services.research.index)
            bundles = []
            records: dict[str, VerifiedTransactionRecord] = {}
            for candidate in corpus.discovery.transactions:
                evidence = retrieve_extraction_context(retriever, candidate.candidate_id)
                bundles.append(TransactionEvidenceBundle(candidate.candidate_id, evidence))
                if evidence:
                    records[candidate.candidate_id] = self.services.extraction.build(
                        candidate, evidence
                    )
            if not records:
                raise ExtractionError("No transaction had sufficient evidence for extraction.")
            valuation_transactions = self.services.transaction_preparer(records)
        except (ExtractionError, TimeoutError, ConnectionError) as error:
            return self._recoverable(
                state,
                FailureCode.EXTRACTION_FAILED,
                "extraction",
                "extract_and_verify",
                error,
                attempt,
                self.retry_policy.extraction,
                started,
            )
        warnings = list(state.get("warnings", ()))
        weak = [item.transaction_id for item in bundles if not item.results]
        if weak:
            warnings.append("No extraction evidence for transactions: " + ", ".join(weak))
        warnings.extend(warning for record in records.values() for warning in record.warnings)
        return self._update(
            evidence_bundles=tuple(bundles),
            verified_transactions=tuple(records.values()),
            valuation_transactions=valuation_transactions,
            status=WorkflowStatus.EXTRACTION_COMPLETE,
            warnings=tuple(dict.fromkeys(warnings)),
            retry_stage=None,
            trace=self._trace(
                state,
                "extract_and_verify",
                WorkflowStatus.EXTRACTION_COMPLETE,
                started,
                f"Produced {len(records)} verified transaction records.",
                attempt - 1,
            ),
        )

    def route_for_human_review(self, state: WorkflowState) -> WorkflowState:
        started = perf_counter()
        request = state["request"]
        reasons, transaction_ids, fields = self._review_reasons(state)
        needed = request.review_policy is ReviewPolicy.ALWAYS or (
            request.review_policy is ReviewPolicy.WHEN_NEEDED and bool(reasons)
        )
        if not needed:
            if reasons:
                warnings = (*state.get("warnings", ()), *reasons)
            else:
                warnings = state.get("warnings", ())
            return self._update(
                status=WorkflowStatus.REVIEW_APPLIED,
                warnings=tuple(dict.fromkeys(warnings)),
                trace=self._trace(
                    state,
                    "route_for_human_review",
                    WorkflowStatus.REVIEW_APPLIED,
                    started,
                    "No human interruption required by policy.",
                ),
            )
        review_request = ReviewRequest(
            tuple(reasons or ["Configured policy requires analyst review."]),
            tuple(dict.fromkeys(transaction_ids)),
            tuple(dict.fromkeys(fields)),
        )
        return self._update(
            review_request=review_request,
            status=WorkflowStatus.AWAITING_HUMAN_REVIEW,
            failure_code=FailureCode.HUMAN_REVIEW_REQUIRED,
            trace=self._trace(
                state,
                "route_for_human_review",
                WorkflowStatus.AWAITING_HUMAN_REVIEW,
                started,
                "Material ambiguity routed to analyst review.",
            ),
        )

    def human_review(self, state: WorkflowState) -> WorkflowState:
        started = perf_counter()
        response = interrupt(self._review_payload(state), response_schema=HumanReviewInput)
        try:
            decision = self._parse_review(response)
            known = {
                item.record.identity.transaction_id
                for item in state.get("verified_transactions", ())
            }
            unknown = {item.transaction_id for item in decision.resolutions} - known
            if unknown:
                raise ValueError(
                    "Unknown resolution transaction IDs: " + ", ".join(sorted(unknown))
                )
            verified = self._apply_resolutions(state.get("verified_transactions", ()), decision)
            valuation = self._apply_resolutions(state.get("valuation_transactions", ()), decision)
        except (KeyError, TypeError, ValueError) as error:
            return self._fail(
                state,
                FailureCode.VERIFICATION_BLOCKED,
                "human_review",
                str(error),
                1,
                started,
            )
        if decision.action is ReviewAction.REJECT:
            return self._update(
                human_review=decision,
                status=WorkflowStatus.REJECTED,
                failure_code=FailureCode.USER_REJECTED,
                trace=self._trace(
                    state,
                    "human_review",
                    WorkflowStatus.REJECTED,
                    started,
                    "Analyst rejected the run.",
                ),
            )
        return self._update(
            human_review=decision,
            verified_transactions=verified,
            valuation_transactions=valuation,
            status=WorkflowStatus.REVIEW_APPLIED,
            failure_code=None,
            trace=self._trace(
                state,
                "human_review",
                WorkflowStatus.REVIEW_APPLIED,
                started,
                "Analyst decision and audit rationale recorded.",
            ),
        )

    def select_precedents(self, state: WorkflowState) -> WorkflowState:
        started = perf_counter()
        request = state["request"]
        overrides = self._manual_overrides(state.get("human_review"))
        selection = self.services.precedent.selector.select(
            request.comparable_target,
            state.get("valuation_transactions", ()),
            overrides,
        )
        if not selection.selected_transaction_ids:
            return self._fail(
                state,
                FailureCode.NO_ELIGIBLE_PRECEDENTS,
                "select_precedents",
                "No transaction remained eligible for precedent valuation.",
                1,
                started,
                selection=selection,
            )
        return self._update(
            selection=selection,
            status=WorkflowStatus.SELECTION_COMPLETE,
            warnings=tuple(dict.fromkeys((*state.get("warnings", ()), *selection.warnings))),
            trace=self._trace(
                state,
                "select_precedents",
                WorkflowStatus.SELECTION_COMPLETE,
                started,
                f"Selected {len(selection.selected_transaction_ids)} precedents.",
            ),
        )

    def calculate_valuation(self, state: WorkflowState) -> WorkflowState:
        started = perf_counter()
        transactions = state.get("valuation_transactions", ())
        selection = state["selection"]
        decisions = {item.transaction_id: item for item in selection.decisions}
        multiples = tuple(
            result
            for transaction in transactions
            for result in self.services.precedent.multiple_engine.calculate(
                transaction, decisions[transaction.record.identity.transaction_id]
            )
        )
        output = self.services.precedent.valuation_engine.build_output(
            state["request"].valuation_target, selection, multiples
        )
        if not output.ranges:
            return self._fail(
                state,
                FailureCode.VALUATION_UNAVAILABLE,
                "calculate_valuation",
                "No compatible target metric and precedent multiple produced a valuation range.",
                1,
                started,
                multiples=multiples,
                valuation=output,
            )
        return self._update(
            multiples=multiples,
            valuation=output,
            status=WorkflowStatus.VALUATION_COMPLETE,
            trace=self._trace(
                state,
                "calculate_valuation",
                WorkflowStatus.VALUATION_COMPLETE,
                started,
                f"Produced {len(output.ranges)} independent valuation ranges.",
            ),
        )

    def generate_explanation(self, state: WorkflowState) -> WorkflowState:
        started = perf_counter()
        output = state["valuation"]
        if self.services.explanation is None:
            return self._update(
                status=WorkflowStatus.EXPLANATION_COMPLETE,
                trace=self._trace(
                    state,
                    "generate_explanation",
                    WorkflowStatus.EXPLANATION_COMPLETE,
                    started,
                    "Explanation omitted because no provider was configured.",
                ),
            )
        explained = self.services.precedent.valuation_engine.attach_explanation(
            output, self.services.explanation
        )
        warnings = list(state.get("warnings", ()))
        errors = state.get("errors", ())
        if explained.explanation is None or explained.explanation.status.value == "unavailable":
            warnings.append("AI explanation failed; deterministic valuation remains valid.")
            errors = (
                *errors,
                WorkflowIssue(
                    FailureCode.EXPLANATION_FAILED,
                    "generate_explanation",
                    "Grounded explanation provider failed; calculations were preserved.",
                    False,
                    1,
                ),
            )
        return self._update(
            valuation=explained,
            status=WorkflowStatus.EXPLANATION_COMPLETE,
            warnings=tuple(dict.fromkeys(warnings)),
            errors=errors,
            trace=self._trace(
                state,
                "generate_explanation",
                WorkflowStatus.EXPLANATION_COMPLETE,
                started,
                "Grounded explanation stage completed without changing calculations.",
            ),
        )

    def evaluate_run(self, state: WorkflowState) -> WorkflowState:
        started = perf_counter()
        research = state.get("research")
        valuation = state.get("valuation")
        selection = state.get("selection")
        verified = state.get("verified_transactions", ())
        evaluation = RunEvaluationMetadata(
            0 if research is None else research.discovery.raw_candidate_count,
            0 if research is None else len(research.discovery.transactions),
            0 if research is None else len(research.parsed_documents),
            sum(len(item.results) for item in state.get("evidence_bundles", ())),
            len(verified),
            sum(len(item.conflicts) for item in verified),
            0 if selection is None else len(selection.selected_transaction_ids),
            sum(
                item.contract.status is MultipleStatus.INCLUDED
                for item in state.get("multiples", ())
            ),
            0 if valuation is None else len(valuation.ranges),
            valuation is not None
            and valuation.explanation is not None
            and valuation.explanation.status.value == "available",
        )
        return self._update(
            evaluation=evaluation,
            trace=self._trace(
                state,
                "evaluate_run",
                state.get("status", WorkflowStatus.FAILED),
                started,
                "Run-level completeness and routing metadata recorded.",
            ),
        )

    def finalize(self, state: WorkflowState) -> WorkflowState:
        started = perf_counter()
        status = state.get("status", WorkflowStatus.FAILED)
        if status not in {WorkflowStatus.FAILED, WorkflowStatus.REJECTED}:
            status = WorkflowStatus.COMPLETED
        trace = self._trace(
            state,
            "finalize",
            status,
            started,
            f"Workflow finalized with status {status.value}.",
        )
        result = PrecedentWorkflowResult(
            state["request"],
            status,
            state.get("failure_code"),
            state.get("research"),
            state.get("verified_transactions", ()),
            state.get("selection"),
            state.get("multiples", ()),
            state.get("valuation"),
            state.get("human_review"),
            state.get("evaluation"),
            state.get("warnings", ()),
            state.get("errors", ()),
            trace,
        )
        return self._update(final_result=result, status=status, trace=trace)

    def _review_reasons(self, state: WorkflowState) -> tuple[list[str], list[str], list[str]]:
        reasons: list[str] = []
        transaction_ids: list[str] = []
        fields: list[str] = []
        for transaction in state.get("verified_transactions", ()):
            transaction_id = transaction.record.identity.transaction_id
            if transaction.conflicts:
                reasons.append(f"{transaction_id} has unresolved source conflicts.")
                transaction_ids.append(transaction_id)
                fields.extend(item.field for item in transaction.conflicts)
            if any(
                item.basis is ValuationBasis.AMBIGUOUS for item in transaction.record.valuations
            ):
                reasons.append(f"{transaction_id} contains an ambiguous deal-value basis.")
                transaction_ids.append(transaction_id)
            if transaction.record.structure.transaction_type is TransactionType.MINORITY_INVESTMENT:
                reasons.append(f"{transaction_id} is a minority or partial-stake transaction.")
                transaction_ids.append(transaction_id)
        return reasons, transaction_ids, fields

    @staticmethod
    def _review_payload(state: WorkflowState) -> dict[str, object]:
        request = state["review_request"]
        return {
            "request_id": state["request"].request_id,
            "reasons": list(request.reasons),
            "transaction_ids": list(request.transaction_ids),
            "conflict_fields": list(request.conflict_fields),
            "allowed_actions": ["approve", "reject"],
            "instructions": (
                "Provide reviewer, rationale, optional conflict resolutions, and optional "
                "force-include/force-exclude overrides."
            ),
        }

    @staticmethod
    def _parse_review(response: HumanReviewInput) -> HumanReviewDecision:
        resolutions = tuple(
            ObservationResolution(
                item["transaction_id"],
                item["field"],
                item["selected_observation_id"],
                item["rationale"],
            )
            for item in response.get("resolutions", [])
        )
        overrides = tuple(
            ReviewOverride(
                item["transaction_id"],
                OverrideAction(item["action"]),
                item["rationale"],
            )
            for item in response.get("overrides", [])
        )
        return HumanReviewDecision(
            ReviewAction(response["action"]),
            response["reviewer"],
            response["rationale"],
            resolutions,
            overrides,
            datetime.now(UTC),
        )

    @staticmethod
    def _apply_resolutions(
        records: tuple[VerifiedTransactionRecord, ...], decision: HumanReviewDecision
    ) -> tuple[VerifiedTransactionRecord, ...]:
        by_transaction: dict[str, list[ObservationResolution]] = {}
        for resolution in decision.resolutions:
            by_transaction.setdefault(resolution.transaction_id, []).append(resolution)
        output = []
        for record in records:
            transaction_id = record.record.identity.transaction_id
            resolutions = by_transaction.get(transaction_id, [])
            conflicts = list(record.conflicts)
            for resolution in resolutions:
                match = next(
                    (
                        item
                        for item in conflicts
                        if item.field == resolution.field
                        and resolution.selected_observation_id in item.observation_ids
                    ),
                    None,
                )
                if match is None:
                    raise ValueError(
                        f"Resolution does not match an unresolved conflict: {transaction_id} "
                        f"{resolution.field}."
                    )
                conflicts.remove(match)
            warnings = record.warnings
            if resolutions:
                warnings = (*warnings, "Analyst conflict resolution applied; audit trail retained.")
            output.append(replace(record, conflicts=tuple(conflicts), warnings=warnings))
        return tuple(output)

    @staticmethod
    def _manual_overrides(decision: HumanReviewDecision | None) -> tuple[ManualOverride, ...]:
        if decision is None:
            return ()
        return tuple(
            ManualOverride(
                item.transaction_id,
                item.action,
                item.rationale,
                decision.reviewer,
                decision.recorded_at,
            )
            for item in decision.overrides
        )

    @staticmethod
    def _update(**values: object) -> WorkflowState:
        return cast(WorkflowState, values)

    @staticmethod
    def _attempt(state: WorkflowState, stage: str) -> int:
        return state.get("retry_counts", {}).get(stage, 0) + 1

    def _recoverable(
        self,
        state: WorkflowState,
        code: FailureCode,
        stage: str,
        node: str,
        error: Exception,
        attempt: int,
        maximum: int,
        started: float,
    ) -> WorkflowState:
        recoverable = attempt <= maximum
        issue = WorkflowIssue(code, stage, str(error), recoverable, attempt)
        if recoverable:
            counts = dict(state.get("retry_counts", {}))
            counts[stage] = attempt
            LOGGER.warning("Recoverable workflow failure at %s attempt %s", stage, attempt)
            return self._update(
                retry_counts=counts,
                retry_stage=stage,
                errors=(*state.get("errors", ()), issue),
                trace=self._trace(
                    state,
                    node,
                    state.get("status", WorkflowStatus.INITIALIZED),
                    started,
                    f"Recoverable {stage} failure; bounded retry scheduled.",
                    attempt,
                ),
            )
        return self._fail(state, code, node, str(error), attempt, started, issue=issue)

    def _fail(
        self,
        state: WorkflowState,
        code: FailureCode,
        node: str,
        message: str,
        attempt: int,
        started: float,
        *,
        issue: WorkflowIssue | None = None,
        **values: object,
    ) -> WorkflowState:
        failure = issue or WorkflowIssue(code, node, message, False, attempt)
        return self._update(
            **values,
            status=WorkflowStatus.FAILED,
            failure_code=code,
            retry_stage=None,
            errors=(*state.get("errors", ()), failure),
            trace=self._trace(
                state,
                node,
                WorkflowStatus.FAILED,
                started,
                message,
                max(0, attempt - 1),
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
        event = WorkflowTraceEvent(
            node,
            status,
            message,
            max(0, round((perf_counter() - started) * 1000)),
            datetime.now(UTC),
            retry_count,
        )
        LOGGER.info("workflow_node=%s status=%s message=%s", node, status.value, message)
        return (*state.get("trace", ()), event)
