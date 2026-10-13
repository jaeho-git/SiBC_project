from __future__ import annotations

from typing import Iterable

from .models import CriterionAssessment, CriterionRole, CriterionState, EvidenceLink
from .rule_schema import DiagnosisRule


def _ratio(values: Iterable[bool]) -> float | None:
    items = list(values)
    if not items:
        return None
    return sum(1.0 for item in items if item) / len(items)


def score_components(
    rule: DiagnosisRule,
    criteria: list[CriterionAssessment],
    evidence: list[EvidenceLink],
    *,
    temporal_issue: bool,
    invalid_link: bool,
) -> dict[str, float | None]:
    by_role: dict[CriterionRole, list[CriterionAssessment]] = {}
    for item in criteria:
        by_role.setdefault(item.role, []).append(item)

    applicability = _ratio(
        item.state == CriterionState.MET
        for item in by_role.get(CriterionRole.APPLICABILITY, [])
    )
    required = _ratio(
        item.state == CriterionState.MET
        for item in by_role.get(CriterionRole.REQUIRED, [])
    )
    supporting = _ratio(
        item.state == CriterionState.MET
        for item in by_role.get(CriterionRole.SUPPORTING, [])
    )
    required_items = by_role.get(CriterionRole.REQUIRED, [])
    linked_ids = {item.evidence_id for item in evidence if item.eligible}
    sufficiency = _ratio(
        bool(set(item.evidence_ids) & linked_ids) for item in required_items
    )
    contradiction_items = by_role.get(CriterionRole.CONTRADICTION, [])
    exclusion_items = by_role.get(CriterionRole.EXCLUSION, [])
    consistency = 1.0
    if any(
        item.state == CriterionState.MET
        for item in contradiction_items + exclusion_items
    ):
        consistency = 0.0
    quality = _ratio(
        item.quality_status == "ACCEPTABLE"
        and item.upstream_validation_status == "VALIDATED"
        and item.eligible
        for item in evidence
    )
    if quality is None:
        quality = 0.0 if required_items else 1.0
    rule_spec_count = len(rule.criterion_specs())
    assessed_ids = {item.criterion_id for item in criteria}
    rule_coverage = (
        len(assessed_ids & {spec.criterion_id for spec in rule.criterion_specs()})
        / rule_spec_count
        if rule_spec_count
        else 0.0
    )
    return {
        "applicability_score": 1.0 if applicability is None else applicability,
        "required_criteria_score": 0.0 if required is None else required,
        "supporting_criteria_score": 1.0 if supporting is None else supporting,
        "evidence_sufficiency_score": 0.0 if sufficiency is None else sufficiency,
        "evidence_consistency_score": consistency,
        "temporal_alignment_score": 0.0 if temporal_issue else 1.0,
        "data_quality_score": quality,
        "diagnostic_specificity_score": 0.0,
        "rule_coverage_score": rule_coverage,
        "invalid_link_penalty": 0.0 if invalid_link else 1.0,
    }


def clinical_validation_score(
    components: dict[str, float | None], weights: dict[str, float]
) -> float:
    total_weight = 0.0
    total = 0.0
    for name, weight in weights.items():
        value = components.get(name)
        if value is None:
            continue
        total += float(value) * float(weight)
        total_weight += float(weight)
    return round(total / total_weight, 4) if total_weight else 0.0


def confidence_components(
    *,
    rule: DiagnosisRule,
    components: dict[str, float | None],
    conflict_uncertainty: float = 0.0,
) -> dict[str, float]:
    def value(name: str) -> float:
        item = components.get(name)
        return 0.0 if item is None else float(item)

    return {
        "rule_determinacy": 1.0 if not rule.integrity_issues() else 0.0,
        "data_coverage": value("evidence_sufficiency_score"),
        "data_quality": value("data_quality_score"),
        "temporal_alignment": value("temporal_alignment_score"),
        "conflict_uncertainty": max(0.0, 1.0 - conflict_uncertainty),
        "boundary_uncertainty": 1.0,
        "source_certainty": (
            1.0 if rule.provenance.get("source_ids") else 0.0
        ),
        "rule_version_certainty": (
            1.0
            if str(rule.integrity.get("version_alignment_status", "")).startswith(
                "ALIGNED"
            )
            else 0.0
        ),
    }

