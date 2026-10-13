from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .config import FIXTURE_ROOT, PrototypeConfig
from .rule_schema import DiagnosisRule, RuleRegistry


DATA_ORIGIN = "SYNTHETIC_CLINICAL_LAYER_OUTPUT"
EVIDENCE_ORIGIN = "SYNTHETIC_TEST_EVIDENCE"
ORACLE_POLICY_VERSION = "fixture_oracle_policy_v0.1"


@dataclass(frozen=True)
class ScenarioCandidateSpec:
    scenario_id: str
    candidate_suffix: str
    rule_id: str
    expected_status: str
    purpose: str
    app_state: str = "MET"
    required_state: str = "MET"
    supporting_state: str = "MET"
    exclusion_state: str = "NOT_MET"
    contradiction_state: str = "NOT_MET"
    omit_roles: tuple[str, ...] = ()
    evidence_time: str = "VALID"
    required_quality: str = "ACCEPTABLE"
    invalid_link: bool = False
    trace_mismatch: bool = False
    upstream_validation_status: str = "VALIDATED"
    rule_version_override: str | None = None
    coexisting_suffixes: tuple[str, ...] = ()
    mutually_exclusive_suffixes: tuple[str, ...] = ()
    expected_cdei_status: str = "COMPLETE"
    expected_blocker: str = ""
    expected_set_status: str = "NONE"
    expected_set_review_required: bool = False


