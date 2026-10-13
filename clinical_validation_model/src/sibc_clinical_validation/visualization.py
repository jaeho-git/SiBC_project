from __future__ import annotations

import binascii
import csv
import json
import math
import struct
import zlib
from collections import OrderedDict
from dataclasses import asdict, dataclass
from html import escape
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from .evaluation import (
    AVAILABLE,
    BLOCKED_BY_REFERENCE_STANDARD,
    MODEL_SLOTS,
    NOT_AVAILABLE,
    STATUS_ORDER,
    EvaluationSnapshot,
    assert_comparable,
    assert_identifier_free,
)
from .cdei import COMPONENTS as CDEI_COMPONENTS


TECHNICAL_CAPTION = (
    "Synthetic scenario-based technical evaluation; not clinical performance."
)


@dataclass(frozen=True)
class FigureSpec:
    figure_id: str
    stem: str
    title: str
    purpose: str
    metric_names: tuple[str, ...]


FIGURE_SPECS: tuple[FigureSpec, ...] = (
    FigureSpec("01", "01_validation_workflow", "Clinical Layer Validation Workflow", "Show how read-only release evidence metadata and synthetic Clinical Layer candidates enter the independent validation module.", ()),
    FigureSpec("02", "02_scenario_matrix_coverage", "Synthetic Scenario Matrix Coverage", "Show normal, error/safety, boundary/quality, and multi-diagnosis scenario coverage.", ("scenario_coverage_rate",)),
    FigureSpec("03", "03_status_distribution_comparison", "Validation Status Distribution Comparison", "Compare baseline and final-selected validation status counts without treating a higher validated rate as intrinsically better.", ("status_exact_match_rate",)),
    FigureSpec("04", "04_confusion_matrix_status", "Expected vs Actual Technical Status Matrix", "Compare expected technical-oracle status with actual final-selected status.", ("status_exact_match_rate",)),
    FigureSpec("05", "05_safety_gate_performance", "Safety Gate Performance", "Compare unsafe pass, exclusions, contradictions, future leakage, unapproved activation, and hard-gate violations.", ("unsafe_pass_rate", "missed_exclusion_rate", "missed_contradiction_rate", "missed_future_leakage_rate", "unapproved_rule_activation_rate", "hard_gate_score_violation_count")),
    FigureSpec("06", "06_component_metric_comparison", "Technical Component Metric Comparison", "Compare data-quality, evidence, rule-trace, CDEI, and decision components.", ("data_quality_gate_accuracy", "evidence_trace_completeness", "rule_trace_completeness", "cdei_component_completeness", "status_exact_match_rate")),
    FigureSpec("07", "07_confidence_correctness_relationship", "Decision Stability Index and Technical Correctness", "Show the relationship between technical correctness and the uncalibrated decision-stability index when assessable.", ("confidence_error_separation", "confidence_calibration_status")),
    FigureSpec("08", "08_cdei_component_profile", "CDEI Component Profile", "Display final-selected Clinical Decision Explanation Index component completeness.", ("cdei_component_completeness", "evidence_trace_completeness", "rule_trace_completeness", "limitation_disclosure_rate", "conflict_disclosure_rate", "narrative_faithfulness_rate", "groundedness_pass_rate", "reproducibility_trace_rate")),
    FigureSpec("09", "09_data_quality_and_coverage", "Data Quality and Coverage", "Summarize evidence coverage, assessability, temporal gates, rule coverage, and scenario coverage.", ("evidence_coverage_rate", "required_evidence_assessable_rate", "data_quality_gate_accuracy", "temporal_alignment_pass_rate", "wearable_availability_classification_accuracy", "rule_coverage_rate", "scenario_coverage_rate")),
    FigureSpec("10", "10_multi_diagnosis_outcomes", "Multi-Diagnosis Scenario Outcomes", "Show coverage of coherent, conflicting, cross-taxonomy, and partially assessable diagnosis-set scenarios.", ("multi_diagnosis_consistency_rate", "conflict_detection_rate")),
    FigureSpec("11", "11_baseline_vs_final_improvement", "Baseline vs Final-Selected Technical Change", "Summarize measured change versus baseline under safety-first selection.", ("status_exact_match_rate", "conflict_detection_rate", "exclusion_gate_accuracy", "cdei_component_completeness", "runtime_seconds", "throughput_candidates_per_second")),
    FigureSpec("12", "12_runtime_and_reproducibility", "Runtime and Deterministic Reproducibility", "Compare runtime, throughput, deterministic replay, regression, and test execution evidence.", ("runtime_seconds", "throughput_candidates_per_second", "deterministic_replay_rate", "regression_pass_rate", "test_pass_rate")),
)


@dataclass(frozen=True)
class FigurePayload:
    kind: str
    title: str
    subtitle: str
    x_label: str
    y_label: str
    labels: tuple[str, ...] = ()
    series: Mapping[str, tuple[float | None, ...]] | None = None
    matrix: tuple[tuple[float, ...], ...] = ()
    matrix_rows: tuple[str, ...] = ()
    matrix_columns: tuple[str, ...] = ()
    annotations: tuple[str, ...] = ()
    observation: str = ""
    limitation: str = ""


