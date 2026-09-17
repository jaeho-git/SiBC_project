"""configs/schema.yaml 로더 — 스키마 앵커링의 단일 진실 원천."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from .env import PROJECT_ROOT

SCHEMA_PATH = PROJECT_ROOT / "configs" / "schema.yaml"


@lru_cache(maxsize=1)
def load_schema() -> dict:
    with open(SCHEMA_PATH) as f:
        return yaml.safe_load(f)


def target_names() -> list[str]:
    return list(load_schema()["targets"].keys())


def feature_names() -> list[str]:
    return list(load_schema()["features"].keys())


def both_provider_features() -> list[str]:
    feats = load_schema()["features"]
    return [k for k, v in feats.items() if v.get("provider") == "both"]


def own_only_features() -> list[str]:
    feats = load_schema()["features"]
    return [k for k, v in feats.items() if v.get("provider") == "own"]


def label_aliases() -> dict[str, str]:
    return dict(load_schema()["label_aliases"])


def windows() -> list[int]:
    return list(load_schema()["windows"])


def assert_no_public_only_columns(columns: list[str]) -> None:
    """통합 테이블 컬럼이 스키마에 정의된 특징/목표/메타만 담는지 검사.

    스키마 밖 컬럼(공공 전용 변수 등)이 발견되면 즉시 실패한다.
    """
    allowed = set(feature_names()) | set(target_names())
    allowed |= {"user_key", "event_date", "source", "sample_weight"}
    # 관측창 전개 컬럼: <feature>__w<window>__<stat>
    unexpected = []
    for col in columns:
        base = col.split("__", 1)[0]
        if col not in allowed and base not in allowed:
            unexpected.append(col)
    if unexpected:
        raise ValueError(f"schema anchoring violation — columns outside schema.yaml: {unexpected}")
