from __future__ import annotations

import json
import math
import re
from collections import Counter, OrderedDict
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping

import pandas as pd

from .cdei import COMPONENTS as CDEI_COMPONENTS


AVAILABLE = "AVAILABLE"
NOT_AVAILABLE = "NOT_AVAILABLE"
BLOCKED_BY_REFERENCE_STANDARD = "BLOCKED_BY_REFERENCE_STANDARD"

MODEL_SLOTS = (
    "baseline",
    "previous_best",
    "current_candidate",
    "final_selected",
)

STATUS_ORDER = (
    "VALIDATED",
    "VALIDATED_WITH_LIMITATIONS",
    "REVIEW_REQUIRED",
    "INSUFFICIENT_EVIDENCE",
    "CONTRADICTED",
    "NOT_APPLICABLE",
    "ABSTAIN",
)

DATA_QUALITY_STATUS_ORDER = ("ACCEPTABLE", "REVIEW_REQUIRED")
_UNAVAILABLE_PROVENANCE = {
    "NOT_AVAILABLE",
    "UNKNOWN",
    "NONE",
    "BLOCKED_BY_RELEASE_ACCESS",
}
_FORBIDDEN_IDENTIFIER_KEYS = {
    "diagnosis_candidate_id",
    "synthetic_case_id",
    "evidence_id",
    "subject_id",
    "user_id",
    "raw_user_id",
    "raw_id",
}
_PRIVATE_VALUE_PATTERNS = (
    re.compile(
        r"\b(?:diagnosis_candidate_id|synthetic_case_id|evidence_id|subject_id|user_id|raw_user_id|raw_id)\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?<![A-Za-z0-9])(?:[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})(?![A-Za-z0-9])",
        re.IGNORECASE,
    ),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9])01[016789][- ]?\d{3,4}[- ]?\d{4}(?![A-Za-z0-9])"),
    re.compile(r"(?<![A-Za-z0-9])\d{6}[- ]?[1-8]\d{6}(?![A-Za-z0-9])"),
)


@dataclass(frozen=True)
class VersionMetadata:
    """Traceability fields required for one comparable technical evaluation."""

    slot: str
    model_version: str
    code_commit: str
    rule_version: str
    feature_version: str
    synthetic_generator_version: str
    synthetic_scenario_version: str
    release_snapshot_id: str
    run_id: str

    def __post_init__(self) -> None:
        if self.slot not in MODEL_SLOTS:
            raise ValueError(f"slot must be one of {', '.join(MODEL_SLOTS)}")
        for name, value in asdict(self).items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
            if name != "slot" and value.strip().upper() in _UNAVAILABLE_PROVENANCE:
                raise ValueError(f"{name} requires governed provenance")
        assert_identifier_free(asdict(self))


@dataclass(frozen=True)
class EvaluationContext:
    """Run-level evidence. Missing evidence remains unavailable, never zero-filled."""

    source_mutation_check: str = NOT_AVAILABLE
    security_scan_status: str = NOT_AVAILABLE
    deterministic_replay_rate: float | None = None
    regression_pass_rate: float | None = None
    test_pass_rate: float | None = None
    branch_coverage: float | None = None
    runtime_seconds: float | None = None
    peak_memory_mb: float | None = None
    throughput_candidates_per_second: float | None = None
    expected_rule_count: int | None = None
    generated_at: str = NOT_AVAILABLE


@dataclass(frozen=True)
class MetricObservation:
    value: float | int | None
    availability_status: str
    interpretation: str
    limitation: str

    @classmethod
    def available(
        cls,
        value: float | int,
        interpretation: str,
        limitation: str = "Synthetic scenario-based technical evaluation only.",
    ) -> "MetricObservation":
        return cls(_finite_number(value), AVAILABLE, interpretation, limitation)

    @classmethod
    def unavailable(
        cls,
        interpretation: str,
        limitation: str,
        *,
        status: str = NOT_AVAILABLE,
    ) -> "MetricObservation":
        return cls(None, status, interpretation, limitation)

    def display_value(self) -> float | int | str:
        return self.value if self.availability_status == AVAILABLE else self.availability_status


@dataclass(frozen=True)
class EvaluationSnapshot:
    """Identifier-free aggregate output for one model slot."""

    metadata: VersionMetadata
    metrics: Mapping[str, MetricObservation]
    status_distribution: Mapping[str, int]
    confusion_matrix: Mapping[str, Mapping[str, int]]
    scenario_category_counts: Mapping[str, int]
    cdei_component_means: Mapping[str, float]
    correctness_confidence: Mapping[str, float | int | str]
    data_quality_summary: Mapping[str, float | int | str]
    multi_diagnosis_outcomes: Mapping[str, int]
    candidate_count: int
    scenario_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": asdict(self.metadata),
            "metrics": {name: asdict(value) for name, value in self.metrics.items()},
            "status_distribution": dict(self.status_distribution),
            "confusion_matrix": {
                expected: dict(actual) for expected, actual in self.confusion_matrix.items()
            },
            "scenario_category_counts": dict(self.scenario_category_counts),
            "cdei_component_means": dict(self.cdei_component_means),
            "correctness_confidence": dict(self.correctness_confidence),
            "data_quality_summary": dict(self.data_quality_summary),
            "multi_diagnosis_outcomes": dict(self.multi_diagnosis_outcomes),
            "candidate_count": self.candidate_count,
            "scenario_count": self.scenario_count,
            "contains_candidate_level_identifiers": False,
            "clinical_performance_claimed": False,
        }


