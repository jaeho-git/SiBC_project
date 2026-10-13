from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import psycopg2
import pandas as pd
import pytest

from sibc_clinical_validation.cli import build_parser, main
from sibc_clinical_validation.config import load_config
from sibc_clinical_validation.env import safe_environment_preflight
from sibc_clinical_validation.medical_adapter import (
    assert_source_unchanged,
    safe_snapshot_manifest,
    snapshot_medical_artifacts,
)
from sibc_clinical_validation.pipeline import PrototypePipeline, _source_hash
from sibc_clinical_validation.reporting import verify_checksums, write_checksums
from sibc_clinical_validation.security import scan_output_tree, scan_text
from sibc_clinical_validation.sql_guard import (
    MANAGED_QUERY_FILES,
    SQLGuardError,
    load_managed_query,
    validate_read_only_sql,
)


@pytest.mark.parametrize(
    ("text", "finding"),
    [
        ("DB_PASSWORD=not-a-real-secret", "SECRET_ASSIGNMENT"),
        ("postgresql://user:pass@db.example/x", "CONNECTION_STRING"),
        ("person@example.com", "EMAIL_ADDRESS"),
        ("010-1234-5678", "KOREAN_MOBILE"),
        ("900101-1234567", "RESIDENT_REGISTRATION_NUMBER"),
        ("-----BEGIN PRIVATE KEY-----", "PRIVATE_KEY"),
        ("AKIAABCDEFGHIJKLMNOP", "AWS_ACCESS_KEY"),
        ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signature", "JWT"),
        ("Authorization: Bearer canary-token", "BEARER_TOKEN"),
        ("user_id=raw-subject-123", "RAW_IDENTIFIER_ASSIGNMENT"),
        ("DB_HOST=db.internal", "SECRET_ASSIGNMENT"),
    ],
)
def test_security_scan_detects_canaries_without_returning_values(text, finding):
    assert finding in scan_text(text)


def test_output_tree_scan_reports_only_file_and_finding_type(tmp_path: Path):
    path = tmp_path / "unsafe.json"
    path.write_text('{"DB_PASSWORD":"canary"}', encoding="utf-8")
    report = scan_output_tree(tmp_path)
    assert report["status"] == "FAILED_SECRET_OR_IDENTIFIER_SCAN"
    assert report["finding_count"] == 1
    assert report["findings"] == [
        {"file": "unsafe.json", "finding_type": "SECRET_ASSIGNMENT"}
    ]
    assert "canary" not in str(report)


def test_output_tree_scan_inspects_parquet_schema_and_string_values(tmp_path: Path):
    path = tmp_path / "unsafe.parquet"
    pd.DataFrame(
        {"user_id": ["raw-subject"], "note": ["Authorization: Bearer canary"]}
    ).to_parquet(path, index=False)
    report = scan_output_tree(tmp_path)
    types = {item["finding_type"] for item in report["findings"]}
    assert "FORBIDDEN_OUTPUT_FIELD" in types
    assert "BEARER_TOKEN" in types
    assert "raw-subject" not in str(report)


def test_output_tree_scan_inspects_svg_and_docx_xml(tmp_path: Path):
    (tmp_path / "unsafe.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text>person@example.com</text></svg>',
        encoding="utf-8",
    )
    with ZipFile(tmp_path / "unsafe.docx", "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="urn:test"><w:t>DB_PASSWORD=canary</w:t></w:document>',
        )
    report = scan_output_tree(tmp_path)
    findings = {(item["file"], item["finding_type"]) for item in report["findings"]}
    assert ("unsafe.svg", "EMAIL_ADDRESS") in findings
    assert ("unsafe.docx", "SECRET_ASSIGNMENT") in findings
    assert "canary" not in str(report)