def render_required_figures(
    output_directory: Path,
    snapshots: Mapping[str, EvaluationSnapshot | None],
    comparison: pd.DataFrame,
    *,
    generated_at: str,
) -> pd.DataFrame:
    """Render all governed PNG/SVG figures plus CSV/JSON traceability manifests."""

    output_directory.mkdir(parents=True, exist_ok=True)
    expected_image_names = {
        f"{spec.stem}.{suffix}"
        for spec in FIGURE_SPECS
        for suffix in ("png", "svg")
    }
    existing_image_names = {
        path.name
        for suffix in ("*.png", "*.svg")
        for path in output_directory.glob(suffix)
        if path.is_file()
    }
    if not existing_image_names <= expected_image_names:
        raise ValueError(
            "UNEXPECTED_STALE_FIGURE_FILES: output directory contains unmanaged images"
        )
    normalized = {slot: snapshots.get(slot) for slot in MODEL_SLOTS}
    assert_comparable(normalized)
    for snapshot in normalized.values():
        if snapshot is not None:
            _validate_snapshot_for_render(snapshot)
    selected = normalized["final_selected"]
    if selected is None:
        raise ValueError("final_selected snapshot is required for figure generation")
    payloads = _build_payloads(normalized, comparison)
    assert_identifier_free(
        {figure_id: asdict(payload) for figure_id, payload in payloads.items()}
    )
    versions = {
        slot: (
            snapshot.metadata.model_version
            if snapshot is not None
            else NOT_AVAILABLE
        )
        for slot, snapshot in normalized.items()
    }
    records: list[dict[str, Any]] = []
    for spec in FIGURE_SPECS:
        payload = payloads[spec.figure_id]
        svg_path = output_directory / f"{spec.stem}.svg"
        png_path = output_directory / f"{spec.stem}.png"
        svg_path.write_text(_render_svg(payload), encoding="utf-8")
        png_path.write_bytes(_render_png(payload))
        for path in (png_path, svg_path):
            records.append(
                {
                    "figure_id": spec.figure_id,
                    "file_name": path.name,
                    "title": spec.title,
                    "purpose": spec.purpose,
                    "source_output_files": json.dumps(
                        [
                            "outputs/clinical_validation_long.parquet",
                            "00_Data/fixtures/synthetic_clinical_layer/expected_validation_results.csv",
                            "outputs/model_performance_comparison.csv",
                        ],
                        ensure_ascii=False,
                    ),
                    "metric_names": json.dumps(list(spec.metric_names), ensure_ascii=False),
                    "model_versions_compared": json.dumps(versions, ensure_ascii=False),
                    "release_snapshot_id": selected.metadata.release_snapshot_id,
                    "synthetic_scenario_version": selected.metadata.synthetic_scenario_version,
                    "generated_at": generated_at,
                    "interpretation_section": f"Figure {spec.figure_id}",
                    "limitations": payload.limitation,
                }
            )
    manifest = pd.DataFrame(records)
    assert_identifier_free(manifest.to_dict(orient="records"))
    rendered_image_names = {
        path.name
        for suffix in ("*.png", "*.svg")
        for path in output_directory.glob(suffix)
        if path.is_file()
    }
    if rendered_image_names != expected_image_names:
        raise RuntimeError("FIGURE_SET_INCOMPLETE: expected exactly 12 PNG and 12 SVG")
    if set(manifest["file_name"]) != expected_image_names or len(manifest) != 24:
        raise RuntimeError("FIGURE_MANIFEST_MISMATCH: manifest does not match images")
    _write_manifest(output_directory, manifest)
    return manifest


def figure_interpretation_markdown(
    snapshots: Mapping[str, EvaluationSnapshot | None],
    comparison: pd.DataFrame,
) -> str:
    normalized = {slot: snapshots.get(slot) for slot in MODEL_SLOTS}
    for snapshot in normalized.values():
        if snapshot is not None:
            _validate_snapshot_for_render(snapshot)
    payloads = _build_payloads(normalized, comparison)
    assert_identifier_free(
        {figure_id: asdict(payload) for figure_id, payload in payloads.items()}
    )
    lines = [
        "# Figure interpretation guide",
        "",
        "> Every figure reports synthetic scenario-based technical evaluation. No figure establishes clinical accuracy, calibration, diagnosis validity, or patient-level performance.",
        "",
    ]
    for spec in FIGURE_SPECS:
        payload = payloads[spec.figure_id]
        lines.extend(
            [
                f"## Figure {spec.figure_id}. {spec.title}",
                "",
                f"- Purpose: {spec.purpose}",
                f"- Comparison: {payload.subtitle}",
                f"- Observed result: {payload.observation}",
                f"- Preferred direction: {_preferred_direction(spec)}",
                "- Interpretation caution: A technically correct synthetic status is not an expert-adjudicated clinical diagnosis.",
                f"- Improvement implication: {_improvement_implication(spec, payload)}",
                f"- Current limitation: {payload.limitation}",
                "",
            ]
        )
    result = "\n".join(lines).rstrip() + "\n"
    assert_identifier_free(result)
    return result


def _validate_snapshot_for_render(snapshot: EvaluationSnapshot) -> None:
    if tuple(snapshot.status_distribution) != STATUS_ORDER:
        raise ValueError("INVALID_STATUS_LABEL: figure status labels are not governed")
    if tuple(snapshot.confusion_matrix) != STATUS_ORDER or any(
        tuple(row) != STATUS_ORDER for row in snapshot.confusion_matrix.values()
    ):
        raise ValueError("INVALID_STATUS_LABEL: confusion matrix labels are not governed")
    if not set(snapshot.cdei_component_means) <= set(CDEI_COMPONENTS):
        raise ValueError("INVALID_CDEI_COMPONENT: figure component label is not governed")
    if not set(snapshot.scenario_category_counts) <= {
        "normal_control",
        "error_and_safety",
        "boundary_and_quality",
        "multi_diagnosis",
        "other",
    }:
        raise ValueError("INVALID_SCENARIO_CATEGORY: figure label is not governed")
    if set(snapshot.multi_diagnosis_outcomes) != {
        "MULTIPLE_COHERENT_DIAGNOSES",
        "MULTIPLE_CONFLICTING_DIAGNOSES",
        "NANDA_OMAHA_CROSS_TAXONOMY_OVERLAP",
        "PARTIALLY_ASSESSABLE_DIAGNOSIS_SET",
    }:
        raise ValueError("INVALID_MULTI_DIAGNOSIS_LABEL: figure label is not governed")
    assert_identifier_free(snapshot.to_dict())


def _preferred_direction(spec: FigureSpec) -> str:
    if spec.figure_id == "03":
        return "Exact agreement with the technical oracle; no individual status proportion is a quality target."
    if spec.figure_id == "04":
        return "Counts on the expected/actual diagonal, subject to independent oracle integrity."
    if spec.figure_id == "05":
        return "All safety miss and violation metrics remain zero."
    if spec.figure_id == "11":
        return "Technical improvement with no safety, privacy, leakage, or reproducibility regression."
    return "Higher completeness/correctness where defined, with unavailable evidence kept explicit."


