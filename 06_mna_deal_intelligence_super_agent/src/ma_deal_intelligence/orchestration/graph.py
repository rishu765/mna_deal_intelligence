"""Checkpointed LangGraph composition and Project 6 application facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from ma_deal_intelligence.orchestration.checkpointing import TrustedLocalSerializer
from ma_deal_intelligence.orchestration.models import (
    AnalystReviewSubmission,
    GraphState,
    HumanReviewInput,
    OrchestrationPolicy,
    OrchestrationStatus,
)
from ma_deal_intelligence.orchestration.nodes import OrchestrationNodes
from ma_deal_intelligence.orchestration.services import OrchestrationServices, default_services
from ma_deal_intelligence.requests import UserDealRequest
from ma_deal_intelligence.state import DealState

CompiledWorkflow = CompiledStateGraph[GraphState, None, GraphState, GraphState]


def build_workflow(
    services: OrchestrationServices | None = None,
    *,
    policy: OrchestrationPolicy | None = None,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledWorkflow:
    nodes = OrchestrationNodes(services or default_services(), policy or OrchestrationPolicy())
    builder = StateGraph(GraphState)
    builder.add_node("validate_request", nodes.validate_request)
    builder.add_node("classify_intent", nodes.classify_intent)
    builder.add_node("build_plan", nodes.build_plan)
    builder.add_node("validate_plan", nodes.validate_plan)
    builder.add_node("initialize_execution", nodes.initialize_execution)
    builder.add_node("prepare_stage", nodes.prepare_stage)
    builder.add_node("dispatch_stage", nodes.passthrough)
    builder.add_node("invoke_specialist", nodes.invoke_specialist)
    builder.add_node("collect_results", nodes.collect_results)
    builder.add_node("dispatch_retries", nodes.passthrough)
    builder.add_node("complete_stage", nodes.complete_stage)
    builder.add_node("reconcile_outputs", nodes.reconcile_outputs)
    builder.add_node("detect_human_review", nodes.detect_human_review)
    builder.add_node("human_review", nodes.human_review)
    builder.add_node("prepare_rerun", nodes.prepare_rerun)
    builder.add_node("dispatch_rerun", nodes.passthrough)
    builder.add_node("finish_rerun", nodes.finish_rerun)
    builder.add_node("finalize_run", nodes.finalize_run)

    builder.add_edge(START, "validate_request")
    builder.add_conditional_edges(
        "validate_request",
        _after_request_validation,
        {"continue": "classify_intent", "finalize": "finalize_run"},
    )
    builder.add_edge("classify_intent", "build_plan")
    builder.add_edge("build_plan", "validate_plan")
    builder.add_conditional_edges(
        "validate_plan",
        _after_plan_validation,
        {"continue": "initialize_execution", "finalize": "finalize_run"},
    )
    builder.add_edge("initialize_execution", "prepare_stage")
    builder.add_conditional_edges(
        "prepare_stage",
        _after_stage_preparation,
        {"dispatch": "dispatch_stage", "reconcile": "reconcile_outputs"},
    )
    builder.add_conditional_edges("dispatch_stage", nodes.route_stage_workers)
    builder.add_edge("invoke_specialist", "collect_results")
    builder.add_conditional_edges(
        "collect_results",
        nodes.route_after_collection,
        {
            "dispatch_retries": "dispatch_retries",
            "finish_rerun": "finish_rerun",
            "complete_stage": "complete_stage",
        },
    )
    builder.add_conditional_edges("dispatch_retries", nodes.route_retry_workers)
    builder.add_edge("complete_stage", "prepare_stage")
    builder.add_edge("finish_rerun", "reconcile_outputs")
    builder.add_edge("reconcile_outputs", "detect_human_review")
    builder.add_conditional_edges(
        "detect_human_review",
        _after_review_detection,
        {"review": "human_review", "finalize": "finalize_run"},
    )
    builder.add_conditional_edges(
        "human_review",
        _after_human_review,
        {
            "rerun": "prepare_rerun",
            "reconcile": "reconcile_outputs",
            "finalize": "finalize_run",
        },
    )
    builder.add_edge("prepare_rerun", "dispatch_rerun")
    builder.add_conditional_edges("dispatch_rerun", nodes.route_rerun_workers)
    builder.add_edge("finalize_run", END)

    saver = checkpointer or InMemorySaver(serde=TrustedLocalSerializer())
    return builder.compile(checkpointer=saver, name="mna_deal_intelligence_super_agent")


@dataclass(frozen=True, slots=True)
class SuperAgentApplication:
    graph: CompiledWorkflow

    def start(
        self,
        request: UserDealRequest,
        deal_state: DealState,
        *,
        thread_id: str,
        run_id: str | None = None,
    ) -> GraphState:
        normalized_thread = _identifier(thread_id, "thread_id")
        resolved_run = _identifier(run_id or f"run:{request.request_id}", "run_id")
        config = _config(normalized_thread)
        existing = self.graph.get_state(config).values
        if existing:
            raise ValueError(f"thread_id already has checkpointed state: {normalized_thread}")
        initial: GraphState = {
            "run_id": resolved_run,
            "thread_id": normalized_thread,
            "request": request,
            "deal_state": deal_state,
            "status": OrchestrationStatus.CREATED,
            "stage_index": 0,
            "active_stage_capabilities": (),
            "execution_complete": False,
            "capability_states": {},
            "specialist_attempts": (),
            "processed_attempt_ids": (),
            "pending_retry_capabilities": (),
            "retry_counts": {},
            "rerun_iteration": 0,
            "rerun_capabilities": (),
            "active_review": None,
            "review_history": (),
            "reviewed_subject_ids": (),
            "review_iteration": 0,
            "clarification": None,
            "errors": (),
            "warnings": (),
            "trace": (),
            "invocation_log": (),
        }
        return cast(GraphState, self.graph.invoke(initial, config=config))

    def resume(
        self,
        *,
        thread_id: str,
        submission: AnalystReviewSubmission,
    ) -> GraphState:
        response: HumanReviewInput = {
            "review_id": submission.review_id,
            "action": submission.action.value,
            "reviewer": submission.reviewer,
            "rationale": submission.rationale,
            "selected_metric_id": submission.selected_metric_id,
        }
        return cast(
            GraphState,
            self.graph.invoke(Command(resume=response), config=_config(thread_id)),
        )

    def state(self, *, thread_id: str) -> GraphState:
        return cast(GraphState, self.graph.get_state(_config(thread_id)).values)


def _after_request_validation(state: GraphState) -> Literal["continue", "finalize"]:
    return "finalize" if state.get("status") is OrchestrationStatus.FAILED else "continue"


def _after_plan_validation(state: GraphState) -> Literal["continue", "finalize"]:
    if state.get("status") in {
        OrchestrationStatus.FAILED,
        OrchestrationStatus.WAITING_FOR_INPUT,
    }:
        return "finalize"
    return "continue"


def _after_stage_preparation(state: GraphState) -> Literal["dispatch", "reconcile"]:
    return "reconcile" if state.get("execution_complete") else "dispatch"


def _after_review_detection(state: GraphState) -> Literal["review", "finalize"]:
    return "review" if state.get("active_review") is not None else "finalize"


def _after_human_review(state: GraphState) -> Literal["rerun", "reconcile", "finalize"]:
    if state.get("status") in {OrchestrationStatus.FAILED, OrchestrationStatus.CANCELLED}:
        return "finalize"
    if state.get("rerun_capabilities"):
        return "rerun"
    return "reconcile"


def _config(thread_id: str) -> RunnableConfig:
    return cast(
        RunnableConfig,
        {"configurable": {"thread_id": _identifier(thread_id, "thread_id")}},
    )


def _identifier(value: str, field: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} must not be blank")
    return normalized
