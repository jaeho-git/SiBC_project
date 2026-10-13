from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from .evaluation import (
    AVAILABLE,
    BLOCKED_BY_REFERENCE_STANDARD,
    EvaluationSnapshot,
    METRIC_BY_NAME,
    MetricObservation,
    assert_comparable,
    assert_identifier_free,
)


ALLOWED_AUTOMATIC_CHANGE_TYPES = frozenset(
    {
        "SCHEMA_VALIDATION_FIX",
        "IMPLEMENTATION_BUG_FIX",
        "TIMESTAMP_HANDLING_FIX",
        "UNIT_HANDLING_FIX",
        "DUPLICATE_HANDLING_FIX",
        "DETERMINISTIC_ORDERING_FIX",
        "EVIDENCE_LINKAGE_FIX",
        "CONFLICT_DETECTION_IMPLEMENTATION_FIX",
        "SCORE_STATUS_CONSISTENCY_FIX",
        "CONFIDENCE_STABILITY_CALCULATION_FIX",
        "CDEI_TRACEABILITY_FIX",
        "TEST_COVERAGE_FIX",
        "PERFORMANCE_OPTIMIZATION",
        "SECRET_MASKING_FIX",
        "REPORTING_FIX",
        "NON_CLINICAL_ORCHESTRATION_FIX",
    }
)

FORBIDDEN_AUTOMATIC_CHANGE_TYPES = frozenset(
    {
        "CLINICAL_RULE_DEFINITION_CHANGE",
        "REQUIRED_CRITERION_CHANGE",
        "EXCLUSION_CRITERION_CHANGE",
        "CONTRADICTION_CRITERION_CHANGE",
        "CLINICAL_THRESHOLD_CHANGE",
        "INTENDED_USE_CHANGE",
        "CLINICAL_ESCALATION_POLICY_CHANGE",
        "LICENSED_CONTENT_CHANGE",
        "REFERENCE_LABEL_CHANGE",
        "EXPECTED_ORACLE_CHANGE",
        "CLINICAL_ACCEPTANCE_CRITERIA_CHANGE",
        "RELEASE_EVIDENCE_VALUE_CHANGE",
    }
)

SAFETY_ZERO_TARGETS = (
    "source_data_mutation_count",
    "sensitive_data_exposure_count",
    "unsafe_pass_rate",
    "unapproved_rule_activation_rate",
    "missed_future_leakage_rate",
)

SAFETY_NON_REGRESSION_METRICS = (
    "false_validated_rate",
    "missed_exclusion_rate",
    "missed_contradiction_rate",
    "hard_gate_score_violation_count",
)

PRIMARY_IMPROVEMENT_METRICS = (
    "status_exact_match_rate",
    "conflict_detection_rate",
    "exclusion_gate_accuracy",
    "contradiction_detection_rate",
    "cdei_component_completeness",
    "evidence_trace_completeness",
    "rule_trace_completeness",
    "narrative_faithfulness_rate",
    "groundedness_pass_rate",
)

EFFICIENCY_IMPROVEMENT_METRICS = (
    "runtime_seconds",
    "peak_memory_mb",
    "throughput_candidates_per_second",
)

CORE_NON_REGRESSION_METRICS = (
    "overall_scenario_accuracy",
    "status_exact_match_rate",
    "required_gate_accuracy",
    "exclusion_gate_accuracy",
    "contradiction_detection_rate",
    "conflict_detection_rate",
    "abstain_decision_accuracy",
    "profile_handoff_gate_accuracy",
    "behavior_handoff_gate_accuracy",
    "score_status_consistency_rate",
    "multi_diagnosis_consistency_rate",
    "deterministic_replay_rate",
    "regression_pass_rate",
)

REQUIRED_ADOPTION_EVIDENCE = (
    "deterministic_replay_rate",
    "regression_pass_rate",
    "test_pass_rate",
)

_ALLOWED_REASON_CODES = {
    "NON_REGRESSION_CONSTRAINT_FAILED",
    "NO_MEANINGFUL_TECHNICAL_OR_EFFICIENCY_IMPROVEMENT",
    "NO_BOUNDED_CHANGE_PROPOSAL_RECORDED",
}
_ALLOWED_REASON_PREFIXES = (
    "REQUIRED_SAFETY_EVIDENCE_UNAVAILABLE:",
    "REQUIRED_ADOPTION_EVIDENCE_UNAVAILABLE:",
    "REQUIRED_ADOPTION_EVIDENCE_FAILED:",
    "SAFETY_ZERO_TARGET_VIOLATED:",
    "SAFETY_COMPARISON_UNAVAILABLE:",
)


