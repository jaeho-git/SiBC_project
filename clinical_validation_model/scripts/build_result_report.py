from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from sibc_clinical_validation.evaluation import (  # noqa: E402
    MODEL_SLOTS,
    EvaluationContext,
    EvaluationSnapshot,
    VersionMetadata,
    assert_identifier_free,
    build_comparison_table,
    comparison_markdown,
    evaluate_version,
)
from sibc_clinical_validation.optimization import (  # noqa: E402
    OptimizationDecision,
    automation_cycle_summary_markdown,
    final_selection_markdown,
    select_candidate,
)
from sibc_clinical_validation.visualization import (  # noqa: E402
    figure_interpretation_markdown,
    render_required_figures,
)


FIXTURE_ROOT = PROJECT_ROOT / "00_Data" / "fixtures" / "synthetic_clinical_layer"


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _resolve_release_latest() -> Path:
    pointer = PROJECT_ROOT / "01_Results" / "release" / "latest_run.json"
    if not pointer.is_file():
        raise FileNotFoundError(
            "BLOCKED_BY_RELEASE_ACCESS: no release latest_run.json is available; "
            "dev/stg fallback is intentionally disabled"
        )
    latest = _load_json(pointer)
    run_id = str(latest.get("run_id", ""))
    if not run_id:
        raise ValueError("release latest_run.json has no run_id")
    return pointer.parent / run_id


def _validate_run_root(run_root: Path) -> Path:
    resolved = run_root.resolve()
    required = (
        resolved / "outputs" / "clinical_validation_long.parquet",
        resolved / "artifacts" / "reproducibility_manifest.json",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            f"BLOCKED_BY_RELEASE_ACCESS: run root is missing required inputs: {missing}"
        )
    return resolved


def _metadata(
    slot: str, run_root: Path, manifest: dict[str, Any]
) -> VersionMetadata:
    def required_text(container: dict[str, Any], name: str) -> str:
        value = container.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"BLOCKED_BY_RELEASE_ACCESS: missing governed provenance field {name}"
            )
        return value.strip()

    fixture = manifest.get("fixture_manifest")
    rule_versions = manifest.get("rule_versions")
    git = manifest.get("git")
    if not isinstance(fixture, dict):
        raise ValueError(
            "BLOCKED_BY_RELEASE_ACCESS: missing governed fixture provenance"
        )
    if not isinstance(rule_versions, dict) or not rule_versions or not all(
        isinstance(key, str)
        and key
        and isinstance(value, str)
        and value
        for key, value in rule_versions.items()
    ):
        raise ValueError(
            "BLOCKED_BY_RELEASE_ACCESS: missing governed rule-set provenance"
        )
    if not isinstance(git, dict):
        raise ValueError("BLOCKED_BY_RELEASE_ACCESS: missing governed git provenance")
    model_version = required_text(manifest, "model_version")
    generator_version = required_text(fixture, "generator_version")
    scenario_version = required_text(fixture, "oracle_policy_version")
    required_text(fixture, "generation_timestamp")
    raw_release_snapshot = manifest.get("data_snapshot_id")
    if raw_release_snapshot is None and manifest.get("execution_mode") == "synthetic_fixture":
        release_snapshot = "SYNTHETIC_FIXTURE_NO_RELEASE_EVIDENCE"
    else:
        release_snapshot = required_text(manifest, "data_snapshot_id")
    run_id = required_text(manifest, "run_id")
    if run_id != run_root.name.lstrip(".").removesuffix(".incomplete"):
        raise ValueError("BLOCKED_BY_RELEASE_ACCESS: run_id does not match run root")
    source_hash = required_text(manifest, "code_source_hash")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", source_hash):
        raise ValueError(
            "BLOCKED_BY_RELEASE_ACCESS: invalid code source hash provenance"
        )
    commit = git.get("commit")
    if commit is not None and (not isinstance(commit, str) or not commit.strip()):
        raise ValueError("BLOCKED_BY_RELEASE_ACCESS: invalid git commit provenance")
    code_revision = f"source-sha256:{source_hash}"
    if isinstance(commit, str) and commit.strip():
        code_revision = f"git:{commit.strip()}|{code_revision}"
    return VersionMetadata(
        slot=slot,
        model_version=model_version,
        code_commit=code_revision,
        rule_version=f"rule-set-sha256:{_canonical_hash(rule_versions)}",
        feature_version="synthetic_contract_v0.1",
        synthetic_generator_version=generator_version,
        synthetic_scenario_version=scenario_version,
        release_snapshot_id=release_snapshot,
        run_id=run_id,
    )


