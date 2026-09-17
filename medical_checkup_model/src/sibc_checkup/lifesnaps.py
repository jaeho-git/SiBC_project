"""LifeSnaps (Zenodo 7229547) -> 사전학습용 일별 long 테이블.

스키마 앵커링: 인코더 입력은 SiBC 수집 가능 채널만 사용한다.
LifeSnaps 전용 변수(VO2Max, 스트레스 점수, EDA 등)는 읽지 않는다 —
서비스 시점의 인코더 입력이 자체 데이터와 동일해야 하기 때문이다.
"""
from __future__ import annotations

import pandas as pd

from .env import PROJECT_ROOT

DAILY_CSV = (PROJECT_ROOT / "00_Data" / "public" / "lifesnaps" / "rais_anonymized"
             / "csv_rais_anonymized" / "daily_fitbit_sema_df_unprocessed.csv")

# LifeSnaps 컬럼 -> SiBC 채널 (단위 변환 방향: 공공 -> SiBC)
COLUMN_MAP = {
    "steps": ("step_count", 1.0),
    "bpm": ("heartrate_median", 1.0),
    "resting_hr": ("heartrate_rest", 1.0),
    "sleep_duration": ("sleep_duration_min", 1.0 / 60_000.0),  # ms -> minutes
    "spo2": ("spo2_median", 1.0),
}


def load_daily() -> pd.DataFrame:
    """(user_key, d, feature, value) — 자체 fetch_daily_features()와 동일 형태."""
    usecols = ["id", "date"] + list(COLUMN_MAP)
    df = pd.read_csv(DAILY_CSV, usecols=usecols)
    frames = []
    for src, (feature, factor) in COLUMN_MAP.items():
        part = df[["id", "date", src]].dropna().rename(columns={src: "value"})
        part["value"] = part["value"].astype(float) * factor
        part["feature"] = feature
        frames.append(part)
    out = pd.concat(frames, ignore_index=True)
    out["user_key"] = "lifesnaps_" + out["id"].astype(str)
    out["d"] = pd.to_datetime(out["date"])
    return out[["user_key", "d", "feature", "value"]]
