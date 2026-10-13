from __future__ import annotations

import json

import pytest

from sibc_clinical_validation.behavior_handoff import decide_handoff
from sibc_clinical_validation.config import load_config
from sibc_clinical_validation.evidence import (
    FixtureContractError,
    materialize_fixture_contract,
)
from sibc_clinical_validation.models import ValidationStatus, parse_bool
from sibc_clinical_validation.rule_schema import RuleRegistry
from sibc_clinical_validation.synthetic import build_fixture_frames
from sibc_clinical_validation.validation import ClinicalValidationEngine


def _materializer_frames(frames):
    return {
        "candidates": frames["diagnosis_candidates"],
        "criteria": frames["diagnosis_candidate_criteria"],
        "evidence": frames["synthetic_evidence_items"],
        "links": frames["diagnosis_candidate_evidence_links"],
    }


def _positive(frames, registry):
    candidates, criteria_by_id, evidence_by_id = materialize_fixture_contract(
        _materializer_frames(frames)
    )
    candidate = next(item for item in candidates if item.scenario_id == "POSITIVE_CONTROL")
    result = ClinicalValidationEngine(registry, "fixture").validate(
        candidate,
        criteria_by_id[candidate.diagnosis_candidate_id],
        evidence_by_id[candidate.diagnosis_candidate_id],
    )
    return candidate, result


@pytest.mark.parametrize(
    ("value", "expected"),
    [(True, True), (False, False), (1, True), (0, False), ("true", True), ("False", False)],
)
def test_strict_boolean_parser(value, expected):
    assert parse_bool(value) is expected


@pytest.mark.parametrize("value", ["yes", "", 2, None, object()])
def test_strict_boolean_parser_rejects_ambiguous_values(value):
    with pytest.raises(ValueError, match="strict boolean"):
        parse_bool(value)


def test_false_string_cannot_be_treated_as_synthetic():
    config = load_config("release", "fixture")
    registry = RuleRegistry.fixture()
    frames = build_fixture_frames(config, registry)
    frames["diagnosis_candidates"]["is_synthetic"] = frames[
        "diagnosis_candidates"
    ]["is_synthetic"].astype(object)
    frames["diagnosis_candidates"].loc[0, "is_synthetic"] = "False"
    with pytest.raises(FixtureContractError, match="non-synthetic"):
        from sibc_clinical_validation.evidence import _assert_synthetic

        _assert_synthetic(frames["diagnosis_candidates"], "candidates")


@pytest.mark.parametrize(
    ("column", "bad_value", "issue"),
    [
        ("source", "UNAPPROVED_SOURCE", "DISALLOWED_EVIDENCE_SOURCE"),
        ("unit", "WRONG_UNIT", "DISALLOWED_EVIDENCE_UNIT"),
    ],
)
def test_disallowed_measurement_source_or_unit_abstains_and_changes_fingerprint(
    column, bad_value, issue
):
    config = load_config("release", "fixture")
    registry = RuleRegistry.fixture()
    baseline_frames = build_fixture_frames(config, registry)
    _, baseline = _positive(baseline_frames, registry)

    changed_frames = build_fixture_frames(config, registry)
    evidence = changed_frames["synthetic_evidence_items"]
    mask = evidence["scenario_id"].eq("POSITIVE_CONTROL")
    evidence.loc[mask, column] = bad_value
    _, changed = _positive(changed_frames, registry)

    assert changed.status is ValidationStatus.ABSTAIN
    assert changed.clinical_validation_score is None
    assert "BLOCKED_BY_DATA" in changed.blockers
    assert issue in changed.data_quality_issues
    assert changed.decision_fingerprint != baseline.decision_fingerprint


def test_reasoning_trace_change_is_covered_by_decision_fingerprint():
    config = load_config("release", "fixture")
    registry = RuleRegistry.fixture()
    baseline_frames = build_fixture_frames(config, registry)
    _, baseline = _positive(baseline_frames, registry)

    changed_frames = build_fixture_frames(config, registry)
    candidates = changed_frames["diagnosis_candidates"]
    index = candidates.index[candidates["scenario_id"].eq("POSITIVE_CONTROL")][0]
    trace = json.loads(candidates.at[index, "clinical_reasoning_trace"])
    trace["non_decision_note"] = "TRACE_REVISION"
    candidates.at[index, "clinical_reasoning_trace"] = json.dumps(trace, sort_keys=True)
    _, changed = _positive(changed_frames, registry)

    assert changed.status is baseline.status
    assert changed.decision_fingerprint != baseline.decision_fingerprint


