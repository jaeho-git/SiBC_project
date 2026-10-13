"""건강검진 항목 산출 v2 — '실측'과 '예측'을 분리한다 (판단 Agent 연계용).

정의
- MEASURED(실측): 웨어러블 기기가 같은 항목을 직접 잰 값(혈압계 → 수축기·이완기, 체중계 → 체중, 체중계+직전 검진 신장비 → BMI).
  예측이 아니므로 예측 구간·정확도를 붙이지 않고 측정 요약(중앙값·횟수·기간)만 낸다.
- PREDICTED(예측): 같은 항목의 측정값을 입력에서 제외하고, 다른 데이터로만 추정한 값.
    HISTORY          : 과거 검진값·경과일·추세 + 성별·연령 (개인화 M1). 웨어러블 미사용. 자체 사용자 61명으로 검증됨.
    HISTORY_WEARABLE : 위 + 웨어러블 간접 신호(걸음·활동량·활동시간·악력)를 쓰는 통합 모델(v1.4). 자체 검증 불가(착용 뒤 검진 15명) → REFERENCE_ONLY.
    WEARABLE_ONLY    : 검진 이력이 없는 사용자. 웨어러블 간접 신호 + 성별·연령만(통합 모델, 앵커 결측). 공공데이터 내부 성능만 존재 → UNVALIDATED.
- 어떤 예측 경로도 같은 항목의 웨어러블 측정값(혈압계·체중계)을 입력으로 쓰지 않는다. (joint_inputs_are_clean 로 강제)
- 상태 판정·안내는 하지 않는다.
"""
from __future__ import annotations

import json
import re
from datetime import date

import joblib
import numpy as np
import pandas as pd

from .env import PROJECT_ROOT
from .schema import target_names
from .serve import _predict_target, build_serving_features, load_rules

OUT_DIR = PROJECT_ROOT / "01_Results" / "predictions"
SCHEMA_PATH = PROJECT_ROOT / "configs" / "prediction_output_schema.json"
JOINT_DIR = PROJECT_ROOT / "01_Results" / "v1.4"
CONTRIB = PROJECT_ROOT / "01_Results" / "wearable_contribution.json"
MEASURED_CH = {"sbp": "bp_systolic_measured", "dbp": "bp_diastolic_measured", "weight": "body_weight_measured"}
MEASURE_LOOKBACK = 180
FORBIDDEN_INPUT = re.compile(r"^(bp_systolic_measured|bp_diastolic_measured|body_weight_measured|bodyfat_pct)__")
WEAR_SIGNAL = ("activity_pct__w7__median", "step_count__w7__median")
UNITS = {"sbp": "mmHg", "dbp": "mmHg", "weight": "kg", "bmi": "kg/m2", "waist": "cm", "fasting_glucose": "mg/dL",
         "total_cholesterol": "mg/dL", "hdl": "mg/dL", "ldl": "mg/dL", "triglyceride": "mg/dL"}
KOR = {"sbp": "수축기혈압", "dbp": "이완기혈압", "weight": "체중", "bmi": "BMI", "waist": "허리둘레", "fasting_glucose": "공복혈당",
       "total_cholesterol": "총콜레스테롤", "hdl": "HDL콜레스테롤", "ldl": "LDL콜레스테롤", "triglyceride": "중성지방"}
ROUTE_MAP = {"MODEL": "M1_MODEL", "CARRY_FORWARD": "CARRY_FORWARD", "MODEL_CROSS": "MODEL_CROSS", "ABSTAIN": "ABSTAIN"}
_JOINT_CACHE: dict = {}


def _joint(t: str) -> dict:
    if t not in _JOINT_CACHE:
        _JOINT_CACHE[t] = joblib.load(JOINT_DIR / f"{t}.joblib")
    return _JOINT_CACHE[t]


def joint_inputs_are_clean() -> bool:
    """통합 모델 입력에 같은 항목 측정값(혈압계·체중계) 관측창이 없는지 검사."""
    return all(not FORBIDDEN_INPUT.match(f) for t in target_names() for f in _joint(t)["features"])


def _has_wearable_signal(row: pd.Series) -> bool:
    return any(pd.notna(row.get(c)) for c in WEAR_SIGNAL)


def _joint_predict(t: str, row: pd.Series, drop_anchor: bool, q: list | None) -> tuple[float, float, float]:
    art = _joint(t); X = {}
    for c in art["features"]:
        v = row.get(c, np.nan)
        if drop_anchor and c.startswith(("anchor_", "trend_")):
            v = np.nan
        if c == "src_own":
            v = 1.0
        elif c in ("src_knhanes", "src_nhanes"):
            v = 0.0
        X[c] = v
    p = float(art["model"].predict(pd.DataFrame([X]))[0])
    lo, hi = (p + q[0], p + q[1]) if q else (np.nan, np.nan)
    return p, lo, hi