def _context(run_root: Path, manifest: dict[str, Any]) -> EvaluationContext:
    security_path = run_root / "artifacts" / "security_scan.json"
    security = _load_json(security_path) if security_path.is_file() else {}
    technical = manifest.get("technical_validation", {})
    benchmark = manifest.get("benchmark", {})
    fixture = manifest.get("fixture_manifest", {})
    replay = technical.get("deterministic_replay_rate")
    regression = technical.get("regression_pass_rate")
    tests = technical.get("test_pass_rate")
    return EvaluationContext(
        source_mutation_check=str(manifest.get("source_mutation_check") or "NOT_AVAILABLE"),
        security_scan_status=str(security.get("status") or "NOT_AVAILABLE"),
        deterministic_replay_rate=float(replay) if replay is not None else None,
        regression_pass_rate=float(regression) if regression is not None else None,
        test_pass_rate=float(tests) if tests is not None else None,
        branch_coverage=(
            float(technical["branch_coverage"])
            if technical.get("branch_coverage") is not None
            else None
        ),
        runtime_seconds=(
            float(benchmark["runtime_seconds"])
            if benchmark.get("runtime_seconds") is not None
            else None
        ),
        peak_memory_mb=(
            float(benchmark["peak_memory_mb"])
            if benchmark.get("peak_memory_mb") is not None
            else None
        ),
        throughput_candidates_per_second=(
            float(benchmark["throughput_candidates_per_second"])
            if benchmark.get("throughput_candidates_per_second") is not None
            else None
        ),
        expected_rule_count=(
            len(manifest["rule_versions"])
            if isinstance(manifest.get("rule_versions"), dict)
            else None
        ),
        generated_at=str(fixture.get("generation_timestamp") or "NOT_AVAILABLE"),
    )


def load_snapshot(slot: str, run_root: Path) -> EvaluationSnapshot:
    run_root = _validate_run_root(run_root)
    manifest = _load_json(run_root / "artifacts" / "reproducibility_manifest.json")
    if manifest.get("environment") != "release":
        raise ValueError(
            "BLOCKED_BY_RELEASE_ACCESS: report evaluation requires an explicit "
            "release run; dev/stg fallback is prohibited"
        )
    actual = pd.read_parquet(run_root / "outputs" / "clinical_validation_long.parquet")
    expected = pd.read_csv(FIXTURE_ROOT / "expected_validation_results.csv")
    scenarios = pd.read_csv(FIXTURE_ROOT / "scenario_manifest.csv")
    return evaluate_version(
        actual,
        expected,
        _metadata(slot, run_root, manifest),
        scenario_manifest=scenarios,
        context=_context(run_root, manifest),
    )