@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM users",
        'SELECT * FROM "public"."users"',
        "SELECT pg_sleep(0)",
        "UPDATE discovery.disc_lifelog_user_step SET step_cnt = 1",
        "SELECT * FROM public.users",
        "SELECT dblink_exec('x', 'DELETE FROM y') FROM discovery.disc_lifelog_user_step",
        "SELECT pg_read_file('/etc/passwd') FROM discovery.disc_lifelog_user_step",
        "SELECT set_config('x', 'y', false) FROM discovery.disc_lifelog_user_step",
        "SELECT lo_unlink(1) FROM discovery.disc_lifelog_user_step",
    ],
)
def test_sql_guard_blocks_qualification_function_write_and_allowlist_bypasses(query):
    with pytest.raises(SQLGuardError):
        validate_read_only_sql(query)


def test_sql_guard_does_not_treat_a_string_literal_as_a_write():
    relations = validate_read_only_sql(
        "SELECT 'delete' AS harmless FROM discovery.disc_lifelog_user_step"
    )
    assert relations == ("discovery.disc_lifelog_user_step",)


def test_every_managed_sql_file_passes_and_is_hash_pinned():
    for name in MANAGED_QUERY_FILES:
        query = load_managed_query(name)
        assert len(query.sha256) == 64
        assert query.path.is_file()


def test_selected_environment_summary_is_redacted_and_single_environment():
    config = load_config("release", "db")
    summary = safe_environment_preflight(config)
    assert summary["data_env"] == "release"
    assert summary["env_file"] == ".env.release"
    assert summary["db_credentials"] == "PRESENT_REDACTED"
    assert summary["secret_values_returned"] == "NO"
    assert "DB_PASSWORD" not in summary
    assert "DB_HOST" not in summary


def test_db_mode_returns_block_without_attempting_connection(monkeypatch):
    attempted = False

    def forbidden_connect(*args, **kwargs):
        nonlocal attempted
        attempted = True
        raise AssertionError("DB connection must not be attempted")

    monkeypatch.setattr(psycopg2, "connect", forbidden_connect)
    result = PrototypePipeline("release", "db").run()
    assert result["status"] == "BLOCKED_BY_DB_ACCESS"
    assert result["connection_attempted"] is False
    assert attempted is False
    assert main(["run", "--data-env", "release", "--mode", "db"]) == 1
    assert attempted is False


def test_cli_defaults_to_release_artifact():
    args = build_parser().parse_args(["preflight"])
    assert args.data_env == "release"
    assert args.mode == "artifact"


def test_medical_artifact_register_and_fingerprints_are_stable():
    config = load_config("release", "artifact")
    run_id, root, before = snapshot_medical_artifacts(config)
    run_id_after, root_after, after = snapshot_medical_artifacts(config)
    assert run_id == run_id_after
    assert root == root_after
    assert_source_unchanged(before, after)
    manifest = safe_snapshot_manifest(run_id, root, before)
    assert manifest["source_data_modified"] is False
    assert manifest["upstream_checksum_register_verified"] is True
    assert manifest["upstream_reproducibility_manifest_verified"] is True
    assert {item.row_count for item in before.values()} >= {290, 393}


def test_source_hash_ignores_install_generated_egg_info(tmp_path: Path):
    for directory in ("src", "configs", "rules", "tests", "scripts"):
        (tmp_path / directory).mkdir()
    (tmp_path / "src" / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    baseline = _source_hash(tmp_path)
    egg = tmp_path / "src" / "package.egg-info"
    egg.mkdir()
    (egg / "PKG-INFO").write_text("generated", encoding="utf-8")
    assert _source_hash(tmp_path) == baseline


def test_checksum_register_is_verified_and_rejects_tampering(tmp_path: Path):
    run_root = tmp_path / "release_technical_run"
    artifacts = run_root / "artifacts"
    artifacts.mkdir(parents=True)
    output = run_root / "outputs" / "summary.csv"
    output.parent.mkdir()
    output.write_text("status\nPASSED\n", encoding="utf-8")
    register = artifacts / "checksums.sha256"
    assert write_checksums(run_root, register) == 1
    assert verify_checksums(run_root, register) == 1
    output.write_text("status\nTAMPERED\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Checksum verification failed"):
        verify_checksums(run_root, register)
