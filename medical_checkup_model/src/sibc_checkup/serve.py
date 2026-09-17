"""M1 서빙: 사용자당 1행 예측 산출 (구축가이드 5.8 최종 산출 스키마).

- 입력 시점(prediction_index_time) 이전 데이터만 사용 (검진·웨어러블 모두)
- 항목별 규칙(configs/m1_serving_rules.json): MODEL / CARRY_FORWARD / ABSTAIN
- 세 종류 값 구분: actual_*(최근 실제 검진값), measured_*(웨어러블 직접 측정 요약),
  pred_*(경로 적용 예측값 + 구간)
- 원본 식별자 없음(가명키). 검증 통과 경로만 pred_* 로 서비스 가능.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd

from .env import PROJECT_ROOT
from .m1 import MAX_ANCHOR_AGE_DAYS, RULES_PATH
from .schema import target_names
from .unified import load_unified

SERVING_DIR = PROJECT_ROOT / "01_Results" / "serving"

# 웨어러블 직접 측정 요약(measured_*)으로 노출할 관측창 컬럼
MEASURED_MAP = {
    "measured_sbp_30d": "bp_systolic_measured__w30__median",
    "measured_dbp_30d": "bp_diastolic_measured__w30__median",
    "measured_weight_30d": "body_weight_measured__w30__median",
    "measured_steps_30d": "step_count__w30__median",
    "measured_rest_hr_30d": "heartrate_rest__w30__median",
    "measured_night_hr_30d": "heartrate_night_median__w30__median",
}
CLINICAL_RULES_PATH = PROJECT_ROOT / "configs" / "clinical_rules.json"
CLINICAL_DIR = PROJECT_ROOT / "01_Results" / "clinical"


def load_clinical_rules() -> dict:
    if not CLINICAL_RULES_PATH.is_file():
        return {"thresholds": {}, "direction": {}}
    with open(CLINICAL_RULES_PATH) as f:
        return json.load(f)


@lru_cache(maxsize=32)
def _load_clinical(fname: str) -> dict:
    return joblib.load(CLINICAL_DIR / fname)


def _clinical_outputs(row: pd.Series, crules: dict) -> dict:
    """임계값 플래그(flag_*)와 변화 방향(direction_*). 서빙 게이트 통과 문제만."""
    out: dict = {}
    for name, r in crules.get("thresholds", {}).items():
        out[f"flag_{name}_prob"], out[f"flag_{name}"] = np.nan, None
        if not r.get("serve"):
            continue
        t = r["base_target"]
        anchor, days = row.get(f"anchor_prev_label__{t}"), row.get(f"anchor_days_since__{t}")
        if pd.isna(anchor) or (days is not None and days > MAX_ANCHOR_AGE_DAYS):
            continue
        art = _load_clinical(r["model_file"])
        X = pd.DataFrame([{c: row.get(c, np.nan) for c in art["features"]}])
        p = float(art["model"].predict_proba(X)[0, 1])
        out[f"flag_{name}_prob"], out[f"flag_{name}"] = round(p, 3), bool(p >= 0.5)
    for t, r in crules.get("direction", {}).items():
        out[f"direction_{t}"], out[f"direction_{t}_worsen_prob"] = None, np.nan
        if not r.get("serve"):
            continue
        anchor, days = row.get(f"anchor_prev_label__{t}"), row.get(f"anchor_days_since__{t}")
        if pd.isna(anchor) or (days is not None and days > MAX_ANCHOR_AGE_DAYS):
            continue
        art = _load_clinical(r["model_file"])
        X = pd.DataFrame([{c: row.get(c, np.nan) for c in art["features"]}])
        proba = art["model"].predict_proba(X)[0]
        classes = list(art["model"].classes_)
        pred = int(classes[int(np.argmax(proba))])
        worsen = float(proba[classes.index(1)]) if 1 in classes else np.nan
        out[f"direction_{t}"] = {1: "worsen", 0: "stable", -1: "improve"}[pred]
        out[f"direction_{t}_worsen_prob"] = round(worsen, 3)
    return out


def load_rules() -> dict:
    with open(RULES_PATH) as f:
        return json.load(f)


@lru_cache(maxsize=32)
def _load_model(version: str, fname: str) -> dict:
    return joblib.load(PROJECT_ROOT / "01_Results" / "m1" / version / fname)


# ---------------------------------------------------------------- 특징 구성

def build_serving_features(index_time: date, with_wearable: bool = True) -> pd.DataFrame:
    """index_time 이전 정보만으로 사용자별 서빙 특징 1행 구성."""
    df = load_unified()
    own = df[df["source"] == "own"].copy()
    own["event_date"] = pd.to_datetime(own["event_date"])
    own = own[own["event_date"] < pd.Timestamp(index_time)]  # 시점 이후 검진 배제
    ts = pd.Timestamp(index_time)

    rows = []
    for user, g in own.sort_values("event_date").groupby("user_key"):
        row: dict = {"user_key": user, "prediction_index_time": index_time.isoformat()}
        last = g.iloc[-1]
        row["demo_sex"] = last.get("demo_sex")
        if pd.notna(last.get("demo_age")):
            row["demo_age"] = float(last["demo_age"]) + (ts - last["event_date"]).days / 365.25
        for t in target_names():
            if t not in g.columns:
                continue
            h = g[g[t].notna()]
            if h.empty:
                continue
            v1, d1 = float(h.iloc[-1][t]), h.iloc[-1]["event_date"]
            row[f"actual_{t}"] = v1
            row[f"actual_{t}_measured_dt"] = d1.strftime("%Y-%m-%d")
            row[f"anchor_prev_label__{t}"] = v1
            row[f"anchor_days_since__{t}"] = float((ts - d1).days)
            if len(h) >= 2:
                v2, d2 = float(h.iloc[-2][t]), h.iloc[-2]["event_date"]
                gap = (d1 - d2).days
                row[f"trend_prev2__{t}"] = v2
                if gap > 0:
                    row[f"trend_slope_per_year__{t}"] = (v1 - v2) / gap * 365.0
        rows.append(row)
    feat = pd.DataFrame(rows)

    if with_wearable and not feat.empty:
        from .features_own import build_windows, fetch_daily_features
        daily = fetch_daily_features()
        events = pd.DataFrame({"user_key": feat["user_key"],
                               "event_date": index_time.isoformat()})
        win = build_windows(daily, events)
        feat = feat.merge(win.drop(columns=["event_date"]), on="user_key", how="left")
    return feat


# ---------------------------------------------------------------- 규칙 적용

def _coverage_grade(row: pd.Series) -> str:
    days = row.get("step_count__w30__days")
    if pd.isna(days):
        return "none"
    return "A" if days >= 21 else "B" if days >= 10 else "C"


def _predict_target(row: pd.Series, t: str, rule: dict, version: str) -> dict:
    anchor = row.get(f"anchor_prev_label__{t}")
    days = row.get(f"anchor_days_since__{t}")
    route = rule.get("route", "ABSTAIN")
    out = {f"pred_{t}": np.nan, f"pred_{t}_lower": np.nan, f"pred_{t}_upper": np.nan,
           f"route_{t}": "ABSTAIN", f"abstain_reason_{t}": None}
    if route == "ABSTAIN":
        out[f"abstain_reason_{t}"] = rule.get("reason", "rule_abstain")
        return out
    max_age = rule.get("max_anchor_age_days", MAX_ANCHOR_AGE_DAYS)
    anchor_fresh = pd.notna(anchor) and not (days is not None and days > max_age)
    if route == "MODEL_CROSS":
        # 하이브리드: 신선한 자기 앵커가 있으면 직전값(CF)이 더 정확 -> CF로 서빙
        if anchor_fresh and rule.get("cf_interval_offsets"):
            lo_off, hi_off = rule["cf_interval_offsets"]
            pred = float(anchor)
            out.update({f"pred_{t}": round(pred, 2), f"pred_{t}_lower": round(pred + lo_off, 2),
                        f"pred_{t}_upper": round(pred + hi_off, 2), f"route_{t}": "CARRY_FORWARD"})
            return out
        if pd.isna(row.get("demo_age")) and pd.isna(row.get("demo_sex")):
            out[f"abstain_reason_{t}"] = "no_prior_checkup_and_no_demo"
            return out
    else:
        if pd.isna(anchor):
            out[f"abstain_reason_{t}"] = "no_prior_checkup"
            return out
        if not anchor_fresh:
            out[f"abstain_reason_{t}"] = f"stale_anchor({int(days)}d)"
            return out

    art = _load_model(version, rule["model_file"]) if rule.get("model_file") else None
    X = (pd.DataFrame([{c: row.get(c, np.nan) for c in art["features"]}]) if art else None)
    if route in ("MODEL", "MODEL_CROSS"):
        pred = float(art["model"].predict(X)[0])
    else:  # CARRY_FORWARD
        pred = float(anchor)

    if rule.get("interval_method") == "cqr" and art is not None:
        lo = float(art["q_lo_model"].predict(X)[0]) - art["cqr_Q"]
        hi = float(art["q_hi_model"].predict(X)[0]) + art["cqr_Q"]
        lo, hi = min(lo, pred), max(hi, pred)
    else:
        lo_off, hi_off = rule["interval_offsets"]
        lo, hi = pred + lo_off, pred + hi_off
    out.update({f"pred_{t}": round(pred, 2), f"pred_{t}_lower": round(lo, 2),
                f"pred_{t}_upper": round(hi, 2), f"route_{t}": route})
    return out


def serve_all(index_time: date | None = None, with_wearable: bool = True) -> pd.DataFrame:
    index_time = index_time or date.today()
    cfg = load_rules()
    version, rules = cfg["version"], cfg["rules"]
    crules = load_clinical_rules()
    feat = build_serving_features(index_time, with_wearable)
    records = []
    for _, row in feat.iterrows():
        rec = {"user_key": row["user_key"], "prediction_index_time": row["prediction_index_time"],
               "coverage_grade": _coverage_grade(row)}
        for k, col in MEASURED_MAP.items():
            rec[k] = round(float(row[col]), 2) if col in row and pd.notna(row[col]) else np.nan
        for t in target_names():
            rec[f"actual_{t}"] = row.get(f"actual_{t}", np.nan)
            rec[f"actual_{t}_measured_dt"] = row.get(f"actual_{t}_measured_dt")
            rec.update(_predict_target(row, t, rules.get(t, {"route": "ABSTAIN", "reason": "no_rule"}), version))
        rec.update(_clinical_outputs(row, crules))
        records.append(rec)
    out = pd.DataFrame(records)
    SERVING_DIR.mkdir(parents=True, exist_ok=True)
    stem = SERVING_DIR / f"m1_predictions_{index_time.isoformat()}"
    out.to_parquet(f"{stem}.parquet", index=False)
    out.to_csv(f"{stem}.csv", index=False)
    return out


def serve_summary(out: pd.DataFrame) -> dict:
    summ = {"n_users": int(len(out)), "coverage_grade": out["coverage_grade"].value_counts().to_dict(),
            "routes": {}}
    for t in target_names():
        col = f"route_{t}"
        if col in out:
            summ["routes"][t] = out[col].value_counts().to_dict()
    return summ
