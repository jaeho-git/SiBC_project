"""자체 건강검진 라벨 추출·정규화.

원천: discovery.disc_health_user_info.health_info_data (JSON array)
시간 기준: health_info_data[].measuredDt (ins_dt 사용 금지)
산출: (user_key, event_date) x 표준 라벨 컬럼 wide 테이블 (가명키만 저장)
"""
from __future__ import annotations

import re

import pandas as pd

from .db import fetch_df
from .schema import label_aliases
from .security import pseudonymize

SQL_LABEL_ITEMS = """
WITH elems AS (
  SELECT h.user_id::text AS user_id, json_array_elements(h.health_info_data) AS e
  FROM discovery.disc_health_user_info h
  WHERE json_typeof(h.health_info_data) = 'array'
), det AS (
  SELECT user_id,
         (e->>'measuredDt') AS measured_dt,
         json_array_elements(e->'medicalUserMeasDetails') AS d
  FROM elems
  WHERE e->'medicalUserMeasDetails' IS NOT NULL
)
SELECT user_id, measured_dt,
       lower(trim(d->>'fieldNm')) AS field_nm,
       trim(d->>'value') AS value
FROM det
WHERE nullif(trim(d->>'value'), '') IS NOT NULL
"""

_NUM = re.compile(r"^-?\d+(\.\d+)?$")
_BP = re.compile(r"^\s*(\d{2,3})\s*/\s*(\d{2,3})\s*$")


def _to_float(v: str) -> float | None:
    v = v.replace(",", "").strip()
    return float(v) if _NUM.match(v) else None


def build_label_table() -> pd.DataFrame:
    raw = fetch_df(SQL_LABEL_ITEMS)
    aliases = label_aliases()

    records: list[dict] = []
    for row in raw.itertuples(index=False):
        std = aliases.get(row.field_nm)
        if std is None:
            continue
        mdt = str(row.measured_dt)[:10]
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", mdt):
            continue
        if std == "bloodpressure_combined":
            m = _BP.match(row.value)
            if m:
                records.append({"user_id": row.user_id, "event_date": mdt,
                                "label": "sbp", "value": float(m.group(1))})
                records.append({"user_id": row.user_id, "event_date": mdt,
                                "label": "dbp", "value": float(m.group(2))})
            continue
        val = _to_float(row.value)
        if val is not None:
            records.append({"user_id": row.user_id, "event_date": mdt,
                            "label": std, "value": val})

    long_df = pd.DataFrame(records)
    if long_df.empty:
        return long_df
    long_df["user_key"] = long_df["user_id"].map(pseudonymize)
    wide = (long_df
            .pivot_table(index=["user_key", "event_date"], columns="label",
                         values="value", aggfunc="median")
            .reset_index())
    wide.columns.name = None
    return wide


def label_user_map() -> pd.DataFrame:
    """user_key <-> 원본 user_id 매핑 (메모리 전용, 디스크 저장 금지)."""
    raw = fetch_df("SELECT DISTINCT user_id::text AS user_id FROM discovery.disc_health_user_info")
    raw["user_key"] = raw["user_id"].map(pseudonymize)
    return raw
