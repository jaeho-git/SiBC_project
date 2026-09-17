"""약한 지도(weak supervision): 웨어러블 측정값을 대리 라벨로 대규모 학습.

검진 혈압 forward 쌍은 극소수지만, 웨어러블 혈압 측정(3천+행)·체중 측정은
검진보다 먼저 대량 존재한다. "생체 패턴(심박·수면·걸음·SpO2) -> 측정 혈압"을
먼저 학습하고, 소량의 검진값으로 눈금(calibration)만 보정한다.

누출 방지
- 입력에서 대리 목표와 같은 채널(혈압 예측 시 bp_*; 체중 예측 시 체중·체지방) 제외
- 관측창은 측정일 '이전'(build_windows: d < event_date)
- 사용자 단위 GroupKFold + 봉인 20%
"""
from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit
from sklearn.pipeline import Pipeline

from .env import PROJECT_ROOT
from .features_demo import add_demo_features
from .features_own import build_windows, fetch_daily_features
from .unified import load_unified

warnings.filterwarnings("ignore")
OUT_DIR = PROJECT_ROOT / "01_Results" / "proxy"

# 대리 목표 -> (일별 측정 채널, 입력에서 제외할 채널)
PROXY = {
    "sbp": ("bp_systolic_measured", {"bp_systolic_measured", "bp_diastolic_measured"}),
    "dbp": ("bp_diastolic_measured", {"bp_systolic_measured", "bp_diastolic_measured"}),
    "weight": ("body_weight_measured", {"body_weight_measured"}),
}
MIN_WEAR_DAYS_7 = 3   # 측정 전 7일 중 최소 관측일


def _model():
    return Pipeline([("impute", SimpleImputer(strategy="median")),
                     ("model", HistGradientBoostingRegressor(max_depth=4, learning_rate=0.05,
                                                             max_iter=300, l2_regularization=1.0,
                                                             min_samples_leaf=30, random_state=42))])


