from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .config import PROJECT_ROOT


SQL_ROOT = PROJECT_ROOT / "sql"
MANAGED_QUERY_FILES = {
    "health_check": "clinical_validation_health_check.sql",
    "wearable": "clinical_validation_wearable.sql",
    "temporal_cohort": "clinical_validation_temporal_cohort.sql",
    "data_quality": "clinical_validation_data_quality.sql",
}
ALLOWED_RELATIONS = {
    "discovery.disc_medical_user_info",
    "discovery.disc_health_user_info",
    "discovery.disc_lifelog_user_info",
    "discovery.disc_lifelog_user_step",
    "information_schema.columns",
}
FORBIDDEN_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "merge",
    "alter",
    "drop",
    "create",
    "truncate",
    "grant",
    "revoke",
    "copy",
    "call",
    "vacuum",
    "reindex",
    "refresh",
    "execute",
    "prepare",
    "deallocate",
    "begin",
    "commit",
    "rollback",
    "savepoint",
    "release",
    "lock",
    "listen",
    "notify",
    "unlisten",
    "set",
    "reset",
    "discard",
    "analyze",
    "cluster",
    "do",
}
FORBIDDEN_FUNCTIONS = {
    "pg_sleep",
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "pg_stat_file",
    "pg_terminate_backend",
    "pg_cancel_backend",
    "set_config",
    "nextval",
    "setval",
    "dblink",
    "dblink_connect",
    "dblink_exec",
    "lo_import",
    "lo_export",
    "lo_unlink",
}
ALLOWED_SQL_CALLS = {"count", "min", "max", "filter", "in", "as", "over"}


class SQLGuardError(ValueError):
    pass


@dataclass(frozen=True)
class ManagedQuery:
    name: str
    path: Path
    sql: str
    sha256: str


def _strip_comments_and_literals(query: str) -> str:
    query = re.sub(r"/\*.*?\*/", " ", query, flags=re.S)
    query = re.sub(r"--[^\n]*", " ", query)
    query = re.sub(r"'(?:''|[^'])*'", "''", query)
    return query


def validate_read_only_sql(query: str) -> tuple[str, ...]:
    cleaned = _strip_comments_and_literals(query).strip()
    if not cleaned:
        raise SQLGuardError("Empty SQL")
    if '"' in cleaned:
        raise SQLGuardError("Quoted identifiers are not allowed in managed SQL")
    if cleaned.count(";") > 1 or (";" in cleaned and not cleaned.endswith(";")):
        raise SQLGuardError("Multiple SQL statements are not allowed")
    normalized = re.sub(r"\s+", " ", cleaned).lower().rstrip(";")
    if "\\" in normalized:
        raise SQLGuardError("psql meta-commands are not allowed")
    if not (normalized.startswith("select ") or normalized.startswith("with ")):
        raise SQLGuardError("Only SELECT/WITH queries are allowed")
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", normalized):
            raise SQLGuardError(f"Forbidden SQL keyword: {keyword}")
    for function in FORBIDDEN_FUNCTIONS:
        if re.search(rf"\b{function}\s*\(", normalized):
            raise SQLGuardError(f"Forbidden SQL function: {function}")
    if re.search(
        r"\bselect\s+(?:[a-z_][a-z0-9_]*\.)?\*(?:\s|,|$)", normalized
    ):
        raise SQLGuardError("Wildcard projections are not allowed")
    if re.search(r"\binto\s+(?:temporary\s+|temp\s+)?[a-z_]", normalized):
        raise SQLGuardError("SELECT INTO is not allowed")
    if re.search(
        r"\bfor\s+(?:update|share|no\s+key\s+update|key\s+share)\b", normalized
    ):
        raise SQLGuardError("Row-locking SELECT is not allowed")
    calls = set(re.findall(r"\b([a-z_][a-z0-9_]*)\s*\(", normalized))
    unapproved_calls = sorted(calls - ALLOWED_SQL_CALLS)
    if unapproved_calls:
        raise SQLGuardError(
            "Unapproved SQL function/construct: " + ", ".join(unapproved_calls)
        )
    unqualified = re.findall(
        r"\b(?:from|join)\s+([a-z_][a-z0-9_]*)(?!\s*\.)\b", normalized
    )
    # CTE names are allowed as unqualified relations; base relations are not.
    ctes = set(re.findall(r"(?:\bwith|,)\s*([a-z_][a-z0-9_]*)\s+as\s*\(", normalized))
    disallowed_unqualified = [name for name in unqualified if name not in ctes]
    if disallowed_unqualified:
        raise SQLGuardError(
            "Unqualified relation(s): " + ", ".join(sorted(set(disallowed_unqualified)))
        )
    relations = tuple(
        sorted(
            {
                f"{schema}.{table}"
                for schema, table in re.findall(
                    r"\b(?:from|join)\s+([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)\b",
                    normalized,
                )
            }
        )
    )
    if not relations:
        raise SQLGuardError("Managed SQL must read at least one allowlisted relation")
    disallowed = sorted(set(relations) - ALLOWED_RELATIONS)
    if disallowed:
        raise SQLGuardError("Disallowed relation(s): " + ", ".join(disallowed))
    if "discovery.disc_health_user_info" in relations:
        if "discovery.disc_medical_user_info" not in relations:
            raise SQLGuardError("Health storage cannot be queried independently")
        if not re.search(
            r"(?:h\.user_health_sn\s*=\s*m\.user_health_sn|m\.user_health_sn\s*=\s*h\.user_health_sn)",
            normalized,
        ):
            raise SQLGuardError("Health storage requires the approved join key")
    return relations


def load_managed_query(name: str) -> ManagedQuery:
    filename = MANAGED_QUERY_FILES.get(name)
    if filename is None:
        raise SQLGuardError(f"Unknown managed query: {name}")
    path = (SQL_ROOT / filename).resolve()
    if path.parent != SQL_ROOT.resolve() or not path.is_file():
        raise SQLGuardError(f"Missing managed query: {name}")
    sql = path.read_text(encoding="utf-8")
    validate_read_only_sql(sql)
    return ManagedQuery(
        name=name,
        path=path,
        sql=sql,
        sha256=hashlib.sha256(sql.encode()).hexdigest(),
    )


def assert_query_unchanged(query: ManagedQuery) -> None:
    current = query.path.read_text(encoding="utf-8")
    current_hash = hashlib.sha256(current.encode()).hexdigest()
    if current_hash != query.sha256:
        raise SQLGuardError("Managed query changed after validation")
    validate_read_only_sql(current)
