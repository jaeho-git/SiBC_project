"""임상 가이드라인 기반 판정 (configs/clinical_guidelines.yaml).

- grade_value : 수치 1개 → 기본 3단계(정상/주의/위험) + 출처별 세부 단계
- grade_bp    : 수축기·이완기 → 더 나쁜 쪽 단계
- goal_status : 기저질환 프로필의 조절 목표 달성 여부
- grade_prediction : 예측값 + 구간 상한을 함께 판정(예측값은 실제 고위험자를 낮게 보는 경향이 있어
                     상한이 위험 구간에 걸치면 '주의'로 올림)
기준표는 의료진 승인 전 초안이며, 수치는 yaml 의 sources 에 명시된 원문에서 확인한 값만 사용한다.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import yaml

from .env import PROJECT_ROOT

PATH = PROJECT_ROOT / "configs" / "clinical_guidelines.yaml"
TIERS = ["정상", "주의", "위험"]


@lru_cache(maxsize=1)
def load() -> dict:
    with open(PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _isnan(v) -> bool:
    return v is None or (isinstance(v, float) and np.isnan(v))


def grade_value(item: str, value, sex: float | None = None) -> str | None:
    """기본 3단계. item: sbp, dbp, fasting_glucose, bmi, waist, total_cholesterol, ldl, triglyceride, hdl"""
    if _isnan(value):
        return None
    t = load()["default_tiers"][item]
    if item == "waist":
        if _isnan(sex):
            return None
        return "위험" if value >= (t["risk_male"] if sex == 1 else t["risk_female"]) else "정상"
    if item == "hdl":
        return "위험" if value < t["risk_below"] else ("주의" if value < t["caution_below"] else "정상")
    return "위험" if value >= t["risk"] else ("주의" if value >= t["caution"] else "정상")


def worst(*tiers: str | None) -> str | None:
    ts = [TIERS.index(x) for x in tiers if x is not None]
    return TIERS[max(ts)] if ts else None


def grade_bp(sbp, dbp) -> str | None:
    return worst(grade_value("sbp", sbp), grade_value("dbp", dbp))


def stage_by_source(item: str, value, source: str) -> str | None:
    """출처별 세부 단계명(단일 수치 항목)."""
    if _isnan(value):
        return None
    for b in load()["items"][item]["by_source"].get(source, []):
        if isinstance(b, dict) and "band" in b:
            lo, hi = b["band"]
            if (lo is None or value >= lo) and (hi is None or value < hi):
                return b["stage"]
    return None


def bp_stage(sbp, dbp, source: str = "KSH2026") -> str | None:
    """혈압 세부 단계: 수축기·이완기 각각의 단계 중 더 높은 단계."""
    if _isnan(sbp) and _isnan(dbp):
        return None
    bands = load()["items"]["blood_pressure"]["by_source"][source]
    def idx(v, key):
        if _isnan(v):
            return -1
        for i, b in enumerate(bands):
            lo, hi = b[key]
            if (lo is None or v >= lo) and (hi is None or v < hi):
                last = i
        # 이완기 <80 은 정상·주의 두 단계에 모두 해당 → 가장 낮은 단계로
        hits = [i for i, b in enumerate(bands) if (b[key][0] is None or v >= b[key][0]) and (b[key][1] is None or v < b[key][1])]
        return min(hits) if hits else -1
    return bands[max(idx(sbp, "sbp"), idx(dbp, "dbp"))]["stage"]


def grade_prediction(item: str, pred, upper=None, sex: float | None = None) -> str | None:
    """예측값 판정. 예측값 단계가 '위험' 미만인데 85% 구간 상한이 위험 구간이면 최소 '주의'."""
    g = grade_value(item, pred, sex)
    if g is None or item == "hdl" or _isnan(upper):
        return g
    gu = grade_value(item, upper, sex)
    if g == "정상" and gu == "위험":
        return "주의"
    return g


def goal_status(profile: str, *, sbp=None, dbp=None, fasting_glucose=None, ldl=None) -> dict:
    """기저질환 프로필의 기본 적용 목표(applied_default) 달성 여부. 값이 없으면 해당 키 생략."""
    g = load()["disease_profiles"][profile]["applied_default"]; out = {}
    if "sbp" in g and not (_isnan(sbp) and _isnan(dbp)):
        out["blood_pressure"] = "조절 필요" if ((not _isnan(sbp) and sbp >= g["sbp"]) or (not _isnan(dbp) and dbp >= g["dbp"])) else "목표 달성"
    if "fasting_glucose_high" in g and not _isnan(fasting_glucose):
        out["fasting_glucose"] = "조절 필요" if fasting_glucose > g["fasting_glucose_high"] else "목표 달성"
    if "ldl" in g and not _isnan(ldl):
        out["ldl"] = "조절 필요" if ldl >= g["ldl"] else "목표 달성"
    return out