def build_proxy_dataset(target: str, daily: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    channel, exclude = PROXY[target]
    lab = daily[daily["feature"] == channel][["user_key", "d", "value"]].rename(columns={"value": "y"})
    lab = lab.sort_values(["user_key", "d"])
    lab["y_prev"] = lab.groupby("user_key")["y"].shift(1)          # 직전 측정(carry-forward 기준선)
    lab["event_date"] = lab["d"].dt.strftime("%Y-%m-%d")
    inputs = daily[~daily["feature"].isin(exclude)]
    feats = build_windows(inputs, lab[["user_key", "event_date"]])
    ds = lab.merge(feats, on=["user_key", "event_date"], how="left")
    ds = add_demo_features(ds)
    # 관측창이 실제로 있는 행만 (걸음 또는 심박 7일 관측일 >= MIN)
    wear_ok = pd.Series(False, index=ds.index)
    for c in ("step_count__w7__days", "heartrate_median__w7__days"):
        if c in ds:
            wear_ok |= ds[c].fillna(0) >= MIN_WEAR_DAYS_7
    ds = ds[wear_ok].copy()
    feat_cols = [c for c in ds.columns if ("__w" in c or c in ("demo_age", "demo_sex"))
                 and ds[c].dtype.kind in "if" and ds[c].notna().mean() >= 0.05]
    return ds, feat_cols


def _cv(ds, feats, n_splits=5):
    gkf = GroupKFold(n_splits=min(n_splits, ds["user_key"].nunique()))
    maes, r2s, cf, base = [], [], [], []
    for tr, te in gkf.split(ds, groups=ds["user_key"]):
        m = _model().fit(ds.iloc[tr][feats], ds.iloc[tr]["y"])
        p = m.predict(ds.iloc[te][feats]); y = ds.iloc[te]["y"].to_numpy()
        maes.append(mean_absolute_error(y, p)); r2s.append(r2_score(y, p))
        base.append(mean_absolute_error(y, np.full(len(y), ds.iloc[tr]["y"].mean())))
        prev = ds.iloc[te]["y_prev"]; ok = prev.notna().to_numpy()
        cf.append(mean_absolute_error(y[ok], prev[ok]) if ok.sum() else np.nan)
    return {"cv_mae": float(np.mean(maes)), "cv_r2": float(np.mean(r2s)),
            "baseline_mean_mae": float(np.mean(base)),
            "carry_forward_prev_measured_mae": float(np.nanmean(cf))}


def _transfer_to_checkup(model, feats: list[str], target: str) -> dict:
    """대리 모델을 검진 forward 행(검진 전 웨어러블 보유)에 적용 — 참고용."""
    df = load_unified()
    own = df[(df["source"] == "own") & df[target].notna()]
    use = [c for c in feats if c in own.columns]
    if not use:
        return {"status": "NO_SHARED_FEATURES"}
    wear = own[[c for c in use if "__w" in c]].notna().any(axis=1)
    d = own[wear]
    if len(d) < 3:
        return {"status": "TOO_FEW_FORWARD_ROWS", "n": int(len(d))}
    X = d.reindex(columns=feats)
    p = model.predict(X); y = d[target].to_numpy()
    return {"status": "REFERENCE_ONLY", "n": int(len(d)),
            "mae_vs_checkup": round(float(mean_absolute_error(y, p)), 3),
            "bias": round(float(np.mean(p - y)), 3)}


def _measured_vs_checkup_calibration(target: str, daily: pd.DataFrame, window_days: int = 30) -> dict:
    """측정값<->검진값 눈금 보정: 검진일 ±window 내 측정 중앙값과 검진값의 선형관계."""
    channel = PROXY[target][0]
    meas = daily[daily["feature"] == channel]
    df = load_unified()
    chk = df[(df["source"] == "own") & df[target].notna()][["user_key", "event_date", target]].copy()
    chk["event_date"] = pd.to_datetime(chk["event_date"])
    pairs = []
    for r in chk.itertuples(index=False):
        m = meas[(meas["user_key"] == r.user_key)
                 & (meas["d"] >= r.event_date - pd.Timedelta(days=window_days))
                 & (meas["d"] <= r.event_date + pd.Timedelta(days=window_days))]
        if len(m):
            pairs.append((float(m["value"].median()), float(getattr(r, target))))
    if len(pairs) < 5:
        return {"n_pairs": len(pairs), "status": "TOO_FEW"}
    x, y = np.array(pairs)[:, 0], np.array(pairs)[:, 1]
    lr = LinearRegression().fit(x.reshape(-1, 1), y)
    return {"n_pairs": len(pairs), "slope": round(float(lr.coef_[0]), 3),
            "intercept": round(float(lr.intercept_), 3),
            "mae_measured_as_is": round(float(mean_absolute_error(y, x)), 3),
            "mae_after_linear_calibration": round(float(mean_absolute_error(y, lr.predict(x.reshape(-1, 1)))), 3)}


def run() -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    daily = fetch_daily_features()
    rep = {"run_at": datetime.now(timezone.utc).isoformat(), "targets": {}}
    for t in PROXY:
        ds, feats = build_proxy_dataset(t, daily)
        entry: dict = {"n_rows": int(len(ds)), "n_users": int(ds["user_key"].nunique()), "features": len(feats)}
        if len(ds) < 100:
            entry["status"] = "SKIP_FEW_ROWS"; rep["targets"][t] = entry; continue
        gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
        tr, te = next(gss.split(ds, groups=ds["user_key"]))
        train, sealed = ds.iloc[tr], ds.iloc[te]
        entry["cv"] = {k: round(v, 3) for k, v in _cv(train, feats).items()}
        model = _model().fit(train[feats], train["y"])
        p = model.predict(sealed[feats]); y = sealed["y"].to_numpy()
        prev = sealed["y_prev"]; ok = prev.notna().to_numpy()
        entry["sealed"] = {
            "n_users": int(sealed["user_key"].nunique()), "n_rows": int(len(sealed)),
            "mae": round(float(mean_absolute_error(y, p)), 3), "r2": round(float(r2_score(y, p)), 3),
            "baseline_mean_mae": round(float(mean_absolute_error(y, np.full(len(y), train["y"].mean()))), 3),
            "carry_forward_prev_measured_mae": round(float(mean_absolute_error(y[ok], prev[ok])), 3) if ok.sum() else None,
        }
        joblib.dump({"model": model, "features": feats, "target": t, "proxy_channel": PROXY[t][0]},
                    OUT_DIR / f"proxy_{t}.joblib")
        entry["transfer_to_checkup"] = _transfer_to_checkup(model, feats, t)
        entry["measured_vs_checkup_calibration"] = _measured_vs_checkup_calibration(t, daily)
        entry["status"] = "TRAINED"
        rep["targets"][t] = entry
    with open(OUT_DIR / "proxy_report.json", "w") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    return rep
