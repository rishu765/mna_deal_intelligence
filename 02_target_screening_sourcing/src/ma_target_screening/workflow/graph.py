"""LangGraph construction and a small programmatic start/resume facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from ma_target_screening.thesis import AcquisitionThesis
from ma_target_screening.workflow.checkpointing import TrustedLocalSerializer
from ma_target_screening.workflow.models import (
    HumanReviewDecision,
    HumanReviewInput,
    RetryPolicy,
    ReviewDecision,
    WorkflowState,
    WorkflowStatus,
)
from ma_target_screening.workflow.nodes import WorkflowNodes
from ma_target_screening.workflow.ports import (
    DiscoveryWorkflowService,
    EnrichmentWorkflowService,
    ScreeningWorkflowService,
)

CompiledWorkflow = CompiledStateGraph[
    WorkflowState,
    None,
    WorkflowState,
    WorkflowState,
]


def build_workflow(
    *,
    discovery: DiscoveryWorkflowService,
    enrichment: EnrichmentWorkflowService,
    screening: ScreeningWorkflowService,
    retry_policy: RetryPolicy | None = None,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledWorkflow:
    """Compile the explicit M1-to-M6 workflow around existing services."""

    nodes = WorkflowNodes(discovery, enrichment, screening, retry_policy or RetryPolicy())
    builder = StateGraph(WorkflowState)
    builder.add_node("validate_thesis", nodes.validate_thesis)
    builder.add_node("discover_candidates", nodes.discover_candidates)
    builder.add_node("enrich_candidates", nodes.enrich_candidates)
    builder.add_node("screen_and_rank", nodes.screen_and_rank)
    builder.add_node("prepare_human_review", nodes.prepare_human_review)
    builder.add_node("human_review", nodes.human_review)
    builder.add_node("finalize", nodes.finalize)

    builder.add_edge(START, "validate_thesis")
    builder.add_conditional_edges(
        "validate_thesis",
        _route_validation,
        {"discover": "discover_candidates", "finalize": "finalize"},
    )
    builder.add_conditional_edges(
        "discover_candidates",
        _route_discovery,
        {
            "retry": "discover_candidates",
            "enrich": "enrich_candidates",
            "screen": "screen_and_rank",
            "finalize": "finalize",
        },
    )
    builder.add_conditional_edges(
        "enrich_candidates",
        _route_enrichment,
        {"retry": "enrich_candidates", "screen": "screen_and_rank"},
    )
    builder.add_conditional_edges(
        "screen_and_rank",
        _route_screening,
        {
            "retry": "screen_and_rank",
            "review": "prepare_human_review",
            "finalize": "finalize",
        },
    )
    builder.add_edge("prepare_human_review", "human_review")
    builder.add_conditional_edges(
        "human_review",
        _route_review,
        {"rerun": "enrich_candidates", "finalize": "finalize"},
    )
    builder.add_edge("finalize", END)
    saver = (
        checkpointer if checkpointer is not None else InMemorySaver(serde=TrustedLocalSerializer())
    )
    return builder.compile(checkpointer=saver, name="mna_target_screening_workflow")


@dataclass(frozen=True, slots=True)
class WorkflowApplication:
    """Drive a checkpointed graph without exposing LangGraph details to callers."""

    graph: CompiledWorkflow

    def start(self, thesis: AcquisitionThesis, *, thread_id: str) -> WorkflowState:
        initial: WorkflowState = {
            "thesis": thesis,
            "status": WorkflowStatus.INITIALIZED,
            "warnings": (),
            "errors": (),
            "retry_counts": {},
            "retry_stage": None,
            "trace": (),
        }
        return cast(WorkflowState, self.graph.invoke(initial, config=_config(thread_id)))

    def resume(self, *, thread_id: str, decision: HumanReviewDecision) -> WorkflowState:
        response: HumanReviewInput = {"decision": decision.decision.value}
        if decision.reviewer_notes is not None:
            response["reviewer_notes"] = decision.reviewer_notes
        if decision.approved_candidates:
            response["approved_candidates"] = list(decision.approved_candidates)
        if decision.rejected_candidates:
            response["rejected_candidates"] = list(decision.rejected_candidates)
        return cast(
            WorkflowState,
            self.graph.invoke(Command(resume=response), config=_config(thread_id)),
        )

    def state(self, *, thread_id: str) -> WorkflowState:
        snapshot = self.graph.get_state(_config(thread_id))
        return cast(WorkflowState, snapshot.values)


def _config(thread_id: str) -> RunnableConfig:
    normalized = thread_id.strip()
    if not normalized:
        raise ValueError("thread_id must not be blank")
    return cast(RunnableConfig, {"configurable": {"thread_id": normalized}})


def _route_validation(state: WorkflowState) -> Literal["discover", "finalize"]:
    return "finalize" if state.get("status") is WorkflowStatus.FAILED else "discover"


def _route_discovery(
    state: WorkflowState,
) -> Literal["retry", "enrich", "screen", "finalize"]:
    if state.get("retry_stage") == "discovery":
        return "retry"
    if state.get("status") is WorkflowStatus.FAILED:
        return "finalize"
    return "enrich" if state.get("candidates") else "screen"


def _route_enrichment(state: WorkflowState) -> Literal["retry", "screen"]:
    return "retry" if state.get("retry_stage") == "enrichment" else "screen"


def _route_screening(state: WorkflowState) -> Literal["retry", "review", "finalize"]:
    if state.get("retry_stage") == "screening":
        return "retry"
    if state.get("status") is WorkflowStatus.FAILED:
        return "finalize"
    return "review"


def _route_review(state: WorkflowState) -> Literal["rerun", "finalize"]:
    review = state.get("human_review")
    if (
        review is not None
        and review.decision is ReviewDecision.RERUN
        and state.get("status") is not WorkflowStatus.FAILED
    ):
        return "rerun"
    return "finalize"
