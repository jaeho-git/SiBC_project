from __future__ import annotations

import json
from collections import Counter
from dataclasses import fields
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from sibc_clinical_validation.conflict_detection import apply_candidate_set_checks
from sibc_clinical_validation.config import PrototypeConfig, load_config
from sibc_clinical_validation.evidence import materialize_fixture_contract
from sibc_clinical_validation.models import DiagnosisCandidate, ValidationStatus
from sibc_clinical_validation.reporting import output_contract
from sibc_clinical_validation.rule_schema import RuleRegistry
from sibc_clinical_validation.synthetic import (
    build_fixture_frames,
    write_fixture_dataset,
)
from sibc_clinical_validation.validation import ClinicalValidationEngine


EXPECTED_STATUSES_BY_SCENARIO = {
    "POSITIVE_CONTROL": Counter({"VALIDATED": 1}),
    "NEGATIVE_CONTROL": Counter({"CONTRADICTED": 1}),
    "MISSING_REQUIRED_EVIDENCE": Counter({"INSUFFICIENT_EVIDENCE": 1}),
    "PARTIAL_SUPPORT": Counter({"VALIDATED_WITH_LIMITATIONS": 1}),
    "EXCLUSION_TRIGGERED": Counter({"CONTRADICTED": 1}),
    "CONTRADICTORY_EVIDENCE": Counter({"CONTRADICTED": 1}),
    "NOT_APPLICABLE": Counter({"NOT_APPLICABLE": 1}),
    "BOUNDARY_VALUE": Counter({"REVIEW_REQUIRED": 1}),
    "STALE_EVIDENCE": Counter({"REVIEW_REQUIRED": 1}),
    "FUTURE_EVIDENCE_LEAKAGE": Counter({"ABSTAIN": 1}),
    "INVALID_EVIDENCE_LINK": Counter({"ABSTAIN": 1}),
    "UNAPPROVED_RULE": Counter({"ABSTAIN": 1}),
    "RULE_VERSION_MISMATCH": Counter({"ABSTAIN": 1}),
    "MULTIPLE_COHERENT_DIAGNOSES": Counter({"VALIDATED": 2}),
    "MULTIPLE_CONFLICTING_DIAGNOSES": Counter({"REVIEW_REQUIRED": 2}),
    "NANDA_OMAHA_CROSS_TAXONOMY_OVERLAP": Counter(
        {"VALIDATED_WITH_LIMITATIONS": 2}
    ),
    "PARTIALLY_ASSESSABLE_DIAGNOSIS_SET": Counter(
        {"VALIDATED": 1, "INSUFFICIENT_EVIDENCE": 1}
    ),
    "EXPLANATION_TRACE_MISMATCH": Counter({"ABSTAIN": 1}),
    "UPSTREAM_VALIDATION_FAILURE": Counter({"ABSTAIN": 1}),
}

EXPECTED_SET_POLICY = {
    "MULTIPLE_COHERENT_DIAGNOSES": (
        "CROSS_TAXONOMY_OVERLAP_DISCLOSED",
        1.0,
        False,
    ),
    "MULTIPLE_CONFLICTING_DIAGNOSES": (
        "MUTUALLY_EXCLUSIVE_CANDIDATES",
        1.0,
        True,
    ),
    "NANDA_OMAHA_CROSS_TAXONOMY_OVERLAP": (
        "CROSS_TAXONOMY_OVERLAP_DISCLOSED",
        1.0,
        False,
    ),
    "PARTIALLY_ASSESSABLE_DIAGNOSIS_SET": (
        "PARTIALLY_ASSESSABLE",
        0.5,
        True,
    ),
}


