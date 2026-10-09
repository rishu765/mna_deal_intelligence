"""Checkpointed LangGraph construction and start/resume facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from ma_precedent_transactions.workflow.checkpointing import TrustedLocalSerializer
from ma_precedent_transactions.workflow.models import (
    HumanReviewDecision,
    HumanReviewInput,
    RetryPolicy,
    WorkflowRequest,
    WorkflowState,
    WorkflowStatus,
)
from ma_precedent_transactions.workflow.nodes import WorkflowNodes
from ma_precedent_transactions.workflow.services import WorkflowServices

CompiledWorkflow = CompiledStateGraph[WorkflowState, None, WorkflowState, WorkflowState]


def build_workflow(
    services: WorkflowServices,
    *,
    retry_policy: RetryPolicy | None = None,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledWorkflow:
    nodes = WorkflowNodes(services, retry_policy or RetryPolicy())
    builder = StateGraph(WorkflowState)
    builder.add_node("validate_input", nodes.validate_input)
    builder.add_node("research_deals", nodes.research_deals)
    builder.add_node("extract_and_verify", nodes.extract_and_verify)
    builder.add_node("route_for_human_review", nodes.route_for_human_review)
    builder.add_node("human_review", nodes.human_review)
    builder.add_node("select_precedents", nodes.select_precedents)
    builder.add_node("calculate_valuation", nodes.calculate_valuation)
    builder.add_node("generate_explanation", nodes.generate_explanation)
    builder.add_node("evaluate_run", nodes.evaluate_run)
    builder.add_node("finalize", nodes.finalize)

    builder.add_edge(START, "validate_input")
    builder.add_conditional_edges(
        "validate_input", _route_failed, {"continue": "research_deals", "finalize": "finalize"}
    )
    builder.add_conditional_edges(
        "research_deals",
        _route_research,
        {"retry": "research_deals", "continue": "extract_and_verify", "finalize": "finalize"},
    )
    builder.add_conditional_edges(
        "extract_and_verify",
        _route_extraction,
        {
            "retry": "extract_and_verify",
            "continue": "route_for_human_review",
            "finalize": "finalize",
        },
    )
    builder.add_conditional_edges(
        "route_for_human_review",
        _route_review_required,
        {"review": "human_review", "continue": "select_precedents"},
    )
    builder.add_conditional_edges(
        "human_review",
        _route_failed,
        {"continue": "select_precedents", "finalize": "finalize"},
    )
    builder.add_conditional_edges(
        "select_precedents",
        _route_failed,
        {"continue": "calculate_valuation", "finalize": "finalize"},
    )
    builder.add_conditional_edges(
        "calculate_valuation",
        _route_failed,
        {"continue": "generate_explanation", "finalize": "finalize"},
    )
    builder.add_edge("generate_explanation", "evaluate_run")
    builder.add_edge("evaluate_run", "finalize")
    builder.add_edge("finalize", END)
    saver = checkpointer or InMemorySaver(serde=TrustedLocalSerializer())
    return builder.compile(checkpointer=saver, name="precedent_transactions_workflow")


@dataclass(frozen=True, slots=True)
class WorkflowApplication:
    graph: CompiledWorkflow

    def start(self, request: WorkflowRequest, *, thread_id: str) -> WorkflowState:
        initial: WorkflowState = {
            "request": request,
            "status": WorkflowStatus.INITIALIZED,
            "failure_code": None,
            "warnings": (),
            "errors": (),
            "retry_counts": {},
            "retry_stage": None,
            "trace": (),
        }
        return cast(WorkflowState, self.graph.invoke(initial, config=_config(thread_id)))

    def resume(self, *, thread_id: str, decision: HumanReviewDecision) -> WorkflowState:
        response: HumanReviewInput = {
            "action": decision.action.value,
            "reviewer": decision.reviewer,
            "rationale": decision.rationale,
        }
        if decision.resolutions:
            response["resolutions"] = [
                {
                    "transaction_id": item.transaction_id,
                    "field": item.field,
                    "selected_observation_id": item.selected_observation_id,
                    "rationale": item.rationale,
                }
                for item in decision.resolutions
            ]
        if decision.overrides:
            response["overrides"] = [
                {
                    "transaction_id": item.transaction_id,
                    "action": item.action.value,
                    "rationale": item.rationale,
                }
                for item in decision.overrides
            ]
        return cast(
            WorkflowState,
            self.graph.invoke(Command(resume=response), config=_config(thread_id)),
        )

    def state(self, *, thread_id: str) -> WorkflowState:
        return cast(WorkflowState, self.graph.get_state(_config(thread_id)).values)


def _config(thread_id: str) -> RunnableConfig:
    if not thread_id.strip():
        raise ValueError("thread_id must not be blank")
    return cast(RunnableConfig, {"configurable": {"thread_id": thread_id.strip()}})


def _route_failed(state: WorkflowState) -> Literal["continue", "finalize"]:
    return (
        "finalize"
        if state.get("status") in {WorkflowStatus.FAILED, WorkflowStatus.REJECTED}
        else "continue"
    )


def _route_research(state: WorkflowState) -> Literal["retry", "continue", "finalize"]:
    if state.get("retry_stage") == "research":
        return "retry"
    return _route_failed(state)


def _route_extraction(state: WorkflowState) -> Literal["retry", "continue", "finalize"]:
    if state.get("retry_stage") == "extraction":
        return "retry"
    return _route_failed(state)


def _route_review_required(state: WorkflowState) -> Literal["review", "continue"]:
    return "review" if state.get("status") is WorkflowStatus.AWAITING_HUMAN_REVIEW else "continue"