def _scenario_specs() -> list[ScenarioCandidateSpec]:
    return [
        ScenarioCandidateSpec("POSITIVE_CONTROL", "A", "CLV-TEST-OMAHA-A", "VALIDATED", "All required technical gates pass."),
        ScenarioCandidateSpec("NEGATIVE_CONTROL", "A", "CLV-TEST-OMAHA-A", "CONTRADICTED", "A required criterion is explicitly not met.", required_state="NOT_MET"),
        ScenarioCandidateSpec("MISSING_REQUIRED_EVIDENCE", "A", "CLV-TEST-OMAHA-A", "INSUFFICIENT_EVIDENCE", "The required criterion and its evidence are absent.", omit_roles=("REQUIRED",)),
        ScenarioCandidateSpec("PARTIAL_SUPPORT", "A", "CLV-TEST-OMAHA-A", "VALIDATED_WITH_LIMITATIONS", "Required evidence passes while supporting evidence is not assessable.", supporting_state="NOT_ASSESSABLE"),
        ScenarioCandidateSpec("EXCLUSION_TRIGGERED", "A", "CLV-TEST-OMAHA-A", "CONTRADICTED", "A hard exclusion is triggered.", exclusion_state="MET"),
        ScenarioCandidateSpec("CONTRADICTORY_EVIDENCE", "A", "CLV-TEST-OMAHA-A", "CONTRADICTED", "Material contradictory evidence is triggered.", contradiction_state="MET"),
        ScenarioCandidateSpec("NOT_APPLICABLE", "A", "CLV-TEST-OMAHA-A", "NOT_APPLICABLE", "The applicability context does not match.", app_state="NOT_MET"),
        ScenarioCandidateSpec("BOUNDARY_VALUE", "A", "CLV-TEST-OMAHA-A", "REVIEW_REQUIRED", "A boundary flag requires review without changing a threshold.", required_quality="BOUNDARY_REVIEW"),
        ScenarioCandidateSpec("STALE_EVIDENCE", "A", "CLV-TEST-OMAHA-A", "REVIEW_REQUIRED", "Required evidence exceeds the configured freshness limit.", evidence_time="STALE"),
        ScenarioCandidateSpec("FUTURE_EVIDENCE_LEAKAGE", "A", "CLV-TEST-OMAHA-A", "ABSTAIN", "Evidence after index_datetime must never be used.", evidence_time="FUTURE", expected_blocker="BLOCKED_BY_DATA"),
        ScenarioCandidateSpec("INVALID_EVIDENCE_LINK", "A", "CLV-TEST-OMAHA-A", "ABSTAIN", "An evidence link points to the wrong criterion.", invalid_link=True, expected_cdei_status="INSUFFICIENT_TRACEABILITY", expected_blocker="BLOCKED_BY_CLINICAL_LAYER_CONTRACT"),
        ScenarioCandidateSpec("UNAPPROVED_RULE", "D", "CLV-RESEARCH-ONLY-D", "ABSTAIN", "A research-only rule cannot produce a validated decision.", expected_blocker="BLOCKED_BY_LICENSE"),
        ScenarioCandidateSpec("RULE_VERSION_MISMATCH", "A", "CLV-TEST-OMAHA-A", "ABSTAIN", "Candidate and registry rule versions differ.", rule_version_override="0.0.9", expected_blocker="BLOCKED_BY_RULE_INTEGRITY"),
        ScenarioCandidateSpec("MULTIPLE_COHERENT_DIAGNOSES", "A", "CLV-TEST-OMAHA-A", "VALIDATED", "Two candidates coexist without a declared conflict.", coexisting_suffixes=("B",), expected_set_status="CROSS_TAXONOMY_OVERLAP_DISCLOSED"),
        ScenarioCandidateSpec("MULTIPLE_COHERENT_DIAGNOSES", "B", "CLV-TEST-NANDA-B", "VALIDATED", "Two candidates coexist without a declared conflict.", coexisting_suffixes=("A",), expected_set_status="CROSS_TAXONOMY_OVERLAP_DISCLOSED"),
        ScenarioCandidateSpec("MULTIPLE_CONFLICTING_DIAGNOSES", "A", "CLV-TEST-OMAHA-A", "REVIEW_REQUIRED", "Mutually exclusive candidates require set-level review.", mutually_exclusive_suffixes=("C",), expected_set_status="MUTUALLY_EXCLUSIVE_CANDIDATES", expected_set_review_required=True),
        ScenarioCandidateSpec("MULTIPLE_CONFLICTING_DIAGNOSES", "C", "CLV-TEST-OMAHA-C", "REVIEW_REQUIRED", "Mutually exclusive candidates require set-level review.", mutually_exclusive_suffixes=("A",), expected_set_status="MUTUALLY_EXCLUSIVE_CANDIDATES", expected_set_review_required=True),
        ScenarioCandidateSpec("NANDA_OMAHA_CROSS_TAXONOMY_OVERLAP", "A", "CLV-TEST-OMAHA-A", "VALIDATED_WITH_LIMITATIONS", "Cross-taxonomy overlap is disclosed and never merged.", supporting_state="NOT_ASSESSABLE", coexisting_suffixes=("B",), expected_set_status="CROSS_TAXONOMY_OVERLAP_DISCLOSED"),
        ScenarioCandidateSpec("NANDA_OMAHA_CROSS_TAXONOMY_OVERLAP", "B", "CLV-TEST-NANDA-B", "VALIDATED_WITH_LIMITATIONS", "Cross-taxonomy overlap is disclosed and never merged.", supporting_state="NOT_ASSESSABLE", coexisting_suffixes=("A",), expected_set_status="CROSS_TAXONOMY_OVERLAP_DISCLOSED"),
        ScenarioCandidateSpec("PARTIALLY_ASSESSABLE_DIAGNOSIS_SET", "A", "CLV-TEST-OMAHA-A", "VALIDATED", "One candidate passes and another lacks required evidence.", coexisting_suffixes=("B",), expected_set_status="PARTIALLY_ASSESSABLE", expected_set_review_required=True),
        ScenarioCandidateSpec("PARTIALLY_ASSESSABLE_DIAGNOSIS_SET", "B", "CLV-TEST-NANDA-B", "INSUFFICIENT_EVIDENCE", "One candidate passes and another lacks required evidence.", omit_roles=("REQUIRED",), coexisting_suffixes=("A",), expected_set_status="PARTIALLY_ASSESSABLE", expected_set_review_required=True),
        ScenarioCandidateSpec("EXPLANATION_TRACE_MISMATCH", "A", "CLV-TEST-OMAHA-A", "ABSTAIN", "The narrative trace contains an ungrounded evidence reference.", trace_mismatch=True, expected_cdei_status="UNFAITHFUL_EXPLANATION"),
        ScenarioCandidateSpec("UPSTREAM_VALIDATION_FAILURE", "A", "CLV-TEST-OMAHA-A", "ABSTAIN", "Upstream validation excludes the candidate evidence.", upstream_validation_status="EXCLUDED", expected_blocker="BLOCKED_BY_UPSTREAM_VALIDATION"),
    ]


