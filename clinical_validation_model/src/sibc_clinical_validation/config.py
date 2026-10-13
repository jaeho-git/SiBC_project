from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = PROJECT_ROOT.parent
CONFIG_ROOT = PROJECT_ROOT / "configs"
RULE_ROOT = PROJECT_ROOT / "rules"
FIXTURE_ROOT = PROJECT_ROOT / "00_Data" / "fixtures" / "synthetic_clinical_layer"
RESULT_ROOT = PROJECT_ROOT / "01_Results"
ACTIVE_ENVIRONMENT = "release"
DISABLED_DATA_ENVS = ("dev", "stg")
ALLOWED_DATA_ENVS = (ACTIVE_ENVIRONMENT,)
ALLOWED_EXECUTION_MODES = ("fixture", "artifact", "db")
DEFAULT_EXECUTION_MODE = "artifact"
ENV_FILE_MAP = {ACTIVE_ENVIRONMENT: REPOSITORY_ROOT / ".env.release"}
RELEASE_EXECUTION_MODE_LABELS = {
    "artifact": "release_artifact",
    "db": "release_db",
    "fixture": "synthetic_fixture",
}


@dataclass(frozen=True)
class PrototypeConfig:
    project_root: Path
    medical_checkup_root: Path
    env_file: Path
    timezone: str
    data_env: str
    execution_mode: str
    model_version: str
    generator_version: str
    random_seed: int
    query_limit: int
    statement_timeout_ms: int
    artifact_source_environment: str
    fixture_generation_timestamp: str
    fixture_index_datetime: str

    @property
    def release_execution_mode(self) -> str:
        """Public execution-mode label used by the release output contract."""

        return RELEASE_EXECUTION_MODE_LABELS[self.execution_mode]


def _managed_yaml(name: str) -> dict[str, Any]:
    path = (CONFIG_ROOT / name).resolve()
    if path.parent != CONFIG_ROOT.resolve() or not path.is_file():
        raise ValueError(f"Unknown managed config: {name}")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return loaded


def validate_data_env(data_env: str) -> str:
    if data_env in DISABLED_DATA_ENVS:
        raise ValueError(
            f"{data_env} execution is disabled; the active environment is release "
            "and fallback is prohibited"
        )
    if data_env != ACTIVE_ENVIRONMENT:
        raise ValueError("data_env must be release")
    return data_env


def validate_execution_mode(execution_mode: str) -> str:
    if execution_mode not in ALLOWED_EXECUTION_MODES:
        raise ValueError(
            f"execution_mode must be one of {', '.join(ALLOWED_EXECUTION_MODES)}"
        )
    return execution_mode


def load_config(
    data_env: str = ACTIVE_ENVIRONMENT,
    execution_mode: str = DEFAULT_EXECUTION_MODE,
) -> PrototypeConfig:
    data_env = validate_data_env(data_env)
    execution_mode = validate_execution_mode(execution_mode)
    raw = _managed_yaml("prototype.yaml")
    configured_root = Path(raw["project_root"]).resolve()
    if configured_root != PROJECT_ROOT.resolve():
        raise ValueError(
            f"Configured project_root {configured_root} does not match {PROJECT_ROOT}"
        )
    medical_root = Path(raw["medical_checkup_root"]).resolve()
    if medical_root != (REPOSITORY_ROOT / "medical_checkup_model").resolve():
        raise ValueError("medical_checkup_root must be the sibling managed project")
    source_env = str(raw["artifact_source_environment"])
    if source_env != ACTIVE_ENVIRONMENT:
        raise ValueError("artifact_source_environment must be release")
    query_limit = int(raw["query_limit"])
    if not 1 <= query_limit <= 10_000:
        raise ValueError("query_limit must be between 1 and 10000")
    statement_timeout_ms = int(raw["statement_timeout_ms"])
    if not 1 <= statement_timeout_ms <= 900_000:
        raise ValueError("statement_timeout_ms must be between 1 and 900000")
    return PrototypeConfig(
        project_root=PROJECT_ROOT,
        medical_checkup_root=medical_root,
        env_file=ENV_FILE_MAP[ACTIVE_ENVIRONMENT],
        timezone=str(raw["timezone"]),
        data_env=data_env,
        execution_mode=execution_mode,
        model_version=str(raw["model_version"]),
        generator_version=str(raw["generator_version"]),
        random_seed=int(raw["random_seed"]),
        query_limit=query_limit,
        statement_timeout_ms=statement_timeout_ms,
        artifact_source_environment=source_env,
        fixture_generation_timestamp=str(raw["fixture_generation_timestamp"]),
        fixture_index_datetime=str(raw["fixture_index_datetime"]),
    )


def load_policy(name: str) -> dict[str, Any]:
    allowlist = {
        "validation": "validation_policy.yaml",
        "scoring": "scoring_policy.yaml",
        "cdei": "cdei_policy.yaml",
        "rule": "rule_policy.yaml",
    }
    if name not in allowlist:
        raise ValueError(f"Unknown policy: {name}")
    return _managed_yaml(allowlist[name])
