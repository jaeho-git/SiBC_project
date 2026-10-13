from __future__ import annotations

from collections import defaultdict

from .models import DiagnosisCandidate, ValidationResult, ValidationStatus
from .rule_schema import RuleRegistry
from .validation import clone_result


ASSESSABLE = {
    ValidationStatus.VALIDATED,
    ValidationStatus.VALIDATED_WITH_LIMITATIONS,
    ValidationStatus.REVIEW_REQUIRED,
    ValidationStatus.CONTRADICTED,
    ValidationStatus.NOT_APPLICABLE,
}


def apply_candidate_set_checks(
    candidates: list[DiagnosisCandidate],
    results: list[ValidationResult],
    registry: RuleRegistry,
) -> list[ValidationResult]:
    candidate_by_id = {item.diagnosis_candidate_id: item for item in candidates}
    groups: dict[tuple[str, str], list[ValidationResult]] = defaultdict(list)
    for result in results:
        groups[(result.scenario_id, result.synthetic_case_id)].append(result)

    updated: list[ValidationResult] = []
    for group_results in groups.values():
        total = len(group_results)
        assessable = sum(result.status in ASSESSABLE for result in group_results)
        completeness = round(assessable / total, 4) if total else None
        conflict_ids: set[str] = set()
        taxonomies = {result.taxonomy for result in group_results}
        for result in group_results:
            candidate = candidate_by_id[result.diagnosis_candidate_id]
            rule = registry.get(result.rule_id) if result.rule_id else None
            declared = set(candidate.mutually_exclusive_diagnosis_ids)
            if declared & set(candidate_by_id):
                conflict_ids.add(result.diagnosis_candidate_id)
                conflict_ids.update(declared & set(candidate_by_id))
            if rule:
                other_rules = {
                    other.rule_id
                    for other in group_results
                    if other.diagnosis_candidate_id != result.diagnosis_candidate_id
                }
                if set(rule.mutually_exclusive_rules) & other_rules:
                    conflict_ids.add(result.diagnosis_candidate_id)

        if conflict_ids:
            set_status = "MUTUALLY_EXCLUSIVE_CANDIDATES"
            review_required = True
        elif total > 1 and assessable < total:
            set_status = "PARTIALLY_ASSESSABLE"
            review_required = True
        elif total > 1 and len(taxonomies) > 1:
            set_status = "CROSS_TAXONOMY_OVERLAP_DISCLOSED"
            review_required = False
        elif total > 1:
            set_status = "COEXISTENT"
            review_required = False
        else:
            set_status = "NONE"
            review_required = False

        for result in group_results:
            if (
                result.diagnosis_candidate_id in conflict_ids
                and result.status
                in {
                    ValidationStatus.VALIDATED,
                    ValidationStatus.VALIDATED_WITH_LIMITATIONS,
                }
            ):
                limitations = sorted(
                    set(result.limitations + ["MUTUALLY_EXCLUSIVE_CANDIDATE_CONFLICT"])
                )
                result = clone_result(
                    result,
                    status=ValidationStatus.REVIEW_REQUIRED,
                    hard_gate_passed=False,
                    limitations=limitations,
                    human_review_required=True,
                    human_review_reason="MUTUALLY_EXCLUSIVE_CANDIDATE_CONFLICT",
                    profile_write_allowed=False,
                    behavior_handoff_allowed=False,
                    behavior_handoff_mode="BLOCKED",
                    behavior_handoff_reason="CANDIDATE_SET_CONFLICT",
                    technical_gate_passed=False,
                )
            result = clone_result(
                result,
                candidate_set_conflict_status=set_status,
                candidate_set_completeness=completeness,
                candidate_set_review_required=review_required,
            )
            updated.append(result)
    return sorted(updated, key=lambda item: item.diagnosis_candidate_id)
