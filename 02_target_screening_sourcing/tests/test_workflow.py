from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ma_target_screening.discovery import CandidateDiscoveryService, LocalDatasetDiscoveryProvider
from ma_target_screening.discovery.models import CandidateDiscoveryResult
from ma_target_screening.domain import CandidateCompany
from ma_target_screening.enrichment import (
    CandidateEnrichmentService,
    StructuredFixtureEnrichmentProvider,
)
from ma_target_screening.errors import DiscoveryUnavailableError, EnrichmentError, StrategicFitError
from ma_target_screening.profile import CandidateProfile
from ma_target_screening.screening import (
    FixtureStrategicFitProvider,
    ScreeningRankingService,
    StrategicFitService,
)
from ma_target_screening.screening.models import Shortlist
from ma_target_screening.thesis import AcquisitionThesis
from ma_target_screening.workflow import (
    HumanReviewDecision,
    RetryPolicy,
    ReviewDecision,
    WorkflowApplication,
    WorkflowStatus,
    build_workflow,
)

ROOT = Path(__file__).parents[1]
THESIS_PATH = ROOT / "examples" / "screening-ranking-demo.json"
DISCOVERY_DATA = ROOT / "data" / "discovery_companies.json"
ENRICHMENT_DATA = ROOT / "data" / "enrichment_profiles.json"
STRATEGIC_DATA = ROOT / "data" / "strategic_fit_assessments.json"


def thesis() -> AcquisitionThesis:
    return AcquisitionThesis.from_json(THESIS_PATH.read_text(encoding="utf-8"))


def discovery_service() -> CandidateDiscoveryService:
    return CandidateDiscoveryService((LocalDatasetDiscoveryProvider(DISCOVERY_DATA),))


def enrichment_service() -> CandidateEnrichmentService:
    return CandidateEnrichmentService((StructuredFixtureEnrichmentProvider(ENRICHMENT_DATA),))


def screening_service() -> ScreeningRankingService:
    return ScreeningRankingService(StrategicFitService(FixtureStrategicFitProvider(STRATEGIC_DATA)))


def application(
    *,
    discovery: object | None = None,
    enrichment: object | None = None,
    screening: object | None = None,
    retry_policy: RetryPolicy | None = None,
) -> WorkflowApplication:
    return WorkflowApplication(
        build_workflow(
            discovery=discovery or discovery_service(),  # type: ignore[arg-type]
            enrichment=enrichment or enrichment_service(),  # type: ignore[arg-type]
            screening=screening or screening_service(),  # type: ignore[arg-type]
            retry_policy=retry_policy,
        )
    )


def empty_discovery(active_thesis: AcquisitionThesis) -> CandidateDiscoveryResult:
    return CandidateDiscoveryResult(
        thesis_id=active_thesis.thesis_id,
        queries=(),
        candidates=(),
        provider_names=("empty-fixture",),
        warnings=("No fixture candidates matched.",),
        raw_candidate_count=0,
        deduplicated_candidate_count=0,
    )


@dataclass
class StaticDiscovery:
    result: CandidateDiscoveryResult

    def discover(self, thesis: AcquisitionThesis) -> CandidateDiscoveryResult:
        assert thesis.thesis_id == self.result.thesis_id
        return self.result


@dataclass
class FlakyDiscovery:
    result: CandidateDiscoveryResult
    failures: int
    calls: int = 0

    def discover(self, thesis: AcquisitionThesis) -> CandidateDiscoveryResult:
        self.calls += 1
        if self.calls <= self.failures:
            raise DiscoveryUnavailableError("temporary discovery outage")
        return self.result


@dataclass
class PartialEnrichment:
    delegate: CandidateEnrichmentService
    failing_domain: str
    calls: int = 0

    def enrich(self, candidate: CandidateCompany, thesis: AcquisitionThesis) -> CandidateProfile:
        self.calls += 1
        if candidate.website_domain == self.failing_domain:
            raise EnrichmentError("fixture record temporarily unavailable")
        return self.delegate.enrich(candidate, thesis)


