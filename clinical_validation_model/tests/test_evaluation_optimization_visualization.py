from __future__ import annotations

import importlib.util
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from sibc_clinical_validation.config import FIXTURE_ROOT, load_config
from sibc_clinical_validation.conflict_detection import apply_candidate_set_checks
from sibc_clinical_validation.evaluation import (
    AVAILABLE,
    BLOCKED_BY_REFERENCE_STANDARD,
    MODEL_SLOTS,
    NOT_AVAILABLE,
    EvaluationContext,
    MetricObservation,
    VersionMetadata,
    build_comparison_table,
    comparison_markdown,
    evaluate_version,
)
from sibc_clinical_validation.evidence import materialize_fixture_contract
from sibc_clinical_validation.optimization import (
    ImprovementProposal,
    OptimizationDecision,
    propose_safe_improvements,
    select_candidate,
)
from sibc_clinical_validation.reporting import result_frame
from sibc_clinical_validation.rule_schema import RuleRegistry
from sibc_clinical_validation.security import scan_output_tree
from sibc_clinical_validation.synthetic import build_fixture_frames
from sibc_clinical_validation.validation import ClinicalValidationEngine
from sibc_clinical_validation.visualization import (
    FIGURE_SPECS,
    figure_interpretation_markdown,
    render_required_figures,
)


@pytest.fixture(scope="module")
def evaluation_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    config = load_config("release", "fixture")
    registry = RuleRegistry.fixture()
    frames = build_fixture_frames(config, registry)
    materializer = {
        "candidates": frames["diagnosis_candidates"],
        "criteria": frames["diagnosis_candidate_criteria"],
        "evidence": frames["synthetic_evidence_items"],
        "links": frames["diagnosis_candidate_evidence_links"],
    }
    candidates, criteria_by_id, evidence_by_id = materialize_fixture_contract(materializer)
    engine = ClinicalValidationEngine(registry, execution_mode="fixture")
    results = [
        engine.validate(
            candidate,
            criteria_by_id.get(candidate.diagnosis_candidate_id, []),
            evidence_by_id.get(candidate.diagnosis_candidate_id, []),
        )
        for candidate in candidates
    ]
    results = apply_candidate_set_checks(candidates, results, registry)
    return result_frame(results), frames["expected_validation_results"], frames["scenario_manifest"]


def _complete_context() -> EvaluationContext:
    return EvaluationContext(
        source_mutation_check="PASSED",
        security_scan_status="PASSED",
        deterministic_replay_rate=1.0,
        regression_pass_rate=1.0,
        test_pass_rate=1.0,
        branch_coverage=0.75,
        runtime_seconds=0.25,
        peak_memory_mb=32.0,
        throughput_candidates_per_second=92.0,
        expected_rule_count=4,
        generated_at="2026-08-06T00:00:00Z",
    )


def _snapshot(
    slot: str,
    frames: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
    *,
    snapshot_id: str = "release_fixture_snapshot",
):
    actual, expected, scenarios = frames
    return evaluate_version(
        actual,
        expected,
        VersionMetadata(
            slot=slot,
            model_version=f"technical-{slot}",
            code_commit="technical-test-commit",
            rule_version="fixture-rule-set-v0.1",
            feature_version="synthetic_contract_v0.1",
            synthetic_generator_version="0.1.0",
            synthetic_scenario_version="fixture_oracle_policy_v0.1",
            release_snapshot_id=snapshot_id,
            run_id=f"release-{slot}",
        ),
        scenario_manifest=scenarios,
        context=_complete_context(),
    )


def test_evaluation_aggregates_exact_oracle_without_clinical_claims(
    evaluation_frames,
) -> None:
    snapshot = _snapshot("baseline", evaluation_frames)

    assert snapshot.candidate_count == 23
    assert snapshot.scenario_count == 19
    assert snapshot.metrics["overall_scenario_accuracy"].value == 1.0
    assert snapshot.metrics["status_exact_match_rate"].value == 1.0
    assert snapshot.metrics["unsafe_pass_rate"].value == 0.0
    assert snapshot.metrics["source_data_mutation_count"].value == 0
    assert snapshot.metrics["sensitive_data_exposure_count"].value == 0
    assert (
        snapshot.metrics["confidence_calibration_status"].availability_status
        == BLOCKED_BY_REFERENCE_STANDARD
    )
    assert (
        snapshot.metrics["wearable_availability_classification_accuracy"].availability_status
        == NOT_AVAILABLE
    )
    serialized = json.dumps(snapshot.to_dict(), sort_keys=True)
    assert "diagnosis_candidate_id" not in serialized
    assert "synthetic_case_id" not in serialized
    assert '"clinical_performance_claimed": false' in serialized


