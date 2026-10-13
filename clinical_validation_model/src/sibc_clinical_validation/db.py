from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any, Iterator, Sequence

import psycopg2
from psycopg2.extensions import connection

from .config import ACTIVE_ENVIRONMENT, PrototypeConfig
from .env import validate_release_environment_identity
from .sql_guard import ManagedQuery, assert_query_unchanged


class ReadOnlyDatabase:
    """Explicit DB-mode scaffold with defense-in-depth read-only controls."""

    def __init__(self, config: PrototypeConfig, env: dict[str, str]):
        if config.data_env != ACTIVE_ENVIRONMENT:
            raise RuntimeError("BLOCKED_BY_RELEASE_ACCESS")
        validate_release_environment_identity(env)
        self.config = config
        self.env = env
        self.connection: connection | None = None
        self.snapshot_id: str | None = None
        self.wal_lsn: str | None = None

    def __enter__(self) -> "ReadOnlyDatabase":
        if self.config.data_env != ACTIVE_ENVIRONMENT:
            raise RuntimeError("BLOCKED_BY_RELEASE_ACCESS")
        if not re.fullmatch(r"[A-Za-z_]+/[A-Za-z_]+", self.config.timezone):
            raise ValueError("Invalid managed timezone")
        sslmode = self.env.get("DB_SSLMODE", "verify-full")
        if sslmode not in {"verify-ca", "verify-full"}:
            raise RuntimeError("BLOCKED_BY_DB_ACCESS: TLS verification is required")
        options = (
            "-c default_transaction_read_only=on "
            f"-c statement_timeout={self.config.statement_timeout_ms} "
            f"-c timezone={self.config.timezone}"
        )
        try:
            self.connection = psycopg2.connect(
                host=self.env["DB_HOST"],
                dbname=self.env["DB_NAME"],
                user=self.env.get("DB_USERNAME") or self.env["DB_USER"],
                password=self.env["DB_PASSWORD"],
                port=int(self.env.get("DB_PORT", "5432")),
                sslmode=sslmode,
                sslrootcert=self.env.get("DB_SSLROOTCERT"),
                connect_timeout=20,
                application_name=(
                    "sibc_clinical_validation_release_readonly"
                ),
                options=options,
            )
            self.connection.set_session(
                readonly=True, autocommit=False, isolation_level="REPEATABLE READ"
            )
            with self.connection.cursor() as cursor:
                cursor.execute("SHOW transaction_read_only")
                if cursor.fetchone()[0] != "on":
                    raise RuntimeError("DB session is not read-only")
                cursor.execute("SHOW transaction_isolation")
                if cursor.fetchone()[0].lower() != "repeatable read":
                    raise RuntimeError("DB session isolation mismatch")
                cursor.execute("SHOW timezone")
                if cursor.fetchone()[0] != self.config.timezone:
                    raise RuntimeError("DB session timezone mismatch")
                cursor.execute(
                    "SELECT txid_current_snapshot()::text, pg_current_wal_lsn()::text"
                )
                self.snapshot_id, self.wal_lsn = cursor.fetchone()
        except (psycopg2.Error, KeyError, ValueError, RuntimeError):
            if self.connection is not None:
                self.connection.close()
                self.connection = None
            raise RuntimeError("BLOCKED_BY_DB_ACCESS") from None
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.connection is not None:
            self.connection.rollback()
            self.connection.close()
            self.connection = None

    @contextmanager
    def cursor(self) -> Iterator[Any]:
        if self.connection is None:
            raise RuntimeError("Database is not connected")
        with self.connection.cursor() as cursor:
            yield cursor

    def fetchall(
        self, query: ManagedQuery, params: Sequence[Any] | None = None
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        assert_query_unchanged(query)
        try:
            with self.cursor() as cursor:
                cursor.execute(query.sql, params)
                columns = [description.name for description in cursor.description]
                rows = cursor.fetchmany(self.config.query_limit + 1)
        except psycopg2.Error:
            raise RuntimeError("BLOCKED_BY_DB_ACCESS") from None
        if len(rows) > self.config.query_limit:
            raise RuntimeError("Managed query exceeded query_limit")
        return columns, rows