@dataclass
class CountingEnrichment:
    delegate: CandidateEnrichmentService
    calls: int = 0

    def enrich(self, candidate: CandidateCompany, thesis: AcquisitionThesis) -> CandidateProfile:
        self.calls += 1
        return self.delegate.enrich(candidate, thesis)


@dataclass
class FlakyScreening:
    delegate: ScreeningRankingService
    failures: int
    calls: int = 0

    def build_shortlist(
        self, thesis: AcquisitionThesis, profiles: tuple[CandidateProfile, ...]
    ) -> Shortlist:
        self.calls += 1
        if self.calls <= self.failures:
            raise StrategicFitError("temporary semantic provider failure")
        return self.delegate.build_shortlist(thesis, profiles)


def test_graph_happy_path_pauses_checkpoints_and_resumes_with_approval() -> None:
    app = application()
    paused = app.start(thesis(), thread_id="happy-path")

    assert paused["status"] is WorkflowStatus.AWAITING_HUMAN_REVIEW
    assert paused["provisional_shortlist"].ranked_candidates
    assert app.state(thread_id="happy-path")["thesis"].thesis_id == thesis().thesis_id

    complete = app.resume(
        thread_id="happy-path",
        decision=HumanReviewDecision(
            ReviewDecision.APPROVE,
            reviewer_notes="Evidence reviewed and shortlist approved.",
        ),
    )

    assert complete["status"] is WorkflowStatus.APPROVED
    assert complete["final_result"].final_shortlist.ranked_candidates
    assert [event.node for event in complete["final_result"].trace] == [
        "validate_thesis",
        "discover_candidates",
        "enrich_candidates",
        "screen_and_rank",
        "prepare_human_review",
        "human_review",
        "finalize",
    ]
    serialized = complete["final_result"].to_dict()
    assert json.loads(json.dumps(serialized))["status"] == "approved"


def test_approval_can_retain_selected_candidates_without_losing_audit_results() -> None:
    app = application()
    paused = app.start(thesis(), thread_id="selective-approval")
    first = paused["provisional_shortlist"].ranked_candidates[0]
    identifier = first.result.profile.candidate.website_domain
    assert identifier is not None

    complete = app.resume(
        thread_id="selective-approval",
        decision=HumanReviewDecision(ReviewDecision.APPROVE, approved_candidates=(identifier,)),
    )
    result = complete["final_result"].final_shortlist

    assert len(result.ranked_candidates) == 1
    assert result.ranked_candidates[0].rank == 1
    assert result.ranked_candidates[0].result.profile.candidate.website_domain == identifier
    assert len(result.screening_results) > len(result.ranked_candidates)


def test_no_candidate_path_reaches_review_and_can_be_approved_as_empty() -> None:
    active_thesis = thesis()
    app = application(discovery=StaticDiscovery(empty_discovery(active_thesis)))
    paused = app.start(active_thesis, thread_id="no-candidates")

    assert paused["status"] is WorkflowStatus.AWAITING_HUMAN_REVIEW
    assert not paused["provisional_shortlist"].ranked_candidates
    assert "No candidate profiles were supplied." in paused["provisional_shortlist"].warnings

    complete = app.resume(
        thread_id="no-candidates",
        decision=HumanReviewDecision(ReviewDecision.APPROVE),
    )
    assert complete["final_result"].status is WorkflowStatus.APPROVED
    assert not complete["final_result"].final_shortlist.ranked_candidates


def test_partial_enrichment_keeps_successful_profiles_and_warning() -> None:
    partial = PartialEnrichment(enrichment_service(), "payflow.example")
    app = application(enrichment=partial)
    paused = app.start(thesis(), thread_id="partial-enrichment")

    assert paused["status"] is WorkflowStatus.AWAITING_HUMAN_REVIEW
    assert len(paused["profiles"]) == len(paused["candidates"]) - 1
    assert any("partial results" in warning for warning in paused["warnings"])
    assert any(issue.stage == "enrichment" for issue in paused["errors"])