def test_evaluation_fails_closed_on_labels_and_never_zero_fills_missing_inputs(
    evaluation_frames,
) -> None:
    actual, expected, scenarios = evaluation_frames
    metadata = _snapshot("baseline", evaluation_frames).metadata

    raw_label = actual.copy()
    raw_label.loc[raw_label.index[0], "status"] = "USR-123"
    with pytest.raises(ValueError, match="INVALID_STATUS_LABEL") as error:
        evaluate_version(
            raw_label,
            expected,
            metadata,
            scenario_manifest=scenarios,
            context=_complete_context(),
        )
    assert "USR-123" not in str(error.value)

    missing_component = actual.copy()
    components = json.loads(missing_component.loc[missing_component.index[0], "cdei_components"])
    components.pop("evidence_linkage")
    missing_component.loc[missing_component.index[0], "cdei_components"] = json.dumps(
        components, sort_keys=True
    )
    incomplete = evaluate_version(
        missing_component,
        expected,
        metadata,
        scenario_manifest=scenarios,
        context=_complete_context(),
    )
    assert (
        incomplete.metrics["evidence_trace_completeness"].availability_status
        == NOT_AVAILABLE
    )

    without_rule_column = evaluate_version(
        actual.drop(columns=["rule_id"]),
        expected,
        metadata,
        scenario_manifest=scenarios,
        context=_complete_context(),
    )
    assert without_rule_column.metrics["rule_coverage_rate"].availability_status == NOT_AVAILABLE

    false_hard_gate = actual.copy()
    validated_index = false_hard_gate.index[false_hard_gate["status"] == "VALIDATED"][0]
    false_hard_gate.loc[validated_index, "hard_gate_passed"] = False
    violation = evaluate_version(
        false_hard_gate,
        expected,
        metadata,
        scenario_manifest=scenarios,
        context=_complete_context(),
    )
    assert violation.metrics["hard_gate_score_violation_count"].value == 1


def test_four_slot_comparison_preserves_unavailable_values_and_comparability(
    evaluation_frames,
) -> None:
    snapshots = {
        "baseline": _snapshot("baseline", evaluation_frames),
        "previous_best": None,
        "current_candidate": _snapshot("current_candidate", evaluation_frames),
        "final_selected": _snapshot("final_selected", evaluation_frames),
    }
    comparison = build_comparison_table(snapshots)

    assert list(comparison.columns) == [
        "metric_group",
        "metric_name",
        "baseline_value",
        "previous_best_value",
        "current_candidate_value",
        "final_selected_value",
        "absolute_change_vs_baseline",
        "relative_change_vs_baseline",
        "acceptance_direction",
        "acceptance_status",
        "interpretation",
        "limitation",
    ]
    assert set(comparison["previous_best_value"]) == {NOT_AVAILABLE}
    calibration = comparison.set_index("metric_name").loc[
        "confidence_calibration_status"
    ]
    assert calibration["baseline_value"] == BLOCKED_BY_REFERENCE_STANDARD
    assert calibration["absolute_change_vs_baseline"] == NOT_AVAILABLE
    assert "does not establish clinical" in comparison_markdown(comparison)

    incompatible = dict(snapshots)
    incompatible["final_selected"] = _snapshot(
        "final_selected", evaluation_frames, snapshot_id="different-release"
    )
    with pytest.raises(ValueError, match="non-comparable"):
        build_comparison_table(incompatible)