def _improvement_implication(spec: FigureSpec, payload: FigurePayload) -> str:
    if payload.kind == "status":
        return "Collect the governed evidence named in the limitation; do not infer or zero-fill it."
    if spec.figure_id == "11" and "No measured change" in payload.observation:
        return "Keep the baseline implementation; no change is justified by the current comparison."
    return "Use only verified failure analysis and bounded non-clinical implementation changes."


def _write_manifest(directory: Path, frame: pd.DataFrame) -> None:
    csv_path = directory / "figure_manifest.csv"
    json_path = directory / "figure_manifest.json"
    frame.to_csv(csv_path, index=False, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    json_path.write_text(
        json.dumps(frame.to_dict(orient="records"), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )


def _build_payloads(
    snapshots: Mapping[str, EvaluationSnapshot | None], comparison: pd.DataFrame
) -> dict[str, FigurePayload]:
    selected = snapshots["final_selected"]
    if selected is None:
        raise ValueError("final_selected snapshot is required")
    baseline = snapshots["baseline"]
    payloads: dict[str, FigurePayload] = {}
    payloads["01"] = FigurePayload(
        kind="workflow",
        title=FIGURE_SPECS[0].title,
        subtitle="Read-only release metadata and synthetic diagnosis candidates remain separated.",
        x_label="Workflow stage",
        y_label="Governed data flow",
        labels=("USER DATA", "CROSS VALIDATION", "CLINICAL DIAGNOSIS ENGINE", "CLINICAL VALIDATION MODEL", "VALIDATED CLINICAL OUTPUT"),
        annotations=("READ-ONLY RELEASE EVIDENCE METADATA", "SYNTHETIC SCENARIO MATRIX", "PROFILE / BEHAVIOR HANDOFF BLOCKED"),
        observation="The validation module remains inside the Clinical Layer and does not write source artifacts.",
        limitation="Production Clinical Layer contract and clinical reference standard remain unavailable.",
    )
    payloads["02"] = _bar_payload(
        FIGURE_SPECS[1].title,
        "Final-selected coverage by governed synthetic scenario category.",
        tuple(selected.scenario_category_counts),
        {"FINAL SELECTED": tuple(float(value) for value in selected.scenario_category_counts.values())},
        "Scenario category",
        "Scenario count",
        f"{selected.scenario_count} synthetic scenarios are represented across the displayed categories.",
        "Coverage counts describe fixture breadth, not prevalence or clinical representativeness.",
    )
    status_labels = tuple(selected.status_distribution)
    payloads["03"] = _bar_payload(
        FIGURE_SPECS[2].title,
        "Baseline and final-selected candidate status counts.",
        status_labels,
        {
            "BASELINE": tuple(
                float(baseline.status_distribution.get(name, 0)) if baseline else None
                for name in status_labels
            ),
            "FINAL SELECTED": tuple(float(selected.status_distribution.get(name, 0)) for name in status_labels),
        },
        "Validation status",
        "Candidate count",
        "Status counts are compared without treating a higher VALIDATED count as an optimization target.",
        "Statuses are synthetic technical-oracle outputs and are not clinical diagnoses.",
    )
    matrix_statuses = tuple(selected.confusion_matrix)
    payloads["04"] = FigurePayload(
        kind="matrix",
        title=FIGURE_SPECS[3].title,
        subtitle="Final-selected synthetic expected status (rows) versus actual status (columns).",
        x_label="Actual technical status",
        y_label="Expected technical status",
        matrix=tuple(
            tuple(float(selected.confusion_matrix[row].get(column, 0)) for column in matrix_statuses)
            for row in matrix_statuses
        ),
        matrix_rows=matrix_statuses,
        matrix_columns=matrix_statuses,
        observation=f"Exact status match rate is {_display_metric(selected, 'status_exact_match_rate')}.",
        limitation="The expected labels are deterministic fixture oracles, not expert-adjudicated clinical truth.",
    )
    safety_names = FIGURE_SPECS[4].metric_names
    payloads["05"] = _metric_bar_payload(
        FIGURE_SPECS[4].title,
        "Safety errors and hard-gate violations across available model slots.",
        safety_names,
        snapshots,
        "Safety metric",
        "Rate or count (target = 0)",
        "Zero is required for unsafe pass, leakage, unapproved activation, and source/privacy violations.",
        "Only metrics backed by supplied run evidence are plotted; missing evidence is labelled NA.",
    )
    component_names = FIGURE_SPECS[5].metric_names
    payloads["06"] = _metric_bar_payload(
        FIGURE_SPECS[5].title,
        "Baseline and final-selected technical component rates.",
        component_names,
        {"baseline": baseline, "final_selected": selected},
        "Technical component",
        "Rate (0 to 1)",
        "Component rates summarize synthetic gate correctness and trace completeness.",
        "CDEI and technical-oracle agreement do not measure clinical accuracy.",
    )
    confidence = selected.metrics["confidence_error_separation"]
    if confidence.availability_status != AVAILABLE:
        payloads["07"] = _status_payload(
            FIGURE_SPECS[6].title,
            "Decision stability index versus technical correctness.",
            NOT_AVAILABLE,
            "All current decision-stability values are policy-fixed and uncalibrated; an error-separation distribution cannot be estimated.",
            "Clinical calibration remains BLOCKED_BY_REFERENCE_STANDARD.",
        )
    else:
        confidence_summary = selected.correctness_confidence
        payloads["07"] = _bar_payload(
            FIGURE_SPECS[6].title,
            "Mean uncalibrated decision-stability index by technical correctness.",
            ("CORRECT", "INCORRECT"),
            {
                "MEAN INDEX": (
                    _numeric_or_none(confidence_summary.get("correct_mean")),
                    _numeric_or_none(confidence_summary.get("incorrect_mean")),
                )
            },
            "Technical result",
            "Decision-stability index (not probability)",
            "The displayed index is not a probability and does not establish calibration.",
            "Clinical calibration remains BLOCKED_BY_REFERENCE_STANDARD.",
        )
    cdei_labels = tuple(selected.cdei_component_means)
    payloads["08"] = _bar_payload(
        FIGURE_SPECS[7].title,
        "Final-selected Clinical Decision Explanation Index components.",
        cdei_labels,
        {"FINAL SELECTED": tuple(selected.cdei_component_means.values())},
        "CDEI component",
        "Completeness (0 to 1)",
        "CDEI components report traceability and explanation reproducibility.",
        "CDEI is not diagnostic accuracy or clinical confidence.",
    )
    payloads["09"] = _metric_bar_payload(
        FIGURE_SPECS[8].title,
        "Final-selected data-quality and coverage metrics.",
        FIGURE_SPECS[8].metric_names,
        {"final_selected": selected},
        "Quality or coverage metric",
        "Rate (0 to 1)",
        "Unavailable wearable or registry evidence is explicitly labelled NA.",
        "The fixture does not establish real-world data availability or population coverage.",
    )
    multi_labels = tuple(selected.multi_diagnosis_outcomes)
    payloads["10"] = _bar_payload(
        FIGURE_SPECS[9].title,
        "Final-selected synthetic multi-diagnosis scenario candidate counts.",
        multi_labels,
        {"CANDIDATES": tuple(float(value) for value in selected.multi_diagnosis_outcomes.values())},
        "Multi-diagnosis scenario",
        "Candidate count",
        f"Multi-diagnosis consistency rate is {_display_metric(selected, 'multi_diagnosis_consistency_rate')}.",
        "Scenario outcomes test implementation policy and do not establish clinical coexistence validity.",
    )
    change_rows = comparison[comparison["metric_name"].isin(FIGURE_SPECS[10].metric_names)]
    change_values = [_numeric_or_none(value) for value in change_rows["absolute_change_vs_baseline"]]
    available_changes = [value for value in change_values if value is not None]
    change_observation = (
        "No measured change versus baseline; no improvement is claimed."
        if available_changes and all(value == 0.0 for value in available_changes)
        else "Only measured, comparable technical changes are shown; unavailable changes are labelled NA."
    )
    payloads["11"] = _bar_payload(
        FIGURE_SPECS[10].title,
        "Final-selected absolute technical change versus baseline.",
        tuple(change_rows["metric_name"]),
        {"ABSOLUTE CHANGE": tuple(change_values)},
        "Technical metric",
        "Absolute change",
        change_observation,
        "Mixed metric units require metric-by-metric interpretation; unavailable baseline comparisons are not zero-filled.",
    )
    runtime_metrics = FIGURE_SPECS[11].metric_names
    if not any(
        selected.metrics[name].availability_status == AVAILABLE for name in runtime_metrics
    ):
        payloads["12"] = _status_payload(
            FIGURE_SPECS[11].title,
            "Runtime, throughput, deterministic replay, regression, and test evidence.",
            NOT_AVAILABLE,
            "No governed benchmark/replay context was supplied for this evaluation snapshot.",
            "Do not replace missing runtime or replay evidence with zero.",
        )
    else:
        payloads["12"] = _metric_bar_payload(
            FIGURE_SPECS[11].title,
            "Available runtime and deterministic replay evidence by model slot.",
            runtime_metrics,
            snapshots,
            "Benchmark or reproducibility metric",
            "Recorded value (mixed units)",
            "Values are displayed only when explicitly supplied by the benchmark or regression context.",
            "Runtime, throughput, rates, and memory use different units and must be read from labels.",
        )
    return payloads


def _metric_bar_payload(
    title: str,
    subtitle: str,
    metric_names: Sequence[str],
    snapshots: Mapping[str, EvaluationSnapshot | None],
    x_label: str,
    y_label: str,
    observation: str,
    limitation: str,
) -> FigurePayload:
    series: dict[str, tuple[float | None, ...]] = OrderedDict()
    for slot in MODEL_SLOTS:
        if slot not in snapshots:
            continue
        snapshot = snapshots.get(slot)
        values = tuple(
            float(snapshot.metrics[name].value)
            if snapshot is not None
            and snapshot.metrics[name].availability_status == AVAILABLE
            and snapshot.metrics[name].value is not None
            else None
            for name in metric_names
        )
        if snapshot is not None or any(value is not None for value in values):
            series[slot.replace("_", " ").upper()] = values
    return _bar_payload(
        title,
        subtitle,
        tuple(metric_names),
        series,
        x_label,
        y_label,
        observation,
        limitation,
    )


def _bar_payload(
    title: str,
    subtitle: str,
    labels: tuple[str, ...],
    series: Mapping[str, tuple[float | None, ...]],
    x_label: str,
    y_label: str,
    observation: str,
    limitation: str,
) -> FigurePayload:
    return FigurePayload(
        kind="bars",
        title=title,
        subtitle=subtitle,
        x_label=x_label,
        y_label=y_label,
        labels=labels,
        series=series,
        observation=observation,
        limitation=limitation,
    )


def _status_payload(
    title: str,
    subtitle: str,
    status: str,
    observation: str,
    limitation: str,
) -> FigurePayload:
    return FigurePayload(
        kind="status",
        title=title,
        subtitle=subtitle,
        x_label="Availability",
        y_label="Status",
        annotations=(status, observation),
        observation=observation,
        limitation=limitation,
    )


def _display_metric(snapshot: EvaluationSnapshot, name: str) -> str:
    metric = snapshot.metrics[name]
    if metric.availability_status != AVAILABLE:
        return metric.availability_status
    return f"{float(metric.value):.3f}"


def _numeric_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


COLORS = (
    "#1f4e79",
    "#4f81bd",
    "#70ad47",
    "#c55a11",
    "#8064a2",
    "#7f7f7f",
)


def _render_svg(payload: FigurePayload) -> str:
    width, height = 1200, 800
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<defs>",
        '<pattern id="stripe" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="8" stroke="#ffffff" stroke-opacity="0.45" stroke-width="2"/></pattern>',
        "</defs>",
        '<rect width="1200" height="800" fill="#ffffff"/>',
        f'<text x="60" y="58" font-family="Arial, sans-serif" font-size="30" font-weight="700" fill="#17365d">{escape(payload.title)}</text>',
        f'<text x="60" y="90" font-family="Arial, sans-serif" font-size="16" fill="#404040">{escape(payload.subtitle)}</text>',
    ]
    if payload.kind == "workflow":
        _svg_workflow(elements, payload)
    elif payload.kind == "matrix":
        _svg_matrix(elements, payload)
    elif payload.kind == "status":
        _svg_status(elements, payload)
    else:
        _svg_bars(elements, payload)
    elements.extend(
        [
            '<line x1="60" y1="720" x2="1140" y2="720" stroke="#bfbfbf"/>',
            f'<text x="60" y="748" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#595959">{escape(TECHNICAL_CAPTION)}</text>',
            f'<text x="60" y="776" font-family="Arial, sans-serif" font-size="12" fill="#7f6000">LIMITATION: {escape(payload.limitation[:155])}</text>',
            "</svg>",
        ]
    )
    return "\n".join(elements) + "\n"


def _svg_workflow(elements: list[str], payload: FigurePayload) -> None:
    y = 230
    box_w, box_h, gap = 180, 96, 28
    start = 40
    for index, label in enumerate(payload.labels):
        x = start + index * (box_w + gap)
        color = COLORS[index % len(COLORS)]
        elements.append(f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="10" fill="{color}"/>')
        elements.append(f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="10" fill="url(#stripe)"/>')
        lines = _wrap_label(label, 20)
        for line_index, line in enumerate(lines[:3]):
            elements.append(f'<text x="{x + box_w / 2}" y="{y + 38 + line_index * 20}" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#ffffff">{escape(line)}</text>')
        if index < len(payload.labels) - 1:
            x1 = x + box_w + 4
            x2 = x + box_w + gap - 4
            elements.append(f'<line x1="{x1}" y1="{y + box_h / 2}" x2="{x2}" y2="{y + box_h / 2}" stroke="#404040" stroke-width="3"/>')
            elements.append(f'<polygon points="{x2},{y + box_h / 2} {x2 - 10},{y + box_h / 2 - 6} {x2 - 10},{y + box_h / 2 + 6}" fill="#404040"/>')
    for index, annotation in enumerate(payload.annotations):
        elements.append(f'<text x="60" y="{410 + index * 34}" font-family="Arial, sans-serif" font-size="18" fill="#404040">• {escape(annotation)}</text>')


def _svg_bars(elements: list[str], payload: FigurePayload) -> None:
    left, top, right, bottom = 155, 150, 1125, 515
    series = payload.series or {}
    values = [value for items in series.values() for value in items if value is not None]
    if not values:
        _svg_status(elements, _status_payload(payload.title, payload.subtitle, NOT_AVAILABLE, "No governed values were supplied.", payload.limitation))
        return
    min_value = min(0.0, min(values))
    max_value = max(0.0, max(values))
    if max_value == min_value:
        max_value = min_value + 1.0
    padding = (max_value - min_value) * 0.12
    chart_min, chart_max = min_value - (padding if min_value < 0 else 0), max_value + padding
    zero_y = bottom - (0 - chart_min) / (chart_max - chart_min) * (bottom - top)
    elements.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#404040" stroke-width="2"/>')
    elements.append(f'<line x1="{left}" y1="{zero_y:.2f}" x2="{right}" y2="{zero_y:.2f}" stroke="#404040" stroke-width="2"/>')
    for tick in range(5):
        value = chart_min + (chart_max - chart_min) * tick / 4
        y = bottom - tick * (bottom - top) / 4
        elements.append(f'<line x1="{left}" y1="{y:.2f}" x2="{right}" y2="{y:.2f}" stroke="#d9e2f3"/>')
        elements.append(f'<text x="{left - 12}" y="{y + 5:.2f}" text-anchor="end" font-family="Arial, sans-serif" font-size="12" fill="#595959">{value:.2g}</text>')
    labels = payload.labels
    group_w = (right - left) / max(len(labels), 1)
    series_names = list(series)
    usable = group_w * 0.72
    bar_w = max(4.0, usable / max(len(series_names), 1))
    for label_index, label in enumerate(labels):
        center = left + group_w * (label_index + 0.5)
        for series_index, name in enumerate(series_names):
            value = series[name][label_index]
            x = center - usable / 2 + series_index * bar_w
            if value is None:
                elements.append(f'<text x="{x + bar_w / 2:.2f}" y="{zero_y - 8:.2f}" text-anchor="middle" font-family="Arial, sans-serif" font-size="10" fill="#a61c00">NA</text>')
                continue
            value_y = bottom - (value - chart_min) / (chart_max - chart_min) * (bottom - top)
            y = min(value_y, zero_y)
            h = max(abs(zero_y - value_y), 2.0)
            color = COLORS[series_index % len(COLORS)]
            elements.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w - 2:.2f}" height="{h:.2f}" fill="{color}"/>')
            elements.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w - 2:.2f}" height="{h:.2f}" fill="url(#stripe)"/>')
            stagger = (
                12 * (series_index % 2)
                if len(series_names) > 2 and bar_w < 45
                else 0
            )
            label_y = y - 5 - stagger if value >= 0 else y + h + 14 + stagger
            elements.append(f'<text x="{x + (bar_w - 2) / 2:.2f}" y="{label_y:.2f}" text-anchor="middle" font-family="Arial, sans-serif" font-size="10" fill="#262626">{value:.3g}</text>')
        max_chars = max(8, int(group_w / 7) - 1)
        for line_index, line in enumerate(
            _wrap_label_complete(label, max_chars, max_lines=4)
        ):
            elements.append(f'<text x="{center:.2f}" y="{bottom + 18 + line_index * 13}" text-anchor="middle" font-family="Arial, sans-serif" font-size="10" fill="#404040">{escape(line)}</text>')
    legend_x = 170
    for index, name in enumerate(series_names):
        x = legend_x + index * 220
        elements.append(f'<rect x="{x}" y="112" width="18" height="12" fill="{COLORS[index % len(COLORS)]}"/>')
        elements.append(f'<path d="M{x} 124 l18 -12" stroke="#ffffff" stroke-opacity="0.65"/>')
        elements.append(f'<text x="{x + 25}" y="123" font-family="Arial, sans-serif" font-size="12" fill="#404040">{escape(name)}</text>')
    elements.append(f'<text x="{(left + right) / 2}" y="690" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" fill="#404040">{escape(payload.x_label)}</text>')
    elements.append(f'<text x="35" y="{(top + bottom) / 2}" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" fill="#404040" transform="rotate(-90 35 {(top + bottom) / 2})">{escape(payload.y_label)}</text>')


def _svg_matrix(elements: list[str], payload: FigurePayload) -> None:
    left, top, size = 285, 145, 385
    rows, columns = len(payload.matrix_rows), len(payload.matrix_columns)
    if not rows or not columns:
        _svg_status(elements, _status_payload(payload.title, payload.subtitle, NOT_AVAILABLE, "No matrix values were supplied.", payload.limitation))
        return
    cell_w, cell_h = size / columns, size / rows
    maximum = max((value for row in payload.matrix for value in row), default=1.0) or 1.0
    for row_index, row in enumerate(payload.matrix):
        for column_index, value in enumerate(row):
            intensity = value / maximum
            blue = int(245 - 145 * intensity)
            color = f"rgb({blue},{blue + 5},{255})"
            x, y = left + column_index * cell_w, top + row_index * cell_h
            elements.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{cell_w:.2f}" height="{cell_h:.2f}" fill="{color}" stroke="#ffffff"/>')
            elements.append(f'<text x="{x + cell_w / 2:.2f}" y="{y + cell_h / 2 + 5:.2f}" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" font-weight="700" fill="#17365d">{value:g}</text>')
    abbreviations = _status_abbreviations(payload.matrix_columns)
    for index, label in enumerate(payload.matrix_columns):
        x = left + (index + 0.5) * cell_w
        elements.append(f'<text x="{x:.2f}" y="{top + size + 18}" text-anchor="middle" font-family="Arial, sans-serif" font-size="9" fill="#404040">{escape(abbreviations[label])}</text>')
    for index, label in enumerate(payload.matrix_rows):
        y = top + (index + 0.5) * cell_h + 4
        elements.append(f'<text x="{left - 12}" y="{y:.2f}" text-anchor="end" font-family="Arial, sans-serif" font-size="9" fill="#404040">{escape(abbreviations[label])}</text>')
    elements.append(f'<text x="{left + size / 2}" y="690" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" fill="#404040">{escape(payload.x_label)}</text>')
    elements.append(f'<text x="90" y="{top + size / 2}" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" fill="#404040" transform="rotate(-90 90 {top + size / 2})">{escape(payload.y_label)}</text>')
    elements.append(f'<text x="735" y="155" font-family="Arial, sans-serif" font-size="16" font-weight="700" fill="#17365d">Status key</text>')
    for index, label in enumerate(payload.matrix_columns):
        elements.append(f'<text x="735" y="{182 + index * 25}" font-family="Arial, sans-serif" font-size="12" fill="#404040">{escape(abbreviations[label])} = {escape(label.replace("_", " "))}</text>')
    elements.append(f'<text x="735" y="390" font-family="Arial, sans-serif" font-size="16" font-weight="700" fill="#17365d">Observation</text>')
    for index, line in enumerate(_wrap_label(payload.observation, 50)):
        elements.append(f'<text x="735" y="{418 + index * 21}" font-family="Arial, sans-serif" font-size="13" fill="#404040">{escape(line)}</text>')


def _svg_status(elements: list[str], payload: FigurePayload) -> None:
    elements.append('<rect x="170" y="170" width="860" height="350" rx="18" fill="#fff2cc" stroke="#bf9000" stroke-width="2"/>')
    status = payload.annotations[0] if payload.annotations else NOT_AVAILABLE
    elements.append(f'<text x="600" y="285" text-anchor="middle" font-family="Arial, sans-serif" font-size="38" font-weight="700" fill="#7f6000">{escape(status)}</text>')
    description = payload.annotations[1] if len(payload.annotations) > 1 else payload.observation
    for index, line in enumerate(_wrap_label(description, 78)):
        elements.append(f'<text x="600" y="{350 + index * 27}" text-anchor="middle" font-family="Arial, sans-serif" font-size="17" fill="#404040">{escape(line)}</text>')


def _short_label(value: str, length: int) -> str:
    normalized = str(value).replace("_", " ").upper()
    return normalized if len(normalized) <= length else normalized[: length - 2] + ".."


def _wrap_label(value: str, width: int) -> list[str]:
    words = str(value).replace("_", " ").split()
    lines: list[str] = []
    current = ""
    for word in words:
        proposed = f"{current} {word}".strip()
        if current and len(proposed) > width:
            lines.append(current)
            current = word
        else:
            current = proposed
    if current:
        lines.append(current)
    return lines or [""]


def _wrap_label_complete(
    value: str, width: int, *, max_lines: int
) -> list[str]:
    """Wrap every character without ellipsis so technical labels remain identifiable."""

    words: list[str] = []
    for word in str(value).replace("_", " ").upper().split():
        if len(word) <= width:
            words.append(word)
        else:
            words.extend(word[index : index + width] for index in range(0, len(word), width))
    lines: list[str] = []
    current = ""
    for word in words:
        proposed = f"{current} {word}".strip()
        if current and len(proposed) > width:
            lines.append(current)
            current = word
        else:
            current = proposed
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        # Preserve all content by compacting overflow into the last line. The
        # governed labels are sized so this branch is not used in required charts.
        overflow = " ".join(lines[max_lines - 1 :])
        lines = lines[: max_lines - 1] + [overflow]
    return lines or [""]


def _status_abbreviations(labels: Sequence[str]) -> dict[str, str]:
    governed = {
        "VALIDATED": "VAL",
        "VALIDATED_WITH_LIMITATIONS": "VAL+LIM",
        "REVIEW_REQUIRED": "REVIEW",
        "INSUFFICIENT_EVIDENCE": "INSUFF",
        "CONTRADICTED": "CONTRA",
        "NOT_APPLICABLE": "N/A",
        "ABSTAIN": "ABSTAIN",
    }
    if not set(labels) <= set(governed):
        raise ValueError("INVALID_STATUS_LABEL: no governed abbreviation exists")
    return {label: governed[label] for label in labels}


# A dependency-free raster renderer keeps report generation reproducible without
# introducing a plotting runtime into the clinical-validation package.
_FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "10010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "00110", "00110"),
    ":": ("00000", "00110", "00110", "00000", "00110", "00110", "00000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    ",": ("00000", "00000", "00000", "00000", "00110", "00110", "00100"),
    ";": ("00000", "00110", "00110", "00000", "00110", "00110", "00100"),
    "'": ("00110", "00110", "00100", "00000", "00000", "00000", "00000"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    "%": ("11001", "11010", "00100", "01000", "10110", "00110", "00000"),
    "?": ("01110", "10001", "00001", "00010", "00100", "00000", "00100"),
    " ": ("00000",) * 7,
}


class _Canvas:
    def __init__(self, width: int = 1200, height: int = 800):
        self.width = width
        self.height = height
        self.pixels = bytearray([255, 255, 255] * width * height)

    def rect(self, x: int, y: int, width: int, height: int, color: tuple[int, int, int], *, stripe: bool = False) -> None:
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.width, x + width), min(self.height, y + height)
        for py in range(y0, y1):
            for px in range(x0, x1):
                actual = color
                if stripe and (px + py) % 12 < 2:
                    actual = tuple(min(255, channel + 65) for channel in color)
                self.pixel(px, py, actual)

    def line(self, x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int], width: int = 1) -> None:
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        error = dx + dy
        while True:
            self.rect(x0 - width // 2, y0 - width // 2, width, width, color)
            if x0 == x1 and y0 == y1:
                break
            twice = 2 * error
            if twice >= dy:
                error += dy
                x0 += sx
            if twice <= dx:
                error += dx
                y0 += sy

    def pixel(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            index = (y * self.width + x) * 3
            self.pixels[index : index + 3] = bytes(color)

    def text(self, x: int, y: int, value: str, color: tuple[int, int, int] = (40, 40, 40), scale: int = 2, *, max_chars: int | None = None) -> None:
        normalized = str(value).upper()
        if max_chars is not None:
            normalized = normalized[:max_chars]
        cursor = x
        for character in normalized:
            glyph = _FONT.get(character, _FONT["?"])
            for row_index, row in enumerate(glyph):
                for column_index, bit in enumerate(row):
                    if bit == "1":
                        self.rect(cursor + column_index * scale, y + row_index * scale, scale, scale, color)
            cursor += 6 * scale

    def png(self) -> bytes:
        rows = b"".join(
            b"\x00" + bytes(self.pixels[y * self.width * 3 : (y + 1) * self.width * 3])
            for y in range(self.height)
        )
        signature = b"\x89PNG\r\n\x1a\n"
        ihdr = struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)
        return signature + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", zlib.compress(rows, 9)) + _png_chunk(b"IEND", b"")


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)


def _hex_color(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]


def _render_png(payload: FigurePayload) -> bytes:
    canvas = _Canvas()
    navy, gray = (23, 54, 93), (64, 64, 64)
    title_scale = 3 if len(payload.title) > 44 else 4
    canvas.text(55, 35, payload.title, navy, title_scale, max_chars=58)
    canvas.text(55, 82, payload.subtitle, gray, 2, max_chars=86)
    if payload.kind == "workflow":
        _png_workflow(canvas, payload)
    elif payload.kind == "matrix":
        _png_matrix(canvas, payload)
    elif payload.kind == "status":
        _png_status(canvas, payload)
    else:
        _png_bars(canvas, payload)
    canvas.line(55, 720, 1145, 720, (190, 190, 190))
    canvas.text(55, 739, TECHNICAL_CAPTION, (89, 89, 89), 2, max_chars=90)
    canvas.text(55, 770, "LIMITATION: " + payload.limitation, (127, 96, 0), 1, max_chars=170)
    return canvas.png()


def _png_workflow(canvas: _Canvas, payload: FigurePayload) -> None:
    box_w, box_h, gap, start, y = 180, 100, 28, 40, 230
    for index, label in enumerate(payload.labels):
        x = start + index * (box_w + gap)
        canvas.rect(x, y, box_w, box_h, _hex_color(COLORS[index % len(COLORS)]), stripe=True)
        for line_index, line in enumerate(
            _wrap_label_complete(label, 13, max_lines=4)
        ):
            canvas.text(
                x + 12,
                y + 15 + line_index * 20,
                line,
                (255, 255, 255),
                2,
                max_chars=13,
            )
        if index < len(payload.labels) - 1:
            canvas.line(x + box_w + 3, y + box_h // 2, x + box_w + gap - 4, y + box_h // 2, (64, 64, 64), 3)
    for index, annotation in enumerate(payload.annotations):
        canvas.text(65, 410 + index * 35, "- " + annotation, (64, 64, 64), 2, max_chars=84)


def _png_bars(canvas: _Canvas, payload: FigurePayload) -> None:
    series = payload.series or {}
    values = [value for items in series.values() for value in items if value is not None]
    if not values:
        _png_status(canvas, _status_payload(payload.title, payload.subtitle, NOT_AVAILABLE, "NO GOVERNED VALUES WERE SUPPLIED", payload.limitation))
        return
    left, top, right, bottom = 145, 155, 1130, 505
    min_value, max_value = min(0.0, min(values)), max(0.0, max(values))
    if max_value == min_value:
        max_value = min_value + 1.0
    padding = (max_value - min_value) * 0.12
    chart_min = min_value - (padding if min_value < 0 else 0)
    chart_max = max_value + padding
    zero_y = int(bottom - (0 - chart_min) / (chart_max - chart_min) * (bottom - top))
    for tick in range(5):
        y = int(bottom - tick * (bottom - top) / 4)
        canvas.line(left, y, right, y, (220, 228, 240))
        value = chart_min + (chart_max - chart_min) * tick / 4
        canvas.text(80, y - 6, f"{value:.2G}", (89, 89, 89), 1, max_chars=8)
    canvas.line(left, top, left, bottom, (64, 64, 64), 2)
    canvas.line(left, zero_y, right, zero_y, (64, 64, 64), 2)
    labels, names = payload.labels, list(series)
    group_w = (right - left) / max(len(labels), 1)
    usable = group_w * 0.72
    bar_w = max(3, int(usable / max(len(names), 1)))
    for label_index, label in enumerate(labels):
        center = int(left + group_w * (label_index + 0.5))
        for series_index, name in enumerate(names):
            value = series[name][label_index]
            x = int(center - usable / 2 + series_index * bar_w)
            if value is None:
                canvas.text(x, zero_y - 15, "NA", (166, 28, 0), 1)
                continue
            value_y = int(bottom - (value - chart_min) / (chart_max - chart_min) * (bottom - top))
            y = min(value_y, zero_y)
            height = max(abs(zero_y - value_y), 2)
            canvas.rect(x, y, max(bar_w - 2, 2), height, _hex_color(COLORS[series_index % len(COLORS)]), stripe=True)
            label = f"{value:.2G}"
            stagger = (
                12 * (series_index % 2)
                if len(names) > 2 and bar_w < 45
                else 0
            )
            label_x = x + max(0, (bar_w - 2 - len(label) * 6) // 2)
            canvas.text(
                label_x,
                max(top, y - 13 - stagger),
                label,
                (38, 38, 38),
                1,
                max_chars=7,
            )
        max_chars = max(8, int(group_w / 6) - 1)
        lines = _wrap_label_complete(label, max_chars, max_lines=4)
        for line_index, line in enumerate(lines):
            text_width = len(line) * 6
            canvas.text(
                max(left, center - text_width // 2),
                bottom + 14 + line_index * 13,
                line,
                (64, 64, 64),
                1,
                max_chars=max_chars,
            )
    for index, name in enumerate(names):
        x = 160 + index * 235
        canvas.rect(x, 120, 18, 12, _hex_color(COLORS[index % len(COLORS)]), stripe=True)
        canvas.text(x + 26, 120, name, (64, 64, 64), 1, max_chars=25)
    canvas.text(430, 682, payload.x_label, (64, 64, 64), 2, max_chars=52)
    canvas.text(20, 105, "Y: " + payload.y_label, (64, 64, 64), 1, max_chars=42)


def _png_matrix(canvas: _Canvas, payload: FigurePayload) -> None:
    left, top, size = 285, 150, 385
    rows, columns = len(payload.matrix_rows), len(payload.matrix_columns)
    if not rows or not columns:
        _png_status(canvas, _status_payload(payload.title, payload.subtitle, NOT_AVAILABLE, "NO MATRIX VALUES WERE SUPPLIED", payload.limitation))
        return
    cell_w, cell_h = size // columns, size // rows
    maximum = max((value for row in payload.matrix for value in row), default=1.0) or 1.0
    for row_index, row in enumerate(payload.matrix):
        for column_index, value in enumerate(row):
            intensity = value / maximum
            shade = int(245 - 145 * intensity)
            x, y = left + column_index * cell_w, top + row_index * cell_h
            canvas.rect(x, y, cell_w - 1, cell_h - 1, (shade, min(255, shade + 5), 255))
            canvas.text(x + cell_w // 2 - 6, y + cell_h // 2 - 6, f"{value:G}", (23, 54, 93), 2, max_chars=3)
    abbreviations = _status_abbreviations(payload.matrix_columns)
    for index, label in enumerate(payload.matrix_rows):
        canvas.text(205, top + index * cell_h + cell_h // 2 - 4, abbreviations[label], (64, 64, 64), 1, max_chars=8)
    for index, label in enumerate(payload.matrix_columns):
        abbreviation = abbreviations[label]
        canvas.text(
            left + index * cell_w + max(0, (cell_w - len(abbreviation) * 6) // 2),
            top + size + 13,
            abbreviation,
            (64, 64, 64),
            1,
            max_chars=8,
        )
    canvas.text(350, 682, payload.x_label, (64, 64, 64), 2, max_chars=40)
    canvas.text(145, 125, payload.y_label, (64, 64, 64), 1, max_chars=34)
    canvas.text(720, 145, "STATUS KEY", (23, 54, 93), 3)
    for index, label in enumerate(payload.matrix_columns):
        canvas.text(
            720,
            185 + index * 25,
            f"{abbreviations[label]} = {label.replace('_', ' ')}",
            (64, 64, 64),
            1,
            max_chars=55,
        )
    canvas.text(720, 390, "OBSERVATION", (23, 54, 93), 3)
    for index, line in enumerate(_wrap_label_complete(payload.observation, 48, max_lines=8)):
        canvas.text(720, 435 + index * 20, line, (64, 64, 64), 1, max_chars=50)


def _png_status(canvas: _Canvas, payload: FigurePayload) -> None:
    canvas.rect(170, 175, 860, 350, (255, 242, 204), stripe=True)
    status = payload.annotations[0] if payload.annotations else NOT_AVAILABLE
    canvas.text(330, 260, status, (127, 96, 0), 5, max_chars=28)
    description = payload.annotations[1] if len(payload.annotations) > 1 else payload.observation
    for index, line in enumerate(_wrap_label(description, 72)[:7]):
        canvas.text(230, 365 + index * 22, line, (64, 64, 64), 2, max_chars=74)