def test_all_hard_failed_candidate_is_retained_for_review_but_not_shortlisted() -> None:
    active_thesis = thesis()
    discovered = discovery_service().discover(active_thesis)
    consumer = next(
        item for item in discovered.candidates if item.website_domain == "consumercredit.example"
    )
    one_candidate = CandidateDiscoveryResult(
        thesis_id=active_thesis.thesis_id,
        queries=discovered.queries,
        candidates=(consumer,),
        provider_names=discovered.provider_names,
        warnings=(),
        raw_candidate_count=1,
        deduplicated_candidate_count=1,
    )
    app = application(discovery=StaticDiscovery(one_candidate))
    paused = app.start(active_thesis, thread_id="all-hard-fail")

    shortlist = paused["provisional_shortlist"]
    assert not shortlist.ranked_candidates
    assert len(shortlist.screening_results) == 1
    assert "No candidate remained shortlist-eligible" in shortlist.warnings[0]


def test_transient_discovery_and_semantic_failures_retry_then_recover() -> None:
    active_thesis = thesis()
    discovered = discovery_service().discover(active_thesis)
    flaky_discovery = FlakyDiscovery(discovered, failures=1)
    flaky_screening = FlakyScreening(screening_service(), failures=1)
    app = application(discovery=flaky_discovery, screening=flaky_screening)

    paused = app.start(active_thesis, thread_id="recoverable-failures")

    assert paused["status"] is WorkflowStatus.AWAITING_HUMAN_REVIEW
    assert flaky_discovery.calls == 2
    assert flaky_screening.calls == 2
    assert paused["retry_counts"] == {"discovery": 1, "screening": 1}
    assert len(paused["errors"]) == 2
    assert all(issue.recoverable for issue in paused["errors"])


def test_retry_limit_produces_terminal_failure_without_human_interrupt() -> None:
    active_thesis = thesis()
    unavailable = FlakyDiscovery(empty_discovery(active_thesis), failures=3)
    app = application(
        discovery=unavailable,
        retry_policy=RetryPolicy(discovery=1, enrichment=0, screening=0),
    )

    complete = app.start(active_thesis, thread_id="retry-exhausted")

    assert complete["status"] is WorkflowStatus.FAILED
    assert complete["final_result"].status is WorkflowStatus.FAILED
    assert unavailable.calls == 2
    assert complete["errors"][-1].recoverable is False
    assert "prepare_human_review" not in {event.node for event in complete["final_result"].trace}


def test_rejection_finishes_with_empty_shortlist_and_preserved_screening_audit() -> None:
    app = application()
    app.start(thesis(), thread_id="rejected")
    complete = app.resume(
        thread_id="rejected",
        decision=HumanReviewDecision(
            ReviewDecision.REJECT, reviewer_notes="Evidence is not sufficient."
        ),
    )

    result = complete["final_result"]
    assert result.status is WorkflowStatus.REJECTED
    assert not result.final_shortlist.ranked_candidates
    assert result.final_shortlist.screening_results


def test_human_rerun_repeats_enrichment_and_pauses_again_before_approval() -> None:
    enrichment = CountingEnrichment(enrichment_service())
    app = application(enrichment=enrichment)
    app.start(thesis(), thread_id="human-rerun")
    initial_calls = enrichment.calls

    second_pause = app.resume(
        thread_id="human-rerun",
        decision=HumanReviewDecision(
            ReviewDecision.RERUN, reviewer_notes="Refresh the evidence once."
        ),
    )

    assert second_pause["status"] is WorkflowStatus.AWAITING_HUMAN_REVIEW
    assert enrichment.calls == initial_calls * 2
    assert second_pause["retry_counts"]["human_rerun"] == 1

    complete = app.resume(
        thread_id="human-rerun",
        decision=HumanReviewDecision(ReviewDecision.APPROVE),
    )
    assert complete["status"] is WorkflowStatus.APPROVED


def test_human_rerun_limit_is_bounded() -> None:
    app = application(retry_policy=RetryPolicy(human_reruns=0))
    app.start(thesis(), thread_id="human-rerun-limit")
    complete = app.resume(
        thread_id="human-rerun-limit",
        decision=HumanReviewDecision(ReviewDecision.RERUN),
    )

    assert complete["status"] is WorkflowStatus.FAILED
    assert complete["final_result"].errors[-1].stage == "human_review"