@dataclass(frozen=True)
class MetricDefinition:
    group: str
    name: str
    direction: str
    interpretation: str
    limitation: str = "Synthetic scenario-based technical evaluation only."


def _definition(
    group: str,
    name: str,
    direction: str,
    interpretation: str,
    limitation: str = "Synthetic scenario-based technical evaluation only.",
) -> MetricDefinition:
    return MetricDefinition(group, name, direction, interpretation, limitation)


METRIC_DEFINITIONS: tuple[MetricDefinition, ...] = (
    _definition("rule_and_decision", "overall_scenario_accuracy", "HIGHER", "Share of synthetic scenarios whose candidate statuses all match the technical oracle."),
    _definition("rule_and_decision", "status_exact_match_rate", "HIGHER", "Candidate-level exact status agreement with the synthetic technical oracle."),
    _definition("rule_and_decision", "required_gate_accuracy", "HIGHER", "Correct handling of required-criterion gate scenarios."),
    _definition("rule_and_decision", "exclusion_gate_accuracy", "HIGHER", "Correct handling of the explicit synthetic exclusion scenario."),
    _definition("rule_and_decision", "contradiction_detection_rate", "HIGHER", "Correct handling of explicit synthetic contradiction scenarios."),
    _definition("rule_and_decision", "conflict_detection_rate", "HIGHER", "Correct candidate-set conflict classification in synthetic multi-diagnosis scenarios."),
    _definition("rule_and_decision", "not_applicable_detection_rate", "HIGHER", "Correct NOT_APPLICABLE decision rate in the designated scenario."),
    _definition("rule_and_decision", "insufficient_evidence_detection_rate", "HIGHER", "Correct INSUFFICIENT_EVIDENCE decision rate in designated scenarios."),
    _definition("rule_and_decision", "abstain_decision_accuracy", "HIGHER", "Correct ABSTAIN decisions for the synthetic hard-block scenarios."),
    _definition("rule_and_decision", "profile_handoff_gate_accuracy", "HIGHER", "Agreement with synthetic expected Profile-write gates."),
    _definition("rule_and_decision", "behavior_handoff_gate_accuracy", "HIGHER", "Agreement with synthetic expected Behavior handoff gates."),
    _definition("safety", "unsafe_pass_rate", "LOWER", "Rate of blocked/non-validatable oracle cases incorrectly emitted as validated."),
    _definition("safety", "false_validated_rate", "LOWER", "Rate of non-validated oracle candidates incorrectly emitted as validated."),
    _definition("safety", "missed_exclusion_rate", "LOWER", "Miss rate for the explicit synthetic exclusion gate."),
    _definition("safety", "missed_contradiction_rate", "LOWER", "Miss rate for explicit synthetic contradiction gates."),
    _definition("safety", "missed_future_leakage_rate", "LOWER", "Miss rate for the synthetic future-evidence leakage gate."),
    _definition("safety", "unapproved_rule_activation_rate", "LOWER", "Activation rate for the synthetic unapproved-rule scenario."),
    _definition("safety", "source_data_mutation_count", "LOWER", "Detected source artifact mutation count."),
    _definition("safety", "sensitive_data_exposure_count", "LOWER", "Sensitive-data findings in the run output security scan."),
    _definition("score_and_status", "score_status_consistency_rate", "HIGHER", "Consistency of score presence and hard status semantics."),
    _definition("score_and_status", "hard_gate_score_violation_count", "LOWER", "Validated outputs that bypass a failed technical hard gate."),
    _definition("score_and_status", "score_monotonicity_pass_rate", "HIGHER", "Perturbation-test monotonicity of the technical score.", "Requires paired perturbation runs; not inferable from one scenario execution."),
    _definition("score_and_status", "boundary_stability_rate", "HIGHER", "Stability under repeated boundary perturbations.", "Requires repeated boundary perturbation runs."),
    _definition("score_and_status", "multi_diagnosis_consistency_rate", "HIGHER", "Exact technical-oracle agreement in multi-diagnosis scenarios."),
    _definition("confidence", "confidence_ordering_accuracy", "HIGHER", "Ordering of the uncalibrated decision-stability index by technical correctness.", "No variation exists while decision confidence remains policy-fixed at zero."),
    _definition("confidence", "confidence_error_separation", "HIGHER", "Separation between correct and incorrect technical decisions.", "Not a probability or clinical calibration metric."),
    _definition("confidence", "high_confidence_error_rate", "LOWER", "Technical error rate above an approved high-confidence boundary.", "No approved high-confidence boundary or calibrated confidence is available."),
    _definition("confidence", "confidence_stability_rate", "HIGHER", "Replay stability of the decision-stability index.", "Requires deterministic replay evidence."),
    _definition("confidence", "confidence_calibration_status", "MONITOR", "Clinical calibration status.", "Expert-adjudicated reference standard is unavailable."),
    _definition("cdei_and_explainability", "cdei_component_completeness", "HIGHER", "Mean completeness across CDEI traceability components."),
    _definition("cdei_and_explainability", "evidence_trace_completeness", "HIGHER", "Mean CDEI evidence-linkage component."),
    _definition("cdei_and_explainability", "rule_trace_completeness", "HIGHER", "Mean CDEI rule-traceability component."),
    _definition("cdei_and_explainability", "limitation_disclosure_rate", "HIGHER", "Mean CDEI limitation-disclosure component."),
    _definition("cdei_and_explainability", "conflict_disclosure_rate", "HIGHER", "Mean CDEI conflict-transparency component."),
    _definition("cdei_and_explainability", "narrative_faithfulness_rate", "HIGHER", "Mean CDEI narrative-faithfulness component."),
    _definition("cdei_and_explainability", "groundedness_pass_rate", "HIGHER", "Mean CDEI groundedness component."),
    _definition("cdei_and_explainability", "reproducibility_trace_rate", "HIGHER", "Share of results with a non-empty deterministic decision fingerprint."),
    _definition("data_quality_and_coverage", "evidence_coverage_rate", "HIGHER", "Mean CDEI evidence-linkage coverage for synthetic evidence."),
    _definition("data_quality_and_coverage", "required_evidence_assessable_rate", "HIGHER", "Required-evidence assessability inferred from designated synthetic scenarios."),
    _definition("data_quality_and_coverage", "data_quality_gate_accuracy", "HIGHER", "Correct status handling in designated synthetic data-quality scenarios."),
    _definition("data_quality_and_coverage", "temporal_alignment_pass_rate", "HIGHER", "Correct technical decisions for stale/future temporal scenarios."),
    _definition("data_quality_and_coverage", "wearable_availability_classification_accuracy", "HIGHER", "Wearable availability classification accuracy.", "The current fixture has no independently labelled wearable availability oracle."),
    _definition("data_quality_and_coverage", "rule_coverage_rate", "HIGHER", "Share of expected test rules represented in the execution."),
    _definition("data_quality_and_coverage", "scenario_coverage_rate", "HIGHER", "Share of manifest scenarios represented by at least one result."),
    _definition("reproducibility_and_efficiency", "deterministic_replay_rate", "HIGHER", "Exact deterministic replay rate supplied by the regression run."),
    _definition("reproducibility_and_efficiency", "regression_pass_rate", "HIGHER", "Regression test pass rate supplied by the run context."),
    _definition("reproducibility_and_efficiency", "test_pass_rate", "HIGHER", "Automated test pass rate supplied by the run context."),
    _definition("reproducibility_and_efficiency", "branch_coverage", "HIGHER", "Measured branch coverage supplied by the test runner."),
    _definition("reproducibility_and_efficiency", "runtime_seconds", "LOWER", "Wall-clock technical evaluation runtime in seconds."),
    _definition("reproducibility_and_efficiency", "peak_memory_mb", "LOWER", "Peak resident memory during evaluation in MiB."),
    _definition("reproducibility_and_efficiency", "throughput_candidates_per_second", "HIGHER", "Candidate validations completed per second."),
)