def _add_activity_pct(feat: pd.DataFrame) -> pd.DataFrame:
    """서빙 시 활동량 브리징: 7일 걸음 중앙값 → KNHANES 성별 걸음 분포 ECDF 백분위 (학습 시 unified._add_activity_bridge 와 동일 규칙)."""
    from .unified import load_unified
    kn = load_unified(); kn = kn[kn["source"] == "knhanes"]
    feat = feat.copy(); col = "activity_pct__w7__median"
    feat[col] = np.nan
    if "step_count__w7__median" not in feat:
        return feat
    for sx in (1.0, 2.0):
        ref = np.sort(kn.loc[(kn["demo_sex"] == sx) & kn["step_count__w7__median"].notna(), "step_count__w7__median"].to_numpy())
        m = (feat["demo_sex"] == sx) & feat["step_count__w7__median"].notna()
        if len(ref) and m.any():
            feat.loc[m, col] = np.searchsorted(ref, feat.loc[m, "step_count__w7__median"].to_numpy(), side="right") / len(ref)
    return feat


def _rec(base: dict, t: str, **kw) -> dict:
    d = {**base, "item": t, "item_kr": KOR[t], "unit": UNITS[t], "kind": "PREDICTED", "method": None, "route": None, "value": np.nan,
         "lower": np.nan, "upper": np.nan, "validation": "N/A", "uses_wearable": False, "inputs": None, "abstain_reason": None,
         "measured_n": 0, "measured_first": None, "measured_last": None}
    d.update(kw); return d


