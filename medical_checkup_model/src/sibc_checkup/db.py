"""읽기 전용 DB 세션 (release invites_loop).

- SELECT/WITH 로 시작하는 문장만 실행을 허용한다.
- 세션은 default_transaction_read_only=on 으로 연다.
- 공유 DB 부하를 고려해 statement_timeout을 건다.
"""
from __future__ import annotations

import re
from contextlib import contextmanager

import psycopg

from .env import db_dsn

_ALLOWED = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


def guard_sql(sql: str) -> str:
    if not _ALLOWED.match(sql):
        raise PermissionError("read-only guard: only SELECT/WITH statements are allowed")
    return sql


@contextmanager
def read_only_conn(statement_timeout_ms: int = 300_000):
    dsn = db_dsn()
    opts = f"-c default_transaction_read_only=on -c statement_timeout={statement_timeout_ms}"
    hosts = [h for h in (dsn["host"], dsn.get("host_public")) if h]
    last_err: Exception | None = None
    for host in hosts:  # private-link 호스트가 로컬에서 해석 안 되면 public으로 폴백
        try:
            with psycopg.connect(
                host=host, port=dsn["port"], dbname=dsn["dbname"],
                user=dsn["user"], password=dsn["password"], options=opts,
            ) as conn:
                yield conn
                return
        except psycopg.OperationalError as exc:
            last_err = exc
    raise last_err  # type: ignore[misc]


def fetch_df(sql: str, params: tuple = (), statement_timeout_ms: int = 300_000):
    import pandas as pd

    guard_sql(sql)
    with read_only_conn(statement_timeout_ms) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d.name for d in cur.description]
            rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)