METRIC_BY_NAME = OrderedDict((item.name, item) for item in METRIC_DEFINITIONS)


def _finite_number(value: float | int) -> float | int:
    number = float(value)
    if not pd.notna(number) or number in (float("inf"), float("-inf")):
        raise ValueError("metric values must be finite")
    if isinstance(value, int):
        return int(value)
    return round(number, 6)


def _json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


def _rate(values: Iterable[bool]) -> float | None:
    materialized = [bool(value) for value in values]
    if not materialized:
        return None
    return round(sum(materialized) / len(materialized), 6)


def _metric(
    name: str,
    value: float | int | None,
    *,
    unavailable_status: str = NOT_AVAILABLE,
    unavailable_reason: str | None = None,
) -> MetricObservation:
    definition = METRIC_BY_NAME[name]
    if value is None:
        return MetricObservation.unavailable(
            definition.interpretation,
            unavailable_reason or definition.limitation,
            status=unavailable_status,
        )
    return MetricObservation.available(value, definition.interpretation, definition.limitation)


def _scenario_rate(joined: pd.DataFrame, scenario_ids: set[str]) -> float | None:
    subset = joined[joined["scenario_id"].isin(scenario_ids)]
    return _rate(subset["status"] == subset["expected_status"])


def _validate_inputs(actual: pd.DataFrame, expected: pd.DataFrame) -> None:
    actual_required = {
        "scenario_id",
        "diagnosis_candidate_id",
        "status",
        "hard_gate_passed",
        "technical_gate_passed",
        "clinical_validation_score",
        "model_decision_confidence",
        "calibration_status",
        "cdei_components",
        "data_quality_status",
        "limitations",
        "profile_write_allowed",
        "behavior_handoff_allowed",
        "candidate_set_conflict_status",
        "candidate_set_review_required",
        "decision_fingerprint",
    }
    expected_required = {
        "scenario_id",
        "diagnosis_candidate_id",
        "expected_status",
        "expected_profile_write_allowed",
        "expected_behavior_handoff_allowed",
        "expected_candidate_set_conflict_status",
        "expected_candidate_set_review_required",
    }
    missing_actual = sorted(actual_required - set(actual.columns))
    missing_expected = sorted(expected_required - set(expected.columns))
    if missing_actual or missing_expected:
        raise ValueError(
            f"evaluation contract missing columns: actual={missing_actual}, expected={missing_expected}"
        )
    if actual["diagnosis_candidate_id"].duplicated().any():
        raise ValueError("actual diagnosis_candidate_id values must be unique")
    if expected["diagnosis_candidate_id"].duplicated().any():
        raise ValueError("expected diagnosis_candidate_id values must be unique")
    if set(actual["diagnosis_candidate_id"]) != set(expected["diagnosis_candidate_id"]):
        raise ValueError("actual and expected candidate sets differ")
    actual_statuses = {str(value) for value in actual["status"]}
    expected_statuses = {str(value) for value in expected["expected_status"]}
    if not actual_statuses <= set(STATUS_ORDER):
        raise ValueError("INVALID_STATUS_LABEL: actual status is outside the governed enum")
    if not expected_statuses <= set(STATUS_ORDER):
        raise ValueError("INVALID_STATUS_LABEL: expected status is outside the governed enum")
    quality_statuses = {str(value) for value in actual["data_quality_status"]}
    if not quality_statuses <= set(DATA_QUALITY_STATUS_ORDER):
        raise ValueError(
            "INVALID_DATA_QUALITY_STATUS: status is outside the governed enum"
        )


