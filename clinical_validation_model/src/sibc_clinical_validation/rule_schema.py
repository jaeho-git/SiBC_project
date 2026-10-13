from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from .config import RULE_ROOT
from .models import CriterionRole


RULE_STATUSES = {
    "RESEARCH_ONLY",
    "LICENSE_REVIEW_REQUIRED",
    "CLINICAL_REVIEW_REQUIRED",
    "APPROVED_FOR_TEST",
    "APPROVED_FOR_OPERATION",
    "REJECTED",
}


@dataclass(frozen=True)
class CriterionSpec:
    criterion_id: str
    feature_id: str
    role: CriterionRole


@dataclass(frozen=True)
class DiagnosisRule:
    rule_id: str
    taxonomy: str
    diagnosis_code_reference: str | None
    diagnosis_name_reference: str | None
    diagnosis_type: str
    rule_version: str
    status: str
    raw: dict[str, Any]

    @property
    def provenance(self) -> dict[str, Any]:
        return dict(self.raw.get("provenance") or {})

    @property
    def integrity(self) -> dict[str, Any]:
        return dict(self.raw.get("integrity") or {})

    @property
    def freshness_limit_days(self) -> int | None:
        value = (self.raw.get("temporal_requirements") or {}).get(
            "freshness_limit_days"
        )
        return None if value is None else int(value)

    @property
    def mutually_exclusive_rules(self) -> tuple[str, ...]:
        values = (self.raw.get("conflicts") or {}).get(
            "mutually_exclusive_rules", []
        )
        return tuple(str(value) for value in values)

    def criterion_specs(self) -> tuple[CriterionSpec, ...]:
        result: list[CriterionSpec] = []
        applicability = self.raw.get("applicability") or {}
        for criterion_id in applicability.get("criteria", []):
            result.append(
                CriterionSpec(
                    criterion_id=str(criterion_id),
                    feature_id="context_applicability",
                    role=CriterionRole.APPLICABILITY,
                )
            )
        mappings = (
            ("required_evidence", CriterionRole.REQUIRED),
            ("supporting_evidence", CriterionRole.SUPPORTING),
            ("contradictory_evidence", CriterionRole.CONTRADICTION),
            ("exclusion_criteria", CriterionRole.EXCLUSION),
            ("related_factors", CriterionRole.RELATED_FACTOR),
            ("risk_factors", CriterionRole.RISK_FACTOR),
        )
        for key, role in mappings:
            for item in self.raw.get(key, []) or []:
                if not isinstance(item, dict):
                    continue
                result.append(
                    CriterionSpec(
                        criterion_id=str(item.get("criterion_id", "")),
                        feature_id=str(item.get("feature_id", "")),
                        role=role,
                    )
                )
        return tuple(result)

    def schema_issues(self) -> list[str]:
        issues: list[str] = []
        if self.taxonomy not in {"NANDA", "OMAHA", "INTERNAL"}:
            issues.append("INVALID_TAXONOMY")
        if self.status not in RULE_STATUSES:
            issues.append("INVALID_RULE_STATUS")
        if not self.rule_id or not self.rule_version:
            issues.append("MISSING_RULE_ID_OR_VERSION")
        provenance = self.provenance
        for key in (
            "source_ids",
            "source_version",
            "license_status",
            "clinical_review_status",
        ):
            if provenance.get(key) in (None, "", []):
                issues.append(f"MISSING_PROVENANCE_{key.upper()}")
        temporal = self.raw.get("temporal_requirements") or {}
        if "index_time_field" not in temporal or "freshness_limit_days" not in temporal:
            issues.append("MISSING_TEMPORAL_REQUIREMENT")
        measurement = self.raw.get("measurement_requirements") or {}
        if not measurement.get("allowed_sources") or not measurement.get("allowed_units"):
            issues.append("MISSING_MEASUREMENT_REQUIREMENT")

        specs = self.criterion_specs()
        identifiers = [spec.criterion_id for spec in specs]
        if any(not item for item in identifiers):
            issues.append("EMPTY_CRITERION_ID")
        if len(identifiers) != len(set(identifiers)):
            issues.append("DUPLICATE_CRITERION_ID")
        required = {
            spec.criterion_id
            for spec in specs
            if spec.role == CriterionRole.REQUIRED
        }
        exclusions = {
            spec.criterion_id
            for spec in specs
            if spec.role == CriterionRole.EXCLUSION
        }
        if required & exclusions:
            issues.append("REQUIRED_EXCLUSION_OVERLAP")
        return sorted(set(issues))

    def integrity_issues(self) -> list[str]:
        issues = self.schema_issues()
        integrity = self.integrity
        required_keys = (
            "source_rule_element_count",
            "implemented_rule_element_count",
            "omitted_elements",
            "modified_elements",
            "version_alignment_status",
        )
        for key in required_keys:
            if key not in integrity:
                issues.append(f"MISSING_INTEGRITY_{key.upper()}")
        source_count = integrity.get("source_rule_element_count")
        implemented_count = integrity.get("implemented_rule_element_count")
        if source_count is not None and implemented_count is not None:
            if int(source_count) != int(implemented_count):
                issues.append("RULE_ELEMENT_COUNT_MISMATCH")
            if int(implemented_count) != len(self.criterion_specs()):
                issues.append("IMPLEMENTED_ELEMENT_COUNT_INCORRECT")
        if integrity.get("omitted_elements"):
            issues.append("OMITTED_RULE_ELEMENTS")
        if integrity.get("modified_elements"):
            issues.append("MODIFIED_RULE_ELEMENTS")
        if not str(integrity.get("version_alignment_status", "")).startswith(
            "ALIGNED"
        ):
            issues.append("RULE_VERSION_NOT_ALIGNED")
        return sorted(set(issues))


