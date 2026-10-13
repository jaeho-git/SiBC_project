from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from sibc_clinical_validation import env as env_module
from sibc_clinical_validation.cli import build_parser, main
from sibc_clinical_validation.config import (
    ACTIVE_ENVIRONMENT,
    ALLOWED_DATA_ENVS,
    ENV_FILE_MAP,
    load_config,
)
from sibc_clinical_validation.db import ReadOnlyDatabase
from sibc_clinical_validation.env import (
    ReleaseAccessError,
    load_release_db_environment,
    safe_environment_preflight,
)
from sibc_clinical_validation.queries import release_query_bundle
from sibc_clinical_validation.sql_guard import SQLGuardError, validate_read_only_sql


def test_release_is_the_only_enabled_environment_and_default():
    config = load_config()
    assert ACTIVE_ENVIRONMENT == "release"
    assert ALLOWED_DATA_ENVS == ("release",)
    assert set(ENV_FILE_MAP) == {"release"}
    assert config.data_env == "release"
    assert config.execution_mode == "artifact"
    assert config.release_execution_mode == "release_artifact"
    assert config.artifact_source_environment == "release"


@pytest.mark.parametrize("disabled_environment", ["dev", "stg"])
def test_dev_and_stg_execution_are_rejected_without_fallback(disabled_environment):
    with pytest.raises(ValueError, match="fallback is prohibited"):
        load_config(disabled_environment, "artifact")
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            ["run", "--data-env", disabled_environment, "--mode", "artifact"]
        )


def test_release_environment_preflight_is_redacted_and_never_reads_fallbacks():
    summary = safe_environment_preflight(load_config("release", "db"))
    assert summary == {
        "status": "RELEASE_ACCESS_VERIFIED",
        "data_env": "release",
        "env_file": ".env.release",
        "APP_ENV": "release",
        "SIBC_DATA_ENV": "release",
        "db_credentials": "PRESENT_REDACTED",
        "secret_values_returned": "NO",
        "dev_env_read": "NO",
        "stg_env_read": "NO",
        "environment_fallback": "DISABLED",
    }


def test_missing_managed_release_env_is_blocked_without_process_or_env_fallback(
    tmp_path: Path, monkeypatch
):
    missing = tmp_path / ".env.release"
    monkeypatch.setitem(env_module.ENV_FILE_MAP, "release", missing)
    config = replace(load_config("release", "db"), env_file=missing)
    with pytest.raises(ReleaseAccessError) as caught:
        safe_environment_preflight(config)
    assert caught.value.status == "BLOCKED_BY_RELEASE_ACCESS"
    assert caught.value.reason_code == "ENV_FILE_UNAVAILABLE"


def test_release_env_identity_mismatch_is_blocked_without_echoing_values(
    tmp_path: Path, monkeypatch
):
    managed = tmp_path / ".env.release"
    managed.write_text(
        "\n".join(
            [
                "APP_ENV=dev",
                "SIBC_DATA_ENV=release",
                "DB_HOST=example.invalid",
                "DB_NAME=example",
                "DB_PORT=5432",
                "DB_USER=reader",
                "DB_PASSWORD=canary-not-returned",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setitem(env_module.ENV_FILE_MAP, "release", managed)
    config = replace(load_config("release", "db"), env_file=managed)
    with pytest.raises(ReleaseAccessError) as caught:
        load_release_db_environment(config)
    assert caught.value.reason_code == "APP_ENV_IDENTITY_MISMATCH"
    assert "canary" not in str(caught.value)


def test_cli_reports_safe_release_block_and_nonzero(monkeypatch, capsys):
    def blocked(_config):
        raise ReleaseAccessError("ENV_FILE_UNAVAILABLE")

    monkeypatch.setattr(
        "sibc_clinical_validation.cli.safe_environment_preflight", blocked
    )
    assert main(["run", "--mode", "artifact"]) == 1
    output = capsys.readouterr().out
    assert '"status": "BLOCKED_BY_RELEASE_ACCESS"' in output
    assert '"environment": "release"' in output
    assert '"environment_fallback": "DISABLED"' in output


class _FakeCursor:
    def __init__(self):
        self.last_sql = ""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, sql, _params=None):
        self.last_sql = sql

    def fetchone(self):
        if self.last_sql == "SHOW transaction_read_only":
            return ("on",)
        if self.last_sql == "SHOW transaction_isolation":
            return ("repeatable read",)
        if self.last_sql == "SHOW timezone":
            return ("Asia/Seoul",)
        return ("snapshot", "0/0000000")


class _FakeConnection:
    def __init__(self):
        self.session_args = None
        self.closed = False
        self.rolled_back = False

    def set_session(self, **kwargs):
        self.session_args = kwargs

    def cursor(self):
        return _FakeCursor()

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_release_db_scaffold_forces_tls_read_only_repeatable_read(monkeypatch):
    config = load_config("release", "db")
    env = load_release_db_environment(config)
    fake_connection = _FakeConnection()
    connect_kwargs = {}

    def fake_connect(**kwargs):
        connect_kwargs.update(kwargs)
        return fake_connection

    monkeypatch.setattr("sibc_clinical_validation.db.psycopg2.connect", fake_connect)
    with ReadOnlyDatabase(config, env) as database:
        assert database.snapshot_id == "snapshot"
    assert connect_kwargs["application_name"] == (
        "sibc_clinical_validation_release_readonly"
    )
    assert connect_kwargs["sslmode"] == "verify-full"
    assert "default_transaction_read_only=on" in connect_kwargs["options"]
    assert fake_connection.session_args == {
        "readonly": True,
        "autocommit": False,
        "isolation_level": "REPEATABLE READ",
    }
    assert fake_connection.rolled_back is True
    assert fake_connection.closed is True


def test_release_query_bundle_is_hash_pinned_and_db_mode_only():
    queries = release_query_bundle(load_config("release", "db"))
    assert len(queries) == 4
    assert all(len(query.sha256) == 64 for query in queries)
    with pytest.raises(RuntimeError, match="BLOCKED_BY_RELEASE_ACCESS"):
        release_query_bundle(load_config("release", "fixture"))


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM discovery.disc_lifelog_user_step",
        "SELECT s.* FROM discovery.disc_lifelog_user_step AS s",
        "SELECT s.step_cnt INTO temp_x FROM discovery.disc_lifelog_user_step AS s",
        "SELECT s.step_cnt FROM discovery.disc_lifelog_user_step AS s FOR UPDATE",
        "SELECT s.step_cnt FROM discovery.disc_lifelog_user_step AS s; \\gexec",
    ],
)
def test_release_sql_guard_blocks_bulk_projection_and_side_effect_clauses(sql):
    with pytest.raises(SQLGuardError):
        validate_read_only_sql(sql)
