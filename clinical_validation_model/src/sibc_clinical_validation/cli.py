from __future__ import annotations

import argparse
import json
from typing import Any

from .config import (
    ACTIVE_ENVIRONMENT,
    ALLOWED_DATA_ENVS,
    ALLOWED_EXECUTION_MODES,
    DEFAULT_EXECUTION_MODE,
    PrototypeConfig,
)
from .env import ReleaseAccessError, safe_environment_preflight
from .medical_adapter import snapshot_medical_artifacts
from .pipeline import PrototypePipeline
from .synthetic import write_fixture_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SiBC Clinical Layer candidate-validation technical prototype"
    )
    parser.add_argument(
        "command", choices=("preflight", "generate-fixtures", "run")
    )
    parser.add_argument(
        "--data-env", choices=ALLOWED_DATA_ENVS, default=ACTIVE_ENVIRONMENT
    )
    parser.add_argument(
        "--mode", choices=ALLOWED_EXECUTION_MODES, default=DEFAULT_EXECUTION_MODE
    )
    return parser


def _verify_release_artifact_access(config: PrototypeConfig) -> None:
    try:
        snapshot_medical_artifacts(config)
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        raise ReleaseAccessError("RELEASE_ARTIFACT_UNAVAILABLE") from None


def _blocked_release_result(
    config: PrototypeConfig | None, error: ReleaseAccessError
) -> dict[str, Any]:
    return {
        "status": error.status,
        "reason_code": error.reason_code,
        "environment": ACTIVE_ENVIRONMENT,
        "execution_mode": (
            config.release_execution_mode if config is not None else "release_artifact"
        ),
        "environment_fallback": "DISABLED",
        "connection_attempted": False,
        "db_write_allowed": False,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pipeline: PrototypePipeline | None = None
    try:
        pipeline = PrototypePipeline(args.data_env, args.mode)
        release_env = safe_environment_preflight(pipeline.config)
        if args.mode == "artifact" and args.command in {"preflight", "run"}:
            _verify_release_artifact_access(pipeline.config)
        try:
            if args.command == "preflight":
                result = pipeline.preflight()
            elif args.command == "generate-fixtures":
                result = write_fixture_dataset(
                    pipeline.config, registry=pipeline.registry
                )
            else:
                result = pipeline.run()
        except (FileNotFoundError, PermissionError, json.JSONDecodeError, ValueError):
            if args.mode != "artifact":
                raise
            raise ReleaseAccessError("RELEASE_ARTIFACT_UNAVAILABLE") from None
        result["environment"] = ACTIVE_ENVIRONMENT
        result["execution_mode"] = pipeline.config.release_execution_mode
        result["release_environment_access"] = release_env["status"]
        result["environment_fallback"] = "DISABLED"
        result["environment_files_read"] = True
        result["environment_file_read"] = release_env["env_file"]
        result["dev_env_read"] = "NO"
        result["stg_env_read"] = "NO"
    except ReleaseAccessError as error:
        result = _blocked_release_result(
            pipeline.config if pipeline is not None else None, error
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    status = str(result.get("status", ""))
    if status == "FAILED" or status.startswith("BLOCKED_"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