class RuleRegistry:
    def __init__(self, rules: Iterable[DiagnosisRule]):
        self._rules: dict[str, DiagnosisRule] = {}
        for rule in rules:
            if rule.rule_id in self._rules:
                raise ValueError(f"Duplicate rule_id: {rule.rule_id}")
            self._rules[rule.rule_id] = rule

    @classmethod
    def from_paths(cls, paths: Iterable[Path]) -> "RuleRegistry":
        rules: list[DiagnosisRule] = []
        managed_root = RULE_ROOT.resolve()
        for path in sorted(paths):
            resolved = path.resolve()
            if managed_root not in resolved.parents:
                raise ValueError(f"Rule file outside managed root: {resolved}")
            raw = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
            entries = raw.get("rules", []) if isinstance(raw, dict) else []
            if not isinstance(entries, list):
                raise ValueError(f"rules must be a list: {resolved}")
            for entry in entries:
                if not isinstance(entry, dict):
                    raise ValueError(f"Rule entry must be a mapping: {resolved}")
                rules.append(
                    DiagnosisRule(
                        rule_id=str(entry.get("rule_id", "")),
                        taxonomy=str(entry.get("taxonomy", "")),
                        diagnosis_code_reference=entry.get(
                            "diagnosis_code_reference"
                        ),
                        diagnosis_name_reference=entry.get(
                            "diagnosis_name_reference"
                        ),
                        diagnosis_type=str(entry.get("diagnosis_type", "")),
                        rule_version=str(entry.get("rule_version", "")),
                        status=str(entry.get("status", "")),
                        raw=dict(entry),
                    )
                )
        return cls(rules)

    @classmethod
    def fixture(cls) -> "RuleRegistry":
        return cls.from_paths([RULE_ROOT / "fixtures" / "test_rules.yaml"])

    def get(self, rule_id: str) -> DiagnosisRule | None:
        return self._rules.get(rule_id)

    def values(self) -> tuple[DiagnosisRule, ...]:
        return tuple(self._rules[key] for key in sorted(self._rules))

    def audit(self) -> list[dict[str, Any]]:
        return [
            {
                "rule_id": rule.rule_id,
                "taxonomy": rule.taxonomy,
                "rule_version": rule.rule_version,
                "status": rule.status,
                "license_status": rule.provenance.get("license_status"),
                "clinical_review_status": rule.provenance.get(
                    "clinical_review_status"
                ),
                "source_rule_element_count": rule.integrity.get(
                    "source_rule_element_count"
                ),
                "implemented_rule_element_count": rule.integrity.get(
                    "implemented_rule_element_count"
                ),
                "omitted_elements": rule.integrity.get("omitted_elements", []),
                "modified_elements": rule.integrity.get("modified_elements", []),
                "version_alignment_status": rule.integrity.get(
                    "version_alignment_status"
                ),
                "integrity_issues": rule.integrity_issues(),
            }
            for rule in self.values()
        ]

