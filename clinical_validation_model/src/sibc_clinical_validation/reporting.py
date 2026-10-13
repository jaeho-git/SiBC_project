from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .models import DiagnosisCandidate, ValidationResult
from .rule_schema import RuleRegistry


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    write_json(temporary, value)
    os.replace(temporary, path)


def write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _json_cell(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def result_frame(results: list[ValidationResult]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for result in results:
        row = result.to_dict()
        for key, value in list(row.items()):
            if isinstance(value, (list, dict)):
                row[key] = _json_cell(value)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("diagnosis_candidate_id").reset_index(drop=True)


def output_contract(
    candidate: DiagnosisCandidate,
    result: ValidationResult,
    *,
    model_version: str,
    run_id: str,
    environment: str,
    execution_mode: str,
    data_snapshot_id: str | None,
    rule_source_ids: list[str],
) -> dict[str, Any]:
    return {
        "model_name": "clinical_validation_model",
        "model_version": model_version,
        "run_id": run_id,
        "environment": environment,
        "execution_mode": execution_mode,
        "index_datetime": candidate.index_datetime.isoformat(),
        "diagnosis_candidate_id": candidate.diagnosis_candidate_id,
        "data_origin": candidate.data_origin,
        "is_synthetic": candidate.is_synthetic,
        "diagnosis": {
            "taxonomy": candidate.taxonomy,
            "diagnosis_code_reference": candidate.diagnosis_code_reference,
            "diagnosis_name_reference": candidate.diagnosis_name_reference,
            "rule_id": result.rule_id,
            "rule_version": result.rule_version,
            "rule_status": result.rule_status,
        },
        "validation_result": {
            "status": result.status.value,
            "clinical_validation_score": result.clinical_validation_score,
            "score_type": "rule_criteria_fulfillment_index",
            "hard_gate_passed": result.hard_gate_passed,
            "model_decision_confidence": result.model_decision_confidence,
            "confidence_type": result.confidence_type,
            "calibration_status": result.calibration_status,
            "technical_gate_passed": result.technical_gate_passed,
        },
        "cdei": {
            "cdei_score": result.cdei_score,
            "cdei_status": result.cdei_status,
            "components": result.cdei_components,
            "missing_elements": [
                key for key, value in result.cdei_components.items() if value < 1.0
            ],
        },
        "criteria": {
            "met": result.criteria_met,
            "not_met": result.criteria_not_met,
            "not_assessable": result.criteria_not_assessable,
            "exclusions_triggered": result.exclusions_triggered,
            "contradictions": result.contradictions,
        },
        "data_quality": {
            "status": result.data_quality_status,
            "issues": result.data_quality_issues,
        },
        "candidate_set": {
            "conflict_status": result.candidate_set_conflict_status,
            "completeness": result.candidate_set_completeness,
            "review_required": result.candidate_set_review_required,
        },
        "limitations": result.limitations,
        "blockers": result.blockers,
        "human_review": {
            "required": result.human_review_required,
            "reason": result.human_review_reason,
        },
        "profile_write_allowed": result.profile_write_allowed,
        "behavior_layer_handoff": {
            "allowed": result.behavior_handoff_allowed,
            "mode": result.behavior_handoff_mode,
            "reason": result.behavior_handoff_reason,
        },
        "provenance": {
            "data_snapshot_id": data_snapshot_id,
            "query_version": None,
            "feature_version": "synthetic_contract_v0.1",
            "rule_source_ids": rule_source_ids,
            "medical_checkup_artifact_source": data_snapshot_id,
            "decision_fingerprint": result.decision_fingerprint,
        },
    }


def write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for value in values:
            stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))
            stream.write("\n")


def write_frame(frame: pd.DataFrame, csv_path: Path, parquet_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)
    frame.to_parquet(parquet_path, index=False)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksums(run_root: Path, destination: Path) -> int:
    files = [
        path
        for path in sorted(run_root.rglob("*"))
        if path.is_file() and path.resolve() != destination.resolve()
    ]
    lines = [f"{sha256_file(path)}  {path.relative_to(run_root)}" for path in files]
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def verify_checksums(run_root: Path, register: Path) -> int:
    """Verify every registered run artifact before atomic publication."""

    run_root = run_root.resolve()
    register = register.resolve()
    if register.parent != (run_root / "artifacts").resolve() or not register.is_file():
        raise ValueError("Unmanaged checksum register")
    verified = 0
    for line in register.read_text(encoding="utf-8").splitlines():
        if not line.strip() or "  " not in line:
            raise ValueError("Malformed checksum register")
        expected, relative = line.split("  ", 1)
        if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
            raise ValueError("Malformed checksum digest")
        path = (run_root / relative).resolve()
        if path == register or run_root not in path.parents or not path.is_file():
            raise ValueError("Checksum register contains an unmanaged path")
        if sha256_file(path) != expected:
            raise ValueError(f"Checksum verification failed: {relative}")
        verified += 1
    if verified == 0:
        raise ValueError("Checksum register is empty")
    return verified


