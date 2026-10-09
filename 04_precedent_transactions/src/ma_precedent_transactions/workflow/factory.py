"""Offline V1 workflow composition using fixture providers and existing services."""

from __future__ import annotations

from pathlib import Path

from ma_precedent_transactions.demo import PROJECT_ROOT, build_fixture_pipeline
from ma_precedent_transactions.extraction import (
    FixtureStructuredExtractor,
    StructuredTransactionService,
    VerifiedTransactionRecord,
)
from ma_precedent_transactions.precedent import (
    FixtureValuationExplanationProvider,
    PrecedentAnalysisService,
    build_precedent_fixture_inputs,
)
from ma_precedent_transactions.workflow.graph import WorkflowApplication, build_workflow
from ma_precedent_transactions.workflow.models import RetryPolicy
from ma_precedent_transactions.workflow.services import WorkflowServices


def build_offline_services(project_root: Path = PROJECT_ROOT) -> WorkflowServices:
    extraction = StructuredTransactionService(
        FixtureStructuredExtractor(project_root / "data" / "fixtures" / "extraction_responses.json")
    )

    def prepare(
        records: dict[str, VerifiedTransactionRecord],
    ) -> tuple[VerifiedTransactionRecord, ...]:
        return build_precedent_fixture_inputs(records)[2]

    return WorkflowServices(
        build_fixture_pipeline(),
        extraction,
        PrecedentAnalysisService(),
        prepare,
        FixtureValuationExplanationProvider(),
    )


def build_offline_application(
    *, retry_policy: RetryPolicy | None = None, project_root: Path = PROJECT_ROOT
) -> WorkflowApplication:
    return WorkflowApplication(
        build_workflow(
            build_offline_services(project_root),
            retry_policy=retry_policy,
        )
    )
