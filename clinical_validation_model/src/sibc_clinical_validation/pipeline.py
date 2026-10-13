from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import resource
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .config import (
    ACTIVE_ENVIRONMENT,
    FIXTURE_ROOT,
    RESULT_ROOT,
    PrototypeConfig,
    load_config,
)
from .conflict_detection import apply_candidate_set_checks
from .evidence import load_fixture_frames, materialize_fixture_contract
from .env import ReleaseAccessError, safe_environment_preflight
from .medical_adapter import (
    SourceDataMutationError,
    assert_source_unchanged,
    safe_snapshot_manifest,
    snapshot_medical_artifacts,
)
from .reporting import (
    atomic_write_json,
    output_contract,
    result_frame,
    write_checksums,
    write_failure_ledger,
    write_frame,
    write_json,
    write_jsonl,
    write_markdown,
    write_reports,
    verify_checksums,
)
from .rule_schema import RuleRegistry
from .security import assert_security_scan_passed, scan_output_tree
from .synthetic import build_fixture_frames, frame_logical_sha256
from .validation import ClinicalValidationEngine


def _git_info(repository_root: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    try:
        commit = run("rev-parse", "HEAD")
        branch = run("branch", "--show-current")
        status = run("status", "--porcelain")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"commit": "UNKNOWN", "branch": "UNKNOWN", "dirty": True}
    return {
        "commit": commit,
        "branch": branch,
        "dirty": bool(status),
        "dirty_entry_count": len(status.splitlines()) if status else 0,
    }