def test_optimization_is_safety_first_and_rejects_forbidden_changes(
    evaluation_frames,
) -> None:
    baseline = _snapshot("baseline", evaluation_frames)
    candidate = _snapshot("current_candidate", evaluation_frames)
    lowered = dict(baseline.metrics)
    lowered["status_exact_match_rate"] = MetricObservation.available(
        0.9, "Synthetic exact match."
    )
    baseline = replace(baseline, metrics=lowered)
    proposal = ImprovementProposal(
        proposal_id="TECH-001",
        change_type="IMPLEMENTATION_BUG_FIX",
        failure_category="IMPLEMENTATION_BUG",
        description="Bounded deterministic implementation fix.",
    )
    adopted = select_candidate(baseline, candidate, cycle=1, proposal=proposal)
    assert adopted.decision == "ADOPTED"
    assert "status_exact_match_rate" in adopted.improved_metrics
    assert adopted.clinical_rule_modified is False

    unsafe_metrics = dict(candidate.metrics)
    unsafe_metrics["unsafe_pass_rate"] = MetricObservation.available(
        0.01, "Synthetic unsafe pass rate."
    )
    rejected = select_candidate(
        baseline,
        replace(candidate, metrics=unsafe_metrics),
        cycle=2,
        proposal=proposal,
    )
    assert rejected.decision == "REJECTED"
    assert any("SAFETY_ZERO_TARGET_VIOLATED" in code for code in rejected.reason_codes)

    forbidden = replace(proposal, change_type="CLINICAL_THRESHOLD_CHANGE")
    with pytest.raises(ValueError, match="forbidden"):
        forbidden.validate()
    proposals = propose_safe_improvements(
        {"IMPLEMENTATION_BUG": 2, "CLINICAL_REVIEW_BLOCK": 9}
    )
    assert [item.change_type for item in proposals] == ["IMPLEMENTATION_BUG_FIX"]

    unavailable_replay_metrics = dict(candidate.metrics)
    unavailable_replay_metrics["deterministic_replay_rate"] = (
        MetricObservation.unavailable(
            "Replay evidence unavailable.",
            "A governed deterministic replay was not supplied.",
        )
    )
    unavailable_replay_metrics["runtime_seconds"] = MetricObservation.available(
        0.1, "Synthetic evaluation runtime."
    )
    replay_blocked = select_candidate(
        baseline,
        replace(candidate, metrics=unavailable_replay_metrics),
        cycle=3,
        proposal=proposal,
    )
    assert replay_blocked.decision == "REJECTED"
    assert (
        "REQUIRED_ADOPTION_EVIDENCE_UNAVAILABLE:deterministic_replay_rate"
        in replay_blocked.reason_codes
    )

    current_as_best = replace(
        baseline,
        metadata=replace(baseline.metadata, slot="current_candidate"),
    )
    with pytest.raises(ValueError, match="baseline slot|distinct governed slots"):
        select_candidate(current_as_best, candidate, cycle=4, proposal=proposal)

    with pytest.raises(ValueError, match="cannot modify clinical rules"):
        OptimizationDecision(
            cycle=1,
            candidate_slot="current_candidate",
            decision="REJECTED",
            reason_codes=("NO_MEANINGFUL_TECHNICAL_OR_EFFICIENCY_IMPROVEMENT",),
            improved_metrics=(),
            regressed_metrics=(),
            final_selected_slot="baseline",
            clinical_rule_modified=True,
        )


