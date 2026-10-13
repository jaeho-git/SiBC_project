from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ValidationStatus(str, Enum):
    VALIDATED = "VALIDATED"
    VALIDATED_WITH_LIMITATIONS = "VALIDATED_WITH_LIMITATIONS"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONTRADICTED = "CONTRADICTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    ABSTAIN = "ABSTAIN"


class CriterionState(str, Enum):
    MET = "MET"
    NOT_MET = "NOT_MET"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"


class CriterionRole(str, Enum):
    APPLICABILITY = "APPLICABILITY"
    REQUIRED = "REQUIRED"
    SUPPORTING = "SUPPORTING"
    EXCLUSION = "EXCLUSION"
    CONTRADICTION = "CONTRADICTION"
    RELATED_FACTOR = "RELATED_FACTOR"
    RISK_FACTOR = "RISK_FACTOR"


def parse_json_list(value: Any) -> list[Any]:
    if value is None:
        return []
    try:
        if value != value:  # NaN
            return []
    except TypeError:
        pass
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        loaded = json.loads(value)
        if not isinstance(loaded, list):
            raise ValueError("Expected a JSON list")
        return loaded
    raise ValueError(f"Expected list-compatible value, got {type(value).__name__}")


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    raise ValueError(f"Expected strict boolean, got {value!r}")


def parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        result = value.to_pydatetime()
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


@dataclass(frozen=True)
class CriterionAssessment:
    scenario_id: str
    diagnosis_candidate_id: str
    criterion_id: str
    feature_id: str
    role: CriterionRole
    state: CriterionState
    evidence_ids: tuple[str, ...] = ()
    rationale_code: str = "SYNTHETIC_TEST_ASSERTION"

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "CriterionAssessment":
        return cls(
            scenario_id=str(value["scenario_id"]),
            diagnosis_candidate_id=str(value["diagnosis_candidate_id"]),
            criterion_id=str(value["criterion_id"]),
            feature_id=str(value["feature_id"]),
            role=CriterionRole(str(value["criterion_role"])),
            state=CriterionState(str(value["criterion_state"])),
            evidence_ids=tuple(str(x) for x in parse_json_list(value.get("evidence_ids"))),
            rationale_code=str(value.get("rationale_code", "SYNTHETIC_TEST_ASSERTION")),
        )


@dataclass(frozen=True)
class EvidenceLink:
    scenario_id: str
    diagnosis_candidate_id: str
    evidence_id: str
    criterion_id: str
    feature_id: str
    measured_datetime: datetime
    source: str
    unit: str
    quality_status: str
    upstream_validation_status: str
    eligible: bool
    provenance: str
    data_origin: str
    value_code: str

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "EvidenceLink":
        return cls(
            scenario_id=str(value["scenario_id"]),
            diagnosis_candidate_id=str(value["diagnosis_candidate_id"]),
            evidence_id=str(value["evidence_id"]),
            criterion_id=str(value["criterion_id"]),
            feature_id=str(value["feature_id"]),
            measured_datetime=parse_datetime(value["measured_datetime"]),
            source=str(value["source"]),
            unit=str(value["unit"]),
            quality_status=str(value["quality_status"]),
            upstream_validation_status=str(value["upstream_validation_status"]),
            eligible=parse_bool(value["eligible"]),
            provenance=str(value.get("provenance", "SYNTHETIC_FIXTURE")),
            data_origin=str(value.get("data_origin", "SYNTHETIC_CLINICAL_LAYER_OUTPUT")),
            value_code=str(value.get("evidence_value_code", "")),
        )