def evaluate_version(
    actual: pd.DataFrame,
    expected: pd.DataFrame,
    metadata: VersionMetadata,
    *,
    scenario_manifest: pd.DataFrame | None = None,
    context: EvaluationContext | None = None,
) -> EvaluationSnapshot:
    """Aggregate one synthetic technical run without retaining candidate identifiers."""

    _validate_inputs(actual, expected)
    context = context or EvaluationContext()
    expected_columns = list(expected.columns)
    joined = actual.merge(
        expected[expected_columns],
        on="diagnosis_candidate_id",
        how="inner",
        validate="one_to_one",
        suffixes=("", "_oracle"),
    )
    if "scenario_id_oracle" in joined.columns:
        if not (joined["scenario_id"] == joined["scenario_id_oracle"]).all():
            raise ValueError("scenario_id mismatch between actual and oracle")
        joined = joined.drop(columns=["scenario_id_oracle"])
    joined = joined.sort_values(["scenario_id", "diagnosis_candidate_id"]).reset_index(drop=True)
    exact = joined["status"] == joined["expected_status"]

    scenario_exact = joined.assign(_exact=exact).groupby("scenario_id", sort=True)["_exact"].all()
    matrix_statuses = list(STATUS_ORDER)
    confusion: dict[str, dict[str, int]] = OrderedDict()
    for expected_status in matrix_statuses:
        confusion[expected_status] = OrderedDict(
            (
                actual_status,
                int(
                    (
                        (joined["expected_status"] == expected_status)
                        & (joined["status"] == actual_status)
                    ).sum()
                ),
            )
            for actual_status in matrix_statuses
        )

    status_counts = Counter(str(value) for value in joined["status"])
    status_distribution = OrderedDict(
        (status, int(status_counts.get(status, 0))) for status in matrix_statuses
    )

    scenario_categories = {
        "normal_control": {"POSITIVE_CONTROL", "NEGATIVE_CONTROL", "PARTIAL_SUPPORT"},
        "error_and_safety": {
            "MISSING_REQUIRED_EVIDENCE",
            "EXCLUSION_TRIGGERED",
            "CONTRADICTORY_EVIDENCE",
            "FUTURE_EVIDENCE_LEAKAGE",
            "INVALID_EVIDENCE_LINK",
            "UNAPPROVED_RULE",
            "RULE_VERSION_MISMATCH",
            "EXPLANATION_TRACE_MISMATCH",
            "UPSTREAM_VALIDATION_FAILURE",
        },
        "boundary_and_quality": {"NOT_APPLICABLE", "BOUNDARY_VALUE", "STALE_EVIDENCE"},
        "multi_diagnosis": {
            "MULTIPLE_COHERENT_DIAGNOSES",
            "MULTIPLE_CONFLICTING_DIAGNOSES",
            "NANDA_OMAHA_CROSS_TAXONOMY_OVERLAP",
            "PARTIALLY_ASSESSABLE_DIAGNOSIS_SET",
        },
    }
    scenario_category_counts = OrderedDict(
        (name, len(set(joined["scenario_id"]) & values))
        for name, values in scenario_categories.items()
    )
    assigned = set().union(*scenario_categories.values())
    other_count = len(set(joined["scenario_id"]) - assigned)
    if other_count:
        scenario_category_counts["other"] = other_count

    parsed_cdei = [_json_value(item, {}) for item in joined["cdei_components"]]
    if not all(isinstance(value, dict) for value in parsed_cdei):
        raise ValueError("INVALID_CDEI_COMPONENT: components must be mappings")
    cdei_rows = [dict(value) for value in parsed_cdei]
    cdei_names = {str(key) for row in cdei_rows for key in row}
    if not cdei_names <= set(CDEI_COMPONENTS):
        raise ValueError("INVALID_CDEI_COMPONENT: component is outside the governed enum")
    if any(
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or not 0.0 <= float(value) <= 1.0
        for row in cdei_rows
        for value in row.values()
    ):
        raise ValueError("INVALID_CDEI_COMPONENT: values must be finite rates")
    cdei_means = OrderedDict(
        (
            name,
            round(
                sum(float(row[name]) for row in cdei_rows) / len(cdei_rows),
                6,
            ),
        )
        for name in CDEI_COMPONENTS
        if cdei_rows and all(name in row for row in cdei_rows)
    ) if cdei_rows else OrderedDict()

    validated_statuses = {"VALIDATED", "VALIDATED_WITH_LIMITATIONS"}
    unsafe_expected = ~joined["expected_status"].isin(validated_statuses)
    false_validated = unsafe_expected & joined["status"].isin(validated_statuses)
    score_consistent = (
        ((joined["status"] == "ABSTAIN") & joined["clinical_validation_score"].isna())
        | ((joined["status"] != "ABSTAIN") & joined["clinical_validation_score"].notna())
    )
    hard_gate_violation = (~joined["hard_gate_passed"].astype(bool)) & joined[
        "status"
    ].isin(validated_statuses)

    multi_ids = scenario_categories["multi_diagnosis"]
    multi_subset = joined[joined["scenario_id"].isin(multi_ids)]
    multi_outcomes = OrderedDict(
        (
            scenario,
            int((multi_subset["scenario_id"] == scenario).sum()),
        )
        for scenario in sorted(multi_ids)
    )

    correctness_confidence: dict[str, float | int | str] = OrderedDict()
    correct_conf = joined.loc[exact, "model_decision_confidence"].dropna()
    incorrect_conf = joined.loc[~exact, "model_decision_confidence"].dropna()
    correctness_confidence["correct_count"] = int(exact.sum())
    correctness_confidence["incorrect_count"] = int((~exact).sum())
    correctness_confidence["correct_mean"] = (
        round(float(correct_conf.mean()), 6) if not correct_conf.empty else NOT_AVAILABLE
    )
    correctness_confidence["incorrect_mean"] = (
        round(float(incorrect_conf.mean()), 6) if not incorrect_conf.empty else NOT_AVAILABLE
    )
    correctness_confidence["calibration_status"] = BLOCKED_BY_REFERENCE_STANDARD

    data_quality_counts = Counter(str(value) for value in joined["data_quality_status"])
    data_quality_summary: dict[str, float | int | str] = OrderedDict(
        (name, int(data_quality_counts[name])) for name in sorted(data_quality_counts)
    )
    data_quality_summary["clinical_reference_standard"] = BLOCKED_BY_REFERENCE_STANDARD

    expected_scenario_count = (
        int(scenario_manifest["scenario_id"].nunique())
        if scenario_manifest is not None and "scenario_id" in scenario_manifest.columns
        else int(expected["scenario_id"].nunique())
    )
    observed_rule_count = (
        int(joined["rule_id"].dropna().nunique())
        if "rule_id" in joined
        else None
    )

    exclusion_rate = _scenario_rate(joined, {"EXCLUSION_TRIGGERED"})
    contradiction_rate = _scenario_rate(joined, {"CONTRADICTORY_EVIDENCE"})
    future_rate = _scenario_rate(joined, {"FUTURE_EVIDENCE_LEAKAGE"})
    unapproved_rate = _scenario_rate(joined, {"UNAPPROVED_RULE"})
    evidence_linkage = cdei_means.get("evidence_linkage")
    required_assessable = [
        "REQUIRED_EVIDENCE_MISSING_OR_NOT_ASSESSABLE"
        not in {
            str(item)
            for item in _json_value(limitations, [])
        }
        for limitations in joined["limitations"]
    ]

    metrics: dict[str, MetricObservation] = OrderedDict()
    metrics["overall_scenario_accuracy"] = _metric("overall_scenario_accuracy", _rate(scenario_exact))
    metrics["status_exact_match_rate"] = _metric("status_exact_match_rate", _rate(exact))
    metrics["required_gate_accuracy"] = _metric(
        "required_gate_accuracy",
        _scenario_rate(joined, {"NEGATIVE_CONTROL", "MISSING_REQUIRED_EVIDENCE"}),
    )
    metrics["exclusion_gate_accuracy"] = _metric("exclusion_gate_accuracy", exclusion_rate)
    metrics["contradiction_detection_rate"] = _metric("contradiction_detection_rate", contradiction_rate)
    conflict_subset = joined[joined["scenario_id"] == "MULTIPLE_CONFLICTING_DIAGNOSES"]
    conflict_correct = (
        (conflict_subset["candidate_set_conflict_status"] == conflict_subset["expected_candidate_set_conflict_status"])
        & (
            conflict_subset["candidate_set_review_required"].astype(bool)
            == conflict_subset["expected_candidate_set_review_required"].astype(bool)
        )
    )
    metrics["conflict_detection_rate"] = _metric("conflict_detection_rate", _rate(conflict_correct))
    metrics["not_applicable_detection_rate"] = _metric(
        "not_applicable_detection_rate", _scenario_rate(joined, {"NOT_APPLICABLE"})
    )
    metrics["insufficient_evidence_detection_rate"] = _metric(
        "insufficient_evidence_detection_rate",
        _scenario_rate(joined, {"MISSING_REQUIRED_EVIDENCE", "PARTIALLY_ASSESSABLE_DIAGNOSIS_SET"}),
    )
    expected_abstain = joined["expected_status"] == "ABSTAIN"
    metrics["abstain_decision_accuracy"] = _metric(
        "abstain_decision_accuracy",
        _rate(joined.loc[expected_abstain, "status"] == "ABSTAIN"),
    )
    metrics["profile_handoff_gate_accuracy"] = _metric(
        "profile_handoff_gate_accuracy",
        _rate(
            joined["profile_write_allowed"].astype(bool)
            == joined["expected_profile_write_allowed"].astype(bool)
        ),
    )
    metrics["behavior_handoff_gate_accuracy"] = _metric(
        "behavior_handoff_gate_accuracy",
        _rate(
            joined["behavior_handoff_allowed"].astype(bool)
            == joined["expected_behavior_handoff_allowed"].astype(bool)
        ),
    )
    metrics["unsafe_pass_rate"] = _metric("unsafe_pass_rate", _rate(false_validated[unsafe_expected]))
    metrics["false_validated_rate"] = _metric("false_validated_rate", _rate(false_validated))
    metrics["missed_exclusion_rate"] = _metric(
        "missed_exclusion_rate", None if exclusion_rate is None else 1.0 - exclusion_rate
    )
    metrics["missed_contradiction_rate"] = _metric(
        "missed_contradiction_rate", None if contradiction_rate is None else 1.0 - contradiction_rate
    )
    metrics["missed_future_leakage_rate"] = _metric(
        "missed_future_leakage_rate", None if future_rate is None else 1.0 - future_rate
    )
    metrics["unapproved_rule_activation_rate"] = _metric(
        "unapproved_rule_activation_rate", None if unapproved_rate is None else 1.0 - unapproved_rate
    )
    metrics["source_data_mutation_count"] = _metric(
        "source_data_mutation_count",
        0 if context.source_mutation_check == "PASSED" else None,
        unavailable_reason="A verified before/after source artifact check was not supplied.",
    )
    metrics["sensitive_data_exposure_count"] = _metric(
        "sensitive_data_exposure_count",
        0 if context.security_scan_status == "PASSED" else None,
        unavailable_reason="A passing output-tree security scan was not supplied.",
    )
    metrics["score_status_consistency_rate"] = _metric("score_status_consistency_rate", _rate(score_consistent))
    metrics["hard_gate_score_violation_count"] = _metric("hard_gate_score_violation_count", int(hard_gate_violation.sum()))
    metrics["score_monotonicity_pass_rate"] = _metric("score_monotonicity_pass_rate", None)
    metrics["boundary_stability_rate"] = _metric("boundary_stability_rate", None)
    metrics["multi_diagnosis_consistency_rate"] = _metric(
        "multi_diagnosis_consistency_rate", _rate(multi_subset["status"] == multi_subset["expected_status"])
    )
    metrics["confidence_ordering_accuracy"] = _metric("confidence_ordering_accuracy", None)
    separation = None
    if not correct_conf.empty and not incorrect_conf.empty:
        separation = float(correct_conf.mean() - incorrect_conf.mean())
    metrics["confidence_error_separation"] = _metric("confidence_error_separation", separation)
    metrics["high_confidence_error_rate"] = _metric("high_confidence_error_rate", None)
    metrics["confidence_stability_rate"] = _metric(
        "confidence_stability_rate", context.deterministic_replay_rate
    )
    metrics["confidence_calibration_status"] = _metric(
        "confidence_calibration_status",
        None,
        unavailable_status=BLOCKED_BY_REFERENCE_STANDARD,
        unavailable_reason="No expert-adjudicated clinical reference standard is available.",
    )
    cdei_overall = (
        round(sum(cdei_means.values()) / len(cdei_means), 6) if cdei_means else None
    )
    metrics["cdei_component_completeness"] = _metric("cdei_component_completeness", cdei_overall)
    component_metric_map = {
        "evidence_trace_completeness": "evidence_linkage",
        "rule_trace_completeness": "rule_traceability",
        "limitation_disclosure_rate": "limitation_disclosure",
        "conflict_disclosure_rate": "conflict_transparency",
        "narrative_faithfulness_rate": "narrative_faithfulness",
        "groundedness_pass_rate": "groundedness",
    }
    for metric_name, component_name in component_metric_map.items():
        metrics[metric_name] = _metric(metric_name, cdei_means.get(component_name))
    metrics["reproducibility_trace_rate"] = _metric(
        "reproducibility_trace_rate",
        _rate(joined["decision_fingerprint"].fillna("").astype(str).str.len() > 0),
    )
    metrics["evidence_coverage_rate"] = _metric("evidence_coverage_rate", evidence_linkage)
    metrics["required_evidence_assessable_rate"] = _metric(
        "required_evidence_assessable_rate",
        _rate(required_assessable),
    )
    metrics["data_quality_gate_accuracy"] = _metric(
        "data_quality_gate_accuracy",
        _scenario_rate(joined, {"STALE_EVIDENCE", "FUTURE_EVIDENCE_LEAKAGE", "INVALID_EVIDENCE_LINK", "UPSTREAM_VALIDATION_FAILURE"}),
    )
    metrics["temporal_alignment_pass_rate"] = _metric(
        "temporal_alignment_pass_rate", _scenario_rate(joined, {"STALE_EVIDENCE", "FUTURE_EVIDENCE_LEAKAGE"})
    )
    metrics["wearable_availability_classification_accuracy"] = _metric(
        "wearable_availability_classification_accuracy", None
    )
    metrics["rule_coverage_rate"] = _metric(
        "rule_coverage_rate",
        (
            min(observed_rule_count / context.expected_rule_count, 1.0)
            if observed_rule_count is not None
            and context.expected_rule_count
            and context.expected_rule_count > 0
            else None
        ),
        unavailable_reason="Expected rule count was not supplied by the governed rule registry.",
    )
    metrics["scenario_coverage_rate"] = _metric(
        "scenario_coverage_rate",
        min(joined["scenario_id"].nunique() / expected_scenario_count, 1.0)
        if expected_scenario_count
        else None,
    )
    context_metrics = {
        "deterministic_replay_rate": context.deterministic_replay_rate,
        "regression_pass_rate": context.regression_pass_rate,
        "test_pass_rate": context.test_pass_rate,
        "branch_coverage": context.branch_coverage,
        "runtime_seconds": context.runtime_seconds,
        "peak_memory_mb": context.peak_memory_mb,
        "throughput_candidates_per_second": context.throughput_candidates_per_second,
    }
    for name, value in context_metrics.items():
        metrics[name] = _metric(name, value)

    if tuple(metrics) != tuple(METRIC_BY_NAME):
        missing = set(METRIC_BY_NAME) - set(metrics)
        extra = set(metrics) - set(METRIC_BY_NAME)
        raise AssertionError(f"metric registry mismatch: missing={missing}, extra={extra}")

    snapshot = EvaluationSnapshot(
        metadata=metadata,
        metrics=metrics,
        status_distribution=status_distribution,
        confusion_matrix=confusion,
        scenario_category_counts=scenario_category_counts,
        cdei_component_means=cdei_means,
        correctness_confidence=correctness_confidence,
        data_quality_summary=data_quality_summary,
        multi_diagnosis_outcomes=multi_outcomes,
        candidate_count=len(joined),
        scenario_count=int(joined["scenario_id"].nunique()),
    )
    assert_identifier_free(snapshot.to_dict())
    return snapshot