@dataclass(frozen=True)
class ImprovementProposal:
    proposal_id: str
    change_type: str
    failure_category: str
    description: str
    clinical_rule_modified: bool = False
    oracle_modified: bool = False
    release_evidence_modified: bool = False

    def validate(self) -> None:
        if self.change_type not in ALLOWED_AUTOMATIC_CHANGE_TYPES:
            if self.change_type in FORBIDDEN_AUTOMATIC_CHANGE_TYPES:
                raise ValueError(f"automatic change type is forbidden: {self.change_type}")
            raise ValueError(f"unknown automatic change type: {self.change_type}")
        if self.clinical_rule_modified:
            raise ValueError("automatic proposals cannot modify clinical rules")
        if self.oracle_modified:
            raise ValueError("automatic proposals cannot modify the expected oracle")
        if self.release_evidence_modified:
            raise ValueError("automatic proposals cannot modify release evidence")
        assert_identifier_free(asdict(self))


@dataclass(frozen=True)
class OptimizationDecision:
    cycle: int
    candidate_slot: str
    decision: str
    reason_codes: tuple[str, ...]
    improved_metrics: tuple[str, ...]
    regressed_metrics: tuple[str, ...]
    final_selected_slot: str
    clinical_rule_modified: bool
    clinical_validation_status: str = BLOCKED_BY_REFERENCE_STANDARD

    def __post_init__(self) -> None:
        if type(self.cycle) is not int or self.cycle < 1:
            raise ValueError("optimization decision cycle must be a positive integer")
        if self.candidate_slot not in ("current_candidate",):
            raise ValueError("optimization candidate slot must be current_candidate")
        if self.final_selected_slot not in ("baseline", "current_candidate"):
            raise ValueError("optimization final slot is outside the governed enum")
        if self.decision not in ("ADOPTED", "REJECTED"):
            raise ValueError("optimization decision is outside the governed enum")
        if type(self.clinical_rule_modified) is not bool:
            raise ValueError("clinical_rule_modified must be a strict boolean")
        if self.clinical_rule_modified:
            raise ValueError("automatic optimization cannot modify clinical rules")
        if self.clinical_validation_status != BLOCKED_BY_REFERENCE_STANDARD:
            raise ValueError("clinical validation status cannot be promoted by automation")
        unknown_metrics = (
            set(self.improved_metrics) | set(self.regressed_metrics)
        ) - set(METRIC_BY_NAME)
        if unknown_metrics:
            raise ValueError("optimization decision contains an unknown metric")
        for reason in self.reason_codes:
            if reason in _ALLOWED_REASON_CODES:
                continue
            if any(reason.startswith(prefix) for prefix in _ALLOWED_REASON_PREFIXES):
                metric = reason.split(":", 1)[1]
                if metric in METRIC_BY_NAME:
                    continue
            raise ValueError("optimization decision contains an unknown reason code")
        assert_identifier_free(
            {
                "candidate_slot": self.candidate_slot,
                "reason_codes": self.reason_codes,
                "improved_metrics": self.improved_metrics,
                "regressed_metrics": self.regressed_metrics,
                "final_selected_slot": self.final_selected_slot,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["reason_codes"] = list(self.reason_codes)
        value["improved_metrics"] = list(self.improved_metrics)
        value["regressed_metrics"] = list(self.regressed_metrics)
        value["clinical_performance_claimed"] = False
        value["decision_schema_version"] = "optimization_decision_v1"
        assert_identifier_free(value)
        return value


def propose_safe_improvements(
    failure_counts: Mapping[str, int],
) -> tuple[ImprovementProposal, ...]:
    """Map aggregate technical failures to bounded, non-clinical proposals."""

    mapping = {
        "DATA_SCHEMA_ERROR": ("SCHEMA_VALIDATION_FIX", "Harden schema parsing and validation."),
        "DATA_QUALITY_ERROR": ("SCHEMA_VALIDATION_FIX", "Correct non-clinical data-quality gate handling."),
        "TEMPORAL_ERROR": ("TIMESTAMP_HANDLING_FIX", "Correct timezone or temporal-window implementation."),
        "RULE_CONFLICT": ("CONFLICT_DETECTION_IMPLEMENTATION_FIX", "Correct conflict graph execution without changing conflict definitions."),
        "SCORING_ERROR": ("SCORE_STATUS_CONSISTENCY_FIX", "Correct score/status implementation consistency."),
        "CONFIDENCE_ERROR": ("CONFIDENCE_STABILITY_CALCULATION_FIX", "Correct stability-index calculation without adding calibration claims."),
        "CDEI_ERROR": ("CDEI_TRACEABILITY_FIX", "Correct CDEI trace construction or faithfulness checks."),
        "EXPLANATION_FAITHFULNESS_ERROR": ("CDEI_TRACEABILITY_FIX", "Correct explanation-to-execution trace consistency."),
        "IMPLEMENTATION_BUG": ("IMPLEMENTATION_BUG_FIX", "Correct a bounded technical implementation defect."),
        "TEST_DEFECT": ("TEST_COVERAGE_FIX", "Correct or expand non-clinical technical tests without changing the oracle to fit output."),
    }
    proposals: list[ImprovementProposal] = []
    for index, failure_category in enumerate(sorted(failure_counts), start=1):
        count = int(failure_counts[failure_category])
        if count <= 0 or failure_category not in mapping:
            continue
        change_type, description = mapping[failure_category]
        proposal = ImprovementProposal(
            proposal_id=f"TECH-{index:03d}",
            change_type=change_type,
            failure_category=failure_category,
            description=f"{description} Aggregate occurrence count: {count}.",
        )
        proposal.validate()
        proposals.append(proposal)
    assert_identifier_free([asdict(item) for item in proposals])
    return tuple(proposals)


def select_candidate(
    current_best: EvaluationSnapshot,
    candidate: EvaluationSnapshot,
    *,
    cycle: int,
    proposal: ImprovementProposal | None = None,
) -> OptimizationDecision:
    """Apply lexicographic safety-first selection to an evaluated candidate."""

    if cycle < 1:
        raise ValueError("optimization cycle must be at least 1")
    if proposal is not None:
        proposal.validate()
    if current_best.metadata.slot != "baseline":
        raise ValueError("current_best must use the baseline slot")
    if candidate.metadata.slot != "current_candidate":
        raise ValueError("candidate must use the current_candidate slot")
    if current_best.metadata.slot == candidate.metadata.slot:
        raise ValueError("optimization snapshots must use distinct governed slots")
    assert_comparable(
        {
            current_best.metadata.slot: current_best,
            candidate.metadata.slot: candidate,
        }
    )
    reasons: list[str] = []
    improved: list[str] = []
    regressed: list[str] = []

    for name in SAFETY_ZERO_TARGETS:
        current = current_best.metrics[name]
        proposed = candidate.metrics[name]
        if proposed.availability_status != AVAILABLE or proposed.value is None:
            reasons.append(f"REQUIRED_SAFETY_EVIDENCE_UNAVAILABLE:{name}")
            continue
        if float(proposed.value) != 0.0:
            reasons.append(f"SAFETY_ZERO_TARGET_VIOLATED:{name}")
        if _available_pair(current, proposed) and float(proposed.value) > float(current.value):
            regressed.append(name)

    for name in SAFETY_NON_REGRESSION_METRICS:
        current = current_best.metrics[name]
        proposed = candidate.metrics[name]
        if not _available_pair(current, proposed):
            reasons.append(f"SAFETY_COMPARISON_UNAVAILABLE:{name}")
        elif float(proposed.value) > float(current.value):
            regressed.append(name)

    for name in REQUIRED_ADOPTION_EVIDENCE:
        proposed = candidate.metrics[name]
        if proposed.availability_status != AVAILABLE or proposed.value is None:
            reasons.append(f"REQUIRED_ADOPTION_EVIDENCE_UNAVAILABLE:{name}")
        elif float(proposed.value) != 1.0:
            reasons.append(f"REQUIRED_ADOPTION_EVIDENCE_FAILED:{name}")

    for name in CORE_NON_REGRESSION_METRICS:
        current = current_best.metrics[name]
        proposed = candidate.metrics[name]
        if _available_pair(current, proposed) and float(proposed.value) < float(current.value):
            regressed.append(name)

    for name in PRIMARY_IMPROVEMENT_METRICS:
        current = current_best.metrics[name]
        proposed = candidate.metrics[name]
        if _available_pair(current, proposed) and float(proposed.value) > float(current.value):
            improved.append(name)

    efficiency_directions = {
        "runtime_seconds": "LOWER",
        "peak_memory_mb": "LOWER",
        "throughput_candidates_per_second": "HIGHER",
    }
    for name in EFFICIENCY_IMPROVEMENT_METRICS:
        current = current_best.metrics[name]
        proposed = candidate.metrics[name]
        if not _available_pair(current, proposed):
            continue
        delta = float(proposed.value) - float(current.value)
        if (efficiency_directions[name] == "LOWER" and delta < 0) or (
            efficiency_directions[name] == "HIGHER" and delta > 0
        ):
            improved.append(name)

    regressed = sorted(set(regressed))
    improved = sorted(set(improved))
    if regressed:
        reasons.append("NON_REGRESSION_CONSTRAINT_FAILED")
    if not improved:
        reasons.append("NO_MEANINGFUL_TECHNICAL_OR_EFFICIENCY_IMPROVEMENT")
    if proposal is None:
        reasons.append("NO_BOUNDED_CHANGE_PROPOSAL_RECORDED")

    accepted = not reasons
    return OptimizationDecision(
        cycle=cycle,
        candidate_slot=candidate.metadata.slot,
        decision="ADOPTED" if accepted else "REJECTED",
        reason_codes=tuple(sorted(set(reasons))),
        improved_metrics=tuple(improved),
        regressed_metrics=tuple(regressed),
        final_selected_slot=candidate.metadata.slot if accepted else current_best.metadata.slot,
        clinical_rule_modified=False,
    )


def _available_pair(
    current: MetricObservation, candidate: MetricObservation
) -> bool:
    return (
        current.availability_status == AVAILABLE
        and candidate.availability_status == AVAILABLE
        and current.value is not None
        and candidate.value is not None
    )


def should_stop(
    decisions: Iterable[OptimizationDecision],
    *,
    max_cycles: int = 10,
    no_improvement_limit: int = 2,
) -> tuple[bool, str]:
    materialized = sorted(decisions, key=lambda item: item.cycle)
    if not materialized:
        return False, "CONTINUE"
    if materialized[-1].cycle >= max_cycles:
        return True, "MAXIMUM_CYCLE_REACHED"
    consecutive = 0
    for item in reversed(materialized):
        if item.decision == "ADOPTED":
            break
        consecutive += 1
    if consecutive >= no_improvement_limit:
        return True, "NO_MEANINGFUL_IMPROVEMENT_FOR_CONSECUTIVE_CYCLES"
    if any(
        any(reason.startswith("SAFETY_ZERO_TARGET_VIOLATED") for reason in item.reason_codes)
        for item in materialized
    ):
        return False, "SAFETY_REGRESSION_CANDIDATE_REJECTED_CONTINUE_WITH_CURRENT_BEST"
    return False, "CONTINUE"


def automation_cycle_summary_markdown(
    decisions: Iterable[OptimizationDecision],
) -> str:
    values = sorted(decisions, key=lambda item: item.cycle)
    stop, stop_reason = should_stop(values)
    lines = [
        "# Automation cycle summary",
        "",
        "> Synthetic scenario-based technical optimization only. Clinical rules, reference labels, thresholds, and release evidence are immutable in this automation.",
        "",
        "| Cycle | Candidate | Decision | Improvements | Regressions | Reason codes |",
        "|---:|---|---|---|---|---|",
    ]
    if not values:
        lines.append("| 0 | NOT_AVAILABLE | NO_AUTOMATIC_CHANGE | - | - | BASELINE_ONLY |")
    for item in values:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item.cycle),
                    item.candidate_slot,
                    item.decision,
                    ", ".join(item.improved_metrics) or "-",
                    ", ".join(item.regressed_metrics) or "-",
                    ", ".join(item.reason_codes) or "ACCEPTANCE_CRITERIA_PASSED",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            f"- Stop after evaluated cycles: `{'YES' if stop else 'NO'}`",
            f"- Stop reason: `{stop_reason}`",
            "- Expected oracle modified: `NO`",
            "- Clinical Rule modified: `NO`",
            "- Release evidence modified: `NO`",
            "",
            "Clinical validation status: `BLOCKED_BY_REFERENCE_STANDARD`.",
            "",
        ]
    )
    return "\n".join(lines)