def _load_decisions(run_root: Path) -> list[OptimizationDecision]:
    path = run_root / "logs" / "optimization_ledger.jsonl"
    if not path.is_file():
        return []
    decisions: list[OptimizationDecision] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError("INVALID_OPTIMIZATION_LEDGER: malformed JSON") from error
        if not isinstance(value, dict):
            raise ValueError("INVALID_OPTIMIZATION_LEDGER: row must be an object")
        if "decision" not in value:
            baseline_fields = {
                "run_id",
                "iteration",
                "action",
                "reason",
                "clinical_rule_modified",
            }
            if set(value) != baseline_fields:
                raise ValueError(
                    "INVALID_OPTIMIZATION_LEDGER: invalid baseline row schema"
                )
            if (
                value["run_id"] != run_root.name.lstrip(".").removesuffix(".incomplete")
                or value["iteration"] != 0
                or value["action"] != "NO_AUTOMATIC_RULE_CHANGE"
                or value["reason"]
                not in {"BASELINE_PASSED", "FAILURES_REQUIRE_IMPLEMENTATION_REVIEW"}
                or value["clinical_rule_modified"] is not False
            ):
                raise ValueError(
                    "INVALID_OPTIMIZATION_LEDGER: invalid baseline governance values"
                )
            continue
        required = {
            "cycle",
            "candidate_slot",
            "decision",
            "reason_codes",
            "improved_metrics",
            "regressed_metrics",
            "final_selected_slot",
            "clinical_rule_modified",
            "clinical_validation_status",
            "clinical_performance_claimed",
            "decision_schema_version",
        }
        if set(value) != required:
            raise ValueError("INVALID_OPTIMIZATION_LEDGER: invalid decision row schema")
        if value["decision_schema_version"] != "optimization_decision_v1":
            raise ValueError("INVALID_OPTIMIZATION_LEDGER: unknown decision schema")
        if value["clinical_rule_modified"] is not False:
            raise ValueError("INVALID_OPTIMIZATION_LEDGER: clinical rule change detected")
        if value["clinical_performance_claimed"] is not False:
            raise ValueError("INVALID_OPTIMIZATION_LEDGER: clinical performance claim detected")
        if type(value["cycle"]) is not int:
            raise ValueError("INVALID_OPTIMIZATION_LEDGER: cycle must be an integer")
        for field in ("reason_codes", "improved_metrics", "regressed_metrics"):
            if not isinstance(value[field], list) or not all(
                isinstance(item, str) for item in value[field]
            ):
                raise ValueError(
                    "INVALID_OPTIMIZATION_LEDGER: metric/reason fields must be string lists"
                )
        assert_identifier_free(value)
        try:
            decision = OptimizationDecision(
                cycle=value["cycle"],
                candidate_slot=value["candidate_slot"],
                decision=value["decision"],
                reason_codes=tuple(value["reason_codes"]),
                improved_metrics=tuple(value["improved_metrics"]),
                regressed_metrics=tuple(value["regressed_metrics"]),
                final_selected_slot=value["final_selected_slot"],
                clinical_rule_modified=value["clinical_rule_modified"],
                clinical_validation_status=value["clinical_validation_status"],
            )
        except (TypeError, ValueError) as error:
            raise ValueError(
                "INVALID_OPTIMIZATION_LEDGER: decision values failed validation"
            ) from error
        decisions.append(decision)
    return decisions


def _assert_final_selection(
    snapshots: dict[str, EvaluationSnapshot | None],
    decisions: list[OptimizationDecision],
) -> None:
    if not decisions:
        raise ValueError("FINAL_SELECTION_MISMATCH: no optimization decision evidence")
    ordered = sorted(decisions, key=lambda item: item.cycle)
    if len({item.cycle for item in ordered}) != len(ordered):
        raise ValueError("FINAL_SELECTION_MISMATCH: duplicate optimization cycles")
    origin_slot = ordered[-1].final_selected_slot
    origin = snapshots.get(origin_slot)
    selected = snapshots.get("final_selected")
    if origin is None or selected is None:
        raise ValueError("FINAL_SELECTION_MISMATCH: selected snapshot is unavailable")

    def comparable_payload(snapshot: EvaluationSnapshot) -> dict[str, Any]:
        payload = snapshot.to_dict()
        metadata = dict(payload["metadata"])
        metadata.pop("slot", None)
        metadata.pop("run_id", None)
        payload["metadata"] = metadata
        return payload

    if comparable_payload(origin) != comparable_payload(selected):
        raise ValueError(
            "FINAL_SELECTION_MISMATCH: final_selected does not match the governed decision origin"
        )


