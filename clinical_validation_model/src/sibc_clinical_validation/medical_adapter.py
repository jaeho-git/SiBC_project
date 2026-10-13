from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from .config import PrototypeConfig


REQUIRED_MEDICAL_ARTIFACTS = (
    "approved_schema_columns.csv",
    "latest_actual_pseudonymized.parquet",
    "temporal_cohort_pseudonymized.parquet",
    "wearable_summary_pseudonymized.parquet",
)
RUN_ID_PATTERN = re.compile(r"^release_[0-9]{8}_[0-9]{6}_[0-9a-f]{7,12}$")


class SourceDataMutationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ArtifactFingerprint:
    filename: str
    sha256: str
    size_bytes: int
    modified_time_ns: int
    row_count: int
    columns: tuple[str, ...]


def _sha256(path: Path) -> str:
    # Do not import executable code from the evidence-producing sibling project.
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def latest_medical_artifact_dir(config: PrototypeConfig) -> tuple[str, Path]:
    pointer = (
        config.medical_checkup_root
        / "01_Results"
        / config.artifact_source_environment
        / "latest_run.json"
    )
    raw = json.loads(pointer.read_text(encoding="utf-8"))
    run_id = str(raw.get("run_id", ""))
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("Managed medical latest_run.json contains an invalid run_id")
    artifact_dir = (
        config.medical_checkup_root
        / "00_Data"
        / config.artifact_source_environment
        / run_id
    ).resolve()
    expected_parent = (
        config.medical_checkup_root
        / "00_Data"
        / config.artifact_source_environment
    ).resolve()
    if artifact_dir.parent != expected_parent:
        raise ValueError("Artifact directory escapes its managed environment")
    return run_id, artifact_dir


def _csv_metadata(path: Path) -> tuple[int, tuple[str, ...]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream)
        header = tuple(next(reader, []))
        rows = sum(1 for _ in reader)
    return rows, header


def fingerprint_artifact(path: Path) -> ArtifactFingerprint:
    stat = path.stat()
    if path.suffix == ".parquet":
        parquet = pq.ParquetFile(path)
        rows = parquet.metadata.num_rows
        columns = tuple(parquet.schema_arrow.names)
    elif path.suffix == ".csv":
        rows, columns = _csv_metadata(path)
    else:
        raise ValueError(f"Unsupported managed artifact: {path.name}")
    return ArtifactFingerprint(
        filename=path.name,
        sha256=_sha256(path),
        size_bytes=stat.st_size,
        modified_time_ns=stat.st_mtime_ns,
        row_count=int(rows),
        columns=columns,
    )


def snapshot_medical_artifacts(
    config: PrototypeConfig,
) -> tuple[str, Path, dict[str, ArtifactFingerprint]]:
    run_id, root = latest_medical_artifact_dir(config)
    fingerprints: dict[str, ArtifactFingerprint] = {}
    for filename in REQUIRED_MEDICAL_ARTIFACTS:
        path = root / filename
        if path.is_symlink() or not path.is_file() or path.resolve().parent != root:
            raise FileNotFoundError(path)
        fingerprints[filename] = fingerprint_artifact(path)
    _verify_upstream_register(config, run_id, fingerprints)
    return run_id, root, fingerprints


def _managed_pointer_path(config: PrototypeConfig, relative: str) -> Path:
    raw_candidate = config.medical_checkup_root / relative
    candidate = raw_candidate.resolve()
    root = config.medical_checkup_root.resolve()
    if root not in candidate.parents or raw_candidate.is_symlink() or not candidate.is_file():
        raise ValueError("Medical latest-run pointer references an unmanaged file")
    return candidate


def _verify_upstream_register(
    config: PrototypeConfig,
    run_id: str,
    fingerprints: dict[str, ArtifactFingerprint],
) -> None:
    pointer_path = (
        config.medical_checkup_root
        / "01_Results"
        / config.artifact_source_environment
        / "latest_run.json"
    )
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    manifest_path = _managed_pointer_path(config, str(pointer.get("manifest", "")))
    checksums_path = _managed_pointer_path(config, str(pointer.get("checksums", "")))
    if run_id not in manifest_path.parts or run_id not in checksums_path.parts:
        raise ValueError("Upstream manifest/checksum run does not match latest run")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("run_id") != run_id:
        raise ValueError("Upstream reproducibility manifest run_id mismatch")
    if manifest.get("data_env") != config.artifact_source_environment:
        raise ValueError("Upstream reproducibility manifest environment mismatch")
    registered: dict[str, str] = {}
    for line in checksums_path.read_text(encoding="utf-8").splitlines():
        if "  " not in line:
            raise ValueError("Invalid upstream checksum register")
        digest, relative = line.split("  ", 1)
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Invalid upstream checksum digest")
        registered[relative] = digest
    for filename, fingerprint in fingerprints.items():
        relative = (
            f"00_Data/{config.artifact_source_environment}/{run_id}/{filename}"
        )
        if registered.get(relative) != fingerprint.sha256:
            raise ValueError(f"Upstream checksum mismatch for managed artifact: {filename}")


def assert_source_unchanged(
    before: dict[str, ArtifactFingerprint],
    after: dict[str, ArtifactFingerprint],
) -> None:
    if set(before) != set(after):
        raise SourceDataMutationError("BLOCKED_BY_SOURCE_DATA_MUTATION: file set changed")
    changed = [name for name in before if before[name] != after[name]]
    if changed:
        raise SourceDataMutationError(
            "BLOCKED_BY_SOURCE_DATA_MUTATION: " + ", ".join(sorted(changed))
        )


def safe_snapshot_manifest(
    run_id: str,
    root: Path,
    fingerprints: dict[str, ArtifactFingerprint],
) -> dict[str, Any]:
    return {
        "source_model": "medical_checkup_model",
        "source_run_id": run_id,
        "source_directory_name": root.name,
        "access_mode": "OFFLINE_READ_ONLY_METADATA_AND_PSEUDONYMIZED_ARTIFACT_REFERENCE",
        "source_data_modified": False,
        "upstream_checksum_register_verified": True,
        "upstream_reproducibility_manifest_verified": True,
        "files": {
            name: asdict(fingerprint) for name, fingerprint in sorted(fingerprints.items())
        },
        "artifact_limitations": [
            "actual_exam_date_is_date_only",
            "source_record_id_and_unit_registry_unavailable",
            "wearable_nonwear_device_sync_app_algorithm_timezone_manual_duplicate_metadata_not_assessable",
            "medical_checkup_prediction_and_risk_fields_are_not_clinical_evidence",
        ],
    }