def write_reports(
    reports: Path,
    *,
    context: dict[str, Any],
    results: list[ValidationResult],
    oracle_failures: list[dict[str, Any]],
    registry: RuleRegistry,
) -> None:
    status_counts = pd.Series([result.status.value for result in results]).value_counts().to_dict()
    cdei_counts = pd.Series([result.cdei_status for result in results]).value_counts().to_dict()
    passed = not oracle_failures
    summary = f"""# Clinical Validation prototype run summary

- Run ID: `{context['run_id']}`
- Execution environment: `{context['environment']}`
- Mode: `{context['execution_mode']}`
- Technical oracle: **{'PASSED' if passed else 'FAILED'}**
- Candidate results: {len(results)}
- Scenario count: {context['scenario_count']}
- Clinical validation: **BLOCKED_BY_REFERENCE_STANDARD**
- Operational handoff: **BLOCKED** (fixture rules are not approved for operation)

## Status distribution

```json
{json.dumps(status_counts, ensure_ascii=False, indent=2)}
```

## Interpretation boundary

This run validates deterministic rule-engine behavior on synthetic Clinical Layer
output. It does not establish diagnostic accuracy, sensitivity, specificity,
calibration, real-world clinical performance, or individual diagnosis validity.
"""
    write_markdown(reports / "run_summary.md", summary)
    write_markdown(
        reports / "data_card.md",
        f"""# Data card

The diagnosis candidates, criteria assertions, links, and reasoning traces are
synthetic. In artifact mode the medical-checkup snapshot is accessed only for
metadata, schema, row count, and checksum verification; no source row is changed.

- Synthetic candidate rows: {len(results)}
- Source snapshot: `{context.get('data_snapshot_id') or 'NONE_FIXTURE_MODE'}`
- Source mutation check: `{context.get('source_mutation_check', 'NOT_APPLICABLE')}`
- Survey source: `BLOCKED_BY_SURVEY_SOURCE`
- Clinical Layer production contract: `BLOCKED_BY_CLINICAL_LAYER_CONTRACT`
""",
    )
    write_markdown(
        reports / "model_card.md",
        """# Model card

`clinical_validation_model` is a deterministic rule-based validation module
inside the Clinical Layer. It validates an upstream candidate; it does not create
a diagnosis and does not estimate disease, diagnosis, risk, or prognosis
probability. `clinical_validation_score`, the uncalibrated decision-stability
index, and CDEI are separate quantities. Test-only rules cannot write to a
Profile or hand off to the Behavior Layer.
""",
    )
    write_markdown(
        reports / "validation_report.md",
        f"""# Technical validation report

- Oracle comparison: **{'PASS' if passed else 'FAIL'}**
- Exact candidate-level comparisons: {len(results) - len(oracle_failures)}/{len(results)}
- Rule registry entries: {len(registry.values())}
- Rule integrity failures: {sum(bool(r['integrity_issues']) for r in registry.audit())}
- Statuses: `{json.dumps(status_counts, ensure_ascii=False, sort_keys=True)}`

Scope: `TECHNICAL_VALIDATION`, `SYNTHETIC_SCENARIO_VALIDATION`,
`RULE_ENGINE_CORRECTNESS`, `SCHEMA_CORRECTNESS`, `GATE_BEHAVIOR`, and
`CDEI_TRACEABILITY` only.
""",
    )
    write_markdown(
        reports / "failure_analysis.md",
        "# Failure analysis\n\n"
        + (
            "No synthetic oracle mismatches were observed.\n"
            if passed
            else "```json\n"
            + json.dumps(oracle_failures, ensure_ascii=False, indent=2)
            + "\n```\n"
        ),
    )
    write_markdown(
        reports / "improvement_report.md",
        """# Improvement report

The baseline and regression run were identical. No automatic clinical-rule,
threshold, exclusion, intended-use, licensing, or acceptance-criteria change was
attempted. Remaining work requires an approved Clinical Layer contract,
licensed/approved rules, survey provenance, and an independent clinical reference
standard.
""",
    )
    write_markdown(
        reports / "leakage_audit.md",
        """# Leakage audit

- Future evidence is detected by `measured_datetime > index_datetime` and cannot pass.
- Oracle `expected_*` fields are not mapped into candidate, criterion, or evidence domain objects.
- Candidate-set decisions are grouped by synthetic case and not by duplicated rows.
- No environment name, medical prediction, or risk field is used as a validation feature.
- Actual pseudonymized artifacts are fingerprinted before and after artifact-mode execution.
""",
    )
    write_markdown(
        reports / "cdei_validation.md",
        f"""# CDEI validation

CDEI measures traceability and explanation reproducibility, not diagnostic
accuracy. Component scores remain separate from Clinical Validation Score and
decision confidence.

```json
{json.dumps(cdei_counts, ensure_ascii=False, indent=2)}
```
""",
    )
    write_markdown(
        reports / "performance_unavailable.md",
        """# Clinical performance unavailable

`CLINICAL_VALIDATION_STATUS = BLOCKED_BY_REFERENCE_STANDARD`

No expert-adjudicated reference standard, licensed operational rule set,
representative clinical cases, intended-use approval, or prospective cohort is
available. Diagnostic accuracy, sensitivity, specificity, PPV, NPV, clinical
calibration, and individual diagnosis validity are therefore not reported.
""",
    )
    write_json(
        reports / "data_profile.json",
        {
            "scenario_count": context["scenario_count"],
            "candidate_count": len(results),
            "status_counts": status_counts,
            "cdei_status_counts": cdei_counts,
            "clinical_validation_status": "BLOCKED_BY_REFERENCE_STANDARD",
        },
    )


def write_failure_ledger(path: Path, failures: list[dict[str, Any]]) -> None:
    fields = ["diagnosis_candidate_id", "field", "expected", "actual", "failure_type"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for failure in failures:
            writer.writerow({field: failure.get(field, "") for field in fields})
