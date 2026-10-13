from __future__ import annotations

from typing import Any

from .models import CriterionAssessment, DiagnosisCandidate, EvidenceLink
from .rule_schema import DiagnosisRule


COMPONENTS = (
    "rule_traceability",
    "source_traceability",
    "evidence_linkage",
    "temporal_explainability",
    "criterion_transparency",
    "conflict_transparency",
    "limitation_disclosure",
    "decision_reproducibility",
    "narrative_faithfulness",
    "groundedness",
)


def evaluate_cdei(
    *,
    candidate: DiagnosisCandidate,
    rule: DiagnosisRule | None,
    criteria: list[CriterionAssessment],
    evidence: list[EvidenceLink],
    limitations: list[str],
    decision_fingerprint: str,
    complete_threshold: float,
    partial_threshold: float,
) -> tuple[float | None, str, dict[str, float], list[str]]:
    if rule is None:
        return None, "NOT_ASSESSABLE", {name: 0.0 for name in COMPONENTS}, list(
            COMPONENTS
        )

    trace: dict[str, Any] = candidate.clinical_reasoning_trace
    trace_criteria = {str(value) for value in trace.get("criterion_ids", [])}
    trace_evidence = {str(value) for value in trace.get("evidence_ids", [])}
    actual_criteria = {item.criterion_id for item in criteria}
    actual_evidence = {item.evidence_id for item in evidence}
    declared_evidence = set(candidate.source_evidence_ids)
    linked_evidence = {
        evidence_id for item in criteria for evidence_id in item.evidence_ids
    }
    narrative_faithful = (
        trace.get("rule_id") == rule.rule_id
        and trace_criteria == actual_criteria
        and trace_evidence == actual_evidence
    )
    criteria_by_id = {item.criterion_id: item for item in criteria}
    linkage_valid = all(
        item.criterion_id in criteria_by_id
        and item.feature_id == criteria_by_id[item.criterion_id].feature_id
        and item.evidence_id in criteria_by_id[item.criterion_id].evidence_ids
        for item in evidence
    ) and all(
        item.role.value != "REQUIRED"
        or bool(item.evidence_ids)
        and bool(set(item.evidence_ids) & actual_evidence)
        for item in criteria
    )
    components = {
        "rule_traceability": float(
            candidate.applied_rule_ids == (rule.rule_id,)
            and trace.get("rule_id") == rule.rule_id
        ),
        "source_traceability": float(bool(rule.provenance.get("source_ids"))),
        "evidence_linkage": float(
            linkage_valid
            and linked_evidence <= actual_evidence
            and actual_evidence <= declared_evidence
        ),
        "temporal_explainability": float(
            bool(candidate.observation_window)
            and all(item.measured_datetime.tzinfo is not None for item in evidence)
        ),
        "criterion_transparency": float(
            bool(criteria)
            and all(item.criterion_id and item.role and item.state for item in criteria)
        ),
        "conflict_transparency": float(
            candidate.coexisting_diagnosis_ids is not None
            and candidate.mutually_exclusive_diagnosis_ids is not None
        ),
        "limitation_disclosure": float(
            bool(limitations) or trace.get("limitations_disclosed", False)
        ),
        "decision_reproducibility": float(bool(decision_fingerprint)),
        "narrative_faithfulness": float(narrative_faithful),
        "groundedness": float(
            trace_criteria <= actual_criteria and trace_evidence <= actual_evidence
        ),
    }
    score = round(sum(components.values()) / len(components), 4)
    missing = [name for name, value in components.items() if value < 1.0]
    if not linkage_valid:
        status = "INSUFFICIENT_TRACEABILITY"
    elif not narrative_faithful:
        status = "UNFAITHFUL_EXPLANATION"
    elif score >= complete_threshold:
        status = "COMPLETE"
    elif score >= partial_threshold:
        status = "PARTIAL"
    else:
        status = "INSUFFICIENT_TRACEABILITY"
    return score, status, components, missing