def test_all_twelve_figures_have_deterministic_png_svg_and_traceability(
    tmp_path, evaluation_frames
) -> None:
    snapshots = {slot: _snapshot(slot, evaluation_frames) for slot in MODEL_SLOTS}
    comparison = build_comparison_table(snapshots)
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_manifest = render_required_figures(
        first,
        snapshots,
        comparison,
        generated_at="2026-08-06T00:00:00Z",
    )
    second_manifest = render_required_figures(
        second,
        snapshots,
        comparison,
        generated_at="2026-08-06T00:00:00Z",
    )

    assert len(FIGURE_SPECS) == 12
    assert len(first_manifest) == 24
    assert first_manifest.to_dict("records") == second_manifest.to_dict("records")
    for spec in FIGURE_SPECS:
        png = first / f"{spec.stem}.png"
        svg = first / f"{spec.stem}.svg"
        assert png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        assert png.read_bytes() == (second / png.name).read_bytes()
        assert "Synthetic scenario-based technical evaluation" in svg.read_text(
            encoding="utf-8"
        )
        assert svg.read_bytes() == (second / svg.name).read_bytes()
    assert (first / "figure_manifest.csv").is_file()
    assert (first / "figure_manifest.json").is_file()
    guide = figure_interpretation_markdown(snapshots, comparison)
    assert guide.count("## Figure ") == 12
    assert "BLOCKED_BY_REFERENCE_STANDARD" in guide
    assert "diagnosis_candidate_id" not in guide

    stale = tmp_path / "stale"
    stale.mkdir()
    (stale / "stale.png").write_bytes(b"not-a-governed-image")
    (stale / "stale.svg").write_text("<svg/>", encoding="utf-8")
    with pytest.raises(ValueError, match="UNEXPECTED_STALE_FIGURE_FILES"):
        render_required_figures(
            stale,
            snapshots,
            comparison,
            generated_at="2026-08-06T00:00:00Z",
        )

    unsafe_distribution = dict(snapshots["final_selected"].status_distribution)
    unsafe_distribution["USR-123"] = 1
    unsafe_snapshots = dict(snapshots)
    unsafe_snapshots["final_selected"] = replace(
        snapshots["final_selected"], status_distribution=unsafe_distribution
    )
    with pytest.raises(ValueError, match="INVALID_STATUS_LABEL") as error:
        render_required_figures(
            tmp_path / "unsafe-label",
            unsafe_snapshots,
            comparison,
            generated_at="2026-08-06T00:00:00Z",
        )
    assert "USR-123" not in str(error.value)