def final_selection_markdown(
    selected: EvaluationSnapshot,
    decisions: Iterable[OptimizationDecision],
) -> str:
    values = list(decisions)
    adopted = [item for item in values if item.decision == "ADOPTED"]
    origin_slot = values[-1].final_selected_slot if values else selected.metadata.slot
    clone_note = (
        "The unchanged baseline was copied into the `final_selected` presentation slot; "
        "no candidate change was adopted."
        if origin_slot == "baseline" and selected.metadata.slot == "final_selected"
        else "The selected evaluation snapshot is reported in its governed model slot."
    )
    return (
        "# Final model selection\n\n"
        "> `Final selected` means the preferred implementation for the governed release snapshot and synthetic Scenario Matrix. It does not mean clinically optimal.\n\n"
        f"- Selected slot: `{selected.metadata.slot}`\n"
        f"- Selection origin slot: `{origin_slot}`\n"
        f"- Model version: `{selected.metadata.model_version}`\n"
        f"- Run ID: `{selected.metadata.run_id}`\n"
        f"- Release snapshot: `{selected.metadata.release_snapshot_id}`\n"
        f"- Synthetic scenario version: `{selected.metadata.synthetic_scenario_version}`\n"
        f"- Adopted automatic cycles: {len(adopted)}\n"
        "- Clinical performance: `BLOCKED_BY_REFERENCE_STANDARD`\n"
        "- Clinical rule changes by automation: `NONE`\n\n"
        f"{clone_note}\n\n"
        "All selections are constrained by source immutability, privacy, unsafe-pass, leakage, hard-gate, oracle immutability, and deterministic replay requirements.\n"
    )
