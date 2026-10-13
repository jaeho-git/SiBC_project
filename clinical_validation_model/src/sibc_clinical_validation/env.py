from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

from .config import ACTIVE_ENVIRONMENT, ENV_FILE_MAP, PrototypeConfig


REQUIRED_RELEASE_KEYS = (
    "APP_ENV",
    "SIBC_DATA_ENV",
    "DB_HOST",
    "DB_NAME",
    "DB_PORT",
    "DB_PASSWORD",
)
ALLOWED_RELEASE_DB_KEYS = frozenset(
    {
        *REQUIRED_RELEASE_KEYS,
        "DB_USERNAME",
        "DB_USER",
        "DB_SSLMODE",
        "DB_SSLROOTCERT",
    }
)
MAX_ENV_FILE_BYTES = 1024 * 1024
_KEY_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class ReleaseAccessError(RuntimeError):
    """Safe, non-secret-bearing release access failure."""

    status = "BLOCKED_BY_RELEASE_ACCESS"

    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(f"{self.status}: {reason_code}")


def _managed_release_env_path(config: PrototypeConfig) -> Path:
    expected = ENV_FILE_MAP[ACTIVE_ENVIRONMENT]
    if config.data_env != ACTIVE_ENVIRONMENT:
        raise ReleaseAccessError("NON_RELEASE_ENVIRONMENT_REJECTED")
    if config.env_file != expected:
        raise ReleaseAccessError("UNMANAGED_ENV_PATH_REJECTED")
    if expected.is_symlink():
        raise ReleaseAccessError("SYMLINK_ENV_FILE_REJECTED")
    try:
        stat = expected.stat()
    except OSError:
        raise ReleaseAccessError("ENV_FILE_UNAVAILABLE") from None
    if not expected.is_file() or stat.st_size > MAX_ENV_FILE_BYTES:
        raise ReleaseAccessError("ENV_FILE_INVALID")
    return expected


def _parse_release_env(path: Path) -> dict[str, str]:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise ReleaseAccessError("ENV_FILE_UNREADABLE") from None

    values: dict[str, str] = {}
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ReleaseAccessError("ENV_FILE_FORMAT_INVALID")
        key, value = line.split("=", 1)
        key = key.strip()
        if not _KEY_PATTERN.fullmatch(key) or key in values:
            raise ReleaseAccessError("ENV_FILE_FORMAT_INVALID")
        values[key] = value.strip().strip("\"'")
    return values


def validate_release_environment_identity(values: Mapping[str, str]) -> None:
    if values.get("APP_ENV") != ACTIVE_ENVIRONMENT:
        raise ReleaseAccessError("APP_ENV_IDENTITY_MISMATCH")
    if values.get("SIBC_DATA_ENV") != ACTIVE_ENVIRONMENT:
        raise ReleaseAccessError("SIBC_DATA_ENV_IDENTITY_MISMATCH")


def load_release_db_environment(config: PrototypeConfig) -> dict[str, str]:
    """Load only managed release DB settings; never inspect dev/stg or process env."""

    path = _managed_release_env_path(config)
    values = _parse_release_env(path)
    missing = [key for key in REQUIRED_RELEASE_KEYS if not values.get(key)]
    if not (values.get("DB_USERNAME") or values.get("DB_USER")):
        missing.append("DB_USERNAME_OR_DB_USER")
    if missing:
        raise ReleaseAccessError("REQUIRED_DB_METADATA_MISSING")
    validate_release_environment_identity(values)
    try:
        port = int(values["DB_PORT"])
    except ValueError:
        raise ReleaseAccessError("DB_PORT_INVALID") from None
    if not 1 <= port <= 65535:
        raise ReleaseAccessError("DB_PORT_INVALID")
    return {
        key: value
        for key, value in values.items()
        if key in ALLOWED_RELEASE_DB_KEYS
    }


def safe_environment_preflight(config: PrototypeConfig) -> dict[str, str]:
    """Verify only ``.env.release`` and return redacted release metadata."""

    load_release_db_environment(config)
    return {
        "status": "RELEASE_ACCESS_VERIFIED",
        "data_env": ACTIVE_ENVIRONMENT,
        "env_file": ".env.release",
        "APP_ENV": ACTIVE_ENVIRONMENT,
        "SIBC_DATA_ENV": ACTIVE_ENVIRONMENT,
        "db_credentials": "PRESENT_REDACTED",
        "secret_values_returned": "NO",
        "dev_env_read": "NO",
        "stg_env_read": "NO",
        "environment_fallback": "DISABLED",
    }