def _supplemental_report_texts(
    selected: EvaluationSnapshot,
) -> dict[str, str]:
    def metric(name: str) -> Any:
        return selected.metrics[name].display_value()

    fixture_only = (
        selected.metadata.release_snapshot_id
        == "SYNTHETIC_FIXTURE_NO_RELEASE_EVIDENCE"
    )
    return {
        "release_data_technical_results.md": (
            "# Release data technical results\n\n"
            f"- Release snapshot: `{selected.metadata.release_snapshot_id}`\n"
            f"- Source mutation count: `{metric('source_data_mutation_count')}`\n"
            f"- Sensitive output finding count: `{metric('sensitive_data_exposure_count')}`\n"
            f"- Release evidence use: `{'NOT_USED_IN_SYNTHETIC_FIXTURE_MODE' if fixture_only else 'READ_ONLY_TECHNICAL_REFERENCE'}`\n\n"
            "These are source-integrity and execution-safety results, not clinical performance.\n"
        ),
        "synthetic_scenario_validation_results.md": (
            "# Synthetic scenario validation results\n\n"
            f"- Scenario count: `{selected.scenario_count}`\n"
            f"- Candidate count: `{selected.candidate_count}`\n"
            f"- Status exact match rate: `{metric('status_exact_match_rate')}`\n"
            f"- Unsafe pass rate: `{metric('unsafe_pass_rate')}`\n"
            f"- Deterministic replay rate: `{metric('deterministic_replay_rate')}`\n\n"
            "All values are synthetic technical-oracle results and are not clinical accuracy.\n"
        ),
        "unavailable_clinical_performance.md": (
            "# Unavailable clinical performance\n\n"
            "`CLINICAL_VALIDATION_STATUS = BLOCKED_BY_REFERENCE_STANDARD`\n\n"
            "Sensitivity, specificity, PPV, NPV, AUROC, clinical calibration, and individual diagnosis validity are not available and are not zero-filled.\n"
        ),
        "remaining_blockers.md": (
            "# Remaining blockers\n\n"
            "- `BLOCKED_BY_REFERENCE_STANDARD`\n"
            "- `BLOCKED_BY_LICENSE` for unlicensed operational taxonomy use\n"
            "- `BLOCKED_BY_CLINICAL_REVIEW`\n"
            "- `BLOCKED_BY_CLINICAL_LAYER_CONTRACT`\n"
            "- `BLOCKED_BY_SURVEY_SOURCE`\n"
            + (
                "- `SYNTHETIC_FIXTURE_NO_RELEASE_EVIDENCE`\n"
                if fixture_only
                else ""
            )
        ),
    }


def _baseline_no_change_decisions(
    snapshots: dict[str, EvaluationSnapshot | None],
) -> list[OptimizationDecision]:
    """Record the governed two-cycle no-improvement stop for a baseline-only run."""

    baseline = snapshots.get("baseline")
    candidate = snapshots.get("current_candidate")
    if baseline is None or candidate is None:
        return []
    return [
        select_candidate(baseline, candidate, cycle=1),
        select_candidate(baseline, candidate, cycle=2),
    ]


def _persist_decisions(
    run_root: Path, decisions: list[OptimizationDecision]
) -> None:
    path = run_root / "logs" / "optimization_ledger.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    lines = [
        json.dumps(item.to_dict(), ensure_ascii=False, sort_keys=True)
        for item in decisions
    ]
    path.write_text(existing + "\n".join(lines) + "\n", encoding="utf-8")


