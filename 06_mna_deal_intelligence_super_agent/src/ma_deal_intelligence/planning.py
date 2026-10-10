"""Deterministic capability planning from classified M&A requests."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ma_deal_intelligence.contracts import CapabilityId
from ma_deal_intelligence.intent import DealIntent, IntentClassification
from ma_deal_intelligence.registry import CapabilityRegistry
from ma_deal_intelligence.requests import UserDealRequest
from ma_deal_intelligence.state import DealState


class PlanStepStatus(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class NormalizedPlanningRequest:
    request_id: str
    query: str
    intents: tuple[DealIntent, ...]
    target_entity_id: str | None
    target_name: str | None
    buyer_entity_id: str | None
    sectors: tuple[str, ...]
    geographies: tuple[str, ...]
    requested_methods: tuple[str, ...]
    requested_workstreams: tuple[str, ...]
    constraints: tuple[str, ...]
    available_inputs: frozenset[str]


@dataclass(frozen=True, slots=True)
class ClarificationRequirement:
    missing_field: str
    reason: str
    blocking: bool
    suggested_question: str
    capability_id: str | None = None


@dataclass(frozen=True, slots=True)
class PlanStep:
    step_id: str
    capability_id: str
    project_id: str
    depends_on: tuple[str, ...]
    rationale: str
    expected_outputs: tuple[str, ...]
    status: PlanStepStatus
    missing_inputs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExecutionStage:
    stage_number: int
    step_ids: tuple[str, ...]
    parallelizable: bool


@dataclass(frozen=True, slots=True)
class SkippedCapability:
    capability_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class PlanIssue:
    code: str
    message: str
    capability_id: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    plan_id: str
    request: NormalizedPlanningRequest
    steps: tuple[PlanStep, ...]
    stages: tuple[ExecutionStage, ...]
    skipped_capabilities: tuple[SkippedCapability, ...]
    required_user_inputs: tuple[ClarificationRequirement, ...]
    expected_outputs: tuple[str, ...]
    warnings: tuple[PlanIssue, ...] = ()
    errors: tuple[PlanIssue, ...] = ()

    @property
    def executable(self) -> bool:
        return not self.errors and not any(item.blocking for item in self.required_user_inputs)


class PlanValidationError(ValueError):
    pass


_INTENT_CAPABILITIES: dict[DealIntent, tuple[str, ...]] = {
    DealIntent.COMPANY_RESEARCH: (CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE,),
    DealIntent.FIND_TARGETS: (CapabilityId.P2_SOURCE_TARGETS,),
    DealIntent.SCREEN_TARGETS: (CapabilityId.P2_SCREEN_TARGETS,),
    DealIntent.VALUE_TARGET: (CapabilityId.P3_PRODUCE_VALUATION_RANGE,),
    DealIntent.RUN_TRADING_COMPS: (CapabilityId.P3_PRODUCE_VALUATION_RANGE,),
    DealIntent.RUN_PRECEDENTS: (CapabilityId.P4_PRODUCE_VALUATION_RANGE,),
    DealIntent.RUN_DUE_DILIGENCE: (CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS,),
    DealIntent.EVALUATE_ACQUISITION: (
        CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE,
        CapabilityId.P3_PRODUCE_VALUATION_RANGE,
        CapabilityId.P4_PRODUCE_VALUATION_RANGE,
        CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS,
    ),
    DealIntent.COMPARE_VALUATION_METHODS: (
        CapabilityId.P3_PRODUCE_VALUATION_RANGE,
        CapabilityId.P4_PRODUCE_VALUATION_RANGE,
    ),
    DealIntent.INVESTIGATE_RISK: (CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS,),
    DealIntent.FULL_DEAL_ANALYSIS: (
        CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE,
        CapabilityId.P3_PRODUCE_VALUATION_RANGE,
        CapabilityId.P4_PRODUCE_VALUATION_RANGE,
        CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS,
    ),
}

_RATIONALES = {
    CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE: "Company and document evidence is needed.",
    CapabilityId.P2_SOURCE_TARGETS: "The request asks to discover acquisition candidates.",
    CapabilityId.P2_SCREEN_TARGETS: "The request asks to screen or rank candidates.",
    CapabilityId.P3_PRODUCE_VALUATION_RANGE: "The request needs trading-comps valuation.",
    CapabilityId.P4_PRODUCE_VALUATION_RANGE: "The request needs historical transaction evidence.",
    CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS: "The request needs VDR diligence or risk findings.",
}


def normalize_request(
    request: UserDealRequest, classification: IntentClassification, state: DealState
) -> NormalizedPlanningRequest:
    target_id = (
        request.target.canonical_entity_id
        if request.target
        else state.deal_context.target_entity_id
    )
    target_name = None
    if request.target is not None:
        target_name = request.target.display_name or request.target.legal_name
    elif target_id is None:
        target = next(
            (item for item in classification.extracted_entities if item.role == "target"), None
        )
        if target is not None:
            target_name = target.name
            target_id = f"entity:unresolved:{_slug(target.name)}"
    buyer_id = (
        request.buyer.canonical_entity_id if request.buyer else state.deal_context.buyer_entity_id
    )
    classified = dict(classification.extracted_constraints)
    sectors = state.deal_context.sectors or tuple(
        value for key, value in classification.extracted_constraints if key == "sector"
    )
    geographies = state.deal_context.geographies or tuple(
        value for key, value in classification.extracted_constraints if key == "geography"
    )
    available: set[str] = set()
    if target_id:
        available.add("target_entity")
    if state.source_documents:
        available.add("documents")
    if state.financial_metrics or state.company_intelligence:
        available.add("target_financials")
    if state.deal_context.reporting_currency or request.reporting_currency:
        available.add("reporting_currency")
    if sectors:
        available.add("sector_context")
    if sectors or geographies or request.constraints:
        available.add("acquisition_criteria")
    if request.user_query.strip():
        available.add("question")
    methods = tuple(
        method
        for method, intent in (
            ("trading_comps", DealIntent.RUN_TRADING_COMPS),
            ("precedents", DealIntent.RUN_PRECEDENTS),
        )
        if intent in classification.intents
    )
    del classified
    return NormalizedPlanningRequest(
        request.request_id,
        request.user_query,
        classification.intents,
        target_id,
        target_name,
        buyer_id,
        sectors,
        geographies,
        methods,
        (),
        request.constraints,
        frozenset(available),
    )


class ExecutionPlanner:
    def __init__(self, registry: CapabilityRegistry) -> None:
        self.registry = registry

    def build(
        self,
        request: UserDealRequest,
        classification: IntentClassification,
        state: DealState,
    ) -> ExecutionPlan:
        normalized = normalize_request(request, classification, state)
        if not normalized.intents:
            return ExecutionPlan(
                f"plan:{request.request_id}",
                normalized,
                (),
                (),
                (),
                (),
                (),
                errors=(PlanIssue("AMBIGUOUS_INTENT", "A supported intent is required."),),
            )
        selected: list[str] = []
        for intent in normalized.intents:
            selected.extend(str(item) for item in _INTENT_CAPABILITIES[intent])
        selected = list(dict.fromkeys(selected))

        # Finding targets followed by valuation needs candidate enrichment before valuation.
        if (
            CapabilityId.P2_SOURCE_TARGETS in selected
            and CapabilityId.P3_PRODUCE_VALUATION_RANGE in selected
            and CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE not in selected
        ):
            selected.insert(
                selected.index(CapabilityId.P3_PRODUCE_VALUATION_RANGE),
                CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE,
            )

        # Project 1 can supply missing financial or sector context when documents are present.
        need_p1 = any(
            item in selected
            for item in (
                CapabilityId.P3_PRODUCE_VALUATION_RANGE,
                CapabilityId.P4_PRODUCE_VALUATION_RANGE,
            )
        ) and (
            "target_financials" not in normalized.available_inputs
            or "sector_context" not in normalized.available_inputs
        )
        if need_p1 and CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE not in selected:
            selected.insert(0, CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE)

        dependencies: dict[str, set[str]] = {item: set() for item in selected}
        if CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE in selected:
            if (
                CapabilityId.P3_PRODUCE_VALUATION_RANGE in selected
                and "target_financials" not in normalized.available_inputs
            ):
                dependencies[str(CapabilityId.P3_PRODUCE_VALUATION_RANGE)].add(
                    str(CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE)
                )
            if (
                CapabilityId.P4_PRODUCE_VALUATION_RANGE in selected
                and "sector_context" not in normalized.available_inputs
            ):
                dependencies[str(CapabilityId.P4_PRODUCE_VALUATION_RANGE)].add(
                    str(CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE)
                )
        if CapabilityId.P2_SOURCE_TARGETS in selected:
            for downstream in (
                CapabilityId.P1_EXTRACT_COMPANY_INTELLIGENCE,
                CapabilityId.P3_PRODUCE_VALUATION_RANGE,
                CapabilityId.P4_PRODUCE_VALUATION_RANGE,
                CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS,
            ):
                if downstream in selected and normalized.target_entity_id is None:
                    dependencies[str(downstream)].add(str(CapabilityId.P2_SOURCE_TARGETS))

        warnings: list[PlanIssue] = []
        skipped: list[SkippedCapability] = []
        steps: list[PlanStep] = []
        unavailable: set[str] = set()
        for capability_id in selected:
            health = self.registry.health(capability_id)
            if not health.healthy:
                unavailable.add(capability_id)
                skipped.append(
                    SkippedCapability(capability_id, health.message or "adapter unavailable")
                )
                warnings.append(
                    PlanIssue(
                        "CAPABILITY_UNAVAILABLE",
                        health.message or "adapter unavailable",
                        capability_id,
                    )
                )
        for capability_id in dependencies:
            dependencies[capability_id].difference_update(unavailable)

        available = set(normalized.available_inputs)
        step_statuses: dict[str, PlanStepStatus] = {}
        for capability_id in selected:
            if capability_id in unavailable:
                continue
            metadata = self.registry.capability(capability_id)
            missing = set(metadata.required_inputs) - available
            for dependency in dependencies[capability_id]:
                if step_statuses.get(dependency) is not PlanStepStatus.READY:
                    continue
                produced = set(self.registry.capability(dependency).produced_outputs)
                missing -= produced
                if "target_candidates" in produced:
                    missing.discard("target_entity")
            status = PlanStepStatus.BLOCKED if missing else PlanStepStatus.READY
            step_statuses[capability_id] = status
            steps.append(
                PlanStep(
                    f"step:{request.request_id}:{capability_id}",
                    capability_id,
                    metadata.project_id.value,
                    tuple(sorted(dependencies[capability_id])),
                    _RATIONALES[CapabilityId(capability_id)],
                    metadata.produced_outputs,
                    status,
                    tuple(sorted(missing)),
                )
            )
            if status is PlanStepStatus.READY:
                available.update(metadata.produced_outputs)

        clarifications = tuple(
            ClarificationRequirement(
                missing,
                f"{step.capability_id} requires {missing}.",
                True,
                _question_for(missing),
                step.capability_id,
            )
            for step in steps
            for missing in step.missing_inputs
        )
        if normalized.target_entity_id is not None:
            skipped.append(
                SkippedCapability(
                    str(CapabilityId.P2_SOURCE_TARGETS), "A target is already specified."
                )
            )
        elif not any(
            item in selected
            for item in (CapabilityId.P2_SOURCE_TARGETS, CapabilityId.P2_SCREEN_TARGETS)
        ):
            skipped.append(
                SkippedCapability(
                    str(CapabilityId.P2_SOURCE_TARGETS),
                    "The request does not ask for target discovery.",
                )
            )
        if CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS not in selected:
            skipped.append(
                SkippedCapability(
                    str(CapabilityId.P5_PRODUCE_DILIGENCE_FINDINGS),
                    "The request does not ask for diligence.",
                )
            )

        stages = _build_stages(tuple(steps))
        plan = ExecutionPlan(
            f"plan:{request.request_id}",
            normalized,
            tuple(steps),
            stages,
            tuple(_dedupe_skips(skipped)),
            clarifications,
            tuple(dict.fromkeys(output for step in steps for output in step.expected_outputs)),
            tuple(warnings),
        )
        self.validate(plan)
        return plan

    def validate(self, plan: ExecutionPlan) -> None:
        ids = {step.capability_id for step in plan.steps}
        for step in plan.steps:
            self.registry.capability(step.capability_id)
            unknown = set(step.depends_on) - ids
            if unknown:
                raise PlanValidationError(
                    f"unresolvable dependencies for {step.capability_id}: {sorted(unknown)}"
                )
        _topological_levels({step.capability_id: set(step.depends_on) for step in plan.steps})


def _build_stages(steps: tuple[PlanStep, ...]) -> tuple[ExecutionStage, ...]:
    levels = _topological_levels({step.capability_id: set(step.depends_on) for step in steps})
    step_ids = {step.capability_id: step.step_id for step in steps}
    return tuple(
        ExecutionStage(
            index,
            tuple(step_ids[capability] for capability in level),
            len(level) > 1,
        )
        for index, level in enumerate(levels, 1)
    )


def _topological_levels(graph: dict[str, set[str]]) -> tuple[tuple[str, ...], ...]:
    remaining = {node: set(dependencies) for node, dependencies in graph.items()}
    levels: list[tuple[str, ...]] = []
    while remaining:
        ready = tuple(sorted(node for node, dependencies in remaining.items() if not dependencies))
        if not ready:
            raise PlanValidationError("dependency cycle detected")
        levels.append(ready)
        for node in ready:
            del remaining[node]
        for dependencies in remaining.values():
            dependencies.difference_update(ready)
    return tuple(levels)


def validate_dependency_graph(graph: dict[str, set[str]]) -> None:
    _topological_levels(graph)


def _question_for(input_name: str) -> str:
    return {
        "target_entity": "Which target company should be analyzed?",
        "documents": "Which indexed documents or VDR files should be used?",
        "target_financials": "Which target financial profile should be used?",
        "reporting_currency": "Which reporting currency should be used?",
        "sector_context": "Which sector should define the precedent search?",
        "acquisition_criteria": "What sector, geography, or acquisition criteria should be used?",
    }.get(input_name, f"Please provide {input_name}.")


def _dedupe_skips(items: list[SkippedCapability]) -> tuple[SkippedCapability, ...]:
    return tuple({item.capability_id: item for item in items}.values())


def _slug(value: str) -> str:
    return "-".join(
        part
        for part in "".join(
            character.lower() if character.isalnum() else " " for character in value
        ).split()
    )