def test_build_result_report_writes_release_package_without_new_dependency(
    tmp_path, evaluation_frames
) -> None:
    actual, _, _ = evaluation_frames
    run_root = tmp_path / "release" / "release_technical_test"
    (run_root / "outputs").mkdir(parents=True)
    (run_root / "artifacts").mkdir(parents=True)
    actual.to_parquet(run_root / "outputs" / "clinical_validation_long.parquet", index=False)
    manifest = {
        "run_id": run_root.name,
        "environment": "release",
        "model_version": "0.1.0",
        "code_source_hash": "a" * 64,
        "data_snapshot_id": "release_fixture_snapshot",
        "source_mutation_check": "PASSED",
        "generator_version": "0.1.0",
        "git": {"commit": "technical-test-commit"},
        "rule_versions": {
            "CLV-TEST-NANDA-A": "0.1.0",
            "CLV-TEST-OMAHA-A": "0.1.0",
            "CLV-TEST-OMAHA-B": "0.1.0",
            "CLV-TEST-UNAPPROVED": "0.1.0",
        },
        "fixture_manifest": {
            "generator_version": "0.1.0",
            "oracle_policy_version": "fixture_oracle_policy_v0.1",
            "generation_timestamp": "2026-08-06T00:00:00Z",
        },
        "technical_validation": {
            "deterministic_replay_rate": 1.0,
            "regression_pass_rate": 1.0,
            "test_pass_rate": 1.0,
            "branch_coverage": 0.75,
        },
        "benchmark": {
            "runtime_seconds": 0.25,
            "peak_memory_mb": 32.0,
            "throughput_candidates_per_second": 92.0,
        },
    }
    (run_root / "artifacts" / "reproducibility_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    (run_root / "artifacts" / "security_scan.json").write_text(
        json.dumps({"status": "PASSED", "finding_count": 0}), encoding="utf-8"
    )
    script = Path(__file__).resolve().parents[1] / "scripts" / "build_result_report.py"
    spec = importlib.util.spec_from_file_location("build_result_report", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    result = module.build_release_report_package(
        run_root,
        baseline_run_root=run_root,
        previous_best_run_root=run_root,
        current_candidate_run_root=run_root,
        final_selected_run_root=run_root,
    )

    assert result["status"] == "PASSED"
    assert result["clinical_validation_status"] == BLOCKED_BY_REFERENCE_STANDARD
    assert result["figure_file_count"] == 24
    assert result["available_model_slots"] == list(MODEL_SLOTS)
    assert scan_output_tree(run_root)["finding_count"] == 0
    for relative in (
        "outputs/model_performance_comparison.csv",
        "outputs/model_performance_comparison.parquet",
        "outputs/technical_evaluation_snapshots.json",
        "figures/figure_manifest.csv",
        "figures/figure_manifest.json",
        "reports/model_performance_comparison.md",
        "reports/figure_interpretation_guide.md",
        "reports/automation_cycle_summary.md",
        "reports/final_model_selection.md",
    ):
        assert (run_root / relative).is_file(), relative
    snapshots_text = (run_root / "outputs" / "technical_evaluation_snapshots.json").read_text(
        encoding="utf-8"
    )
    assert "diagnosis_candidate_id" not in snapshots_text
    assert '"clinical_performance_claimed": false' in snapshots_text
    cycle_summary = (run_root / "reports" / "automation_cycle_summary.md").read_text(
        encoding="utf-8"
    )
    assert cycle_summary.count("| REJECTED |") == 2
    assert "NO_MEANINGFUL_IMPROVEMENT_FOR_CONSECUTIVE_CYCLES" in cycle_summary
    final_selection = (run_root / "reports" / "final_model_selection.md").read_text(
        encoding="utf-8"
    )
    assert "Selection origin slot: `baseline`" in final_selection
    assert "unchanged baseline was copied" in final_selection
    ledger_rows = [
        json.loads(line)
        for line in (run_root / "logs" / "optimization_ledger.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert [row["cycle"] for row in ledger_rows] == [1, 2]
    assert {row["decision"] for row in ledger_rows} == {"REJECTED"}

    snapshot_payload = json.loads(snapshots_text)
    code_revision = snapshot_payload["baseline"]["metadata"]["code_commit"]
    assert "git:technical-test-commit" in code_revision
    assert f"source-sha256:{'a' * 64}" in code_revision

    ledger_path = run_root / "logs" / "optimization_ledger.jsonl"
    valid_ledger = ledger_path.read_text(encoding="utf-8")
    ledger_path.write_text('{"decision":"REJECTED"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="INVALID_OPTIMIZATION_LEDGER"):
        module._load_decisions(run_root)

    governed_row = json.loads(valid_ledger.splitlines()[0])
    raw_row = dict(governed_row)
    raw_row["reason_codes"] = ["diagnosis_candidate_id=DC-RAW-007"]
    ledger_path.write_text(json.dumps(raw_row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="private identifier") as error:
        module._load_decisions(run_root)
    assert "DC-RAW-007" not in str(error.value)

    clinical_change = dict(governed_row)
    clinical_change["clinical_rule_modified"] = True
    ledger_path.write_text(json.dumps(clinical_change) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="clinical rule change"):
        module._load_decisions(run_root)
    ledger_path.write_text(valid_ledger, encoding="utf-8")

    candidate_root = run_root.parent / "release_unsafe_candidate"
    shutil.copytree(run_root, candidate_root)
    candidate_manifest = dict(manifest)
    candidate_manifest["run_id"] = candidate_root.name
    candidate_manifest["model_version"] = "0.2.0-unsafe-candidate"
    (candidate_root / "artifacts" / "reproducibility_manifest.json").write_text(
        json.dumps(candidate_manifest), encoding="utf-8"
    )
    candidate_actual = actual.copy()
    candidate_actual.loc[
        candidate_actual.index[candidate_actual["scenario_id"] == "POSITIVE_CONTROL"][0],
        "status",
    ] = "CONTRADICTED"
    candidate_actual.to_parquet(
        candidate_root / "outputs" / "clinical_validation_long.parquet", index=False
    )
    with pytest.raises(ValueError, match="FINAL_SELECTION_MISMATCH"):
        module.build_release_report_package(
            run_root,
            baseline_run_root=run_root,
            previous_best_run_root=run_root,
            current_candidate_run_root=candidate_root,
            final_selected_run_root=candidate_root,
        )

    missing_provenance = dict(manifest)
    missing_provenance.pop("code_source_hash")
    (run_root / "artifacts" / "reproducibility_manifest.json").write_text(
        json.dumps(missing_provenance), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="missing governed provenance"):
        module.load_snapshot("baseline", run_root)
    (run_root / "artifacts" / "reproducibility_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    manifest["environment"] = "dev"
    (run_root / "artifacts" / "reproducibility_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="BLOCKED_BY_RELEASE_ACCESS"):
        module.load_snapshot("baseline", run_root)