def _materializer_frames(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    return {
        "candidates": frames["diagnosis_candidates"],
        "criteria": frames["diagnosis_candidate_criteria"],
        "evidence": frames["synthetic_evidence_items"],
        "links": frames["diagnosis_candidate_evidence_links"],
    }


def _evaluate(
    frames: dict[str, pd.DataFrame],
    registry: RuleRegistry,
    *,
    execution_mode: str = "fixture",
) -> tuple[list[DiagnosisCandidate], list[Any]]:
    candidates, criteria_by_id, evidence_by_id = materialize_fixture_contract(
        _materializer_frames(frames)
    )
    engine = ClinicalValidationEngine(registry, execution_mode=execution_mode)
    results = [
        engine.validate(
            candidate,
            criteria_by_id.get(candidate.diagnosis_candidate_id, []),
            evidence_by_id.get(candidate.diagnosis_candidate_id, []),
        )
        for candidate in candidates
    ]
    return candidates, apply_candidate_set_checks(candidates, results, registry)


@pytest.fixture(scope="module")
def fixture_bundle() -> dict[str, Any]:
    config = load_config("release", "fixture")
    registry = RuleRegistry.fixture()
    frames = build_fixture_frames(config, registry)
    candidates, results = _evaluate(frames, registry)
    return {
        "config": config,
        "registry": registry,
        "frames": frames,
        "candidates": candidates,
        "results": results,
    }


def _results_for(bundle: dict[str, Any], scenario_id: str) -> list[Any]:
    return [
        result
        for result in bundle["results"]
        if result.scenario_id == scenario_id
    ]


def test_fixture_contains_the_required_19_scenarios_and_23_candidates(
    fixture_bundle: dict[str, Any],
) -> None:
    frames = fixture_bundle["frames"]
    manifest = frames["scenario_manifest"]
    candidates = frames["diagnosis_candidates"]
    expected = frames["expected_validation_results"]

    assert set(manifest["scenario_id"]) == set(EXPECTED_STATUSES_BY_SCENARIO)
    assert len(manifest) == 19
    assert len(candidates) == 23
    assert len(expected) == 23
    assert candidates["diagnosis_candidate_id"].is_unique
    assert expected["diagnosis_candidate_id"].is_unique
    assert set(candidates["diagnosis_candidate_id"]) == set(
        expected["diagnosis_candidate_id"]
    )

    generated_counts = candidates.groupby("scenario_id").size().to_dict()
    manifest_counts = manifest.set_index("scenario_id")["candidate_count"].to_dict()
    assert generated_counts == manifest_counts


def test_generated_oracle_and_engine_match_the_independent_scenario_matrix(
    fixture_bundle: dict[str, Any],
) -> None:
    frames = fixture_bundle["frames"]
    results = fixture_bundle["results"]
    oracle = frames["expected_validation_results"].set_index(
        "diagnosis_candidate_id"
    )

    actual_by_scenario: dict[str, Counter[str]] = {}
    for scenario_id in EXPECTED_STATUSES_BY_SCENARIO:
        actual_by_scenario[scenario_id] = Counter(
            result.status.value
            for result in results
            if result.scenario_id == scenario_id
        )
    assert actual_by_scenario == EXPECTED_STATUSES_BY_SCENARIO

    for result in results:
        expected = oracle.loc[result.diagnosis_candidate_id]
        assert result.status.value == expected["expected_status"]
        assert result.cdei_status == expected["expected_cdei_status"]
        assert result.model_decision_confidence == pytest.approx(
            float(expected["expected_model_decision_confidence"])
        )
        assert result.confidence_type == expected["expected_confidence_type"]
        assert result.calibration_status == expected["expected_calibration_status"]
        assert result.profile_write_allowed is bool(
            expected["expected_profile_write_allowed"]
        )
        assert result.behavior_handoff_allowed is bool(
            expected["expected_behavior_handoff_allowed"]
        )
        assert (
            result.candidate_set_conflict_status
            == expected["expected_candidate_set_conflict_status"]
        )
        assert result.candidate_set_review_required is bool(
            expected["expected_candidate_set_review_required"]
        )

        raw_blocker = expected["expected_blocker"]
        expected_blocker = "" if pd.isna(raw_blocker) else str(raw_blocker)
        if expected_blocker:
            assert expected_blocker in result.blockers

        if result.status is ValidationStatus.ABSTAIN:
            assert result.clinical_validation_score is None
        else:
            assert result.clinical_validation_score is not None
            assert 0.0 <= result.clinical_validation_score <= 1.0
        assert result.cdei_score is not None
        assert 0.0 <= result.cdei_score <= 1.0


@pytest.mark.parametrize(
    ("scenario_id", "expected_status", "required_reason"),
    [
        ("NEGATIVE_CONTROL", "CONTRADICTED", "REQUIRED_CRITERION_NOT_MET"),
        (
            "MISSING_REQUIRED_EVIDENCE",
            "INSUFFICIENT_EVIDENCE",
            "REQUIRED_EVIDENCE_MISSING_OR_NOT_ASSESSABLE",
        ),
        ("EXCLUSION_TRIGGERED", "CONTRADICTED", "EXCLUSION_TRIGGERED"),
        (
            "CONTRADICTORY_EVIDENCE",
            "CONTRADICTED",
            "CONTRADICTORY_EVIDENCE_TRIGGERED",
        ),
        ("BOUNDARY_VALUE", "REVIEW_REQUIRED", "BOUNDARY_VALUE_REVIEW"),
        ("STALE_EVIDENCE", "REVIEW_REQUIRED", "STALE_EVIDENCE"),
        (
            "FUTURE_EVIDENCE_LEAKAGE",
            "ABSTAIN",
            "FUTURE_EVIDENCE_LEAKAGE",
        ),
        (
            "INVALID_EVIDENCE_LINK",
            "ABSTAIN",
            "INVALID_EVIDENCE_LINK",
        ),
        ("UNAPPROVED_RULE", "ABSTAIN", "BLOCKED_BY_LICENSE"),
        (
            "RULE_VERSION_MISMATCH",
            "ABSTAIN",
            "BLOCKED_BY_RULE_INTEGRITY",
        ),
        (
            "UPSTREAM_VALIDATION_FAILURE",
            "ABSTAIN",
            "BLOCKED_BY_UPSTREAM_VALIDATION",
        ),
    ],
)
def test_hard_gates_cannot_be_overridden_by_numeric_scores(
    fixture_bundle: dict[str, Any],
    scenario_id: str,
    expected_status: str,
    required_reason: str,
) -> None:
    results = _results_for(fixture_bundle, scenario_id)
    assert results
    for result in results:
        recorded_reasons = set(
            result.blockers + result.limitations + result.data_quality_issues
        )
        assert result.status.value == expected_status
        assert result.hard_gate_passed is False
        assert result.technical_gate_passed is False
        assert result.profile_write_allowed is False
        assert result.behavior_handoff_allowed is False
        if result.status is ValidationStatus.ABSTAIN:
            assert result.clinical_validation_score is None
        else:
            assert result.clinical_validation_score is not None
        assert required_reason in recorded_reasons


def test_explicit_exclusion_and_contradiction_traces_remain_separate(
    fixture_bundle: dict[str, Any],
) -> None:
    exclusion = _results_for(fixture_bundle, "EXCLUSION_TRIGGERED")[0]
    contradiction = _results_for(fixture_bundle, "CONTRADICTORY_EVIDENCE")[0]

    assert exclusion.exclusions_triggered
    assert exclusion.contradictions == []
    assert contradiction.contradictions
    assert contradiction.exclusions_triggered == []
    assert exclusion.status is ValidationStatus.CONTRADICTED
    assert contradiction.status is ValidationStatus.CONTRADICTED


def test_oracle_fields_and_generator_claims_cannot_affect_decisions(
    fixture_bundle: dict[str, Any],
) -> None:
    registry = fixture_bundle["registry"]
    original_frames = fixture_bundle["frames"]
    poisoned_frames = {
        name: frame.copy(deep=True) for name, frame in original_frames.items()
    }

    for frame in poisoned_frames.values():
        for column in [name for name in frame.columns if name.startswith("expected_")]:
            if pd.api.types.is_bool_dtype(frame[column]):
                frame[column] = ~frame[column].astype(bool)
            elif pd.api.types.is_numeric_dtype(frame[column]):
                frame[column] = 999999
            else:
                frame[column] = "ORACLE_POISON_MUST_NOT_ENTER_ENGINE"

    candidate_claims = poisoned_frames["diagnosis_candidates"]
    for column in (
        "criteria_met",
        "criteria_not_met",
        "criteria_not_assessable",
        "exclusions_detected",
        "contradictions_detected",
    ):
        candidate_claims[column] = json.dumps(["POISONED_GENERATOR_CLAIM"])

    _, poisoned_results = _evaluate(poisoned_frames, registry)
    original = [result.to_dict() for result in fixture_bundle["results"]]
    poisoned = [result.to_dict() for result in poisoned_results]

    assert poisoned == original
    assert not any(
        field.name.startswith("expected_") for field in fields(DiagnosisCandidate)
    )


def test_mutually_exclusive_candidates_are_downgraded_only_at_set_check(
    fixture_bundle: dict[str, Any],
) -> None:
    frames = fixture_bundle["frames"]
    registry = fixture_bundle["registry"]
    candidates, criteria_by_id, evidence_by_id = materialize_fixture_contract(
        _materializer_frames(frames)
    )
    candidates = [
        candidate
        for candidate in candidates
        if candidate.scenario_id == "MULTIPLE_CONFLICTING_DIAGNOSES"
    ]
    engine = ClinicalValidationEngine(registry, execution_mode="fixture")
    pre_conflict = [
        engine.validate(
            candidate,
            criteria_by_id[candidate.diagnosis_candidate_id],
            evidence_by_id[candidate.diagnosis_candidate_id],
        )
        for candidate in candidates
    ]
    assert {result.status for result in pre_conflict} == {ValidationStatus.VALIDATED}

    final = apply_candidate_set_checks(candidates, pre_conflict, registry)
    assert {result.status for result in final} == {ValidationStatus.REVIEW_REQUIRED}
    for result in final:
        assert result.candidate_set_conflict_status == "MUTUALLY_EXCLUSIVE_CANDIDATES"
        assert result.candidate_set_completeness == pytest.approx(1.0)
        assert result.candidate_set_review_required is True
        assert "MUTUALLY_EXCLUSIVE_CANDIDATE_CONFLICT" in result.limitations
        assert result.profile_write_allowed is False
        assert result.behavior_handoff_allowed is False


@pytest.mark.parametrize(
    "scenario_id",
    list(EXPECTED_SET_POLICY),
)
def test_candidate_set_status_completeness_and_review_policy(
    fixture_bundle: dict[str, Any], scenario_id: str
) -> None:
    expected_status, expected_completeness, expected_review = EXPECTED_SET_POLICY[
        scenario_id
    ]
    results = _results_for(fixture_bundle, scenario_id)
    assert len(results) == 2
    assert {result.candidate_set_conflict_status for result in results} == {
        expected_status
    }
    assert {
        result.candidate_set_completeness for result in results
    } == {expected_completeness}
    assert {result.candidate_set_review_required for result in results} == {
        expected_review
    }


def test_cross_taxonomy_candidates_are_disclosed_without_rule_merging(
    fixture_bundle: dict[str, Any],
) -> None:
    results = _results_for(
        fixture_bundle, "NANDA_OMAHA_CROSS_TAXONOMY_OVERLAP"
    )
    assert {result.taxonomy for result in results} == {"NANDA", "OMAHA"}
    assert len({result.rule_id for result in results}) == 2
    assert {result.status for result in results} == {
        ValidationStatus.VALIDATED_WITH_LIMITATIONS
    }
    assert {result.candidate_set_conflict_status for result in results} == {
        "CROSS_TAXONOMY_OVERLAP_DISCLOSED"
    }


def test_partially_assessable_set_preserves_candidate_level_independence(
    fixture_bundle: dict[str, Any],
) -> None:
    results = _results_for(
        fixture_bundle, "PARTIALLY_ASSESSABLE_DIAGNOSIS_SET"
    )
    by_status = {result.status: result for result in results}
    assert set(by_status) == {
        ValidationStatus.VALIDATED,
        ValidationStatus.INSUFFICIENT_EVIDENCE,
    }
    assert all(
        result.candidate_set_completeness == pytest.approx(0.5)
        for result in results
    )
    assert by_status[ValidationStatus.VALIDATED].hard_gate_passed is True
    assert (
        by_status[ValidationStatus.INSUFFICIENT_EVIDENCE].hard_gate_passed
        is False
    )


def test_cdei_unfaithful_explanation_forces_abstention_and_blocks_handoff(
    fixture_bundle: dict[str, Any],
) -> None:
    result = _results_for(fixture_bundle, "EXPLANATION_TRACE_MISMATCH")[0]

    assert result.clinical_validation_score is None
    assert result.cdei_status == "UNFAITHFUL_EXPLANATION"
    assert result.cdei_components["narrative_faithfulness"] == 0.0
    assert result.cdei_components["groundedness"] == 0.0
    assert result.status is ValidationStatus.ABSTAIN
    assert result.hard_gate_passed is False
    assert "EXPLANATION_TRACE_MISMATCH" in result.limitations
    assert "EXPLANATION_FAITHFULNESS_ERROR" in result.data_quality_issues
    assert result.behavior_handoff_allowed is False


def test_fixture_generation_is_logically_and_byte_deterministic(
    fixture_bundle: dict[str, Any], tmp_path: Path
) -> None:
    config: PrototypeConfig = fixture_bundle["config"]
    registry: RuleRegistry = fixture_bundle["registry"]
    first_frames = build_fixture_frames(config, registry)
    second_frames = build_fixture_frames(config, registry)

    assert first_frames.keys() == second_frames.keys()
    for name in first_frames:
        pd.testing.assert_frame_equal(first_frames[name], second_frames[name])

    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_manifest = write_fixture_dataset(config, first_root, registry)
    second_manifest = write_fixture_dataset(config, second_root, registry)
    assert first_manifest == second_manifest
    assert first_manifest["scenario_count"] == 19
    assert first_manifest["candidate_count"] == 23
    assert first_manifest["clinical_truth_claimed"] is False

    first_files = {path.name: path for path in first_root.iterdir()}
    second_files = {path.name: path for path in second_root.iterdir()}
    assert first_files.keys() == second_files.keys()
    for name in first_files:
        assert first_files[name].read_bytes() == second_files[name].read_bytes()


@pytest.mark.parametrize(
    ("execution_mode", "expected_status"),
    [
        ("fixture", ValidationStatus.VALIDATED),
        ("artifact", ValidationStatus.VALIDATED),
        ("db", ValidationStatus.ABSTAIN),
    ],
)
def test_test_only_rules_never_enable_profile_or_behavior_handoff(
    fixture_bundle: dict[str, Any],
    execution_mode: str,
    expected_status: ValidationStatus,
) -> None:
    frames = fixture_bundle["frames"]
    registry = fixture_bundle["registry"]
    candidates, criteria_by_id, evidence_by_id = materialize_fixture_contract(
        _materializer_frames(frames)
    )
    candidate = next(
        item for item in candidates if item.scenario_id == "POSITIVE_CONTROL"
    )
    result = ClinicalValidationEngine(registry, execution_mode).validate(
        candidate,
        criteria_by_id[candidate.diagnosis_candidate_id],
        evidence_by_id[candidate.diagnosis_candidate_id],
    )

    assert result.status is expected_status
    assert result.profile_write_allowed is False
    assert result.behavior_handoff_allowed is False
    if execution_mode in {"fixture", "artifact"}:
        assert result.technical_gate_passed is True
        assert result.behavior_handoff_mode == "TEST_ONLY_BLOCKED"
        assert result.behavior_handoff_reason == "RULE_NOT_APPROVED_FOR_OPERATION"
    else:
        assert result.technical_gate_passed is False
        assert result.behavior_handoff_mode == "BLOCKED"


def test_serialized_output_contract_blocks_every_synthetic_fixture_handoff(
    fixture_bundle: dict[str, Any],
) -> None:
    config: PrototypeConfig = fixture_bundle["config"]
    registry: RuleRegistry = fixture_bundle["registry"]
    candidates_by_id = {
        candidate.diagnosis_candidate_id: candidate
        for candidate in fixture_bundle["candidates"]
    }

    for result in fixture_bundle["results"]:
        candidate = candidates_by_id[result.diagnosis_candidate_id]
        rule = registry.get(result.rule_id) if result.rule_id else None
        contract = output_contract(
            candidate,
            result,
            model_version=config.model_version,
            run_id="release_test_run",
            environment="release",
            execution_mode="fixture",
            data_snapshot_id=None,
            rule_source_ids=(
                list(rule.provenance.get("source_ids", [])) if rule else []
            ),
        )
        assert contract["profile_write_allowed"] is False
        assert contract["behavior_layer_handoff"]["allowed"] is False
        assert contract["is_synthetic"] is True
        assert "expected_" not in json.dumps(contract, sort_keys=True)
