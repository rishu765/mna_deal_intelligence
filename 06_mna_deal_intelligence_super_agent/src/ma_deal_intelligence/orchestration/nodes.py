"""LangGraph nodes that compose Project 6 services without specialist business logic."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from langgraph.types import Send, interrupt

from ma_deal_intelligence.evidence import ProjectId
from ma_deal_intelligence.finance import FindingSeverity, FindingStatus, MetricBasis
from ma_deal_intelligence.ingestion import ingest_result
from ma_deal_intelligence.orchestration.models import (
    AnalystReviewRequest,
    CapabilityRuntimeState,
    CapabilityTransition,
    ClarificationState,
    FailureKind,
    GraphState,
    GraphTraceEvent,
    HumanReviewInput,
    OrchestrationPolicy,
    OrchestrationStatus,
    OrchestrationTerminalResult,
    ReviewAuditEvent,
    ReviewDecisionAction,
    ReviewOption,
    SpecialistAttemptResult,
    TraceEventType,
)
from ma_deal_intelligence.orchestration.services import (
    OrchestrationServices,
    TransientAdapterError,
)
from ma_deal_intelligence.outputs import ProjectResultEnvelope
from ma_deal_intelligence.planning import PlanStepStatus
from ma_deal_intelligence.reconciliation_models import (
    ReconciliationIssue,
    ReconciliationIssueType,
)
from ma_deal_intelligence.runner import request_for_capability
from ma_deal_intelligence.state import DealState
from ma_deal_intelligence.workflow import (
    AnalystDecision,
    DealError,
    DecisionAction,
    ExecutionStatus,
    WorkflowStatus,
)


class GraphInvariantError(ValueError):
    """Raised when orchestration would violate a specialist ownership invariant."""


class OrchestrationNodes:
    def __init__(
        self,
        services: OrchestrationServices,
        policy: OrchestrationPolicy,
    ) -> None:
        self.services = services
        self.policy = policy

    @staticmethod
    def passthrough(state: GraphState) -> GraphState:
        del state
        return {}

    def validate_request(self, state: GraphState) -> GraphState:
        request = state["request"]
        errors: list[DealError] = []
        if not request.request_id.strip():
            errors.append(
                self._request_error(state, "REQUEST_ID_REQUIRED", "request ID is required")
            )
        if not request.user_query.strip():
            errors.append(self._request_error(state, "QUERY_REQUIRED", "user query is required"))
        status = OrchestrationStatus.FAILED if errors else OrchestrationStatus.VALIDATING
        message = "Request validation failed." if errors else "Request validated."
        return {
            "status": status,
            "errors": (*state.get("errors", ()), *errors),
            "trace": self._trace(
                state,
                "validate_request",
                TraceEventType.REQUEST_VALIDATED,
                message,
                token="request",
                status=status,
            ),
        }

    def classify_intent(self, state: GraphState) -> GraphState:
        classification = self.services.classifier.classify(state["request"])
        return {
            "classification": classification,
            "status": OrchestrationStatus.CLASSIFYING,
            "warnings": (*state.get("warnings", ()), *classification.warnings),
            "trace": self._trace(
                state,
                "classify_intent",
                TraceEventType.INTENT_CLASSIFIED,
                "Intent classified using the configured deterministic-first classifier.",
                token="intent",
                status=OrchestrationStatus.CLASSIFYING,
            ),
        }

    def build_plan(self, state: GraphState) -> GraphState:
        plan = self.services.planner.build(
            state["request"], state["classification"], state["deal_state"]
        )
        return {
            "execution_plan": plan,
            "status": OrchestrationStatus.PLANNING,
            "warnings": (
                *state.get("warnings", ()),
                *(item.message for item in plan.warnings),
            ),
            "trace": self._trace(
                state,
                "build_plan",
                TraceEventType.PLAN_BUILT,
                f"Plan selected {len(plan.steps)} capability steps.",
                token=plan.plan_id,
                status=OrchestrationStatus.PLANNING,
            ),
        }

    def validate_plan(self, state: GraphState) -> GraphState:
        plan = state["execution_plan"]
        if plan.errors:
            errors = tuple(
                DealError(
                    f"error:{state['run_id']}:plan:{index}",
                    item.code,
                    ProjectId.PROJECT_6,
                    item.capability_id,
                    False,
                    False,
                    item.message,
                    "execution_plan",
                )
                for index, item in enumerate(plan.errors, 1)
            )
            return {
                "status": OrchestrationStatus.FAILED,
                "errors": (*state.get("errors", ()), *errors),
                "trace": self._trace(
                    state,
                    "validate_plan",
                    TraceEventType.PLAN_VALIDATED,
                    "Execution plan is invalid.",
                    token="invalid",
                    status=OrchestrationStatus.FAILED,
                ),
            }
        blocking = tuple(item for item in plan.required_user_inputs if item.blocking)
        if blocking:
            clarification = ClarificationState(
                blocking,
                tuple(
                    dict.fromkeys(
                        item.capability_id for item in blocking if item.capability_id is not None
                    )
                ),
                "Required inputs are missing from the request and canonical deal state.",
                tuple(item.suggested_question for item in blocking),
            )
            return {
                "status": OrchestrationStatus.WAITING_FOR_INPUT,
                "clarification": clarification,
                "trace": self._trace(
                    state,
                    "validate_plan",
                    TraceEventType.PLAN_VALIDATED,
                    "Plan requires additional user input.",
                    token="waiting",
                    status=OrchestrationStatus.WAITING_FOR_INPUT,
                    branch="waiting_for_input",
                ),
            }
        self.services.planner.validate(plan)
        return {
            "status": OrchestrationStatus.READY,
            "trace": self._trace(
                state,
                "validate_plan",
                TraceEventType.PLAN_VALIDATED,
                "Execution plan validated.",
                token="ready",
                status=OrchestrationStatus.READY,
            ),
        }

    def initialize_execution(self, state: GraphState) -> GraphState:
        now = datetime.now(UTC)
        runtimes: dict[str, CapabilityRuntimeState] = {}
        trace: list[GraphTraceEvent] = []
        for step in state["execution_plan"].steps:
            transition = CapabilityTransition(ExecutionStatus.NOT_STARTED, now, step.rationale)
            runtimes[step.capability_id] = CapabilityRuntimeState(
                step.capability_id, ExecutionStatus.NOT_STARTED, (transition,)
            )
            trace.extend(
                self._trace(
                    state,
                    "initialize_execution",
                    TraceEventType.CAPABILITY_SELECTED,
                    step.rationale,
                    token=step.capability_id,
                    capability_id=step.capability_id,
                    status=OrchestrationStatus.RUNNING,
                )
            )
        for skipped in state["execution_plan"].skipped_capabilities:
            if skipped.capability_id in runtimes:
                continue
            transition = CapabilityTransition(ExecutionStatus.SKIPPED, now, skipped.reason)
            runtimes[skipped.capability_id] = CapabilityRuntimeState(
                skipped.capability_id, ExecutionStatus.SKIPPED, (transition,)
            )
            trace.extend(
                self._trace(
                    state,
                    "initialize_execution",
                    TraceEventType.CAPABILITY_SKIPPED,
                    skipped.reason,
                    token=f"planned-skip:{skipped.capability_id}",
                    capability_id=skipped.capability_id,
                    status=OrchestrationStatus.RUNNING,
                    branch="not_selected",
                )
            )
        return {
            "status": OrchestrationStatus.RUNNING,
            "stage_index": 0,
            "execution_complete": not bool(state["execution_plan"].stages),
            "capability_states": runtimes,
            "trace": tuple(trace),
        }

    def prepare_stage(self, state: GraphState) -> GraphState:
        plan = state["execution_plan"]
        index = state.get("stage_index", 0)
        if index >= len(plan.stages):
            return {"execution_complete": True, "active_stage_capabilities": ()}
        stage = plan.stages[index]
        steps = {step.step_id: step for step in plan.steps}
        runtimes = dict(state.get("capability_states", {}))
        active: list[str] = []
        trace: list[GraphTraceEvent] = []
        for step_id in stage.step_ids:
            step = steps[step_id]
            failed_dependencies = tuple(
                dependency
                for dependency in step.depends_on
                if runtimes.get(dependency) is None
                or runtimes[dependency].status
                not in {ExecutionStatus.COMPLETED, ExecutionStatus.COMPLETED_WITH_WARNINGS}
            )
            if step.status is PlanStepStatus.BLOCKED or failed_dependencies:
                reason = (
                    f"Dependency did not complete: {', '.join(failed_dependencies)}"
                    if failed_dependencies
                    else f"Missing inputs: {', '.join(step.missing_inputs)}"
                )
                runtimes[step.capability_id] = self._transition(
                    runtimes[step.capability_id], ExecutionStatus.SKIPPED, reason
                )
                trace.extend(
                    self._trace(
                        state,
                        "prepare_stage",
                        TraceEventType.CAPABILITY_SKIPPED,
                        reason,
                        token=f"{index}:{step.capability_id}",
                        capability_id=step.capability_id,
                        branch="dependency_skip",
                    )
                )
                continue
            runtimes[step.capability_id] = self._transition(
                runtimes[step.capability_id], ExecutionStatus.READY, "Dependencies satisfied."
            )
            active.append(step.capability_id)
        return {
            "active_stage_capabilities": tuple(active),
            "capability_states": runtimes,
            "execution_complete": False,
            "trace": tuple(trace),
        }

    def route_stage_workers(self, state: GraphState) -> list[Send] | str:
        capabilities = state.get("active_stage_capabilities", ())
        if not capabilities:
            return "complete_stage"
        return [
            self._send(state, capability, 1, state.get("rerun_iteration", 0))
            for capability in capabilities
        ]

    def invoke_specialist(self, state: GraphState) -> GraphState:
        capability_id = state["worker_capability_id"]
        attempt = state["worker_attempt"]
        rerun_iteration = state.get("worker_rerun_iteration", 0)
        attempt_id = f"{state['run_id']}:{capability_id}:r{rerun_iteration}:a{attempt}"
        started = datetime.now(UTC)
        timer = perf_counter()
        runtime = state["capability_states"][capability_id]
        runtime = self._transition(
            runtime, ExecutionStatus.RUNNING, "Adapter invocation started.", attempt
        )
        try:
            request = request_for_capability(
                capability_id,
                state["execution_plan"],
                state["deal_state"],
                execution_id=attempt_id,
            )
            envelope = self.services.invoker.invoke(capability_id, request)
            status = (
                ExecutionStatus.COMPLETED_WITH_WARNINGS
                if envelope.warnings or envelope.errors
                else ExecutionStatus.COMPLETED
            )
            runtime = replace(
                self._transition(runtime, status, "Specialist result returned.", attempt),
                attempts=max(runtime.attempts, attempt),
                result_run_ids=tuple(dict.fromkeys((*runtime.result_run_ids, envelope.run_id))),
                last_error_id=None,
            )
            finished = datetime.now(UTC)
            result = SpecialistAttemptResult(
                attempt_id,
                capability_id,
                attempt,
                rerun_iteration,
                started,
                finished,
                envelope=envelope,
            )
            trace = (
                *self._trace(
                    state,
                    "invoke_specialist",
                    TraceEventType.ADAPTER_INVOKED,
                    "Adapter invoked.",
                    token=f"{attempt_id}:invoked",
                    capability_id=capability_id,
                    retry_count=attempt - 1,
                ),
                *self._trace(
                    state,
                    "invoke_specialist",
                    TraceEventType.ADAPTER_SUCCEEDED,
                    "Specialist completed and returned a typed result envelope.",
                    token=f"{attempt_id}:succeeded",
                    capability_id=capability_id,
                    result_id=envelope.run_id,
                    retry_count=attempt - 1,
                    duration_ms=max(0, round((perf_counter() - timer) * 1000)),
                ),
            )
            return {
                "specialist_attempts": (result,),
                "capability_states": {capability_id: runtime},
                "trace": trace,
                "invocation_log": (capability_id,),
            }
        except Exception as exc:  # isolate the specialist boundary
            failure_kind = self._failure_kind(exc)
            error = DealError(
                f"error:{attempt_id}",
                "SPECIALIST_INVOCATION_FAILED",
                self.services.registry.capability(capability_id).project_id,
                capability_id,
                failure_kind is not FailureKind.BLOCKING,
                failure_kind is FailureKind.RETRYABLE,
                str(exc),
                "specialist_execution",
                (("exception_type", type(exc).__name__), ("attempt", str(attempt))),
            )
            runtime = replace(
                self._transition(runtime, ExecutionStatus.FAILED, str(exc), attempt),
                attempts=max(runtime.attempts, attempt),
                last_error_id=error.error_id,
            )
            result = SpecialistAttemptResult(
                attempt_id,
                capability_id,
                attempt,
                rerun_iteration,
                started,
                datetime.now(UTC),
                error=error,
                failure_kind=failure_kind,
            )
            return {
                "specialist_attempts": (result,),
                "capability_states": {capability_id: runtime},
                "trace": self._trace(
                    state,
                    "invoke_specialist",
                    TraceEventType.ADAPTER_FAILED,
                    f"Specialist failed with policy {failure_kind.value}.",
                    token=f"{attempt_id}:failed",
                    capability_id=capability_id,
                    retry_count=attempt - 1,
                    duration_ms=max(0, round((perf_counter() - timer) * 1000)),
                ),
                "invocation_log": (capability_id,),
            }

    def collect_results(self, state: GraphState) -> GraphState:
        processed = set(state.get("processed_attempt_ids", ()))
        new_attempts = tuple(
            item
            for item in state.get("specialist_attempts", ())
            if item.attempt_id not in processed
        )
        deal_state = state["deal_state"]
        errors = list(state.get("errors", ()))
        retries: list[str] = []
        retry_counts = dict(state.get("retry_counts", {}))
        runtimes = dict(state.get("capability_states", {}))
        trace: list[GraphTraceEvent] = []
        for item in new_attempts:
            if item.succeeded:
                assert item.envelope is not None
                prior_revision = deal_state.revision
                deal_state = ingest_result(deal_state, item.envelope)
                if deal_state.revision != prior_revision:
                    trace.extend(
                        self._trace(
                            state,
                            "collect_results",
                            TraceEventType.RESULT_INGESTED,
                            "Typed specialist result ingested into canonical DealState.",
                            token=item.attempt_id,
                            capability_id=item.capability_id,
                            result_id=item.envelope.run_id,
                        )
                    )
                continue
            assert item.error is not None
            errors.append(item.error)
            retry_counts[item.capability_id] = item.attempt
            if (
                item.failure_kind is FailureKind.RETRYABLE
                and item.attempt < self.policy.retry.max_attempts
            ):
                retries.append(item.capability_id)
                runtimes[item.capability_id] = self._transition(
                    runtimes[item.capability_id],
                    ExecutionStatus.READY,
                    "Retryable failure; bounded retry scheduled.",
                    item.attempt,
                )
                trace.extend(
                    self._trace(
                        state,
                        "collect_results",
                        TraceEventType.RETRY_SCHEDULED,
                        "Retryable adapter failure scheduled for one bounded retry.",
                        token=item.attempt_id,
                        capability_id=item.capability_id,
                        retry_count=item.attempt,
                        branch="retry",
                    )
                )
        return {
            "deal_state": deal_state,
            "errors": tuple({item.error_id: item for item in errors}.values()),
            "processed_attempt_ids": tuple(item.attempt_id for item in new_attempts),
            "pending_retry_capabilities": tuple(dict.fromkeys(retries)),
            "retry_counts": retry_counts,
            "capability_states": runtimes,
            "trace": tuple(trace),
        }

    def route_after_collection(self, state: GraphState) -> str:
        if state.get("pending_retry_capabilities"):
            return "dispatch_retries"
        if state.get("rerun_capabilities"):
            return "finish_rerun"
        return "complete_stage"

    def route_retry_workers(self, state: GraphState) -> list[Send] | str:
        capabilities = state.get("pending_retry_capabilities", ())
        if not capabilities:
            return "complete_stage"
        sends = [
            self._send(
                state,
                capability,
                state.get("retry_counts", {}).get(capability, 0) + 1,
                state.get("rerun_iteration", 0),
            )
            for capability in capabilities
        ]
        return sends

    def clear_retry_queue(self, state: GraphState) -> GraphState:
        del state
        return {"pending_retry_capabilities": ()}

    def complete_stage(self, state: GraphState) -> GraphState:
        return {
            "stage_index": state.get("stage_index", 0) + 1,
            "active_stage_capabilities": (),
            "pending_retry_capabilities": (),
        }

    def reconcile_outputs(self, state: GraphState) -> GraphState:
        result = self.services.reconciler.reconcile(state["deal_state"])
        updated = self.services.reconciler.apply_staleness(state["deal_state"], result)
        return {
            "deal_state": updated,
            "reconciliation": result,
            "status": OrchestrationStatus.RECONCILING,
            "trace": self._trace(
                state,
                "reconcile_outputs",
                TraceEventType.RECONCILED,
                (
                    f"M3 reconciliation produced {len(result.snapshot.issues)} issues and "
                    f"{len(result.snapshot.recomputation_requests)} recomputation requests."
                ),
                token=f"r{state.get('rerun_iteration', 0)}",
                status=OrchestrationStatus.RECONCILING,
            ),
        }

    def detect_human_review(self, state: GraphState) -> GraphState:
        if state.get("review_iteration", 0) >= self.policy.max_review_iterations:
            return {
                "active_review": None,
                "warnings": (
                    *state.get("warnings", ()),
                    "Maximum analyst review iterations reached; unresolved items were retained.",
                ),
            }
        reviewed = set(state.get("reviewed_subject_ids", ()))
        candidates = self._review_candidates(state)
        active = next((item for item in candidates if item.review_id not in reviewed), None)
        if active is None:
            return {"active_review": None}
        return {
            "active_review": active,
            "status": OrchestrationStatus.REVIEW_REQUIRED,
            "trace": self._trace(
                state,
                "detect_human_review",
                TraceEventType.REVIEW_INTERRUPTED,
                active.summary,
                token=active.review_id,
                status=OrchestrationStatus.REVIEW_REQUIRED,
                branch="human_review",
            ),
        }

    def human_review(self, state: GraphState) -> GraphState:
        review = state["active_review"]
        if review is None:
            return {}
        raw: HumanReviewInput = interrupt(
            self.review_payload(review), response_schema=HumanReviewInput
        )
        try:
            action = ReviewDecisionAction(raw["action"])
            if raw["review_id"] != review.review_id:
                raise ValueError("review response does not match the active review")
            if action not in {item.action for item in review.options}:
                raise ValueError(f"action {action.value} is not valid for this review")
            reviewer = raw["reviewer"].strip()
            rationale = raw["rationale"].strip()
            if not reviewer or not rationale:
                raise ValueError("reviewer and rationale are required")
        except (KeyError, TypeError, ValueError) as exc:
            error = DealError(
                f"error:{state['run_id']}:review:{review.review_id}",
                "INVALID_REVIEW_DECISION",
                ProjectId.PROJECT_6,
                None,
                False,
                False,
                str(exc),
                "analyst_review",
            )
            return {
                "status": OrchestrationStatus.FAILED,
                "errors": (*state.get("errors", ()), error),
                "active_review": None,
            }
        resulting_action = self._resulting_action(review, action)
        audit = ReviewAuditEvent(
            f"audit:{review.review_id}:{state.get('review_iteration', 0) + 1}",
            review.review_id,
            review.issue_ids,
            state["run_id"],
            OrchestrationStatus.REVIEW_REQUIRED,
            tuple(item.action for item in review.options),
            action,
            rationale,
            reviewer,
            datetime.now(UTC),
            resulting_action,
        )
        deal_state = self._apply_review_decisions(
            state["deal_state"], review, action, reviewer, rationale, raw.get("selected_metric_id")
        )
        reruns = self._reruns_for(state, review, action)
        status = (
            OrchestrationStatus.CANCELLED
            if action is ReviewDecisionAction.CANCEL
            else OrchestrationStatus.RUNNING
        )
        return {
            "deal_state": deal_state,
            "status": status,
            "active_review": None,
            "review_history": (*state.get("review_history", ()), audit),
            "reviewed_subject_ids": (*state.get("reviewed_subject_ids", ()), review.review_id),
            "review_iteration": state.get("review_iteration", 0) + 1,
            "rerun_capabilities": reruns,
            "trace": self._trace(
                state,
                "human_review",
                TraceEventType.REVIEW_RESUMED,
                f"Analyst selected {action.value}; {resulting_action}.",
                token=audit.audit_id,
                status=status,
                branch=resulting_action,
            ),
        }

    def prepare_rerun(self, state: GraphState) -> GraphState:
        iteration = state.get("rerun_iteration", 0) + 1
        runtimes = dict(state.get("capability_states", {}))
        trace: list[GraphTraceEvent] = []
        for capability in state.get("rerun_capabilities", ()):
            runtimes[capability] = self._transition(
                runtimes[capability], ExecutionStatus.READY, "Analyst-approved rerun."
            )
            trace.extend(
                self._trace(
                    state,
                    "prepare_rerun",
                    TraceEventType.RERUN_SCHEDULED,
                    "Analyst-approved specialist rerun scheduled.",
                    token=f"{iteration}:{capability}",
                    capability_id=capability,
                    branch="rerun",
                )
            )
        return {
            "rerun_iteration": iteration,
            "active_stage_capabilities": state.get("rerun_capabilities", ()),
            "capability_states": runtimes,
            "trace": tuple(trace),
        }

    def route_rerun_workers(self, state: GraphState) -> list[Send] | str:
        capabilities = state.get("rerun_capabilities", ())
        if not capabilities:
            return "reconcile_outputs"
        return [
            self._send(state, capability, 1, state.get("rerun_iteration", 0))
            for capability in capabilities
        ]

    def finish_rerun(self, state: GraphState) -> GraphState:
        del state
        return {
            "rerun_capabilities": (),
            "active_stage_capabilities": (),
            "pending_retry_capabilities": (),
        }

    def finalize_run(self, state: GraphState) -> GraphState:
        status = state.get("status", OrchestrationStatus.FAILED)
        runtimes = state.get("capability_states", {})
        completed = tuple(
            capability
            for capability, runtime in runtimes.items()
            if runtime.status
            in {ExecutionStatus.COMPLETED, ExecutionStatus.COMPLETED_WITH_WARNINGS}
        )
        failed = tuple(
            capability
            for capability, runtime in runtimes.items()
            if runtime.status is ExecutionStatus.FAILED
        )
        skipped = tuple(
            capability
            for capability, runtime in runtimes.items()
            if runtime.status in {ExecutionStatus.SKIPPED, ExecutionStatus.BLOCKED}
        )
        if status not in {
            OrchestrationStatus.FAILED,
            OrchestrationStatus.WAITING_FOR_INPUT,
            OrchestrationStatus.CANCELLED,
        }:
            if failed and completed:
                status = OrchestrationStatus.COMPLETED_WITH_WARNINGS
            elif not completed:
                status = OrchestrationStatus.FAILED
            elif state.get("errors") or state.get("warnings") or state["deal_state"].warnings:
                status = OrchestrationStatus.COMPLETED_WITH_WARNINGS
            else:
                status = OrchestrationStatus.COMPLETED
        workflow_status = self._workflow_status(status)
        deal_state = replace(state["deal_state"], workflow_status=workflow_status)
        self.assert_invariants(state, deal_state, status)
        ready = status in {
            OrchestrationStatus.COMPLETED,
            OrchestrationStatus.COMPLETED_WITH_WARNINGS,
            OrchestrationStatus.PARTIALLY_COMPLETED,
        }
        terminal = OrchestrationTerminalResult(
            state["run_id"],
            status,
            deal_state,
            state.get("reconciliation"),
            completed,
            failed,
            skipped,
            len(state.get("warnings", ())) + len(deal_state.warnings),
            len(state.get("errors", ())) + len(deal_state.errors),
            ready,
            f"Run terminated with status {status.value}.",
        )
        return {
            "status": status,
            "deal_state": deal_state,
            "terminal_result": terminal,
            "trace": self._trace(
                state,
                "finalize_run",
                TraceEventType.TERMINATED,
                terminal.message,
                token=status.value,
                status=status,
            ),
        }

    def assert_invariants(
        self,
        state: GraphState,
        deal_state: DealState | None = None,
        terminal_status: OrchestrationStatus | None = None,
    ) -> None:
        canonical = deal_state or state["deal_state"]
        evidence_ids = {item.evidence_id for item in canonical.evidence}
        for attempt in state.get("specialist_attempts", ()):
            if attempt.envelope is None:
                continue
            envelope = attempt.envelope
            if envelope.source_project is None:
                raise GraphInvariantError("completed specialist result must identify its project")
            missing = set(envelope.evidence_refs) - evidence_ids
            if missing:
                raise GraphInvariantError(f"ingestion lost evidence references: {sorted(missing)}")
            self._assert_payload_values_preserved(envelope, canonical)
        if state.get("rerun_iteration", 0) and not any(
            item.selected_action
            in {ReviewDecisionAction.RUN_ADJUSTED, ReviewDecisionAction.RUN_BOTH}
            for item in state.get("review_history", ())
        ):
            raise GraphInvariantError("material specialist rerun requires an analyst decision")
        if terminal_status is OrchestrationStatus.COMPLETED and state.get("errors"):
            raise GraphInvariantError("COMPLETED cannot hide recorded orchestration errors")
        if terminal_status in {
            OrchestrationStatus.COMPLETED,
            OrchestrationStatus.COMPLETED_WITH_WARNINGS,
            OrchestrationStatus.PARTIALLY_COMPLETED,
        }:
            nonterminal = {
                capability: runtime.status
                for capability, runtime in state.get("capability_states", {}).items()
                if runtime.status
                in {
                    ExecutionStatus.NOT_STARTED,
                    ExecutionStatus.READY,
                    ExecutionStatus.RUNNING,
                }
            }
            if nonterminal:
                raise GraphInvariantError(
                    f"terminal state contains unfinished capabilities: {nonterminal}"
                )
        plan = state.get("execution_plan")
        selected = {step.capability_id for step in plan.steps} if plan is not None else set()
        if terminal_status is OrchestrationStatus.COMPLETED and any(
            runtime.status
            not in {ExecutionStatus.COMPLETED, ExecutionStatus.COMPLETED_WITH_WARNINGS}
            for capability, runtime in state.get("capability_states", {}).items()
            if capability in selected
        ):
            raise GraphInvariantError(
                "COMPLETED requires every planned capability to finish successfully"
            )

    @staticmethod
    def review_payload(review: AnalystReviewRequest) -> dict[str, object]:
        return {
            "review_id": review.review_id,
            "issue": review.title,
            "summary": review.summary,
            "conflicting_values": list(review.conflicting_values),
            "affected_outputs": list(review.affected_output_ids),
            "evidence_refs": list(review.evidence_refs),
            "available_decisions": [
                {
                    "action": option.action.value,
                    "label": option.label,
                    "resulting_action": option.resulting_action,
                }
                for option in review.options
            ],
        }

    def _review_candidates(self, state: GraphState) -> tuple[AnalystReviewRequest, ...]:
        result = state["reconciliation"]
        issues = result.snapshot.issues
        now = datetime.now(UTC)
        candidates: list[AnalystReviewRequest] = []
        ebitda_issues = tuple(
            issue
            for issue in issues
            if issue.analyst_review_required
            and (
                "ebitda" in issue.description.casefold()
                or issue.issue_type
                in {
                    ReconciliationIssueType.BASIS_MISMATCH,
                    ReconciliationIssueType.STALE_RESULT,
                    ReconciliationIssueType.DILIGENCE_IMPACT,
                }
            )
        )
        if ebitda_issues:
            metrics = tuple(
                item
                for item in state["deal_state"].financial_metrics
                if item.metric_type.casefold() == "ebitda"
            )
            candidates.append(
                AnalystReviewRequest(
                    f"review:{state['run_id']}:ebitda-basis",
                    state["run_id"],
                    tuple(item.issue_id for item in ebitda_issues),
                    "ebitda-basis",
                    "EBITDA basis mismatch",
                    "Reported and diligence-adjusted EBITDA affect the valuation scenario.",
                    tuple(
                        (
                            f"{item.source_project.value}: {item.value} {item.unit} "
                            f"({item.basis.value})"
                        )
                        for item in metrics
                    ),
                    tuple(
                        dict.fromkeys(
                            output
                            for issue in ebitda_issues
                            for output in issue.affected_output_ids
                        )
                    ),
                    tuple(
                        dict.fromkeys(
                            evidence for issue in ebitda_issues for evidence in issue.evidence_refs
                        )
                    ),
                    (
                        ReviewOption(
                            ReviewDecisionAction.KEEP_REPORTED,
                            "Keep reported EBITDA valuation",
                            "retain_reported_scenario",
                        ),
                        ReviewOption(
                            ReviewDecisionAction.RUN_ADJUSTED,
                            "Run diligence-adjusted scenario",
                            "rerun_project_3",
                        ),
                        ReviewOption(
                            ReviewDecisionAction.RUN_BOTH,
                            "Run both scenarios",
                            "rerun_project_3_and_retain_history",
                        ),
                        ReviewOption(
                            ReviewDecisionAction.DEFER,
                            "Defer decision",
                            "continue_with_unresolved_issue",
                        ),
                    ),
                    now,
                )
            )
        for finding in result.snapshot.diligence_findings:
            if finding.status is FindingStatus.UNDER_REVIEW and finding.severity in {
                FindingSeverity.HIGH,
                FindingSeverity.CRITICAL,
            }:
                candidates.append(
                    AnalystReviewRequest(
                        f"review:{state['run_id']}:finding:{finding.finding_id}",
                        state["run_id"],
                        (),
                        finding.finding_id,
                        finding.title,
                        "A material diligence finding remains under analyst review.",
                        (f"Severity: {finding.severity.value}",),
                        finding.deal_impacts,
                        finding.evidence_refs,
                        (
                            ReviewOption(
                                ReviewDecisionAction.ACCEPT,
                                "Accept risk for current analysis",
                                "continue_with_recorded_risk",
                            ),
                            ReviewOption(
                                ReviewDecisionAction.DEFER,
                                "Defer pending more information",
                                "continue_with_open_question",
                            ),
                            ReviewOption(
                                ReviewDecisionAction.CANCEL,
                                "Cancel run",
                                "cancel_run",
                            ),
                        ),
                        now,
                    )
                )
        grouped_issue_ids = {item for review in candidates for item in review.issue_ids}
        for item in result.snapshot.review_queue:
            remaining = tuple(issue for issue in item.issue_ids if issue not in grouped_issue_ids)
            if not remaining:
                continue
            issue_by_id = {issue.issue_id: issue for issue in issues}
            selected_issues = tuple(
                issue_by_id[issue] for issue in remaining if issue in issue_by_id
            )
            candidates.append(self._generic_review(state, item.subject_id, selected_issues, now))
        return tuple(candidates)

    @staticmethod
    def _generic_review(
        state: GraphState,
        subject_id: str,
        issues: tuple[ReconciliationIssue, ...],
        requested_at: datetime,
    ) -> AnalystReviewRequest:
        return AnalystReviewRequest(
            f"review:{state['run_id']}:{subject_id}",
            state["run_id"],
            tuple(item.issue_id for item in issues),
            subject_id,
            "Reconciliation judgment required",
            issues[0].description if issues else "Analyst judgment is required.",
            (),
            tuple(dict.fromkeys(output for item in issues for output in item.affected_output_ids)),
            tuple(dict.fromkeys(evidence for item in issues for evidence in item.evidence_refs)),
            (
                ReviewOption(
                    ReviewDecisionAction.ACCEPT,
                    "Accept current interpretation",
                    "resolve_and_continue",
                ),
                ReviewOption(
                    ReviewDecisionAction.CONTINUE_WITH_WARNINGS,
                    "Continue with warnings",
                    "continue_with_warning",
                ),
                ReviewOption(
                    ReviewDecisionAction.DEFER,
                    "Defer decision",
                    "retain_open_issue",
                ),
            ),
            requested_at,
        )

    def _apply_review_decisions(
        self,
        deal_state: DealState,
        review: AnalystReviewRequest,
        action: ReviewDecisionAction,
        reviewer: str,
        rationale: str,
        selected_metric_id: str | None,
    ) -> DealState:
        if action in {ReviewDecisionAction.DEFER, ReviewDecisionAction.CANCEL}:
            return deal_state
        selected = selected_metric_id
        if action is ReviewDecisionAction.KEEP_REPORTED:
            selected = self._metric_for_basis(deal_state, MetricBasis.REPORTED)
        elif action is ReviewDecisionAction.RUN_ADJUSTED:
            selected = self._metric_for_basis(deal_state, MetricBasis.ADJUSTED)
        decision_action = (
            DecisionAction.SELECT
            if action in {ReviewDecisionAction.KEEP_REPORTED, ReviewDecisionAction.RUN_ADJUSTED}
            else DecisionAction.APPROVE
        )
        subjects = review.issue_ids or (review.subject_id,)
        decisions = tuple(
            AnalystDecision(
                f"decision:{review.review_id}:{index}",
                "reconciliation_issue" if review.issue_ids else "diligence_finding",
                subject,
                "review_required",
                decision_action,
                rationale,
                reviewer,
                datetime.now(UTC),
                selected,
            )
            for index, subject in enumerate(subjects, 1)
        )
        existing = {item.decision_id for item in deal_state.analyst_decisions}
        additions = tuple(item for item in decisions if item.decision_id not in existing)
        return replace(
            deal_state,
            analyst_decisions=(*deal_state.analyst_decisions, *additions),
            revision=deal_state.revision + (1 if additions else 0),
            updated_at=datetime.now(UTC) if additions else deal_state.updated_at,
        )

    @staticmethod
    def _metric_for_basis(deal_state: DealState, basis: MetricBasis) -> str | None:
        return next(
            (
                item.metric_id
                for item in deal_state.financial_metrics
                if item.metric_type.casefold() == "ebitda" and item.basis is basis
            ),
            None,
        )

    @staticmethod
    def _reruns_for(
        state: GraphState,
        review: AnalystReviewRequest,
        action: ReviewDecisionAction,
    ) -> tuple[str, ...]:
        if action not in {ReviewDecisionAction.RUN_ADJUSTED, ReviewDecisionAction.RUN_BOTH}:
            return ()
        requests = state["reconciliation"].snapshot.recomputation_requests
        affected = set(review.affected_output_ids)
        return tuple(
            dict.fromkeys(
                item.target_capability
                for item in requests
                if item.source_output_id in affected or "ebitda" in item.stale_because.casefold()
            )
        )

    @staticmethod
    def _resulting_action(review: AnalystReviewRequest, action: ReviewDecisionAction) -> str:
        option = next(item for item in review.options if item.action is action)
        return option.resulting_action

    def _send(
        self, state: GraphState, capability_id: str, attempt: int, rerun_iteration: int
    ) -> Send:
        return Send(
            "invoke_specialist",
            {
                "run_id": state["run_id"],
                "thread_id": state["thread_id"],
                "status": OrchestrationStatus.RUNNING,
                "execution_plan": state["execution_plan"],
                "deal_state": state["deal_state"],
                "capability_states": state["capability_states"],
                "worker_capability_id": capability_id,
                "worker_attempt": attempt,
                "worker_rerun_iteration": rerun_iteration,
            },
        )

    @staticmethod
    def _transition(
        runtime: CapabilityRuntimeState,
        status: ExecutionStatus,
        reason: str,
        attempt: int = 0,
    ) -> CapabilityRuntimeState:
        transition = CapabilityTransition(status, datetime.now(UTC), reason, attempt)
        if runtime.transitions and runtime.transitions[-1] == transition:
            return runtime
        return replace(
            runtime,
            status=status,
            transitions=(*runtime.transitions, transition),
            attempts=max(runtime.attempts, attempt),
        )

    @staticmethod
    def _failure_kind(error: Exception) -> FailureKind:
        if isinstance(error, (TransientAdapterError, TimeoutError, ConnectionError)):
            return FailureKind.RETRYABLE
        if isinstance(error, (KeyError, TypeError, ValueError)):
            return FailureKind.BLOCKING
        return FailureKind.NONBLOCKING

    @staticmethod
    def _assert_payload_values_preserved(
        envelope: ProjectResultEnvelope[Any], deal_state: DealState
    ) -> None:
        payload = envelope.payload
        payload_metrics = getattr(payload, "financial_metrics", ())
        canonical_metrics = {item.metric_id: item for item in deal_state.financial_metrics}
        for metric in payload_metrics:
            canonical_metric = canonical_metrics.get(metric.metric_id)
            if canonical_metric is not None and canonical_metric.value != metric.value:
                raise GraphInvariantError(f"orchestration mutated metric {metric.metric_id}")
        payload_valuations = getattr(payload, "valuations", ())
        canonical_valuations = {item.valuation_id: item for item in deal_state.valuation_outputs}
        for valuation in payload_valuations:
            canonical_valuation = canonical_valuations.get(valuation.valuation_id)
            if canonical_valuation is not None and (
                canonical_valuation.low,
                canonical_valuation.midpoint,
                canonical_valuation.high,
            ) != (valuation.low, valuation.midpoint, valuation.high):
                raise GraphInvariantError(
                    f"orchestration mutated valuation {valuation.valuation_id}"
                )

    @staticmethod
    def _workflow_status(status: OrchestrationStatus) -> WorkflowStatus:
        mapping = {
            OrchestrationStatus.WAITING_FOR_INPUT: WorkflowStatus.WAITING_FOR_INPUT,
            OrchestrationStatus.REVIEW_REQUIRED: WorkflowStatus.REVIEW_REQUIRED,
            OrchestrationStatus.PARTIALLY_COMPLETED: WorkflowStatus.PARTIALLY_COMPLETED,
            OrchestrationStatus.COMPLETED: WorkflowStatus.COMPLETED,
            OrchestrationStatus.COMPLETED_WITH_WARNINGS: WorkflowStatus.COMPLETED_WITH_WARNINGS,
            OrchestrationStatus.FAILED: WorkflowStatus.FAILED,
            OrchestrationStatus.CANCELLED: WorkflowStatus.FAILED,
        }
        return mapping.get(status, WorkflowStatus.FAILED)

    @staticmethod
    def _request_error(state: GraphState, code: str, message: str) -> DealError:
        return DealError(
            f"error:{state['run_id']}:{code.casefold()}",
            code,
            ProjectId.PROJECT_6,
            None,
            False,
            False,
            message,
            "user_request",
        )

    @staticmethod
    def _trace(
        state: GraphState,
        node: str,
        event_type: TraceEventType,
        message: str,
        *,
        token: str,
        status: OrchestrationStatus | None = None,
        capability_id: str | None = None,
        result_id: str | None = None,
        retry_count: int = 0,
        branch: str | None = None,
        duration_ms: int | None = None,
    ) -> tuple[GraphTraceEvent, ...]:
        resolved_status = status or state.get("status", OrchestrationStatus.RUNNING)
        entered = GraphTraceEvent(
            f"trace:{state['run_id']}:{node}:{TraceEventType.NODE_ENTERED.value}:{token}",
            state["run_id"],
            node,
            TraceEventType.NODE_ENTERED,
            resolved_status,
            datetime.now(UTC),
            f"Entered {node}.",
            capability_id,
            result_id,
            retry_count,
            branch,
        )
        event = GraphTraceEvent(
            f"trace:{state['run_id']}:{node}:{event_type.value}:{token}",
            state["run_id"],
            node,
            event_type,
            resolved_status,
            datetime.now(UTC),
            message,
            capability_id,
            result_id,
            retry_count,
            branch,
            duration_ms,
        )
        return (entered, event) if event_type is not TraceEventType.NODE_ENTERED else (event,)