def assert_comparable(snapshots: Mapping[str, EvaluationSnapshot | None]) -> None:
    available = [item for item in snapshots.values() if item is not None]
    if not available:
        raise ValueError("at least one evaluation snapshot is required")
    fields = (
        "release_snapshot_id",
        "synthetic_generator_version",
        "synthetic_scenario_version",
        "rule_version",
        "feature_version",
    )
    reference = available[0].metadata
    mismatches: dict[str, list[str]] = {}
    for name in fields:
        values = sorted({str(getattr(item.metadata, name)) for item in available})
        if any(value.strip().upper() in _UNAVAILABLE_PROVENANCE for value in values):
            raise ValueError(f"missing governed comparison provenance: {name}")
        if len(values) != 1:
            mismatches[name] = values
    if mismatches:
        raise ValueError(f"non-comparable evaluation snapshots: {mismatches}")
    for slot, snapshot in snapshots.items():
        if snapshot is not None and snapshot.metadata.slot != slot:
            raise ValueError(f"snapshot key {slot!r} does not match metadata slot")


def build_comparison_table(
    snapshots: Mapping[str, EvaluationSnapshot | None],
) -> pd.DataFrame:
    """Build the governed four-slot comparison table with explicit unavailable cells."""

    unknown = set(snapshots) - set(MODEL_SLOTS)
    if unknown:
        raise ValueError(f"unknown model slots: {sorted(unknown)}")
    normalized = {slot: snapshots.get(slot) for slot in MODEL_SLOTS}
    assert_comparable(normalized)
    rows: list[dict[str, Any]] = []
    for definition in METRIC_DEFINITIONS:
        observations = {
            slot: (
                normalized[slot].metrics[definition.name]
                if normalized[slot] is not None
                else MetricObservation.unavailable(
                    definition.interpretation,
                    f"No {slot} evaluation snapshot was supplied.",
                )
            )
            for slot in MODEL_SLOTS
        }
        baseline = observations["baseline"]
        final = observations["final_selected"]
        absolute_change: float | str
        relative_change: float | str
        if (
            baseline.availability_status == AVAILABLE
            and final.availability_status == AVAILABLE
            and baseline.value is not None
            and final.value is not None
        ):
            absolute_change = round(float(final.value) - float(baseline.value), 6)
            relative_change = (
                round(absolute_change / abs(float(baseline.value)), 6)
                if float(baseline.value) != 0.0
                else NOT_AVAILABLE
            )
            acceptance = _acceptance_status(
                float(baseline.value), float(final.value), definition.direction
            )
        else:
            absolute_change = NOT_AVAILABLE
            relative_change = NOT_AVAILABLE
            acceptance = "NOT_ASSESSABLE"
        limitations = sorted(
            {
                item.limitation
                for item in observations.values()
                if item.limitation
            }
        )
        rows.append(
            {
                "metric_group": definition.group,
                "metric_name": definition.name,
                "baseline_value": observations["baseline"].display_value(),
                "previous_best_value": observations["previous_best"].display_value(),
                "current_candidate_value": observations["current_candidate"].display_value(),
                "final_selected_value": observations["final_selected"].display_value(),
                "absolute_change_vs_baseline": absolute_change,
                "relative_change_vs_baseline": relative_change,
                "acceptance_direction": definition.direction,
                "acceptance_status": acceptance,
                "interpretation": definition.interpretation,
                "limitation": " | ".join(limitations),
            }
        )
    frame = pd.DataFrame(rows)
    assert list(frame.columns) == [
        "metric_group",
        "metric_name",
        "baseline_value",
        "previous_best_value",
        "current_candidate_value",
        "final_selected_value",
        "absolute_change_vs_baseline",
        "relative_change_vs_baseline",
        "acceptance_direction",
        "acceptance_status",
        "interpretation",
        "limitation",
    ]
    assert_identifier_free(frame.to_dict(orient="records"))
    return frame