def _common(
    spec: ScenarioCandidateSpec,
    config: PrototypeConfig,
    rule: DiagnosisRule,
) -> dict[str, Any]:
    return {
        "data_origin": DATA_ORIGIN,
        "is_synthetic": True,
        "generator_version": config.generator_version,
        "scenario_id": spec.scenario_id,
        "source_rule_ids": json.dumps([rule.rule_id]),
        "source_versions": json.dumps([rule.rule_version]),
        "source_rule_hashes": json.dumps(
            [
                hashlib.sha256(
                    json.dumps(rule.raw, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
            ]
        ),
        "generation_timestamp": config.fixture_generation_timestamp,
        "expected_validation_result": spec.expected_status,
        "intended_test_purpose": spec.purpose,
    }


def _candidate_id(spec: ScenarioCandidateSpec) -> str:
    return f"SYN-{spec.scenario_id}-{spec.candidate_suffix}"


def _case_id(spec: ScenarioCandidateSpec) -> str:
    digest = hashlib.sha256(spec.scenario_id.encode()).hexdigest()[:12]
    return f"SC_{digest}"


def _criterion_state(spec: ScenarioCandidateSpec, role: str) -> str:
    return {
        "APPLICABILITY": spec.app_state,
        "REQUIRED": spec.required_state,
        "SUPPORTING": spec.supporting_state,
        "EXCLUSION": spec.exclusion_state,
        "CONTRADICTION": spec.contradiction_state,
        "RELATED_FACTOR": "NOT_ASSESSABLE",
        "RISK_FACTOR": "NOT_ASSESSABLE",
    }[role]


def _evidence_datetime(index_datetime: datetime, mode: str) -> datetime:
    if mode == "STALE":
        return index_datetime - timedelta(days=45)
    if mode == "FUTURE":
        return index_datetime + timedelta(seconds=1)
    return index_datetime - timedelta(days=7)


def build_fixture_frames(
    config: PrototypeConfig, registry: RuleRegistry | None = None
) -> dict[str, pd.DataFrame]:
    registry = registry or RuleRegistry.fixture()
    index_datetime = datetime.fromisoformat(
        config.fixture_index_datetime.replace("Z", "+00:00")
    ).astimezone(timezone.utc)
    candidates: list[dict[str, Any]] = []
    criteria_rows: list[dict[str, Any]] = []
    link_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    conflict_rows: list[dict[str, Any]] = []
    expected_rows: list[dict[str, Any]] = []
    manifest_by_scenario: dict[str, dict[str, Any]] = {}

    for spec in _scenario_specs():
        rule = registry.get(spec.rule_id)
        if rule is None:
            raise ValueError(f"Fixture spec references unknown rule: {spec.rule_id}")
        common = _common(spec, config, rule)
        candidate_id = _candidate_id(spec)
        case_id = _case_id(spec)
        criterion_entries: list[dict[str, Any]] = []
        evidence_ids: list[str] = []

        for ordinal, criterion in enumerate(rule.criterion_specs(), start=1):
            role = criterion.role.value
            if role in spec.omit_roles:
                continue
            evidence_id = ""
            criterion_evidence_ids: list[str] = []
            if role != "APPLICABILITY":
                evidence_id = f"E-{candidate_id}-{ordinal:02d}"
                evidence_ids.append(evidence_id)
                criterion_evidence_ids = [evidence_id]
                measured_datetime = _evidence_datetime(
                    index_datetime,
                    spec.evidence_time if role == "REQUIRED" else "VALID",
                )
                quality = (
                    spec.required_quality if role == "REQUIRED" else "ACCEPTABLE"
                )
                evidence_common = dict(common)
                evidence_common["data_origin"] = EVIDENCE_ORIGIN
                evidence_rows.append(
                    {
                        **evidence_common,
                        "synthetic_case_id": case_id,
                        "diagnosis_candidate_id": candidate_id,
                        "evidence_id": evidence_id,
                        "feature_id": criterion.feature_id,
                        "evidence_value_code": f"TEST_{_criterion_state(spec, role)}",
                        "unit": "FLAG" if role in {"EXCLUSION", "CONTRADICTION"} else "TEST_UNIT",
                        "measured_datetime": measured_datetime.isoformat(),
                        "source": "SYNTHETIC_TEST_SOURCE",
                        "quality_status": quality,
                        "upstream_validation_status": "VALIDATED",
                        "eligible": True,
                        "provenance": "DETERMINISTIC_FIXTURE_GENERATOR",
                    }
                )
                link_criterion = (
                    "INVALID-CRITERION"
                    if spec.invalid_link and role == "REQUIRED"
                    else criterion.criterion_id
                )
                link_rows.append(
                    {
                        **common,
                        "synthetic_case_id": case_id,
                        "diagnosis_candidate_id": candidate_id,
                        "evidence_id": evidence_id,
                        "criterion_id": link_criterion,
                        "feature_id": criterion.feature_id,
                        "link_status": "CLAIMED_BY_SYNTHETIC_DIAGNOSIS_ENGINE",
                    }
                )

            criterion_entries.append(
                {
                    **common,
                    "synthetic_case_id": case_id,
                    "diagnosis_candidate_id": candidate_id,
                    "criterion_id": criterion.criterion_id,
                    "feature_id": criterion.feature_id,
                    "criterion_role": role,
                    "criterion_state": _criterion_state(spec, role),
                    "evidence_ids": json.dumps(criterion_evidence_ids),
                    "rationale_code": "SYNTHETIC_TEST_ASSERTION",
                }
            )

        criteria_rows.extend(criterion_entries)
        criterion_ids = [row["criterion_id"] for row in criterion_entries]
        trace_evidence = list(evidence_ids)
        if spec.trace_mismatch:
            trace_evidence.append("E-UNGROUNDED-TRACE")
        trace = {
            "rule_id": rule.rule_id,
            "criterion_ids": criterion_ids,
            "evidence_ids": trace_evidence,
            "limitations_disclosed": True,
            "trace_type": "SYNTHETIC_TECHNICAL_ORACLE",
        }
        coexisting_ids = [
            f"SYN-{spec.scenario_id}-{suffix}" for suffix in spec.coexisting_suffixes
        ]
        mutually_exclusive_ids = [
            f"SYN-{spec.scenario_id}-{suffix}"
            for suffix in spec.mutually_exclusive_suffixes
        ]
        states_by_role: dict[str, list[str]] = {
            "MET": [],
            "NOT_MET": [],
            "NOT_ASSESSABLE": [],
        }
        for row in criterion_entries:
            states_by_role[row["criterion_state"]].append(row["criterion_id"])
        candidates.append(
            {
                **common,
                "synthetic_case_id": case_id,
                "diagnosis_candidate_id": candidate_id,
                "taxonomy": rule.taxonomy,
                "diagnosis_code_reference": rule.diagnosis_code_reference,
                "diagnosis_name_reference": rule.diagnosis_name_reference,
                "diagnosis_type": rule.diagnosis_type,
                "candidate_status": "GENERATED_NOT_VALIDATED",
                "applied_rule_ids": json.dumps([rule.rule_id]),
                "applied_rule_version": spec.rule_version_override or rule.rule_version,
                "source_evidence_ids": json.dumps(sorted(evidence_ids)),
                "criteria_met": json.dumps(sorted(states_by_role["MET"])),
                "criteria_not_met": json.dumps(sorted(states_by_role["NOT_MET"])),
                "criteria_not_assessable": json.dumps(
                    sorted(states_by_role["NOT_ASSESSABLE"])
                ),
                "exclusions_detected": json.dumps(
                    sorted(
                        row["criterion_id"]
                        for row in criterion_entries
                        if row["criterion_role"] == "EXCLUSION"
                        and row["criterion_state"] == "MET"
                    )
                ),
                "contradictions_detected": json.dumps(
                    sorted(
                        row["criterion_id"]
                        for row in criterion_entries
                        if row["criterion_role"] == "CONTRADICTION"
                        and row["criterion_state"] == "MET"
                    )
                ),
                "related_factors_detected": "[]",
                "risk_factors_detected": "[]",
                "signs_symptoms_detected": "[]",
                "index_datetime": index_datetime.isoformat(),
                "observation_window": "P30D",
                "clinical_reasoning_trace": json.dumps(trace, sort_keys=True),
                "candidate_priority": 1 if spec.candidate_suffix == "A" else 2,
                "coexisting_diagnosis_ids": json.dumps(coexisting_ids),
                "mutually_exclusive_diagnosis_ids": json.dumps(
                    mutually_exclusive_ids
                ),
                "expected_validation_status": spec.expected_status,
                "expected_profile_write_allowed": False,
                "expected_behavior_handoff_allowed": False,
                "upstream_validation_status": spec.upstream_validation_status,
            }
        )
        conflict_rows.append(
            {
                **common,
                "synthetic_case_id": case_id,
                "diagnosis_candidate_id": candidate_id,
                "coexisting_diagnosis_ids": json.dumps(coexisting_ids),
                "mutually_exclusive_diagnosis_ids": json.dumps(
                    mutually_exclusive_ids
                ),
                "expected_candidate_set_conflict_status": spec.expected_set_status,
                "expected_candidate_set_review_required": spec.expected_set_review_required,
            }
        )
        expected_rows.append(
            {
                **common,
                "oracle_policy_version": ORACLE_POLICY_VERSION,
                "synthetic_case_id": case_id,
                "diagnosis_candidate_id": candidate_id,
                "expected_status": spec.expected_status,
                "expected_cdei_status": spec.expected_cdei_status,
                "expected_blocker": spec.expected_blocker,
                "expected_model_decision_confidence": 0.0,
                "expected_confidence_type": "rule_decision_stability_index",
                "expected_calibration_status": "NOT_CALIBRATED",
                "expected_profile_write_allowed": False,
                "expected_behavior_handoff_allowed": False,
                "expected_candidate_set_conflict_status": spec.expected_set_status,
                "expected_candidate_set_review_required": spec.expected_set_review_required,
                "score_constraint": "0<=score<=1;never_interpret_as_probability",
                "cdei_constraint": "0<=cdei<=1;never_interpret_as_accuracy",
            }
        )
        manifest = manifest_by_scenario.setdefault(
            spec.scenario_id,
            {
                **common,
                "synthetic_case_id": case_id,
                "candidate_count": 0,
                "expected_statuses": [],
                "oracle_type": "TECHNICAL_EXPECTATION_NOT_CLINICAL_TRUTH",
            },
        )
        manifest["candidate_count"] += 1
        manifest["expected_statuses"].append(spec.expected_status)

    scenario_manifest = []
    for scenario_id in sorted(manifest_by_scenario):
        row = dict(manifest_by_scenario[scenario_id])
        row["expected_statuses"] = json.dumps(row["expected_statuses"])
        scenario_manifest.append(row)

    return {
        "diagnosis_candidates": pd.DataFrame(candidates),
        "diagnosis_candidate_evidence_links": pd.DataFrame(link_rows),
        "diagnosis_candidate_criteria": pd.DataFrame(criteria_rows),
        "diagnosis_candidate_conflicts": pd.DataFrame(conflict_rows),
        "synthetic_evidence_items": pd.DataFrame(evidence_rows),
        "scenario_manifest": pd.DataFrame(scenario_manifest),
        "expected_validation_results": pd.DataFrame(expected_rows),
    }


def frame_logical_sha256(frame: pd.DataFrame) -> str:
    payload = frame.to_json(orient="records", date_format="iso", force_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_fixture_dataset(
    config: PrototypeConfig,
    destination: Path = FIXTURE_ROOT,
    registry: RuleRegistry | None = None,
) -> dict[str, Any]:
    destination.mkdir(parents=True, exist_ok=True)
    frames = build_fixture_frames(config, registry)
    file_map = {
        "diagnosis_candidates": "diagnosis_candidates.parquet",
        "diagnosis_candidate_evidence_links": "diagnosis_candidate_evidence_links.parquet",
        "diagnosis_candidate_criteria": "diagnosis_candidate_criteria.parquet",
        "diagnosis_candidate_conflicts": "diagnosis_candidate_conflicts.parquet",
        "synthetic_evidence_items": "synthetic_evidence_items.parquet",
        "scenario_manifest": "scenario_manifest.csv",
        "expected_validation_results": "expected_validation_results.csv",
    }
    files: dict[str, Any] = {}
    for name, filename in file_map.items():
        path = destination / filename
        temporary = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
        frame = frames[name]
        if path.suffix == ".parquet":
            frame.to_parquet(temporary, index=False)
        else:
            frame.to_csv(temporary, index=False)
        os.replace(temporary, path)
        files[filename] = {
            "rows": len(frame),
            "columns": list(frame.columns),
            "logical_sha256": frame_logical_sha256(frame),
        }
    manifest = {
        "dataset_name": "synthetic_clinical_layer",
        "data_origin": DATA_ORIGIN,
        "is_synthetic": True,
        "generator_version": config.generator_version,
        "generation_timestamp": config.fixture_generation_timestamp,
        "random_seed": config.random_seed,
        "oracle_policy_version": ORACLE_POLICY_VERSION,
        "scenario_count": len(frames["scenario_manifest"]),
        "candidate_count": len(frames["diagnosis_candidates"]),
        "files": files,
        "clinical_truth_claimed": False,
        "allowed_claims": [
            "TECHNICAL_VALIDATION",
            "SYNTHETIC_SCENARIO_VALIDATION",
            "RULE_ENGINE_CORRECTNESS",
            "SCHEMA_CORRECTNESS",
            "GATE_BEHAVIOR",
            "CDEI_TRACEABILITY",
        ],
        "prohibited_claims": [
            "REAL_WORLD_CLINICAL_PERFORMANCE",
            "DIAGNOSTIC_ACCURACY",
            "SENSITIVITY",
            "SPECIFICITY",
            "PPV",
            "NPV",
            "CLINICAL_CALIBRATION",
            "INDIVIDUAL_DIAGNOSIS_VALIDITY",
        ],
    }
    manifest_path = destination / "synthetic_generation_manifest.json"
    temporary_manifest = manifest_path.with_suffix(
        manifest_path.suffix + f".tmp.{os.getpid()}"
    )
    temporary_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_manifest, manifest_path)
    return manifest
