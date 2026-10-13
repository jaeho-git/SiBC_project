from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from sibc_clinical_validation.config import FIXTURE_ROOT, load_config
from sibc_clinical_validation.pipeline import PrototypePipeline, _source_hash


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fixture_pipeline_publishes_atomically_without_rewriting_fixtures(
    tmp_path, monkeypatch
):
    isolated_result_root = tmp_path / "01_Results"
    monkeypatch.setattr(
        "sibc_clinical_validation.pipeline.RESULT_ROOT", isolated_result_root
    )
    fixture_files = {
        path.name: (_sha256(path), path.stat().st_mtime_ns)
        for path in FIXTURE_ROOT.iterdir()
        if path.is_file()
    }
    pipeline = PrototypePipeline("release", "fixture")
    result = pipeline.run()

    assert result["status"] == "PASSED"
    assert result["clinical_validation_status"] == "BLOCKED_BY_REFERENCE_STANDARD"
    assert result["scenario_count"] == 19
    assert result["candidate_count"] == 23
    assert result["oracle_failure_count"] == 0
    assert result["operational_handoff_count"] == 0
    assert result["execution_mode"] == "synthetic_fixture"
    assert result["release_report_package_status"] == "PASSED"

    run_root = Path(result["result_directory"])
    assert run_root.is_dir()
    assert not (run_root.parent / f".{result['run_id']}.incomplete").exists()
    latest = json.loads((run_root.parent / "latest_run.json").read_text(encoding="utf-8"))
    assert latest["run_id"] == result["run_id"]
    assert latest["status"] == "PASSED"

    manifest = json.loads(
        (run_root / "artifacts" / "reproducibility_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["code_source_hash"] == _source_hash(load_config().project_root)
    assert manifest["technical_validation"]["synthetic_oracle_failures"] == 0
    assert manifest["technical_validation"]["deterministic_replay_rate"] == 1.0
    assert manifest["environment"] == "release"
    assert manifest["execution_mode"] == "synthetic_fixture"
    assert manifest["clinical_performance_claimed"] is False
    assert manifest["governance_file_hashes"]["uv.lock"]
    assert manifest["runtime"]["python"]
    security = json.loads(
        (run_root / "artifacts" / "security_scan.json").read_text(encoding="utf-8")
    )
    assert security["status"] == "PASSED"
    assert security["finding_count"] == 0
    assert security["scanned_text_file_count"] >= 60

    summary = pd.read_csv(run_root / "outputs" / "clinical_validation_summary.csv")
    assert len(summary) == 23
    assert not summary["behavior_handoff_allowed"].any()
    assert (run_root / "outputs" / "validated_clinical_output.jsonl").is_file()
    comparison = pd.read_csv(
        run_root / "outputs" / "model_performance_comparison.csv"
    )
    assert len(comparison) == 51
    assert {
        "baseline_value",
        "previous_best_value",
        "current_candidate_value",
        "final_selected_value",
    } <= set(comparison.columns)
    for figure_number in range(1, 13):
        prefix = f"{figure_number:02d}_"
        assert len(list((run_root / "figures").glob(f"{prefix}*.png"))) == 1
        assert len(list((run_root / "figures").glob(f"{prefix}*.svg"))) == 1
    assert (run_root / "figures" / "figure_manifest.csv").is_file()
    assert (run_root / "figures" / "figure_manifest.json").is_file()
    assert (run_root / "reports" / "figure_interpretation_guide.docx").is_file()
    optimization_rows = [
        json.loads(line)
        for line in (run_root / "logs" / "optimization_ledger.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if '"decision"' in line
    ]
    assert [row["decision"] for row in optimization_rows] == ["REJECTED", "REJECTED"]

    for line in (run_root / "artifacts" / "checksums.sha256").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, relative = line.split("  ", 1)
        assert _sha256(run_root / relative) == digest

    after = {
        path.name: (_sha256(path), path.stat().st_mtime_ns)
        for path in FIXTURE_ROOT.iterdir()
        if path.is_file()
    }
    assert after == fixture_files
