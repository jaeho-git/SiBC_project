from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from .config import FIXTURE_ROOT
from .models import (
    CriterionAssessment,
    DiagnosisCandidate,
    EvidenceLink,
    parse_bool,
)


REQUIRED_FILES = {
    "candidates": "diagnosis_candidates.parquet",
    "links": "diagnosis_candidate_evidence_links.parquet",
    "criteria": "diagnosis_candidate_criteria.parquet",
    "conflicts": "diagnosis_candidate_conflicts.parquet",
    "evidence": "synthetic_evidence_items.parquet",
    "scenarios": "scenario_manifest.csv",
    "expected": "expected_validation_results.csv",
    "generation_manifest": "synthetic_generation_manifest.json",
}


class FixtureContractError(ValueError):
    pass


def _read_frame(path: Path) -> pd.DataFrame:
    return (
        pd.read_parquet(path)
        if path.suffix == ".parquet"
        else pd.read_csv(path, keep_default_na=False)
    )


def _assert_synthetic(frame: pd.DataFrame, name: str) -> None:
    common = {
        "data_origin",
        "is_synthetic",
        "generator_version",
        "scenario_id",
        "source_rule_ids",
        "source_versions",
        "generation_timestamp",
        "expected_validation_result",
        "intended_test_purpose",
    }
    missing = common - set(frame.columns)
    if missing:
        raise FixtureContractError(
            f"{name} missing synthetic provenance: {', '.join(sorted(missing))}"
        )
    try:
        synthetic_flags = frame["is_synthetic"].map(parse_bool)
    except ValueError as error:
        raise FixtureContractError(f"{name} has an invalid synthetic flag") from error
    if not synthetic_flags.all():
        raise FixtureContractError(f"{name} contains non-synthetic rows")


def load_fixture_frames(root: Path = FIXTURE_ROOT) -> dict[str, pd.DataFrame]:
    missing = [filename for filename in REQUIRED_FILES.values() if not (root / filename).is_file()]
    if missing:
        raise FixtureContractError(f"Missing fixture files: {', '.join(missing)}")
    frames = {
        name: _read_frame(root / filename)
        for name, filename in REQUIRED_FILES.items()
        if name != "generation_manifest"
    }
    for name, frame in frames.items():
        _assert_synthetic(frame, name)
    return frames


def materialize_fixture_contract(
    frames: dict[str, pd.DataFrame],
) -> tuple[
    list[DiagnosisCandidate],
    dict[str, list[CriterionAssessment]],
    dict[str, list[EvidenceLink]],
]:
    # Expected/oracle columns deliberately never enter any domain object.
    candidates = [
        DiagnosisCandidate.from_mapping(row)
        for row in frames["candidates"].to_dict(orient="records")
    ]
    criteria_by_candidate: dict[str, list[CriterionAssessment]] = defaultdict(list)
    for row in frames["criteria"].to_dict(orient="records"):
        item = CriterionAssessment.from_mapping(row)
        criteria_by_candidate[item.diagnosis_candidate_id].append(item)

    evidence_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in frames["evidence"].to_dict(orient="records"):
        key = (str(row["diagnosis_candidate_id"]), str(row["evidence_id"]))
        if key in evidence_lookup:
            raise FixtureContractError(f"Duplicate evidence item: {key}")
        evidence_lookup[key] = row

    evidence_by_candidate: dict[str, list[EvidenceLink]] = defaultdict(list)
    for row in frames["links"].to_dict(orient="records"):
        key = (str(row["diagnosis_candidate_id"]), str(row["evidence_id"]))
        source = evidence_lookup.get(key)
        if source is None:
            raise FixtureContractError(f"Evidence link has no evidence item: {key}")
        if str(row["feature_id"]) != str(source["feature_id"]):
            raise FixtureContractError(f"Link/evidence feature mismatch: {key}")
        merged = {
            **source,
            "criterion_id": row["criterion_id"],
            "feature_id": row["feature_id"],
        }
        evidence_by_candidate[key[0]].append(EvidenceLink.from_mapping(merged))

    candidate_ids = {item.diagnosis_candidate_id for item in candidates}
    extra_criteria = set(criteria_by_candidate) - candidate_ids
    extra_evidence = set(evidence_by_candidate) - candidate_ids
    if extra_criteria or extra_evidence:
        raise FixtureContractError("Orphan criterion or evidence rows")
    return candidates, dict(criteria_by_candidate), dict(evidence_by_candidate)