@dataclass(frozen=True)
class DiagnosisCandidate:
    scenario_id: str
    synthetic_case_id: str
    diagnosis_candidate_id: str
    taxonomy: str
    diagnosis_code_reference: str | None
    diagnosis_name_reference: str
    diagnosis_type: str
    candidate_status: str
    applied_rule_ids: tuple[str, ...]
    applied_rule_version: str
    source_evidence_ids: tuple[str, ...]
    index_datetime: datetime
    observation_window: str
    clinical_reasoning_trace: dict[str, Any]
    candidate_priority: int
    coexisting_diagnosis_ids: tuple[str, ...]
    mutually_exclusive_diagnosis_ids: tuple[str, ...]
    upstream_validation_status: str
    data_origin: str
    is_synthetic: bool
    generator_version: str

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "DiagnosisCandidate":
        trace = value.get("clinical_reasoning_trace", {})
        if isinstance(trace, str):
            trace = json.loads(trace)
        return cls(
            scenario_id=str(value["scenario_id"]),
            synthetic_case_id=str(value["synthetic_case_id"]),
            diagnosis_candidate_id=str(value["diagnosis_candidate_id"]),
            taxonomy=str(value["taxonomy"]),
            diagnosis_code_reference=(
                None
                if value.get("diagnosis_code_reference") in (None, "", "null")
                else str(value["diagnosis_code_reference"])
            ),
            diagnosis_name_reference=str(value["diagnosis_name_reference"]),
            diagnosis_type=str(value["diagnosis_type"]),
            candidate_status=str(value["candidate_status"]),
            applied_rule_ids=tuple(str(x) for x in parse_json_list(value["applied_rule_ids"])),
            applied_rule_version=str(value["applied_rule_version"]),
            source_evidence_ids=tuple(
                str(x) for x in parse_json_list(value.get("source_evidence_ids"))
            ),
            index_datetime=parse_datetime(value["index_datetime"]),
            observation_window=str(value["observation_window"]),
            clinical_reasoning_trace=dict(trace),
            candidate_priority=int(value["candidate_priority"]),
            coexisting_diagnosis_ids=tuple(
                str(x) for x in parse_json_list(value.get("coexisting_diagnosis_ids"))
            ),
            mutually_exclusive_diagnosis_ids=tuple(
                str(x)
                for x in parse_json_list(value.get("mutually_exclusive_diagnosis_ids"))
            ),
            upstream_validation_status=str(
                value.get("upstream_validation_status", "VALIDATED")
            ),
            data_origin=str(value["data_origin"]),
            is_synthetic=parse_bool(value["is_synthetic"]),
            generator_version=str(value["generator_version"]),
        )


@dataclass
class ValidationResult:
    scenario_id: str
    synthetic_case_id: str
    diagnosis_candidate_id: str
    taxonomy: str
    rule_id: str | None
    rule_version: str | None
    rule_status: str | None
    status: ValidationStatus
    clinical_validation_score: float | None
    score_components: dict[str, float | None]
    hard_gate_passed: bool
    model_decision_confidence: float
    confidence_type: str
    calibration_status: str
    confidence_components: dict[str, float]
    cdei_score: float | None
    cdei_status: str
    cdei_components: dict[str, float]
    criteria_met: list[str]
    criteria_not_met: list[str]
    criteria_not_assessable: list[str]
    exclusions_triggered: list[str]
    contradictions: list[str]
    data_quality_status: str
    data_quality_issues: list[str]
    limitations: list[str]
    blockers: list[str]
    human_review_required: bool
    human_review_reason: str | None
    profile_write_allowed: bool
    behavior_handoff_allowed: bool
    behavior_handoff_mode: str
    behavior_handoff_reason: str
    technical_gate_passed: bool
    candidate_set_conflict_status: str = "NONE"
    candidate_set_completeness: float | None = None
    candidate_set_review_required: bool = False
    decision_fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        return result


@dataclass(frozen=True)
class SurveyEvidenceProvider:
    """Explicit placeholder until a real survey source contract is approved."""

    source_status: str = "BLOCKED_BY_SURVEY_SOURCE"

    def load_responses(self, subject_key: str, index_datetime: datetime) -> list[Any]:
        del subject_key, index_datetime
        return []