def _acceptance_status(baseline: float, final: float, direction: str) -> str:
    delta = round(final - baseline, 12)
    if delta == 0:
        return "UNCHANGED"
    if direction == "HIGHER":
        return "IMPROVED" if delta > 0 else "REGRESSED"
    if direction == "LOWER":
        return "IMPROVED" if delta < 0 else "REGRESSED"
    return "MONITORED_CHANGE"


def comparison_markdown(
    frame: pd.DataFrame,
    snapshots: Mapping[str, EvaluationSnapshot | None] | None = None,
) -> str:
    """Create a deterministic, dependency-free Markdown comparison report."""

    required = {definition.name for definition in METRIC_DEFINITIONS}
    if set(frame["metric_name"]) != required:
        raise ValueError("comparison frame does not contain the governed metric registry")
    lines = [
        "# Model performance comparison",
        "",
        "> Synthetic scenario-based technical evaluation. This report does not establish clinical diagnostic performance, calibration, or individual diagnosis validity.",
        "",
        "Clinical performance status: `BLOCKED_BY_REFERENCE_STANDARD`.",
        "",
    ]
    if snapshots is not None:
        unknown = set(snapshots) - set(MODEL_SLOTS)
        if unknown:
            raise ValueError(f"unknown model slots: {sorted(unknown)}")
        lines.extend(
            [
                "## Version traceability",
                "",
                "| Slot | Model version | Code commit | Rule version | Feature version | Synthetic generator | Scenario version | Release snapshot | Run ID |",
                "|---|---|---|---|---|---|---|---|---|",
            ]
        )
        for slot in MODEL_SLOTS:
            snapshot = snapshots.get(slot)
            if snapshot is None:
                values = [slot, *(NOT_AVAILABLE for _ in range(8))]
            else:
                metadata = snapshot.metadata
                values = [
                    slot,
                    metadata.model_version,
                    metadata.code_commit,
                    metadata.rule_version,
                    metadata.feature_version,
                    metadata.synthetic_generator_version,
                    metadata.synthetic_scenario_version,
                    metadata.release_snapshot_id,
                    metadata.run_id,
                ]
            lines.append("| " + " | ".join(_md_cell(value) for value in values) + " |")
        lines.extend(["", "## Governed technical metrics", ""])
    lines.extend(
        [
            "| Group | Metric | Baseline | Previous best | Current candidate | Final selected | Change vs baseline | Acceptance |",
            "|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in frame.to_dict(orient="records"):
        cells = [
            row["metric_group"],
            row["metric_name"],
            row["baseline_value"],
            row["previous_best_value"],
            row["current_candidate_value"],
            row["final_selected_value"],
            row["absolute_change_vs_baseline"],
            row["acceptance_status"],
        ]
        lines.append("| " + " | ".join(_md_cell(value) for value in cells) + " |")
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "Synthetic technical-oracle agreement is not sensitivity, specificity, PPV, NPV, AUROC, clinical calibration, or real-world accuracy. Score, confidence, and CDEI are separate non-probabilistic quantities. `NOT_AVAILABLE` values were not replaced with zero.",
            "",
        ]
    )
    return "\n".join(lines)


def _md_cell(value: Any) -> str:
    if isinstance(value, float):
        value = f"{value:.6g}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def assert_identifier_free(value: Any) -> None:
    """Reject accidental candidate/case/evidence identifiers in aggregate artifacts."""

    def walk(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, nested in item.items():
                normalized = str(key).strip().lower()
                if normalized in _FORBIDDEN_IDENTIFIER_KEYS:
                    raise ValueError("aggregate artifact contains an identifier field")
                walk(nested)
            return
        if isinstance(item, (list, tuple, set)):
            for nested in item:
                walk(nested)
            return
        if isinstance(item, str) and any(
            pattern.search(item) for pattern in _PRIVATE_VALUE_PATTERNS
        ):
            raise ValueError("aggregate artifact contains a private identifier value")

    walk(value)
