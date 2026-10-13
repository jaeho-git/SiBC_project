from __future__ import annotations

from .models import EvidenceLink


def evidence_quality_issues(evidence: list[EvidenceLink]) -> list[str]:
    issues: set[str] = set()
    for item in evidence:
        if item.quality_status == "BOUNDARY_REVIEW":
            issues.add("BOUNDARY_VALUE_REVIEW")
        elif item.quality_status != "ACCEPTABLE":
            issues.add("INADEQUATE_EVIDENCE_QUALITY")
        if item.upstream_validation_status != "VALIDATED" or not item.eligible:
            issues.add("UPSTREAM_EVIDENCE_EXCLUDED")
        if not item.source or not item.provenance or not item.unit:
            issues.add("MISSING_EVIDENCE_PROVENANCE")
    return sorted(issues)