def build_release_report_package(
    output_run_root: Path,
    *,
    baseline_run_root: Path | None = None,
    previous_best_run_root: Path | None = None,
    current_candidate_run_root: Path | None = None,
    final_selected_run_root: Path | None = None,
) -> dict[str, Any]:
    """Build comparison/report artifacts without altering source or fixture data."""

    output_run_root = _validate_run_root(output_run_root)
    final_selected_run_root = final_selected_run_root or output_run_root
    slot_roots = {
        "baseline": baseline_run_root,
        "previous_best": previous_best_run_root,
        "current_candidate": current_candidate_run_root,
        "final_selected": final_selected_run_root,
    }
    snapshots: dict[str, EvaluationSnapshot | None] = {
        slot: load_snapshot(slot, root) if root is not None else None
        for slot, root in slot_roots.items()
    }
    comparison = build_comparison_table(snapshots)
    decisions = _load_decisions(output_run_root)
    if not decisions:
        decisions = _baseline_no_change_decisions(snapshots)
        _persist_decisions(output_run_root, decisions)
    _assert_final_selection(snapshots, decisions)
    outputs = output_run_root / "outputs"
    reports = output_run_root / "reports"
    figures = output_run_root / "figures"
    for directory in (outputs, reports, figures):
        directory.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(
        outputs / "model_performance_comparison.csv", index=False, lineterminator="\n"
    )
    parquet_comparison = comparison.copy()
    # Availability states and numeric observations intentionally share the same
    # governed value columns. Store their lexical representation in Parquet so
    # NOT_AVAILABLE is preserved instead of being coerced to zero/NaN.
    for column in (
        "baseline_value",
        "previous_best_value",
        "current_candidate_value",
        "final_selected_value",
        "absolute_change_vs_baseline",
        "relative_change_vs_baseline",
    ):
        parquet_comparison[column] = parquet_comparison[column].map(str)
    parquet_comparison.to_parquet(
        outputs / "model_performance_comparison.parquet", index=False
    )
    (reports / "model_performance_comparison.md").write_text(
        comparison_markdown(comparison, snapshots), encoding="utf-8"
    )
    selected = snapshots["final_selected"]
    if selected is None:
        raise AssertionError("final_selected snapshot was not built")
    generated_at = _context(
        final_selected_run_root,
        _load_json(
            final_selected_run_root / "artifacts" / "reproducibility_manifest.json"
        ),
    ).generated_at
    manifest = render_required_figures(
        figures, snapshots, comparison, generated_at=generated_at
    )
    (reports / "figure_interpretation_guide.md").write_text(
        figure_interpretation_markdown(snapshots, comparison), encoding="utf-8"
    )
    (reports / "automation_cycle_summary.md").write_text(
        automation_cycle_summary_markdown(decisions), encoding="utf-8"
    )
    (reports / "final_model_selection.md").write_text(
        final_selection_markdown(selected, decisions), encoding="utf-8"
    )
    for file_name, text in _supplemental_report_texts(selected).items():
        assert_identifier_free(text)
        (reports / file_name).write_text(text, encoding="utf-8")
    snapshot_payload = {
        slot: snapshot.to_dict() if snapshot is not None else "NOT_AVAILABLE"
        for slot, snapshot in snapshots.items()
    }
    assert_identifier_free(snapshot_payload)
    (outputs / "technical_evaluation_snapshots.json").write_text(
        json.dumps(snapshot_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "status": "PASSED",
        "clinical_validation_status": "BLOCKED_BY_REFERENCE_STANDARD",
        "clinical_performance_claimed": False,
        "output_run_root": str(output_run_root),
        "comparison_metric_count": len(comparison),
        "figure_file_count": len(manifest),
        "available_model_slots": [
            slot for slot in MODEL_SLOTS if snapshots[slot] is not None
        ],
        "unavailable_model_slots": [
            slot for slot in MODEL_SLOTS if snapshots[slot] is None
        ],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build deterministic Clinical Validation technical reports."
    )
    parser.add_argument(
        "--output-run-root",
        type=Path,
        help="Destination release run root. Defaults only to release/latest_run.json.",
    )
    parser.add_argument("--baseline-run-root", type=Path)
    parser.add_argument("--previous-best-run-root", type=Path)
    parser.add_argument("--current-candidate-run-root", type=Path)
    parser.add_argument("--final-selected-run-root", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        output = args.output_run_root or _resolve_release_latest()
        result = build_release_report_package(
            output,
            baseline_run_root=args.baseline_run_root,
            previous_best_run_root=args.previous_best_run_root,
            current_candidate_run_root=args.current_candidate_run_root,
            final_selected_run_root=args.final_selected_run_root,
        )
    except (FileNotFoundError, ValueError) as error:
        if "BLOCKED_BY_RELEASE_ACCESS" not in str(error):
            raise
        print(
            json.dumps(
                {
                    "status": "BLOCKED_BY_RELEASE_ACCESS",
                    "reason": str(error).split(":", 1)[-1].strip(),
                    "fallback_attempted": False,
                    "clinical_performance_claimed": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