def _source_hash(project_root: Path) -> str:
    roots = [
        project_root / "src",
        project_root / "configs",
        project_root / "rules",
        project_root / "tests",
        project_root / "scripts",
    ]
    files = [
        path
        for root in roots
        for path in root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and not any(part.endswith(".egg-info") for part in path.parts)
    ]
    files.extend(
        path
        for path in (
            project_root / "pyproject.toml",
            project_root / "requirements-lock.txt",
            project_root / "uv.lock",
            project_root / "README.md",
            project_root / "MODEL_CARD.md",
        )
        if path.is_file()
    )
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(str(path.relative_to(project_root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _governance_hashes(project_root: Path) -> dict[str, str]:
    files = [
        *sorted((project_root / "configs").glob("*.yaml")),
        *sorted((project_root / "rules").rglob("*.yaml")),
        *sorted((project_root / "sql").glob("*.sql")),
        project_root / "uv.lock",
        project_root / "pyproject.toml",
    ]
    return {
        str(path.relative_to(project_root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in files
        if path.is_file()
    }


def _runtime_manifest() -> dict[str, Any]:
    packages = {}
    for name in (
        "pandas",
        "pyarrow",
        "PyYAML",
        "psycopg2-binary",
        "python-docx",
    ):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = "NOT_INSTALLED"
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "packages": packages,
    }


def _peak_memory_mb() -> float:
    maximum_rss = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
    return round(maximum_rss / divisor, 6)


def _assert_release_package_complete(run_root: Path) -> None:
    required = [
        run_root / "outputs" / "model_performance_comparison.csv",
        run_root / "outputs" / "model_performance_comparison.parquet",
        run_root / "figures" / "figure_manifest.csv",
        run_root / "figures" / "figure_manifest.json",
        run_root / "reports" / "model_performance_comparison.md",
        run_root / "reports" / "figure_interpretation_guide.md",
        run_root / "reports" / "figure_interpretation_guide.docx",
        run_root / "reports" / "automation_cycle_summary.md",
        run_root / "reports" / "final_model_selection.md",
    ]
    stems = (
        "01_validation_workflow",
        "02_scenario_matrix_coverage",
        "03_status_distribution_comparison",
        "04_confusion_matrix_status",
        "05_safety_gate_performance",
        "06_component_metric_comparison",
        "07_confidence_correctness_relationship",
        "08_cdei_component_profile",
        "09_data_quality_and_coverage",
        "10_multi_diagnosis_outcomes",
        "11_baseline_vs_final_improvement",
        "12_runtime_and_reproducibility",
    )
    required.extend(
        run_root / "figures" / f"{stem}.{suffix}"
        for stem in stems
        for suffix in ("png", "svg")
    )
    missing = [str(path.relative_to(run_root)) for path in required if not path.is_file()]
    empty = [
        str(path.relative_to(run_root))
        for path in required
        if path.is_file() and path.stat().st_size == 0
    ]
    if missing or empty:
        raise RuntimeError(
            "RELEASE_PACKAGE_INCOMPLETE: "
            + json.dumps({"missing": missing, "empty": empty}, sort_keys=True)
        )


def _run_id(config: PrototypeConfig, git_info: dict[str, Any], source_hash: str) -> str:
    timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d_%H%M%S%f")
    commit = str(git_info.get("commit", ""))[:7]
    suffix = source_hash[:7] if git_info.get("dirty") or commit == "UNKNOWN" else commit
    return f"{config.data_env}_{timestamp}_{suffix}"


def _oracle_failures(
    results_frame: pd.DataFrame, expected: pd.DataFrame
) -> list[dict[str, Any]]:
    actual = results_frame.set_index("diagnosis_candidate_id")
    oracle = expected.set_index("diagnosis_candidate_id")
    failures: list[dict[str, Any]] = []
    mappings = {
        "expected_status": "status",
        "expected_cdei_status": "cdei_status",
        "expected_model_decision_confidence": "model_decision_confidence",
        "expected_calibration_status": "calibration_status",
        "expected_profile_write_allowed": "profile_write_allowed",
        "expected_behavior_handoff_allowed": "behavior_handoff_allowed",
        "expected_candidate_set_conflict_status": "candidate_set_conflict_status",
        "expected_candidate_set_review_required": "candidate_set_review_required",
    }
    for candidate_id, expected_row in oracle.iterrows():
        if candidate_id not in actual.index:
            failures.append(
                {
                    "diagnosis_candidate_id": candidate_id,
                    "field": "candidate_presence",
                    "expected": "PRESENT",
                    "actual": "MISSING",
                    "failure_type": "IMPLEMENTATION_BUG",
                }
            )
            continue
        actual_row = actual.loc[candidate_id]
        for expected_field, actual_field in mappings.items():
            expected_value = expected_row[expected_field]
            actual_value = actual_row[actual_field]
            if isinstance(expected_value, bool):
                actual_value = bool(actual_value)
            if str(expected_value) != str(actual_value):
                failures.append(
                    {
                        "diagnosis_candidate_id": candidate_id,
                        "field": actual_field,
                        "expected": expected_value,
                        "actual": actual_value,
                        "failure_type": "IMPLEMENTATION_BUG",
                    }
                )
        raw_blocker = expected_row.get("expected_blocker", "")
        expected_blocker = "" if pd.isna(raw_blocker) else str(raw_blocker)
        blockers = json.loads(actual_row["blockers"])
        if expected_blocker and expected_blocker not in blockers:
            failures.append(
                {
                    "diagnosis_candidate_id": candidate_id,
                    "field": "blockers",
                    "expected": expected_blocker,
                    "actual": blockers,
                    "failure_type": "IMPLEMENTATION_BUG",
                }
            )
    for candidate_id in set(actual.index) - set(oracle.index):
        failures.append(
            {
                "diagnosis_candidate_id": candidate_id,
                "field": "candidate_presence",
                "expected": "ABSENT",
                "actual": "PRESENT",
                "failure_type": "TEST_DEFECT",
            }
        )
    return failures


class PrototypePipeline:
    def __init__(
        self,
        data_env: str = ACTIVE_ENVIRONMENT,
        execution_mode: str = "artifact",
    ):
        self.config = load_config(data_env, execution_mode)
        self.registry = RuleRegistry.fixture()

    def preflight(self) -> dict[str, Any]:
        git = _git_info(self.config.project_root.parent)
        env_presence = {
            environment: (
                self.config.project_root.parent / f".env.{environment}"
            ).is_file()
            for environment in ("dev", "stg", "release")
        }
        try:
            release_access = safe_environment_preflight(self.config)
        except ReleaseAccessError as error:
            return {
                "status": error.status,
                "reason_code": error.reason_code,
                "environment": ACTIVE_ENVIRONMENT,
                "environment_fallback": "DISABLED",
                "secret_values_returned": "NO",
            }
        rule_audit = self.registry.audit()
        result: dict[str, Any] = {
            "status": "READY_FOR_TECHNICAL_PROTOTYPE",
            "environment": self.config.data_env,
            "execution_mode": self.config.release_execution_mode,
            "git": git,
            "environment_files_present": env_presence,
            "environment_files_read": False,
            "rule_count": len(rule_audit),
            "rule_integrity_issue_count": sum(
                bool(item["integrity_issues"]) for item in rule_audit
            ),
            "clinical_layer_contract": "BLOCKED_BY_CLINICAL_LAYER_CONTRACT",
            "survey_source": "BLOCKED_BY_SURVEY_SOURCE",
            "clinical_validation": "BLOCKED_BY_REFERENCE_STANDARD",
            "db_write_allowed": False,
            "release_access": release_access,
        }
        if self.config.execution_mode == "artifact":
            try:
                source_run, _, fingerprints = snapshot_medical_artifacts(self.config)
            except (FileNotFoundError, ValueError):
                result["status"] = "BLOCKED_BY_RELEASE_ACCESS"
                result["reason_code"] = "RELEASE_ARTIFACT_UNAVAILABLE"
                return result
            result["medical_artifact_source_run"] = source_run
            result["medical_artifact_file_count"] = len(fingerprints)
            result["medical_artifact_access"] = "READ_ONLY_METADATA_PREFLIGHT"
        elif self.config.execution_mode == "db":
            result["status"] = "BLOCKED_BY_DB_ACCESS"
            result["db_mode"] = "SCAFFOLD_ONLY_NO_CONNECTION_ATTEMPTED"
        return result

    def run(self) -> dict[str, Any]:
        try:
            safe_environment_preflight(self.config)
        except ReleaseAccessError as error:
            return {
                "status": error.status,
                "reason_code": error.reason_code,
                "environment": ACTIVE_ENVIRONMENT,
                "execution_mode": self.config.release_execution_mode,
                "environment_fallback": "DISABLED",
                "connection_attempted": False,
            }
        if self.config.execution_mode == "db":
            return {
                "status": "BLOCKED_BY_DB_ACCESS",
                "reason": "DB mode requires a separately approved managed-query snapshot implementation.",
                "connection_attempted": False,
                "db_write_allowed": False,
            }

        source_run_id: str | None = None
        source_manifest: dict[str, Any] | None = None
        before = None
        if self.config.execution_mode == "artifact":
            try:
                source_run_id, source_root, before = snapshot_medical_artifacts(
                    self.config
                )
            except (FileNotFoundError, ValueError):
                return {
                    "status": "BLOCKED_BY_RELEASE_ACCESS",
                    "reason_code": "RELEASE_ARTIFACT_UNAVAILABLE",
                    "environment": ACTIVE_ENVIRONMENT,
                    "execution_mode": self.config.release_execution_mode,
                    "environment_fallback": "DISABLED",
                    "connection_attempted": False,
                }
            source_manifest = safe_snapshot_manifest(source_run_id, source_root, before)

        fixture_manifest = json.loads(
            (FIXTURE_ROOT / "synthetic_generation_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        frames = load_fixture_frames(FIXTURE_ROOT)
        expected_frames = build_fixture_frames(self.config, self.registry)
        fixture_names = {
            "candidates": ("diagnosis_candidates", "diagnosis_candidates.parquet"),
            "links": (
                "diagnosis_candidate_evidence_links",
                "diagnosis_candidate_evidence_links.parquet",
            ),
            "criteria": (
                "diagnosis_candidate_criteria",
                "diagnosis_candidate_criteria.parquet",
            ),
            "conflicts": (
                "diagnosis_candidate_conflicts",
                "diagnosis_candidate_conflicts.parquet",
            ),
            "evidence": ("synthetic_evidence_items", "synthetic_evidence_items.parquet"),
            "scenarios": ("scenario_manifest", "scenario_manifest.csv"),
            "expected": ("expected_validation_results", "expected_validation_results.csv"),
        }
        for loaded_name, (generated_name, filename) in fixture_names.items():
            expected_hash = frame_logical_sha256(expected_frames[generated_name])
            loaded_hash = frame_logical_sha256(frames[loaded_name])
            recorded_hash = fixture_manifest["files"][filename]["logical_sha256"]
            if not (expected_hash == loaded_hash == recorded_hash):
                raise RuntimeError(
                    "FIXTURE_INTEGRITY_ERROR: run generate-fixtures before validation"
                )
        candidates, criteria_by_id, evidence_by_id = materialize_fixture_contract(frames)
        engine = ClinicalValidationEngine(
            self.registry, execution_mode=self.config.execution_mode
        )
        evaluation_started = time.perf_counter()
        results = [
            engine.validate(
                candidate,
                criteria_by_id.get(candidate.diagnosis_candidate_id, []),
                evidence_by_id.get(candidate.diagnosis_candidate_id, []),
            )
            for candidate in candidates
        ]
        results = apply_candidate_set_checks(candidates, results, self.registry)
        evaluation_runtime_seconds = max(time.perf_counter() - evaluation_started, 1e-9)
        replay_engine = ClinicalValidationEngine(
            self.registry, execution_mode=self.config.execution_mode
        )
        replay_results = [
            replay_engine.validate(
                candidate,
                criteria_by_id.get(candidate.diagnosis_candidate_id, []),
                evidence_by_id.get(candidate.diagnosis_candidate_id, []),
            )
            for candidate in candidates
        ]
        replay_results = apply_candidate_set_checks(
            candidates, replay_results, self.registry
        )
        deterministic_replay = json.dumps(
            [result.to_dict() for result in results],
            sort_keys=True,
            default=str,
        ) == json.dumps(
            [result.to_dict() for result in replay_results],
            sort_keys=True,
            default=str,
        )

        if before is not None:
            try:
                after_run_id, _, after = snapshot_medical_artifacts(self.config)
            except (ValueError, FileNotFoundError) as error:
                return self._publish_source_mutation_block(
                    f"source trust verification failed: {type(error).__name__}",
                    source_run_id,
                )
            if after_run_id != source_run_id:
                return self._publish_source_mutation_block(
                    "latest source pointer changed", source_run_id
                )
            try:
                assert_source_unchanged(before, after)
            except SourceDataMutationError as error:
                return self._publish_source_mutation_block(str(error), source_run_id)

        git = _git_info(self.config.project_root.parent)
        source_hash = _source_hash(self.config.project_root)
        run_id = _run_id(self.config, git, source_hash)
        final_run_root = RESULT_ROOT / self.config.data_env / run_id
        run_root = RESULT_ROOT / self.config.data_env / f".{run_id}.incomplete"
        artifacts = run_root / "artifacts"
        figures = run_root / "figures"
        logs = run_root / "logs"
        outputs = run_root / "outputs"
        reports = run_root / "reports"
        for directory in (artifacts, figures, logs, outputs, reports):
            directory.mkdir(parents=True, exist_ok=False)

        frame = result_frame(results)
        oracle_failures = _oracle_failures(frame, frames["expected"])
        candidate_by_id = {item.diagnosis_candidate_id: item for item in candidates}
        contracts = []
        for result in results:
            rule = self.registry.get(result.rule_id) if result.rule_id else None
            source_ids = list(rule.provenance.get("source_ids", [])) if rule else []
            contracts.append(
                output_contract(
                    candidate_by_id[result.diagnosis_candidate_id],
                    result,
                    model_version=self.config.model_version,
                    run_id=run_id,
                    environment=self.config.data_env,
                    execution_mode=self.config.release_execution_mode,
                    data_snapshot_id=source_run_id,
                    rule_source_ids=source_ids,
                )
            )

        write_frame(
            frame,
            outputs / "clinical_validation_long.csv",
            outputs / "clinical_validation_long.parquet",
        )
        summary_columns = [
            "scenario_id",
            "synthetic_case_id",
            "diagnosis_candidate_id",
            "taxonomy",
            "status",
            "clinical_validation_score",
            "model_decision_confidence",
            "cdei_score",
            "cdei_status",
            "human_review_required",
            "profile_write_allowed",
            "behavior_handoff_allowed",
            "candidate_set_conflict_status",
            "candidate_set_completeness",
        ]
        write_frame(
            frame[summary_columns],
            outputs / "clinical_validation_summary.csv",
            outputs / "clinical_validation_summary.parquet",
        )
        write_frame(
            frame[["diagnosis_candidate_id", "cdei_score", "cdei_status", "cdei_components"]],
            outputs / "cdei_results.csv",
            outputs / "cdei_results.parquet",
        )
        frame[[
            "scenario_id",
            "diagnosis_candidate_id",
            "candidate_set_conflict_status",
            "candidate_set_review_required",
        ]].to_csv(outputs / "rule_conflicts.csv", index=False)
        frame[[
            "scenario_id",
            "diagnosis_candidate_id",
            "data_quality_status",
            "data_quality_issues",
        ]].to_csv(outputs / "data_quality_issues.csv", index=False)
        frame[[
            "diagnosis_candidate_id",
            "status",
            "profile_write_allowed",
            "behavior_handoff_allowed",
            "behavior_handoff_mode",
            "behavior_handoff_reason",
        ]].to_csv(outputs / "behavior_handoff.csv", index=False)
        write_jsonl(outputs / "validated_clinical_output.jsonl", contracts)

        rule_audit = self.registry.audit()
        pd.DataFrame(rule_audit).assign(
            integrity_issues=lambda data: data["integrity_issues"].map(json.dumps),
            omitted_elements=lambda data: data["omitted_elements"].map(json.dumps),
            modified_elements=lambda data: data["modified_elements"].map(json.dumps),
        ).to_csv(artifacts / "rule_registry.csv", index=False)
        write_json(artifacts / "rule_registry.json", rule_audit)
        evidence_registry = (
            pd.DataFrame(
                [
                    {
                        "feature_id": evidence.feature_id,
                        "source": evidence.source,
                        "unit": evidence.unit,
                        "data_origin": evidence.data_origin,
                        "provenance": evidence.provenance,
                        "quality_status": evidence.quality_status,
                        "upstream_validation_status": evidence.upstream_validation_status,
                    }
                    for evidence_items in evidence_by_id.values()
                    for evidence in evidence_items
                ]
            )
            .value_counts(sort=False)
            .rename("evidence_count")
            .reset_index()
            .sort_values(
                ["feature_id", "source", "unit", "quality_status"],
                kind="stable",
            )
            .reset_index(drop=True)
        )
        evidence_registry.to_csv(artifacts / "evidence_registry.csv", index=False)
        write_json(
            artifacts / "evidence_registry.json",
            {
                "records": evidence_registry.to_dict(orient="records"),
                "value_payload_persisted_in_run_registry": False,
                "candidate_level_identifiers_persisted": False,
            },
        )
        pd.DataFrame(
            [
                {
                    "feature_id": spec.feature_id,
                    "criterion_id": spec.criterion_id,
                    "role": spec.role.value,
                    "rule_id": rule.rule_id,
                }
                for rule in self.registry.values()
                for spec in rule.criterion_specs()
            ]
        ).to_csv(artifacts / "feature_registry.csv", index=False)
        write_json(
            artifacts / "feature_registry.json",
            [
                {
                    "feature_id": spec.feature_id,
                    "criterion_id": spec.criterion_id,
                    "role": spec.role.value,
                    "rule_id": rule.rule_id,
                }
                for rule in self.registry.values()
                for spec in rule.criterion_specs()
            ],
        )
        write_json(
            artifacts / "source_register.json",
            {
                "fixture_source": "SIBC-SYNTHETIC-RULE-SPEC",
                "taxonomy_content_copied": False,
                "research_registers": [
                    "docs/NANDA_RESEARCH_REGISTER.md",
                    "docs/OMAHA_RESEARCH_REGISTER.md",
                ],
            },
        )
        write_json(
            artifacts / "data_lineage.json",
            {
                "actual_pseudonymized_evidence": (
                    "READ_ONLY_METADATA_REFERENCE" if source_manifest else "NOT_USED"
                ),
                "synthetic_clinical_layer_output": str(
                    FIXTURE_ROOT.relative_to(self.config.project_root)
                ),
                "merge_policy": "NO_ACTUAL_ROW_VALUES_JOINED_IN_BASELINE",
                "oracle_fields_used_as_features": False,
            },
        )
        if source_manifest:
            write_json(artifacts / "source_snapshot_manifest.json", source_manifest)

        context = {
            "run_id": run_id,
            "environment": self.config.data_env,
            "execution_mode": self.config.release_execution_mode,
            "scenario_count": fixture_manifest["scenario_count"],
            "candidate_count": fixture_manifest["candidate_count"],
            "data_snapshot_id": source_run_id,
            "source_mutation_check": "PASSED" if source_manifest else "NOT_APPLICABLE",
            "technical_oracle_status": (
                "PASSED"
                if not oracle_failures and deterministic_replay
                else "FAILED"
            ),
            "clinical_validation_status": "BLOCKED_BY_REFERENCE_STANDARD",
        }
        write_json(artifacts / "report_context.json", context)
        manifest = {
            **context,
            "model_version": self.config.model_version,
            "generator_version": self.config.generator_version,
            "code_source_hash": source_hash,
            "governance_file_hashes": _governance_hashes(
                self.config.project_root
            ),
            "runtime": _runtime_manifest(),
            "git": git,
            "rule_versions": {
                rule.rule_id: rule.rule_version for rule in self.registry.values()
            },
            "fixture_manifest": fixture_manifest,
            "oracle_failure_count": len(oracle_failures),
            "technical_validation": {
                "synthetic_oracle_comparisons": len(results),
                "synthetic_oracle_failures": len(oracle_failures),
                "deterministic_replay_rate": 1.0 if deterministic_replay else 0.0,
                "pytest_status": "RUN_SEPARATELY_BY_REGRESSION_SCRIPT",
                "pytest_command": "uv run pytest",
            },
            "benchmark": {
                "runtime_seconds": round(evaluation_runtime_seconds, 6),
                "peak_memory_mb": _peak_memory_mb(),
                "throughput_candidates_per_second": round(
                    len(results) / evaluation_runtime_seconds, 6
                ),
                "scope": "SYNTHETIC_RULE_EVALUATION_ONLY",
            },
            "confidence_calibration_status": "NOT_CALIBRATED",
            "clinical_performance_claimed": False,
        }
        write_json(artifacts / "reproducibility_manifest.json", manifest)

        experiment = {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "BASELINE_AND_REGRESSION",
            "technical_oracle_status": context["technical_oracle_status"],
            "candidate_count": len(results),
            "oracle_failure_count": len(oracle_failures),
        }
        pd.DataFrame([experiment]).to_csv(logs / "experiment_ledger.csv", index=False)
        write_jsonl(logs / "experiment_ledger.jsonl", [experiment])
        write_failure_ledger(logs / "failure_ledger.csv", oracle_failures)
        write_jsonl(
            logs / "optimization_ledger.jsonl",
            [
                {
                    "run_id": run_id,
                    "iteration": 0,
                    "action": "NO_AUTOMATIC_RULE_CHANGE",
                    "reason": (
                        "BASELINE_PASSED"
                        if not oracle_failures
                        else "FAILURES_REQUIRE_IMPLEMENTATION_REVIEW"
                    ),
                    "clinical_rule_modified": False,
                }
            ],
        )
        write_reports(
            reports,
            context=context,
            results=results,
            oracle_failures=oracle_failures,
            registry=self.registry,
        )
        preliminary_security = scan_output_tree(run_root)
        if preliminary_security.get("finding_count"):
            shutil.rmtree(run_root)
            assert_security_scan_passed(preliminary_security)
        write_json(artifacts / "security_scan.json", preliminary_security)

        report_builder = self.config.project_root / "scripts" / "build_result_report.py"
        report_command = [
            sys.executable,
            str(report_builder),
            "--output-run-root",
            str(run_root),
            "--baseline-run-root",
            str(run_root),
            "--previous-best-run-root",
            str(run_root),
            "--current-candidate-run-root",
            str(run_root),
            "--final-selected-run-root",
            str(run_root),
        ]
        package_stage = "COMPARISON_AND_FIGURE_REPORTS"
        try:
            subprocess.run(
                report_command,
                cwd=self.config.project_root,
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            package_stage = "FIGURE_INTERPRETATION_DOCX"
            document_python = Path(
                os.environ.get("SIBC_DOCUMENT_PYTHON", sys.executable)
            )
            if not document_python.is_absolute() or not document_python.is_file():
                raise RuntimeError("UNMANAGED_DOCUMENT_PYTHON")
            subprocess.run(
                [
                    str(document_python),
                    str(
                        self.config.project_root
                        / "scripts"
                        / "build_figure_interpretation_docx.py"
                    ),
                    "--run-root",
                    str(run_root),
                ],
                cwd=self.config.project_root,
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.SubprocessError, RuntimeError) as error:
            shutil.rmtree(run_root)
            raise RuntimeError(
                "RELEASE_REPORT_PACKAGE_GENERATION_FAILED:"
                f"{package_stage}:{type(error).__name__}"
            ) from None

        _assert_release_package_complete(run_root)
        optimization_decisions = [
            json.loads(line)
            for line in (logs / "optimization_ledger.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip() and '"decision"' in line
        ]
        if (
            len(optimization_decisions) != 2
            or any(item.get("decision") != "REJECTED" for item in optimization_decisions)
        ):
            shutil.rmtree(run_root)
            raise RuntimeError("AUTOMATION_CYCLE_CONTRACT_FAILED")
        manifest["automation_cycle"] = {
            "evaluated_cycle_count": 2,
            "adopted_cycle_count": 0,
            "stop_reason": "NO_MEANINGFUL_IMPROVEMENT_FOR_CONSECUTIVE_CYCLES",
            "selection_origin": "baseline",
            "presentation_slot": "final_selected",
            "clinical_rule_modified": False,
            "expected_oracle_modified": False,
            "release_evidence_modified": False,
        }
        write_json(artifacts / "reproducibility_manifest.json", manifest)
        if before is not None:
            try:
                final_source_run_id, _, final_source_snapshot = (
                    snapshot_medical_artifacts(self.config)
                )
            except (ValueError, FileNotFoundError) as error:
                shutil.rmtree(run_root)
                return self._publish_source_mutation_block(
                    f"final source trust verification failed: {type(error).__name__}",
                    source_run_id,
                )
            if final_source_run_id != source_run_id:
                shutil.rmtree(run_root)
                return self._publish_source_mutation_block(
                    "latest source pointer changed before publication", source_run_id
                )
            try:
                assert_source_unchanged(before, final_source_snapshot)
            except SourceDataMutationError as error:
                shutil.rmtree(run_root)
                return self._publish_source_mutation_block(str(error), source_run_id)
        if _source_hash(self.config.project_root) != source_hash:
            shutil.rmtree(run_root)
            raise RuntimeError("CODE_SOURCE_MUTATION_DURING_RUN")

        security_report = scan_output_tree(run_root)
        if security_report.get("finding_count"):
            shutil.rmtree(run_root)
            assert_security_scan_passed(security_report)
        write_json(artifacts / "security_scan.json", security_report)
        write_json(
            artifacts / "completion_manifest.json",
            {
                "run_id": run_id,
                "state": "READY_FOR_ATOMIC_PUBLICATION",
                "release_report_package": "COMPLETE",
                "source_reverified_before_publication": before is not None,
            },
        )
        checksum_count = write_checksums(
            run_root, artifacts / "checksums.sha256"
        )
        verified_checksum_count = verify_checksums(
            run_root, artifacts / "checksums.sha256"
        )
        if verified_checksum_count != checksum_count:
            shutil.rmtree(run_root)
            raise RuntimeError("CHECKSUM_REGISTRATION_COUNT_MISMATCH")
        os.replace(run_root, final_run_root)
        run_root = final_run_root
        artifacts = run_root / "artifacts"
        latest = {
            "run_id": run_id,
            "status": context["technical_oracle_status"],
            "clinical_validation_status": "BLOCKED_BY_REFERENCE_STANDARD",
            "execution_mode": self.config.release_execution_mode,
            "release_report_package_status": "PASSED",
            "manifest": str(
                (artifacts / "reproducibility_manifest.json").relative_to(
                    RESULT_ROOT.parent
                )
            ),
            "checksums": str(
                (artifacts / "checksums.sha256").relative_to(RESULT_ROOT.parent)
            ),
            "checksum_file_count": checksum_count,
        }
        atomic_write_json(RESULT_ROOT / self.config.data_env / "latest_run.json", latest)
        return {
            **latest,
            "result_directory": str(run_root),
            "candidate_count": len(results),
            "scenario_count": fixture_manifest["scenario_count"],
            "oracle_failure_count": len(oracle_failures),
            "source_mutation_check": context["source_mutation_check"],
            "operational_handoff_count": int(frame["behavior_handoff_allowed"].sum()),
        }

    def _publish_source_mutation_block(
        self, reason: str, source_run_id: str | None
    ) -> dict[str, Any]:
        git = _git_info(self.config.project_root.parent)
        source_hash = _source_hash(self.config.project_root)
        run_id = _run_id(self.config, git, source_hash)
        final_root = RESULT_ROOT / self.config.data_env / run_id
        staging_root = RESULT_ROOT / self.config.data_env / f".{run_id}.incomplete"
        artifacts = staging_root / "artifacts"
        logs = staging_root / "logs"
        reports = staging_root / "reports"
        for directory in (
            artifacts,
            staging_root / "figures",
            logs,
            staging_root / "outputs",
            reports,
        ):
            directory.mkdir(parents=True, exist_ok=False)
        safe_reason = reason.replace(str(self.config.project_root.parent), "<REPOSITORY>")
        manifest = {
            "run_id": run_id,
            "status": "BLOCKED_BY_SOURCE_DATA_MUTATION",
            "source_run_id": source_run_id,
            "reason": safe_reason,
            "code_source_hash": source_hash,
            "git": git,
            "clinical_performance_claimed": False,
            "source_write_attempted": False,
        }
        write_json(artifacts / "reproducibility_manifest.json", manifest)
        write_failure_ledger(
            logs / "failure_ledger.csv",
            [
                {
                    "diagnosis_candidate_id": "RUN_LEVEL",
                    "field": "source_artifact_integrity",
                    "expected": "UNCHANGED",
                    "actual": "CHANGED",
                    "failure_type": "BLOCKED_BY_SOURCE_DATA_MUTATION",
                }
            ],
        )
        write_markdown(
            reports / "run_summary.md",
            "# Run blocked\n\n`BLOCKED_BY_SOURCE_DATA_MUTATION` was detected. "
            "Validation stopped and no source write was attempted.\n",
        )
        security_report = scan_output_tree(staging_root)
        if security_report.get("finding_count"):
            shutil.rmtree(staging_root)
            assert_security_scan_passed(security_report)
        write_json(artifacts / "security_scan.json", security_report)
        checksum_count = write_checksums(
            staging_root, artifacts / "checksums.sha256"
        )
        os.replace(staging_root, final_root)
        latest = {
            "run_id": run_id,
            "status": "BLOCKED_BY_SOURCE_DATA_MUTATION",
            "manifest": str(
                (final_root / "artifacts" / "reproducibility_manifest.json").relative_to(
                    RESULT_ROOT.parent
                )
            ),
            "checksums": str(
                (final_root / "artifacts" / "checksums.sha256").relative_to(
                    RESULT_ROOT.parent
                )
            ),
            "checksum_file_count": checksum_count,
        }
        atomic_write_json(RESULT_ROOT / self.config.data_env / "latest_run.json", latest)
        return {**latest, "result_directory": str(final_root)}
