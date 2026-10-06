"""Offline subsystem evaluation runner for Project 2 V1."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ma_target_screening.composition import OfflinePaths, OfflineServices, build_offline_services
from ma_target_screening.discovery.models import CandidateDiscoveryResult
from ma_target_screening.domain import CandidateCompany
from ma_target_screening.errors import DiscoveryUnavailableError, EnrichmentError, StrategicFitError
from ma_target_screening.evaluation.dataset import EvaluationCase, EvaluationDataset
from ma_target_screening.evaluation.models import EvaluationReport, SubsystemEvaluation
from ma_target_screening.profile import CandidateProfile
from ma_target_screening.screening.models import CriterionOutcome, Shortlist
from ma_target_screening.thesis import AcquisitionThesis
from ma_target_screening.workflow import (
    HumanReviewDecision,
    RetryPolicy,
    ReviewDecision,
    WorkflowApplication,
    WorkflowStatus,
    build_workflow,
)
from ma_target_screening.workflow.ports import (
    EnrichmentWorkflowService,
    ScreeningWorkflowService,
)


@dataclass(frozen=True, slots=True)
class EvaluationRunner:
    project_root: Path
    services: OfflineServices

    @classmethod
    def offline(cls, project_root: Path) -> EvaluationRunner:
        return cls(
            project_root=project_root,
            services=build_offline_services(OfflinePaths.from_project_root(project_root)),
        )

    def run(self, dataset: EvaluationDataset) -> EvaluationReport:
        artifacts = tuple(self._artifacts(case) for case in dataset.cases)
        return EvaluationReport.create(
            dataset_version=dataset.schema_version,
            case_count=len(dataset.cases),
            subsystems=(
                self._thesis(dataset),
                self._discovery(dataset, artifacts),
                self._enrichment(dataset, artifacts),
                self._screening(dataset, artifacts),
                self._strategic_fit(dataset, artifacts),
                self._ranking(dataset, artifacts),
                self._workflow(dataset.cases[0]),
            ),
            limitations=(
                "The benchmark has five synthetic cases and does not establish external validity.",
                "Only the payments case has complete enrichment, semantic, and ranking "
                "gold labels.",
                "Discovery metrics measure the bundled six-company fixture rather than "
                "the open web.",
                "Strategic-fit labels are human-authored fixtures, not an independent "
                "expert panel.",
            ),
        )

    def _artifacts(self, case: EvaluationCase) -> _CaseArtifacts:
        discovery = self.services.discovery.discover(case.thesis)
        profiles = tuple(
            self.services.enrichment.enrich(candidate, case.thesis)
            for candidate in discovery.candidates
        )
        shortlist = self.services.screening.build_shortlist(case.thesis, profiles)
        return _CaseArtifacts(discovery, profiles, shortlist)

    @staticmethod
    def _thesis(dataset: EvaluationDataset) -> SubsystemEvaluation:
        expected = 0
        correct = 0
        preserved = 0
        for case in dataset.cases:
            restored = AcquisitionThesis.from_dict(case.thesis.to_dict())
            preserved += restored == case.thesis
            actual = {item.criterion_id: item.requirement for item in case.thesis.criteria}
            for criterion_id, requirement in case.expected_requirements:
                expected += 1
                correct += actual.get(criterion_id) is requirement
        return SubsystemEvaluation(
            "thesis",
            (
                ("schema_validity", 1.0),
                ("serialization_preservation", _ratio(preserved, len(dataset.cases))),
                ("requirement_classification_accuracy", _ratio(correct, expected)),
            ),
            strengths=("All five theses validate and preserve typed criteria through JSON.",),
            weaknesses=("Natural-language extraction is intentionally outside V1.",),
        )

    @staticmethod
    def _discovery(
        dataset: EvaluationDataset, artifacts: tuple[_CaseArtifacts, ...]
    ) -> SubsystemEvaluation:
        true_positive = 0
        retrieved = 0
        relevant = 0
        raw = 0
        deduplicated = 0
        evidence_total = 0
        evidence_present = 0
        evaluated_cases = 0
        failures: list[str] = []
        for case, artifact in zip(dataset.cases, artifacts, strict=True):
            domains = {
                item.website_domain for item in artifact.discovery.candidates if item.website_domain
            }
            gold = set(case.relevant_domains)
            if gold:
                evaluated_cases += 1
                true_positive += len(domains & gold)
                retrieved += len(domains)
                relevant += len(gold)
                missed = sorted(gold - domains)
                if missed:
                    failures.append(f"{case.case_id} missed: {', '.join(missed)}")
            raw += artifact.discovery.raw_candidate_count
            deduplicated += artifact.discovery.deduplicated_candidate_count
            for candidate in artifact.discovery.candidates:
                evidence_total += 1
                evidence_present += bool(candidate.discovery_evidence)
        duplicate_rate = 0.0 if raw == 0 else (raw - deduplicated) / raw
        return SubsystemEvaluation(
            "discovery",
            (
                ("evaluated_case_count", float(evaluated_cases)),
                ("recall", _ratio(true_positive, relevant)),
                ("precision", _ratio(true_positive, retrieved)),
                ("duplicate_rate_before_deduplication", duplicate_rate),
                ("provenance_coverage", _ratio(evidence_present, evidence_total)),
            ),
            strengths=("Every normalized candidate retains discovery provenance.",),
            weaknesses=("Precision and recall are measured on a six-company synthetic corpus.",),
            representative_failures=tuple(failures),
        )

    @staticmethod
    def _enrichment(
        dataset: EvaluationDataset, artifacts: tuple[_CaseArtifacts, ...]
    ) -> SubsystemEvaluation:
        assertions = 0
        correct = 0
        claims = 0
        supported = 0
        inferences = 0
        supported_inferences = 0
        financial = 0
        financial_complete = 0
        failures: list[str] = []
        for case, artifact in zip(dataset.cases, artifacts, strict=True):
            profiles = {_domain(item): item for item in artifact.profiles}
            for domain, expected in case.profile_expectations.items():
                profile = profiles.get(domain)
                if profile is None:
                    failures.append(f"{case.case_id}: missing profile {domain}")
                    continue
                facts = {item.field.value: item.value for item in profile.facts}
                for field, value in expected.get("facts", {}).items():
                    assertions += 1
                    matched = value.casefold() in facts.get(field, "").casefold()
                    correct += matched
                    if not matched:
                        failures.append(f"{case.case_id}/{domain}: fact mismatch for {field}")
                unknowns = {item.field.value for item in profile.unknown_fields}
                for field in expected.get("unknown_fields", []):
                    assertions += 1
                    matched = field in unknowns
                    correct += matched
                    if not matched:
                        failures.append(f"{case.case_id}/{domain}: missing unknown {field}")
                for expected_metric in expected.get("financial_metrics", []):
                    assertions += 1
                    matched = any(
                        all(getattr(metric, key) == value for key, value in expected_metric.items())
                        for metric in profile.financial_metrics
                    )
                    correct += matched
                    if not matched:
                        failures.append(f"{case.case_id}/{domain}: financial metadata mismatch")
            for profile in artifact.profiles:
                claims += (
                    len(profile.facts) + len(profile.inferences) + len(profile.financial_metrics)
                )
                supported += sum(bool(item.evidence) for item in profile.facts)
                supported += sum(bool(item.evidence) for item in profile.inferences)
                supported += sum(bool(item.evidence) for item in profile.financial_metrics)
                inferences += len(profile.inferences)
                supported_inferences += sum(bool(item.evidence) for item in profile.inferences)
                financial += len(profile.financial_metrics)
                financial_complete += sum(
                    bool(item.currency and item.unit and item.fiscal_period and item.evidence)
                    for item in profile.financial_metrics
                )
        return SubsystemEvaluation(
            "enrichment",
            (
                ("gold_assertion_accuracy", _ratio(correct, assertions)),
                ("claim_evidence_support", _ratio(supported, claims)),
                ("supported_inference_rate", _ratio(supported_inferences, inferences)),
                ("unsupported_inference_rate", 1.0 - _ratio(supported_inferences, inferences)),
                ("financial_metadata_completeness", _ratio(financial_complete, financial)),
            ),
            strengths=("Fixture facts, inferences, and financial metrics require evidence.",),
            weaknesses=("The AI target has no enrichment fixture and remains explicitly unknown.",),
            representative_failures=tuple(failures),
        )

    @staticmethod
    def _screening(
        dataset: EvaluationDataset, artifacts: tuple[_CaseArtifacts, ...]
    ) -> SubsystemEvaluation:
        expected = 0
        correct = 0
        unknown_expected = 0
        unknown_correct = 0
        failures: list[str] = []
        for case, artifact in zip(dataset.cases, artifacts, strict=True):
            results = {_domain(item.profile): item for item in artifact.shortlist.screening_results}
            for domain, criteria in case.screening_expectations.items():
                result = results.get(domain)
                if result is None:
                    failures.append(f"{case.case_id}: no screening result for {domain}")
                    continue
                evaluations = {item.criterion_id: item.outcome.value for item in result.evaluations}
                for criterion_id, outcome in criteria.items():
                    expected += 1
                    matched = evaluations.get(criterion_id) == outcome
                    correct += matched
                    if outcome == CriterionOutcome.UNKNOWN.value:
                        unknown_expected += 1
                        unknown_correct += matched
                    if not matched:
                        failures.append(
                            f"{case.case_id}/{domain}/{criterion_id}: "
                            f"expected {outcome}, got {evaluations.get(criterion_id)}"
                        )
        return SubsystemEvaluation(
            "screening",
            (
                ("criterion_outcome_agreement", _ratio(correct, expected)),
                ("unknown_handling_agreement", _ratio(unknown_correct, unknown_expected)),
            ),
            strengths=("Hard failures, exclusions, and unknowns are evaluated independently.",),
            representative_failures=tuple(failures),
        )

    @staticmethod
    def _strategic_fit(
        dataset: EvaluationDataset, artifacts: tuple[_CaseArtifacts, ...]
    ) -> SubsystemEvaluation:
        expected = 0
        correct = 0
        known = 0
        grounded = 0
        failures: list[str] = []
        for case, artifact in zip(dataset.cases, artifacts, strict=True):
            results = {_domain(item.profile): item for item in artifact.shortlist.screening_results}
            for domain, criteria in case.strategic_fit_expectations.items():
                result = results.get(domain)
                if result is None:
                    failures.append(f"{case.case_id}: no strategic result for {domain}")
                    continue
                evaluations = {item.criterion_id: item for item in result.strategic_fit.evaluations}
                for criterion_id, outcome in criteria.items():
                    expected += 1
                    evaluation = evaluations.get(criterion_id)
                    matched = evaluation is not None and evaluation.outcome.value == outcome
                    correct += matched
                    if not matched:
                        failures.append(
                            f"{case.case_id}/{domain}/{criterion_id}: semantic mismatch"
                        )
                for evaluation in evaluations.values():
                    if evaluation.outcome not in {
                        CriterionOutcome.UNKNOWN,
                        CriterionOutcome.NOT_APPLICABLE,
                    }:
                        known += 1
                        grounded += bool(evaluation.evidence)
        grounding = _ratio(grounded, known)
        return SubsystemEvaluation(
            "strategic_fit",
            (
                ("rubric_outcome_agreement", _ratio(correct, expected)),
                ("known_assessment_grounding_rate", grounding),
                ("unsupported_known_claim_rate", 1.0 - grounding),
            ),
            strengths=("Known semantic conclusions must cite profile evidence IDs.",),
            weaknesses=(
                "Rubric labels are curated fixtures rather than independent deal-team ratings.",
            ),
            representative_failures=tuple(failures),
        )

    def _ranking(
        self, dataset: EvaluationDataset, artifacts: tuple[_CaseArtifacts, ...]
    ) -> SubsystemEvaluation:
        top_expected = 0
        top_present = 0
        pairs = 0
        pair_correct = 0
        stable = 0
        stability_cases = 0
        failures: list[str] = []
        for case, artifact in zip(dataset.cases, artifacts, strict=True):
            if not case.expected_top_domains and not case.expected_pairs:
                continue
            ranked = [_domain(item.result.profile) for item in artifact.shortlist.ranked_candidates]
            top_expected += len(case.expected_top_domains)
            top_present += len(
                set(ranked[: len(case.expected_top_domains)]) & set(case.expected_top_domains)
            )
            positions = {domain: index for index, domain in enumerate(ranked)}
            for higher, lower in case.expected_pairs:
                pairs += 1
                matched = (
                    higher in positions
                    and lower in positions
                    and positions[higher] < positions[lower]
                )
                pair_correct += matched
                if not matched:
                    failures.append(f"{case.case_id}: expected {higher} above {lower}")
            second = self.services.screening.build_shortlist(case.thesis, artifact.profiles)
            second_ranked = [_domain(item.result.profile) for item in second.ranked_candidates]
            stability_cases += 1
            stable += ranked == second_ranked
        return SubsystemEvaluation(
            "ranking",
            (
                ("expected_top_k_inclusion", _ratio(top_present, top_expected)),
                ("pairwise_ordering_accuracy", _ratio(pair_correct, pairs)),
                ("deterministic_stability", _ratio(stable, stability_cases)),
            ),
            strengths=("Fixed inputs and fixed semantic outputs produce stable ranking.",),
            weaknesses=("Only one case has defensible full-order labels.",),
            representative_failures=tuple(failures),
        )

    def _workflow(self, case: EvaluationCase) -> SubsystemEvaluation:
        scenarios: list[tuple[str, WorkflowStatus, WorkflowStatus]] = []

        approval = self.services.workflow.start(case.thesis, thread_id="eval-happy")
        scenarios.append(
            (
                "happy_path",
                WorkflowStatus.AWAITING_HUMAN_REVIEW,
                approval["status"],
            )
        )
        approved = self.services.workflow.resume(
            thread_id="eval-happy",
            decision=HumanReviewDecision(ReviewDecision.APPROVE),
        )
        scenarios.append(("human_approval", WorkflowStatus.APPROVED, approved["status"]))
        rejection = self.services.workflow.start(case.thesis, thread_id="eval-reject")
        assert rejection["status"] is WorkflowStatus.AWAITING_HUMAN_REVIEW
        rejected = self.services.workflow.resume(
            thread_id="eval-reject",
            decision=HumanReviewDecision(ReviewDecision.REJECT),
        )
        scenarios.append(("human_rejection", WorkflowStatus.REJECTED, rejected["status"]))
        assert approval["status"] is WorkflowStatus.AWAITING_HUMAN_REVIEW

        empty = _EmptyDiscovery(case.thesis.thesis_id)
        empty_app = WorkflowApplication(
            build_workflow(
                discovery=empty,
                enrichment=self.services.enrichment,
                screening=self.services.screening,
            )
        )
        empty_app.start(case.thesis, thread_id="eval-empty")
        empty_done = empty_app.resume(
            thread_id="eval-empty", decision=HumanReviewDecision(ReviewDecision.APPROVE)
        )
        scenarios.append(("no_candidates", WorkflowStatus.APPROVED, empty_done["status"]))

        discovered = self.services.discovery.discover(case.thesis)
        consumer = next(
            item
            for item in discovered.candidates
            if item.website_domain == "consumercredit.example"
        )
        hard_fail_result = CandidateDiscoveryResult(
            thesis_id=case.thesis.thesis_id,
            queries=discovered.queries,
            candidates=(consumer,),
            provider_names=discovered.provider_names,
            warnings=(),
            raw_candidate_count=1,
            deduplicated_candidate_count=1,
        )
        hard_fail_app = WorkflowApplication(
            build_workflow(
                discovery=_StaticDiscovery(hard_fail_result),
                enrichment=self.services.enrichment,
                screening=self.services.screening,
            )
        )
        hard_fail = hard_fail_app.start(case.thesis, thread_id="eval-all-hard-fail")
        scenarios.append(
            (
                "all_hard_fail",
                WorkflowStatus.AWAITING_HUMAN_REVIEW,
                hard_fail["status"],
            )
        )

        partial = _PartialEnrichment(self.services.enrichment)
        partial_app = WorkflowApplication(
            build_workflow(
                discovery=self.services.discovery,
                enrichment=partial,
                screening=self.services.screening,
            )
        )
        partial_state = partial_app.start(case.thesis, thread_id="eval-partial")
        scenarios.append(
            ("partial_enrichment", WorkflowStatus.AWAITING_HUMAN_REVIEW, partial_state["status"])
        )

        flaky = _FlakyScreening(self.services.screening, failures=1)
        retry_app = WorkflowApplication(
            build_workflow(
                discovery=self.services.discovery,
                enrichment=self.services.enrichment,
                screening=flaky,
            )
        )
        retry_state = retry_app.start(case.thesis, thread_id="eval-semantic-retry")
        scenarios.append(
            ("semantic_retry_success", WorkflowStatus.AWAITING_HUMAN_REVIEW, retry_state["status"])
        )

        semantic_failed_app = WorkflowApplication(
            build_workflow(
                discovery=self.services.discovery,
                enrichment=self.services.enrichment,
                screening=_FlakyScreening(self.services.screening, failures=3),
                retry_policy=RetryPolicy(screening=1),
            )
        )
        semantic_failed = semantic_failed_app.start(case.thesis, thread_id="eval-semantic-failed")
        scenarios.append(("semantic_failure", WorkflowStatus.FAILED, semantic_failed["status"]))

        failed_app = WorkflowApplication(
            build_workflow(
                discovery=_UnavailableDiscovery(),
                enrichment=self.services.enrichment,
                screening=self.services.screening,
                retry_policy=RetryPolicy(discovery=1),
            )
        )
        failed = failed_app.start(case.thesis, thread_id="eval-retry-exhausted")
        scenarios.append(("retry_exhaustion", WorkflowStatus.FAILED, failed["status"]))

        actual = sum(expected is observed for _, expected, observed in scenarios)
        failures = tuple(
            f"{name}: expected {expected.value}, got {observed.value}"
            for name, expected, observed in scenarios
            if expected is not observed
        )
        return SubsystemEvaluation(
            "workflow",
            (
                ("scenario_count", float(len(scenarios))),
                ("final_state_accuracy", _ratio(actual, len(scenarios))),
                ("retry_recovery_accuracy", float(flaky.calls == 2)),
                (
                    "human_review_checkpoint_accuracy",
                    float(approval["status"] is WorkflowStatus.AWAITING_HUMAN_REVIEW),
                ),
            ),
            strengths=(
                "Approval, rejection, empty, partial, retry, and failure routes are "
                "reproducible offline.",
            ),
            representative_failures=failures,
        )


@dataclass(frozen=True, slots=True)
class _CaseArtifacts:
    discovery: CandidateDiscoveryResult
    profiles: tuple[CandidateProfile, ...]
    shortlist: Shortlist


@dataclass(frozen=True, slots=True)
class _EmptyDiscovery:
    thesis_id: str

    def discover(self, thesis: AcquisitionThesis) -> CandidateDiscoveryResult:
        return CandidateDiscoveryResult(thesis.thesis_id, (), (), ("evaluation-empty",), (), 0, 0)


@dataclass(frozen=True, slots=True)
class _StaticDiscovery:
    result: CandidateDiscoveryResult

    def discover(self, thesis: AcquisitionThesis) -> CandidateDiscoveryResult:
        if thesis.thesis_id != self.result.thesis_id:
            raise ValueError("static discovery thesis ID mismatch")
        return self.result


@dataclass(frozen=True, slots=True)
class _PartialEnrichment:
    delegate: EnrichmentWorkflowService

    def enrich(self, candidate: CandidateCompany, thesis: AcquisitionThesis) -> CandidateProfile:
        if candidate.website_domain == "payflow.example":
            raise EnrichmentError("synthetic partial-enrichment failure")
        return self.delegate.enrich(candidate, thesis)


@dataclass(slots=True)
class _FlakyScreening:
    delegate: ScreeningWorkflowService
    failures: int
    calls: int = 0

    def build_shortlist(
        self,
        thesis: AcquisitionThesis,
        profiles: tuple[CandidateProfile, ...],
        *,
        top_n: int | None = None,
        include_review_required: bool = True,
    ) -> Shortlist:
        self.calls += 1
        if self.calls <= self.failures:
            raise StrategicFitError("synthetic semantic evaluator failure")
        return self.delegate.build_shortlist(
            thesis,
            profiles,
            top_n=top_n,
            include_review_required=include_review_required,
        )


class _UnavailableDiscovery:
    def discover(self, thesis: AcquisitionThesis) -> CandidateDiscoveryResult:
        raise DiscoveryUnavailableError(f"synthetic outage for {thesis.thesis_id}")


def _domain(profile: CandidateProfile) -> str:
    return profile.candidate.website_domain or profile.candidate.canonical_name.casefold()


def _ratio(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else round(numerator / denominator, 4)