def test_claimed_criterion_state_must_match_independently_mapped_evidence_code():
    config = load_config("release", "fixture")
    registry = RuleRegistry.fixture()
    frames = build_fixture_frames(config, registry)
    criteria = frames["diagnosis_candidate_criteria"]
    mask = criteria["scenario_id"].eq("POSITIVE_CONTROL") & criteria[
        "criterion_role"
    ].eq("REQUIRED")
    criteria.loc[mask, "criterion_state"] = "NOT_MET"
    candidate, result = _positive(frames, registry)
    del candidate

    assert result.status is ValidationStatus.ABSTAIN
    assert "BLOCKED_BY_CLINICAL_LAYER_CONTRACT" in result.blockers
    assert "CRITERION_STATE_EVIDENCE_MISMATCH" in result.data_quality_issues


def test_required_criterion_cannot_validate_without_eligible_linked_evidence():
    config = load_config("release", "fixture")
    registry = RuleRegistry.fixture()
    frames = build_fixture_frames(config, registry)
    scenario = "POSITIVE_CONTROL"
    criteria = frames["diagnosis_candidate_criteria"]
    required_mask = criteria["scenario_id"].eq(scenario) & criteria[
        "criterion_role"
    ].eq("REQUIRED")
    required_evidence_id = json.loads(criteria.loc[required_mask, "evidence_ids"].iloc[0])[0]
    criteria.loc[required_mask, "evidence_ids"] = "[]"
    frames["diagnosis_candidate_evidence_links"] = frames[
        "diagnosis_candidate_evidence_links"
    ].loc[
        ~frames["diagnosis_candidate_evidence_links"]["evidence_id"].eq(
            required_evidence_id
        )
    ]
    frames["synthetic_evidence_items"] = frames["synthetic_evidence_items"].loc[
        ~frames["synthetic_evidence_items"]["evidence_id"].eq(required_evidence_id)
    ]
    candidates = frames["diagnosis_candidates"]
    candidate_mask = candidates["scenario_id"].eq(scenario)
    source_ids = json.loads(candidates.loc[candidate_mask, "source_evidence_ids"].iloc[0])
    candidates.loc[candidate_mask, "source_evidence_ids"] = json.dumps(
        [item for item in source_ids if item != required_evidence_id]
    )
    trace = json.loads(candidates.loc[candidate_mask, "clinical_reasoning_trace"].iloc[0])
    trace["evidence_ids"] = [
        item for item in trace["evidence_ids"] if item != required_evidence_id
    ]
    candidates.loc[candidate_mask, "clinical_reasoning_trace"] = json.dumps(
        trace, sort_keys=True
    )

    _, result = _positive(frames, registry)
    assert result.status is ValidationStatus.INSUFFICIENT_EVIDENCE
    assert result.hard_gate_passed is False
    assert "REQUIRED_EVIDENCE_LINK_MISSING" in result.data_quality_issues
    assert result.cdei_status == "INSUFFICIENT_TRACEABILITY"


def test_reference_standard_blocks_even_an_operational_rule_handoff():
    allowed = decide_handoff(
        ValidationStatus.VALIDATED,
        "APPROVED_FOR_OPERATION",
        "BLOCKED_BY_REFERENCE_STANDARD",
    )
    assert allowed[0] is False
    assert allowed[1] is False
    assert allowed[3] == "BLOCKED_BY_REFERENCE_STANDARD"
    assert allowed[4] is True


def test_future_invalid_link_and_unfaithful_explanation_abstain():
    config = load_config("release", "fixture")
    registry = RuleRegistry.fixture()
    frames = build_fixture_frames(config, registry)
    candidates, criteria_by_id, evidence_by_id = materialize_fixture_contract(
        _materializer_frames(frames)
    )
    engine = ClinicalValidationEngine(registry, "fixture")
    results = {
        candidate.scenario_id: engine.validate(
            candidate,
            criteria_by_id[candidate.diagnosis_candidate_id],
            evidence_by_id[candidate.diagnosis_candidate_id],
        )
        for candidate in candidates
        if candidate.scenario_id
        in {
            "FUTURE_EVIDENCE_LEAKAGE",
            "INVALID_EVIDENCE_LINK",
            "EXPLANATION_TRACE_MISMATCH",
        }
    }
    assert all(result.status is ValidationStatus.ABSTAIN for result in results.values())
    assert results["INVALID_EVIDENCE_LINK"].cdei_status == "INSUFFICIENT_TRACEABILITY"
    assert results["EXPLANATION_TRACE_MISMATCH"].cdei_status == "UNFAITHFUL_EXPLANATION"
