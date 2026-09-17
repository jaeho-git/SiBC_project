"""통합 학습 테이블 (구축가이드 v1.3, 7.2절).

- 공공(NHANES) 행 + 자체(own) 행을 한 테이블로 결합
- source(출처 표시 변수), sample_weight 부여
- 스키마 앵커링 검사: schema.yaml 밖 컬럼 발견 시 즉시 실패
- 자체 라벨이 소량인 동안 자체 행 가중 비중에 상한 (modeling_policy)
"""
from __future__ import annotations

import pandas as pd
import yaml

from .env import PROJECT_ROOT
from .schema import assert_no_public_only_columns

PROCESSED_DIR = PROJECT_ROOT / "00_Data" / "processed"
POLICY_PATH = PROJECT_ROOT / "configs" / "modeling_policy.yaml"

# NHANES 착용 7일 <-> 자체 w7 관측창 정합: 공공 요약을 w7 중앙값 슬롯에 매핑
_PUBLIC_FEATURE_SLOT = {
    "activity_daily_volume": "activity_daily_volume__w7__median",
    "activity_active_hours": "activity_active_hours__w7__median",
    "grip_strength_kg": "grip_strength_kg__w7__median",
}


def load_policy() -> dict:
    with open(POLICY_PATH) as f:
        return yaml.safe_load(f)


def build_unified(own_rows: pd.DataFrame, public_rows: pd.DataFrame,
                  knhanes_rows: pd.DataFrame | None = None) -> pd.DataFrame:
    public = public_rows.rename(columns=_PUBLIC_FEATURE_SLOT).copy()
    own = own_rows.copy()
    own["source"] = "own"

    parts = [own, public]
    if knhanes_rows is not None and not knhanes_rows.empty:
        parts.append(knhanes_rows.copy())  # 이미 w7 슬롯명으로 정렬됨
    unified = pd.concat(parts, ignore_index=True, sort=False)
    unified = _add_activity_bridge(unified)
    assert_no_public_only_columns([c for c in unified.columns])

    unified["sample_weight"] = _weights(unified)
    return unified


def _add_activity_bridge(unified: pd.DataFrame) -> pd.DataFrame:
    """활동량 브리징(분포 정합): 단위가 다른 소스의 활동 지표를 성별 층화 백분위로 공통화.

    - NHANES: 손목 가속도 MIMS 활동량 -> NHANES 내부 백분위 (같은 성별)
    - KNHANES·자체: 일별 걸음 -> KNHANES 걸음 분포(한국 기준) ECDF 백분위 (같은 성별)
    가정: 성별 내 활동량 순위 분포가 모집단 간 비교 가능. 변환 방향은 공공->공통 척도.
    """
    import numpy as np

    col = "activity_pct__w7__median"
    unified[col] = np.nan
    sex = unified.get("demo_sex")
    if sex is None:
        return unified
    vol = unified.get("activity_daily_volume__w7__median")
    steps = unified.get("step_count__w7__median")
    is_nh = unified["source"] == "nhanes"
    is_kn = unified["source"] == "knhanes"
    is_own = unified["source"] == "own"
    for s in (1.0, 2.0):
        if vol is not None:
            m = is_nh & (sex == s) & vol.notna()
            if m.sum() > 10:
                unified.loc[m, col] = vol[m].rank(pct=True).to_numpy()
        if steps is not None:
            ref = np.sort(steps[is_kn & (sex == s) & steps.notna()].to_numpy())
            m = (is_kn | is_own) & (sex == s) & steps.notna()
            if len(ref) > 10 and m.any():
                unified.loc[m, col] = np.searchsorted(ref, steps[m].to_numpy(), side="right") / len(ref)
    return unified


def _weights(df: pd.DataFrame) -> pd.Series:
    """행 가중치. 도메인 정합 순으로 own > knhanes(한국인) > nhanes(미국).

    - own 총 가중치가 목표 비중(cap)을 넘지 않게 배분(행당 >=1.0).
    - knhanes는 한국인 도메인이므로 nhanes보다 높은 기본 가중치.
    """
    policy = load_policy()
    cap = float(policy["joint_training"]["own_weight_cap_initial"])
    kn_w = float(policy["joint_training"].get("knhanes_weight", 3.0))
    n_own = int((df["source"] == "own").sum())
    n_pub = int((df["source"] != "own").sum())
    if n_own == 0 or n_pub == 0:
        base = {"own": 1.0, "knhanes": kn_w, "nhanes": 1.0}
        return pd.Series([base.get(s, 1.0) for s in df["source"]], index=df.index)
    own_w = max(1.0, (cap / (1 - cap)) * n_pub / n_own)
    wmap = {"own": own_w, "knhanes": kn_w, "nhanes": 1.0}
    return pd.Series([wmap.get(s, 1.0) for s in df["source"]], index=df.index)


def save_unified(unified: pd.DataFrame) -> str:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PROCESSED_DIR / "unified_table.parquet"
    unified.to_parquet(path, index=False)
    return str(path)


def load_unified() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED_DIR / "unified_table.parquet")