def predict_all(index_time: date | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(long, wide). long = 사용자 × 항목 × kind(× method)."""
    from .features_demo import fetch_birth_year, fetch_sex
    from .features_own import build_windows, fetch_daily_features
    it = index_time or date.today(); ts = pd.Timestamp(it)
    assert joint_inputs_are_clean(), "통합 모델 입력에 같은 항목 측정값이 포함됨"
    cfg = load_rules(); m1v, rules = cfg["version"], cfg["rules"]
    contrib = json.loads(CONTRIB.read_text()) if CONTRIB.is_file() else {}; qpub = contrib.get("interval_quantiles_public", {})
    daily = fetch_daily_features(); daily["d"] = pd.to_datetime(daily["d"]); daily = daily[daily["d"] < ts]
    # (1) 검진 이력 보유 사용자: 앵커 + 웨어러블 관측창
    feat = build_serving_features(it, with_wearable=True); feat["has_checkup"] = True
    # (2) 검진 이력 없는 사용자: 웨어러블 관측창 + 인구통계
    others = sorted(set(daily["user_key"]) - set(feat["user_key"]))
    if others:
        win = build_windows(daily, pd.DataFrame({"user_key": others, "event_date": [it.isoformat()] * len(others)}))
        demo = pd.DataFrame({"user_key": others}).merge(fetch_sex(), on="user_key", how="left"); by = fetch_birth_year()
        demo = demo.merge(by, on="user_key", how="left") if not by.empty else demo.assign(birth_year=np.nan)
        demo["demo_age"] = it.year - demo["birth_year"]
        feat2 = demo[["user_key", "demo_sex", "demo_age"]].merge(win.drop(columns=["event_date"]), on="user_key", how="left")
        feat2["prediction_index_time"] = it.isoformat(); feat2["has_checkup"] = False
        feat = pd.concat([feat, feat2], ignore_index=True)
    feat = _add_activity_pct(feat)
    recent = daily[daily["d"] >= ts - pd.Timedelta(days=MEASURE_LOOKBACK)]
    meas = {}
    for t, ch in MEASURED_CH.items():
        g = recent[recent["feature"] == ch].groupby("user_key")
        meas[t] = pd.DataFrame({"median": g["value"].median(), "n": g["value"].size(), "first_d": g["d"].min(), "last_d": g["d"].max()})
    rows = []
    for _, row in feat.iterrows():
        u = row["user_key"]; has = bool(row["has_checkup"]); wear = _has_wearable_signal(row); has_demo = pd.notna(row.get("demo_sex")) and pd.notna(row.get("demo_age"))
        base = {"user_key": u, "prediction_index_time": it.isoformat()}
        # ---- 실측
        for t, ch in MEASURED_CH.items():
            if u in meas[t].index:
                m = meas[t].loc[u]
                rows.append(_rec(base, t, kind="MEASURED", method="DEVICE", value=round(float(m["median"]), 2), uses_wearable=True, inputs=f"{ch} 중앙값(180일)",
                                 measured_n=int(m["n"]), measured_first=str(m["first_d"].date()), measured_last=str(m["last_d"].date())))
        if u in meas["weight"].index and pd.notna(row.get("actual_bmi")) and pd.notna(row.get("actual_weight")) and row["actual_weight"] > 0:
            m = meas["weight"].loc[u]; k = row["actual_bmi"] / row["actual_weight"]
            rows.append(_rec(base, "bmi", kind="MEASURED", method="DEVICE_DERIVED", value=round(float(m["median"]) * k, 2), uses_wearable=True, inputs="체중계 중앙값 × (직전 검진 BMI/체중)",
                             measured_n=int(m["n"]), measured_first=str(m["first_d"].date()), measured_last=str(m["last_d"].date())))
        # ---- 예측
        for t in target_names():
            if has:
                r = _predict_target(row, t, rules.get(t, {"route": "ABSTAIN", "reason": "no_rule"}), m1v)
                route = ROUTE_MAP.get(r[f"route_{t}"], r[f"route_{t}"])
                rows.append(_rec(base, t, method="HISTORY", route=route, value=r[f"pred_{t}"], lower=r[f"pred_{t}_lower"], upper=r[f"pred_{t}_upper"],
                                 validation="VALIDATED_OWN" if route != "ABSTAIN" else "N/A", abstain_reason=r[f"abstain_reason_{t}"], inputs="과거 검진값·경과일·추세, 성별·연령"))
                if wear:
                    p, lo, hi = _joint_predict(t, row, drop_anchor=False, q=qpub.get(t))
                    rows.append(_rec(base, t, method="HISTORY_WEARABLE", route="JOINT_MODEL", value=round(p, 2), lower=round(lo, 2), upper=round(hi, 2), validation="REFERENCE_ONLY",
                                     uses_wearable=True, inputs="과거 검진값 + 걸음·활동량·활동시간·악력(7일) + 성별·연령"))
                else:
                    rows.append(_rec(base, t, method="HISTORY_WEARABLE", route="ABSTAIN", abstain_reason="no_wearable_signal"))
            elif wear and has_demo:
                p, lo, hi = _joint_predict(t, row, drop_anchor=True, q=qpub.get(t))
                rows.append(_rec(base, t, method="WEARABLE_ONLY", route="JOINT_MODEL", value=round(p, 2), lower=round(lo, 2), upper=round(hi, 2), validation="UNVALIDATED",
                                 uses_wearable=True, inputs="걸음·활동량·활동시간·악력(7일) + 성별·연령"))
            else:
                rows.append(_rec(base, t, method="WEARABLE_ONLY", route="ABSTAIN", abstain_reason="no_checkup_and_no_wearable_signal" if not wear else "no_demographics"))
    L = pd.DataFrame(rows)
    fmap = feat.set_index("user_key")
    L["basis_prev_checkup_value"] = np.nan; L["basis_prev_checkup_date"] = None
    for t in target_names():
        idx = (L["item"] == t) & (L["kind"] == "PREDICTED")
        if f"actual_{t}" in fmap:
            L.loc[idx, "basis_prev_checkup_value"] = L.loc[idx, "user_key"].map(fmap[f"actual_{t}"]).to_numpy()
            L.loc[idx, "basis_prev_checkup_date"] = L.loc[idx, "user_key"].map(fmap[f"actual_{t}_measured_dt"]).to_numpy()
    L.loc[L["route"] == "ABSTAIN", ["value", "lower", "upper"]] = np.nan
    L["interval_level"] = np.where((L["kind"] == "PREDICTED") & L["value"].notna(), 0.85, np.nan)
    L["model_version"] = f"{m1v}+v1.4"
    cols = ["user_key", "prediction_index_time", "item", "item_kr", "unit", "kind", "method", "route", "value", "lower", "upper", "interval_level", "validation",
            "uses_wearable", "inputs", "abstain_reason", "basis_prev_checkup_value", "basis_prev_checkup_date", "measured_n", "measured_first", "measured_last", "model_version"]
    L = L[cols].sort_values(["user_key", "item", "kind", "method"]).reset_index(drop=True)
    # wide
    W = pd.DataFrame({"user_key": sorted(L["user_key"].unique())}).set_index("user_key")
    for kind, meth, pre in (("MEASURED", ["DEVICE", "DEVICE_DERIVED"], "measured"), ("PREDICTED", ["HISTORY"], "pred_hist"), ("PREDICTED", ["HISTORY_WEARABLE", "WEARABLE_ONLY"], "pred_wear")):
        s = L[(L["kind"] == kind) & (L["method"].isin(meth))].pivot_table(index="user_key", columns="item", values="value", aggfunc="first")
        for t in target_names():
            W[f"{pre}_{t}"] = s[t] if t in s else np.nan
    W = W.reset_index(); W.insert(1, "prediction_index_time", it.isoformat()); W["has_checkup"] = W["user_key"].map(fmap["has_checkup"]).astype(bool)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    L.to_parquet(OUT_DIR / f"predictions_long_{it.isoformat()}.parquet", index=False); L.to_csv(OUT_DIR / f"predictions_long_{it.isoformat()}.csv", index=False)
    W.to_parquet(OUT_DIR / f"predictions_wide_{it.isoformat()}.parquet", index=False); W.to_csv(OUT_DIR / f"predictions_wide_{it.isoformat()}.csv", index=False)
    return L, W


def write_schema() -> dict:
    schema = {
        "name": "sibc_checkup_prediction", "version": "2.0", "grain": "user_key x item x kind(x method) (long) / user_key (wide)",
        "purpose": "웨어러블·검진 이력 기반 건강검진 항목 산출. '실측'과 '예측'을 분리하며 상태 판정·안내는 하지 않는다(판단 Agent 입력)",
        "items": [{"item": t, "item_kr": KOR[t], "unit": UNITS[t], "measurable_by_wearable": t in ("sbp", "dbp", "weight", "bmi")} for t in target_names()],
        "kind": {"MEASURED": "웨어러블 기기가 같은 항목을 직접 잰 값의 요약(기준일 이전 180일 중앙값). 예측 아님 → 구간·정확도 없음",
                 "PREDICTED": "같은 항목의 측정값을 입력에서 제외하고 다른 데이터로 추정한 값"},
        "method": {"DEVICE": "혈압계·체중계 측정 중앙값", "DEVICE_DERIVED": "체중계 중앙값 × (직전 검진 BMI/체중)",
                   "HISTORY": "과거 검진값·경과일·추세 + 성별·연령 (개인화 M1). 웨어러블 미사용",
                   "HISTORY_WEARABLE": "과거 검진값 + 웨어러블 간접 신호(걸음·활동량·활동시간·악력) 통합 모델",
                   "WEARABLE_ONLY": "검진 이력 없음: 웨어러블 간접 신호 + 성별·연령 통합 모델"},
        "validation": {"VALIDATED_OWN": "자체 사용자 61명 검증에서 직전값 대비 성능 확인", "REFERENCE_ONLY": "자체 검증 불가('착용 뒤 검진' 15명). 공공데이터 내부 성능과 소표본 참고치만 존재",
                       "UNVALIDATED": "자체 검증 없음. 공공데이터 내부 성능만 존재", "N/A": "실측 또는 보류"},
        "route": {"M1_MODEL": "개인화 모델", "CARRY_FORWARD": "직전 검진값 유지", "MODEL_CROSS": "다른 항목 직전값 기반(지질)", "JOINT_MODEL": "공공+자체 통합 모델 v1.4", "ABSTAIN": "보류"},
        "fields": {"value": "실측 중앙값 또는 예측값. ABSTAIN이면 null", "lower/upper": "예측 행만: 85% 예측 구간. HISTORY는 자체 검증 잔차, HISTORY_WEARABLE·WEARABLE_ONLY는 공공 홀드아웃 잔차 기준(참고)",
                   "uses_wearable": "웨어러블 데이터 사용 여부", "inputs": "사용한 입력의 설명", "abstain_reason": "no_prior_checkup / stale_anchor(Nd) / no_wearable_signal / no_checkup_and_no_wearable_signal / no_demographics",
                   "basis_prev_checkup_value/date": "예측 행의 직전 검진 실제값·검진일", "measured_n/first/last": "실측 행의 측정 횟수·기간", "model_version": "M1 버전 + 통합 모델 버전"},
        "guarantees": ["어떤 PREDICTED 행도 같은 항목의 웨어러블 측정값을 입력으로 쓰지 않는다(계약 테스트)", "정상/주의/위험 판정·플래그·안내·변화 방향을 포함하지 않는다"],
        "wide_columns": "measured_<item>, pred_hist_<item>, pred_wear_<item>, has_checkup",
    }
    SCHEMA_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=1)); return schema
