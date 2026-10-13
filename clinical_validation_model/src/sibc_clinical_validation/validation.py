from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import timedelta
from typing import Any

from .behavior_handoff import decide_handoff
from .cdei import evaluate_cdei
from .config import load_policy
from .models import (
    CriterionAssessment,
    CriterionRole,
    CriterionState,
    DiagnosisCandidate,
    EvidenceLink,
    ValidationResult,
    ValidationStatus,
)
from .rule_schema import DiagnosisRule, RuleRegistry
from .scoring import (
    clinical_validation_score,
    confidence_components,
    score_components,
)


def _fingerprint(
    candidate: DiagnosisCandidate,
    criteria: list[CriterionAssessment],
    evidence: list[EvidenceLink],
    rule: DiagnosisRule | None,
) -> str:
    payload = {
        "candidate": {
            "id": candidate.diagnosis_candidate_id,
            "taxonomy": candidate.taxonomy,
            "rule_ids": candidate.applied_rule_ids,
            "rule_version": candidate.applied_rule_version,
            "index_datetime": candidate.index_datetime.isoformat(),
            "observation_window": candidate.observation_window,
            "upstream_validation_status": candidate.upstream_validation_status,
            "reasoning_trace": candidate.clinical_reasoning_trace,
            "coexisting_diagnosis_ids": candidate.coexisting_diagnosis_ids,
            "mutually_exclusive_diagnosis_ids": candidate.mutually_exclusive_diagnosis_ids,
            "data_origin": candidate.data_origin,
            "is_synthetic": candidate.is_synthetic,
        },
        "criteria": [
            {
                "criterion_id": item.criterion_id,
                "feature_id": item.feature_id,
                "role": item.role.value,
                "state": item.state.value,
                "evidence_ids": item.evidence_ids,
            }
            for item in sorted(criteria, key=lambda item: item.criterion_id)
        ],
        "evidence": [
            {
                "evidence_id": item.evidence_id,
                "criterion_id": item.criterion_id,
                "feature_id": item.feature_id,
                "measured_datetime": item.measured_datetime.isoformat(),
                "quality_status": item.quality_status,
                "upstream_validation_status": item.upstream_validation_status,
                "eligible": item.eligible,
                "source": item.source,
                "unit": item.unit,
                "provenance": item.provenance,
                "data_origin": item.data_origin,
                "value_code": item.value_code,
            }
            for item in sorted(evidence, key=lambda item: item.evidence_id)
        ],
        "rule": None
        if rule is None
        else {
            "rule_id": rule.rule_id,
            "rule_version": rule.rule_version,
            "content_sha256": hashlib.sha256(
                json.dumps(rule.raw, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        },
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _role_lists(
    criteria: list[CriterionAssessment],
) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    met = sorted(
        item.criterion_id
        for item in criteria
        if item.state == CriterionState.MET
        and item.role not in {CriterionRole.EXCLUSION, CriterionRole.CONTRADICTION}
    )
    not_met = sorted(
        item.criterion_id
        for item in criteria
        if item.state == CriterionState.NOT_MET
    )
    not_assessable = sorted(
        item.criterion_id
        for item in criteria
        if item.state == CriterionState.NOT_ASSESSABLE
    )
    exclusions = sorted(
        item.criterion_id
        for item in criteria
        if item.role == CriterionRole.EXCLUSION
        and item.state == CriterionState.MET
    )
    contradictions = sorted(
        item.criterion_id
        for item in criteria
        if item.role == CriterionRole.CONTRADICTION
        and item.state == CriterionState.MET
    )
    return met, not_met, not_assessable, exclusions, contradictions


class ClinicalValidationEngine:
    def __init__(self, registry: RuleRegistry, execution_mode: str = "fixture"):
        self.registry = registry
        self.execution_mode = execution_mode
        self.validation_policy = load_policy("validation")
        self.scoring_policy = load_policy("scoring")
        self.cdei_policy = load_policy("cdei")

    def validate(
        self,
        candidate: DiagnosisCandidate,
        criteria: list[CriterionAssessment],
        evidence: list[EvidenceLink],
    ) -> ValidationResult:
        rule_id = candidate.applied_rule_ids[0] if len(candidate.applied_rule_ids) == 1 else None
        rule = self.registry.get(rule_id) if rule_id else None
        fingerprint = _fingerprint(candidate, criteria, evidence, rule)
        met, not_met, not_assessable, exclusions, contradictions = _role_lists(
            criteria
        )
        limitations: list[str] = []
        blockers: list[str] = []
        quality_issues: list[str] = []
        invalid_link = False
        temporal_issue = False
        future_evidence = False
        stale_evidence = False
        measurement_issue = False

        status: ValidationStatus
        hard_gate_passed = False

        if rule is None:
            status = ValidationStatus.ABSTAIN
            blockers.append("BLOCKED_BY_RULE_DEFINITION")
            limitations.append("EXACTLY_ONE_REGISTERED_RULE_REQUIRED")
            return self._build_result(
                candidate=candidate,
                rule=None,
                criteria=criteria,
                evidence=evidence,
                status=status,
                hard_gate_passed=False,
                limitations=limitations,
                blockers=blockers,
                quality_issues=quality_issues,
                invalid_link=True,
                temporal_issue=False,
                fingerprint=fingerprint,
                role_lists=(met, not_met, not_assessable, exclusions, contradictions),
            )

        if candidate.taxonomy != rule.taxonomy:
            blockers.append("BLOCKED_BY_RULE_INTEGRITY")
            limitations.append("TAXONOMY_RULE_MISMATCH")
        if candidate.applied_rule_version != rule.rule_version:
            blockers.append("BLOCKED_BY_RULE_INTEGRITY")
            limitations.append("RULE_VERSION_MISMATCH")
        integrity_issues = rule.integrity_issues()
        if integrity_issues:
            blockers.append("BLOCKED_BY_RULE_INTEGRITY")
            limitations.extend(integrity_issues)

        allowed_statuses = set(
            self.validation_policy["evaluation_rule_statuses"][self.execution_mode]
        )
        if rule.status not in allowed_statuses:
            if "LICENSE" in str(rule.provenance.get("license_status", "")):
                blockers.append("BLOCKED_BY_LICENSE")
            else:
                blockers.append("BLOCKED_BY_CLINICAL_REVIEW")
            limitations.append("RULE_NOT_APPROVED_FOR_EVALUATION_MODE")

        if candidate.upstream_validation_status != "VALIDATED":
            blockers.append("BLOCKED_BY_UPSTREAM_VALIDATION")
            limitations.append("UPSTREAM_EVIDENCE_NOT_ELIGIBLE")

        specs = {spec.criterion_id: spec for spec in rule.criterion_specs()}
        observed = {item.criterion_id: item for item in criteria}
        for item in criteria:
            spec = specs.get(item.criterion_id)
            if spec is None or spec.role != item.role:
                invalid_link = True
                quality_issues.append("INVALID_CRITERION_REFERENCE")
            elif item.role != CriterionRole.APPLICABILITY and spec.feature_id != item.feature_id:
                invalid_link = True
                quality_issues.append("FEATURE_CRITERION_MISMATCH")

        evidence_ids = {item.evidence_id for item in evidence}
        if evidence_ids != set(candidate.source_evidence_ids):
            invalid_link = True
            quality_issues.append("CANDIDATE_EVIDENCE_SET_MISMATCH")
        for item in evidence:
            criterion = observed.get(item.criterion_id)
            if (
                criterion is None
                or item.evidence_id not in criterion.evidence_ids
                or item.feature_id != criterion.feature_id
            ):
                invalid_link = True
                quality_issues.append("INVALID_EVIDENCE_LINK")
            if item.measured_datetime > candidate.index_datetime:
                temporal_issue = True
                future_evidence = True
                quality_issues.append("FUTURE_EVIDENCE_LEAKAGE")
            if (
                rule.freshness_limit_days is not None
                and item.measured_datetime
                < candidate.index_datetime
                - timedelta(days=rule.freshness_limit_days)
            ):
                temporal_issue = True
                stale_evidence = True
                quality_issues.append("STALE_EVIDENCE")
            if item.quality_status == "BOUNDARY_REVIEW":
                quality_issues.append("BOUNDARY_VALUE_REVIEW")
            elif item.quality_status != "ACCEPTABLE":
                quality_issues.append("INADEQUATE_EVIDENCE_QUALITY")
            if item.upstream_validation_status != "VALIDATED" or not item.eligible:
                quality_issues.append("UPSTREAM_EVIDENCE_EXCLUDED")
            measurement = rule.raw.get("measurement_requirements") or {}
            if item.source not in set(measurement.get("allowed_sources", [])):
                measurement_issue = True
                quality_issues.append("DISALLOWED_EVIDENCE_SOURCE")
            if item.unit not in set(measurement.get("allowed_units", [])):
                measurement_issue = True
                quality_issues.append("DISALLOWED_EVIDENCE_UNIT")

        state_code_map = {
            str(key): str(value)
            for key, value in (
                (rule.raw.get("measurement_requirements") or {}).get(
                    "state_code_map", {}
                )
            ).items()
        }
        evidence_by_criterion: dict[str, list[EvidenceLink]] = {}
        for item in evidence:
            evidence_by_criterion.setdefault(item.criterion_id, []).append(item)
        for criterion in criteria:
            if criterion.role == CriterionRole.APPLICABILITY:
                continue
            linked = evidence_by_criterion.get(criterion.criterion_id, [])
            derived_states = {
                state_code_map[item.value_code]
                for item in linked
                if item.value_code in state_code_map
            }
            if linked and (
                len(derived_states) != 1
                or next(iter(derived_states)) != criterion.state.value
            ):
                invalid_link = True
                quality_issues.append("CRITERION_STATE_EVIDENCE_MISMATCH")

        quality_issues = sorted(set(quality_issues))
        limitations = sorted(set(limitations))
        blockers = sorted(set(blockers))

        app_specs = {
            spec.criterion_id
            for spec in specs.values()
            if spec.role == CriterionRole.APPLICABILITY
        }
        required_specs = {
            spec.criterion_id
            for spec in specs.values()
            if spec.role == CriterionRole.REQUIRED
        }
        app_items = [observed[item] for item in app_specs if item in observed]
        required_items = [observed[item] for item in required_specs if item in observed]
        eligible_evidence_ids = {
            item.evidence_id
            for item in evidence
            if item.eligible and item.upstream_validation_status == "VALIDATED"
        }
        required_link_missing = any(
            not item.evidence_ids
            or not (set(item.evidence_ids) & eligible_evidence_ids)
            for item in required_items
        )

        if blockers:
            status = ValidationStatus.ABSTAIN
        elif any(item.state == CriterionState.NOT_MET for item in app_items):
            status = ValidationStatus.NOT_APPLICABLE
        elif app_specs - set(observed):
            status = ValidationStatus.INSUFFICIENT_EVIDENCE
            limitations.append("MISSING_APPLICABILITY_ASSESSMENT")
        elif invalid_link:
            status = ValidationStatus.ABSTAIN
            limitations.append("EVIDENCE_LINKAGE_INVALID")
            blockers.append("BLOCKED_BY_CLINICAL_LAYER_CONTRACT")
        elif future_evidence:
            status = ValidationStatus.ABSTAIN
            limitations.append("FUTURE_EVIDENCE_MUST_BE_EXCLUDED")
            blockers.append("BLOCKED_BY_DATA")
        elif measurement_issue:
            status = ValidationStatus.ABSTAIN
            limitations.append("MEASUREMENT_REQUIREMENT_FAILED")
            blockers.append("BLOCKED_BY_DATA")
        elif stale_evidence or temporal_issue:
            status = ValidationStatus.REVIEW_REQUIRED
            limitations.append("TEMPORAL_REQUIREMENT_FAILED")
        elif any(
            issue
            in {
                "BOUNDARY_VALUE_REVIEW",
                "INADEQUATE_EVIDENCE_QUALITY",
                "UPSTREAM_EVIDENCE_EXCLUDED",
            }
            for issue in quality_issues
        ):
            status = ValidationStatus.REVIEW_REQUIRED
            limitations.append("DATA_QUALITY_REVIEW_REQUIRED")
        elif required_specs - set(observed) or required_link_missing or any(
            item.state == CriterionState.NOT_ASSESSABLE for item in required_items
        ):
            status = ValidationStatus.INSUFFICIENT_EVIDENCE
            limitations.append("REQUIRED_EVIDENCE_MISSING_OR_NOT_ASSESSABLE")
            if required_link_missing:
                quality_issues.append("REQUIRED_EVIDENCE_LINK_MISSING")
        elif any(item.state == CriterionState.NOT_MET for item in required_items):
            status = ValidationStatus.CONTRADICTED
            limitations.append("REQUIRED_CRITERION_NOT_MET")
        elif exclusions:
            status = ValidationStatus.CONTRADICTED
            limitations.append("EXCLUSION_TRIGGERED")
        elif contradictions:
            status = ValidationStatus.CONTRADICTED
            limitations.append("CONTRADICTORY_EVIDENCE_TRIGGERED")
        else:
            supporting = [
                item for item in criteria if item.role == CriterionRole.SUPPORTING
            ]
            if supporting and any(
                item.state != CriterionState.MET for item in supporting
            ):
                status = ValidationStatus.VALIDATED_WITH_LIMITATIONS
                limitations.append("SUPPORTING_EVIDENCE_INCOMPLETE")
            else:
                status = ValidationStatus.VALIDATED
            hard_gate_passed = True

        return self._build_result(
            candidate=candidate,
            rule=rule,
            criteria=criteria,
            evidence=evidence,
            status=status,
            hard_gate_passed=hard_gate_passed,
            limitations=sorted(set(limitations)),
            blockers=blockers,
            quality_issues=quality_issues,
            invalid_link=invalid_link,
            temporal_issue=temporal_issue,
            fingerprint=fingerprint,
            role_lists=(met, not_met, not_assessable, exclusions, contradictions),
        )

    def _build_result(
        self,
        *,
        candidate: DiagnosisCandidate,
        rule: DiagnosisRule | None,
        criteria: list[CriterionAssessment],
        evidence: list[EvidenceLink],
        status: ValidationStatus,
        hard_gate_passed: bool,
        limitations: list[str],
        blockers: list[str],
        quality_issues: list[str],
        invalid_link: bool,
        temporal_issue: bool,
        fingerprint: str,
        role_lists: tuple[list[str], list[str], list[str], list[str], list[str]],
    ) -> ValidationResult:
        if rule is None:
            components: dict[str, float | None] = {
                key: None
                for key in self.scoring_policy["weights"]
            }
            score = None
            confidence_detail: dict[str, float] = {}
        else:
            components = score_components(
                rule,
                criteria,
                evidence,
                temporal_issue=temporal_issue,
                invalid_link=invalid_link,
            )
            score = clinical_validation_score(
                components, self.scoring_policy["weights"]
            )
            if status == ValidationStatus.ABSTAIN:
                score = None
            confidence_detail = confidence_components(
                rule=rule, components=components
            )

        cdei_score, cdei_status, cdei_components, _ = evaluate_cdei(
            candidate=candidate,
            rule=rule,
            criteria=criteria,
            evidence=evidence,
            limitations=limitations,
            decision_fingerprint=fingerprint,
            complete_threshold=float(self.cdei_policy["complete_threshold"]),
            partial_threshold=float(self.cdei_policy["partial_threshold"]),
        )
        if cdei_status == "UNFAITHFUL_EXPLANATION" and status != ValidationStatus.ABSTAIN:
            status = ValidationStatus.ABSTAIN
            hard_gate_passed = False
            limitations = sorted(set(limitations + ["EXPLANATION_TRACE_MISMATCH"]))
            quality_issues = sorted(
                set(quality_issues + ["EXPLANATION_FAITHFULNESS_ERROR"])
            )

        profile_allowed, behavior_allowed, handoff_mode, handoff_reason, technical = (
            decide_handoff(
                status,
                None if rule is None else rule.status,
                self.validation_policy.get(
                    "clinical_validation_status", "BLOCKED_BY_REFERENCE_STANDARD"
                ),
            )
        )
        if status == ValidationStatus.ABSTAIN:
            score = None
        human_review = status in {
            ValidationStatus.REVIEW_REQUIRED,
            ValidationStatus.ABSTAIN,
            ValidationStatus.VALIDATED_WITH_LIMITATIONS,
        }
        review_reason = None
        if human_review:
            review_reason = (
                blockers[0]
                if blockers
                else limitations[0]
                if limitations
                else status.value
            )
        met, not_met, not_assessable, exclusions, contradictions = role_lists
        return ValidationResult(
            scenario_id=candidate.scenario_id,
            synthetic_case_id=candidate.synthetic_case_id,
            diagnosis_candidate_id=candidate.diagnosis_candidate_id,
            taxonomy=candidate.taxonomy,
            rule_id=None if rule is None else rule.rule_id,
            rule_version=None if rule is None else rule.rule_version,
            rule_status=None if rule is None else rule.status,
            status=status,
            clinical_validation_score=score,
            score_components=components,
            hard_gate_passed=hard_gate_passed,
            model_decision_confidence=0.0,
            confidence_type="rule_decision_stability_index",
            calibration_status="NOT_CALIBRATED",
            confidence_components=confidence_detail,
            cdei_score=cdei_score,
            cdei_status=cdei_status,
            cdei_components=cdei_components,
            criteria_met=met,
            criteria_not_met=not_met,
            criteria_not_assessable=not_assessable,
            exclusions_triggered=exclusions,
            contradictions=contradictions,
            data_quality_status=(
                "ACCEPTABLE" if not quality_issues else "REVIEW_REQUIRED"
            ),
            data_quality_issues=quality_issues,
            limitations=limitations,
            blockers=blockers,
            human_review_required=human_review,
            human_review_reason=review_reason,
            profile_write_allowed=profile_allowed,
            behavior_handoff_allowed=behavior_allowed,
            behavior_handoff_mode=handoff_mode,
            behavior_handoff_reason=handoff_reason,
            technical_gate_passed=technical,
            decision_fingerprint=fingerprint,
        )


def clone_result(result: ValidationResult, **updates: Any) -> ValidationResult:
    return replace(result, **updates)
