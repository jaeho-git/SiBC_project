"""트랙 1 — M1 개인화 모델 학습·검증 파이프라인 (v3).

입력: 직전 검진값(앵커) + 경과일 + 추세 + 다른 항목 직전값 + 인구통계
      + (있으면) 웨어러블 관측창  ->  다음 검진의 실제값 (항목별)

절차
1. 자체(own) 행에서 대상값·앵커가 모두 있는 행 선별 (항목별)
2. 사용자 20%를 봉인 테스트로 분리 (마지막 1회 평가 전용)
3. 학습 사용자 내 GroupKFold(5)로 후보 비교 -> 항목별 최적 선택
   후보: elasticnet / hist_gbm / random_forest / mixed_effects(경험적 베이즈 축소)
4. 승격 규칙(사전 규정, 봉인셋 미참조): carry-forward 대비 >=3% 개선 & 과반 폴드 승리
   & 표본 정책(학습>=100명, 봉인>=30명) -> MODEL, 아니면 CARRY_FORWARD
5. 예측구간: (a) 상수 오프셋(잔차 분위수) (b) CQR(분위수 회귀 + 컨포멀 보정) —
   봉인 PICP>=0.80 이면서 더 좁은 쪽 채택
6. 교차특징 변형(MODEL_CROSS): 자체 앵커가 부족한 항목(지질)은 다른 항목 앵커·demo로
   학습해 모집단 평균 대비 개선 시 채택
7. ABSTAIN: 앵커 없음 / 앵커 3년 초과. 산출: 모델, configs/m1_serving_rules.json, 리포트, 레지스트리
"""
from __future__ import annotations

import json
import math
import warnings
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .env import PROJECT_ROOT
from .schema import target_names
from .unified import load_unified

warnings.filterwarnings("ignore")

RESULTS_DIR = PROJECT_ROOT / "01_Results" / "m1"
RULES_PATH = PROJECT_ROOT / "configs" / "m1_serving_rules.json"
REGISTRY = PROJECT_ROOT / "01_Results" / "model_registry.jsonl"

SEALED_FRACTION = 0.2
N_FOLDS = 5
MIN_IMPROVEMENT = 0.03
MAX_ANCHOR_AGE_DAYS = 3 * 365
MIN_ROWS = 60
INTERVAL_NOMINAL = 0.85
_Q_LO, _Q_HI = (1 - INTERVAL_NOMINAL) / 2 * 100, (1 + INTERVAL_NOMINAL) / 2 * 100
CROSS_TARGETS = {"total_cholesterol", "hdl", "ldl", "triglyceride"}  # 앵커 희소 항목


# ---------------------------------------------------------------- 혼합효과(경험적 베이즈) 추정기

class EBShrinkageRegressor(BaseEstimator, RegressorMixin):
    """경험적 베이즈 축소: 사용자 이력 평균과 (성별x연령대) 모집단 평균을 분산비로 가중.

    pred = w*user_mean + (1-w)*pop_mean,  w = n_i*tau2 / (n_i*tau2 + sigma2)
    - user_mean: 직전값·직전-직전값 평균 (n_i = 보유 개수)
    - sigma2(개인 내 잡음) ~ var(y - anchor)/2, tau2(개인 간 분산) ~ var(anchor) - sigma2
    """

    def __init__(self, target: str = "sbp"):
        self.target = target

    def fit(self, X, y):
        X = pd.DataFrame(X); y = np.asarray(y, dtype=float)
        a = X[f"anchor_prev_label__{self.target}"].to_numpy(float)
        band = pd.cut(X["demo_age"], [0, 30, 40, 50, 60, 70, 200], labels=False)
        key = pd.Series(list(zip(X["demo_sex"].to_numpy(), band.to_numpy())))
        self.pop_ = pd.Series(y).groupby(key.to_numpy()).mean().to_dict()
        self.global_ = float(np.nanmean(y))
        within = float(np.nanvar(y - a) / 2.0)
        self.sigma2_ = max(within, 1e-6)
        self.tau2_ = max(float(np.nanvar(a)) - within, 1e-6)
        return self

    def predict(self, X):
        X = pd.DataFrame(X)
        a = X[f"anchor_prev_label__{self.target}"].to_numpy(float)
        p2 = X[f"trend_prev2__{self.target}"].to_numpy(float) if f"trend_prev2__{self.target}" in X else np.full(len(X), np.nan)
        hist = np.vstack([a, p2])
        n_i = np.sum(~np.isnan(hist), axis=0)
        user_mean = np.nanmean(np.where(np.isnan(hist), np.nan, hist), axis=0)
        band = pd.cut(X["demo_age"], [0, 30, 40, 50, 60, 70, 200], labels=False)
        pop = np.array([self.pop_.get((s, b), self.global_) for s, b in zip(X["demo_sex"], band)], float)
        pop = np.where(np.isnan(pop), self.global_, pop)
        w = n_i * self.tau2_ / (n_i * self.tau2_ + self.sigma2_)
        pred = w * np.nan_to_num(user_mean, nan=0.0) + (1 - w) * pop
        return np.where(n_i == 0, pop, pred)


def _candidates(t: str) -> dict:
    return {
        "elasticnet": Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()),
                                ("model", ElasticNet(alpha=0.3, l1_ratio=0.5, max_iter=5000))]),
        "hist_gbm": Pipeline([("impute", SimpleImputer(strategy="median")),
                              ("model", HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=300,
                                                                      l2_regularization=1.0, min_samples_leaf=20,
                                                                      random_state=42))]),
        "random_forest": Pipeline([("impute", SimpleImputer(strategy="median")),
                                   ("model", RandomForestRegressor(n_estimators=300, max_depth=6, min_samples_leaf=5,
                                                                   n_jobs=-1, random_state=42))]),
        "mixed_effects": EBShrinkageRegressor(target=t),
    }


def _quantile_model(q: float) -> Pipeline:
    return Pipeline([("impute", SimpleImputer(strategy="median")),
                     ("model", HistGradientBoostingRegressor(loss="quantile", quantile=q, max_depth=3,
                                                             learning_rate=0.05, max_iter=300, l2_regularization=1.0,
                                                             min_samples_leaf=20, random_state=42))])


# ---------------------------------------------------------------- 데이터 구성

def _add_trend(own: pd.DataFrame, t: str) -> pd.DataFrame:
    own = own.sort_values(["user_key", "event_date"]).copy()
    ed = pd.to_datetime(own["event_date"])
    prev2 = own.groupby("user_key")[t].shift(2)
    d2 = (ed - ed.groupby(own["user_key"]).shift(2)).dt.days
    prev1, d1 = own[f"anchor_prev_label__{t}"], own[f"anchor_days_since__{t}"]
    own[f"trend_prev2__{t}"] = prev2
    gap = (d2 - d1).replace(0, np.nan)
    own[f"trend_slope_per_year__{t}"] = (prev1 - prev2) / gap * 365.0
    return own


def build_m1_dataset(t: str, require_anchor: bool = True) -> tuple[pd.DataFrame, list[str]]:
    df = load_unified()
    own = df[df["source"] == "own"].copy()
    anchor, days = f"anchor_prev_label__{t}", f"anchor_days_since__{t}"
    own = _add_trend(own, t)
    d = own[own[t].notna()].copy()
    if require_anchor:
        d = d[d[anchor].notna()].copy()
    d["abstain"] = d[days].fillna(0) > MAX_ANCHOR_AGE_DAYS
    feats = [c for c in d.columns if (
        c.startswith("anchor_prev_label__") or c.startswith("anchor_days_since__")
        or c.startswith("trend_") or c in ("demo_age", "demo_sex")
        or ("__w" in c and not c.startswith(("anchor", "trend")))
    ) and d[c].dtype.kind in "if"]
    feats = [c for c in feats if d[c].notna().mean() >= 0.05]
    if not require_anchor:  # 교차 변형: mixed_effects가 요구하는 자기 앵커 컬럼은 유지(대부분 결측)
        for c in (anchor, f"trend_prev2__{t}"):
            if c in d.columns and c not in feats:
                feats.append(c)
    return d, feats


# ---------------------------------------------------------------- 학습·검증

def _sealed_split(d: pd.DataFrame, seed: int = 42):
    gss = GroupShuffleSplit(n_splits=1, test_size=SEALED_FRACTION, random_state=seed)
    tr, te = next(gss.split(d, groups=d["user_key"]))
    return d.iloc[tr].copy(), d.iloc[te].copy()


def _conformal_q(scores: np.ndarray, coverage: float) -> float:
    s = np.sort(scores[~np.isnan(scores)])
    n = len(s)
    k = min(n - 1, max(0, math.ceil((n + 1) * coverage) - 1))
    return float(s[k])


def _cv_compare(train: pd.DataFrame, feats: list[str], t: str, baseline: str = "cf") -> dict:
    """후보별 GroupKFold. baseline='cf'(직전값) 또는 'mean'(모집단 평균, 교차 변형용)."""
    anchor = f"anchor_prev_label__{t}"
    gkf = GroupKFold(n_splits=min(N_FOLDS, train["user_key"].nunique()))
    splits = list(gkf.split(train, groups=train["user_key"]))
    y_all = train[t].to_numpy()
    if baseline == "cf":
        base_resid = y_all - train[anchor].to_numpy()
    else:
        base_resid = y_all - y_all.mean()
    b_lo, b_hi = float(np.nanpercentile(base_resid, _Q_LO)), float(np.nanpercentile(base_resid, _Q_HI))

    out = {}
    for name, est in _candidates(t).items():
        fold_mae, fold_base, oof = [], [], np.full(len(train), np.nan)
        for tr, te in splits:
            m = clone(est).fit(train.iloc[tr][feats], train.iloc[tr][t])
            pred = m.predict(train.iloc[te][feats]); y = y_all[te]
            fold_mae.append(mean_absolute_error(y, pred))
            fold_base.append(mean_absolute_error(y, train.iloc[te][anchor]) if baseline == "cf"
                             else mean_absolute_error(y, np.full(len(y), train.iloc[tr][t].mean())))
            oof[te] = y - pred
        out[name] = {
            "cv_mae": float(np.mean(fold_mae)), "cv_mae_std": float(np.std(fold_mae)),
            "base_mae": float(np.mean(fold_base)),
            "fold_wins_vs_base": int(sum(a < b for a, b in zip(fold_mae, fold_base))), "n_folds": len(fold_mae),
            "resid_q_lo": float(np.nanpercentile(oof, _Q_LO)), "resid_q_hi": float(np.nanpercentile(oof, _Q_HI)),
            "base_resid_q_lo": b_lo, "base_resid_q_hi": b_hi,
        }
    # CQR: OOF 분위수 예측 + 컨포멀 보정량 Q
    qlo, qhi = np.full(len(train), np.nan), np.full(len(train), np.nan)
    for tr, te in splits:
        qlo[te] = clone(_quantile_model(_Q_LO / 100)).fit(train.iloc[tr][feats], train.iloc[tr][t]).predict(train.iloc[te][feats])
        qhi[te] = clone(_quantile_model(_Q_HI / 100)).fit(train.iloc[tr][feats], train.iloc[tr][t]).predict(train.iloc[te][feats])
    E = np.maximum(qlo - y_all, y_all - qhi)
    Q = _conformal_q(E, INTERVAL_NOMINAL)
    out["_cqr"] = {"Q": Q, "oof_picp": float(np.mean((y_all >= qlo - Q) & (y_all <= qhi + Q))),
                   "oof_width": float(np.mean((qhi + Q) - (qlo - Q)))}
    return out


def _policy_thresholds() -> tuple[int, int]:
    from .unified import load_policy
    ev = load_policy()["evaluation"]
    return int(ev.get("train_min_users", 100)), int(ev.get("sealed_test_min_users", 30))


def _promotion_rule(best: dict, n_users_train: int | None = None, n_users_sealed: int | None = None) -> str:
    wins = best.get("fold_wins_vs_base", best.get("fold_wins_vs_cf", 0))
    base = best.get("base_mae", best.get("cf_mae"))
    improved = best["cv_mae"] < base * (1 - MIN_IMPROVEMENT)
    majority = wins * 2 > best["n_folds"]
    if n_users_train is not None and n_users_sealed is not None:
        mt, ms = _policy_thresholds()
        if n_users_train < mt or n_users_sealed < ms:
            return "CARRY_FORWARD"
    return "MODEL" if (improved and majority) else "CARRY_FORWARD"


def _promotion_reason(best: dict, n_users_train: int, n_users_sealed: int) -> str:
    mt, ms = _policy_thresholds()
    wins = best.get("fold_wins_vs_base", best.get("fold_wins_vs_cf", 0))
    base = best.get("base_mae", best.get("cf_mae"))
    if n_users_train < mt or n_users_sealed < ms:
        return f"insufficient_users(train={n_users_train}<{mt} or sealed={n_users_sealed}<{ms})"
    if not best["cv_mae"] < base * (1 - MIN_IMPROVEMENT):
        return "improvement_below_threshold"
    if not wins * 2 > best["n_folds"]:
        return "not_majority_folds"
    return "promoted"


def _sealed_eval(model, sealed: pd.DataFrame, feats: list[str], t: str, best: dict, route: str,
                 q_models: tuple | None, Q: float | None, point_is_model: bool) -> dict:
    y = sealed[t].to_numpy()
    pred = model.predict(sealed[feats])
    anchor = f"anchor_prev_label__{t}"
    base_point = sealed[anchor].to_numpy() if anchor in sealed and sealed[anchor].notna().all() else np.full(len(y), np.nan)
    point = pred if point_is_model else base_point
    c_lo, c_hi = point + best["resid_q_lo"], point + best["resid_q_hi"]
    if not point_is_model:
        c_lo, c_hi = point + best["base_resid_q_lo"], point + best["base_resid_q_hi"]
    res = {
        "n_users": int(sealed["user_key"].nunique()), "n_rows": int(len(sealed)),
        "mae": round(float(mean_absolute_error(y, pred)), 3),
        "rmse": round(float(np.sqrt(mean_squared_error(y, pred))), 3),
        "r2": round(float(r2_score(y, pred)), 3), "bias": round(float(np.mean(pred - y)), 3),
        "nominal_coverage": INTERVAL_NOMINAL,
        "constant": {"picp": round(float(np.nanmean((y >= c_lo) & (y <= c_hi))), 3),
                     "width": round(float(np.nanmean(c_hi - c_lo)), 3)},
    }
    if not np.isnan(base_point).all():
        res["carry_forward_mae"] = round(float(mean_absolute_error(y, base_point)), 3)
    if q_models is not None:
        lo = q_models[0].predict(sealed[feats]) - Q; hi = q_models[1].predict(sealed[feats]) + Q
        lo, hi = np.minimum(lo, point), np.maximum(hi, point)  # 점추정 포함 보장
        res["cqr"] = {"picp": round(float(np.mean((y >= lo) & (y <= hi))), 3),
                      "width": round(float(np.mean(hi - lo)), 3)}
    return res


def _choose_interval(sealed_res: dict) -> str:
    """커버리지(>=0.80) 충족을 최우선, 둘 다 충족하면 더 좁은 쪽, 둘 다 미달이면 더 높은 PICP."""
    c, q = sealed_res["constant"], sealed_res.get("cqr")
    if not q:
        return "constant"
    c_ok, q_ok = c["picp"] >= 0.80, q["picp"] >= 0.80
    if c_ok and q_ok:
        return "cqr" if q["width"] < c["width"] else "constant"
    if q_ok:
        return "cqr"
    if c_ok:
        return "constant"
    return "cqr" if q["picp"] > c["picp"] else "constant"


def _fit_and_eval(t: str, d: pd.DataFrame, feats: list[str], out_dir, baseline: str, seed: int):
    train, sealed = _sealed_split(d, seed)
    cv = _cv_compare(train, feats, t, baseline=baseline)
    cqr_info = cv.pop("_cqr")
    best_name = min(cv, key=lambda k: cv[k]["cv_mae"]); best = cv[best_name]
    n_tr, n_se = int(train["user_key"].nunique()), int(sealed["user_key"].nunique())
    route = _promotion_rule(best, n_tr, n_se)
    reason = _promotion_reason(best, n_tr, n_se)
    model = clone(_candidates(t)[best_name]).fit(train[feats], train[t])
    q_models = (clone(_quantile_model(_Q_LO / 100)).fit(train[feats], train[t]),
                clone(_quantile_model(_Q_HI / 100)).fit(train[feats], train[t]))
    point_is_model = route == "MODEL"
    sealed_res = _sealed_eval(model, sealed, feats, t, best, route, q_models, cqr_info["Q"], point_is_model)
    interval_method = _choose_interval(sealed_res)
    tag = "cross_" if baseline == "mean" else ""
    joblib.dump({"model": model, "features": feats, "target": t, "q_lo_model": q_models[0],
                 "q_hi_model": q_models[1], "cqr_Q": cqr_info["Q"],
                 "resid_q_lo": best["resid_q_lo"], "resid_q_hi": best["resid_q_hi"],
                 "base_resid_q_lo": best["base_resid_q_lo"], "base_resid_q_hi": best["base_resid_q_hi"]},
                out_dir / f"{tag}{t}.joblib")
    return {"train": train, "sealed": sealed, "cv": cv, "cqr": cqr_info, "best_name": best_name, "best": best,
            "n_tr": n_tr, "n_se": n_se, "route": route, "reason": reason, "sealed_res": sealed_res,
            "interval_method": interval_method, "model_file": f"{tag}{t}.joblib"}


def _round(d: dict) -> dict:
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items()}


def train_m1(version: str = "m1_v3", seed: int = 42) -> dict:
    out_dir = RESULTS_DIR / version
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"version": version, "trained_at": datetime.now(timezone.utc).isoformat(),
              "policy": {"sealed_fraction": SEALED_FRACTION, "n_folds": N_FOLDS, "min_improvement": MIN_IMPROVEMENT,
                         "max_anchor_age_days": MAX_ANCHOR_AGE_DAYS, "interval_nominal": INTERVAL_NOMINAL},
              "targets": {}}
    rules = {}
    for t in target_names():
        d, feats = build_m1_dataset(t)
        usable = d[~d["abstain"]]
        entry: dict = {"n_rows_usable": int(len(usable)), "n_users": int(usable["user_key"].nunique()),
                       "n_abstain_stale_anchor": int(d["abstain"].sum()), "features": len(feats)}
        rule: dict = {"max_anchor_age_days": MAX_ANCHOR_AGE_DAYS, "nominal_coverage": INTERVAL_NOMINAL}

        if len(usable) >= MIN_ROWS:
            r = _fit_and_eval(t, usable, feats, out_dir, "cf", seed)
            entry.update({"status": "TRAINED", "best_model": r["best_name"], "route": r["route"],
                          "route_reason": r["reason"], "n_users_train": r["n_tr"], "n_users_sealed": r["n_se"],
                          "cv": {k: _round(v) for k, v in r["cv"].items()}, "cqr_oof": _round(r["cqr"]),
                          "sealed": r["sealed_res"], "interval_method": r["interval_method"]})
            active_off = ([r["best"]["resid_q_lo"], r["best"]["resid_q_hi"]] if r["route"] == "MODEL"
                          else [r["best"]["base_resid_q_lo"], r["best"]["base_resid_q_hi"]])
            rule.update({"route": r["route"], "reason": r["reason"],
                         "model": r["best_name"] if r["route"] == "MODEL" else None, "model_file": r["model_file"],
                         "interval_method": r["interval_method"], "cqr_Q": round(r["cqr"]["Q"], 3),
                         "interval_offsets": [round(active_off[0], 3), round(active_off[1], 3)],
                         "cv_mae": round(r["best"]["cv_mae"], 3), "cv_carry_forward_mae": round(r["best"]["base_mae"], 3),
                         "sealed_picp": r["sealed_res"]["cqr" if r["interval_method"] == "cqr" else "constant"]["picp"]})
        else:
            entry["status"] = "SKIP_FEW_ROWS"
            rule.update({"route": "ABSTAIN", "reason": "insufficient_rows"})

        # 교차특징 변형: 앵커 부족으로 MODEL 미달인 지질 항목
        if t in CROSS_TARGETS and rule.get("route") != "MODEL":
            d2, feats2 = build_m1_dataset(t, require_anchor=False)
            d2 = d2[~d2["abstain"]]
            if len(d2) >= MIN_ROWS:
                r2 = _fit_and_eval(t, d2, feats2, out_dir, "mean", seed)
                cross_route = "MODEL_CROSS" if r2["route"] == "MODEL" else "NOT_PROMOTED"
                entry["cross"] = {"n_rows": int(len(d2)), "n_users": int(d2["user_key"].nunique()),
                                  "best_model": r2["best_name"], "route": cross_route, "reason": r2["reason"],
                                  "cv": {k: _round(v) for k, v in r2["cv"].items()},
                                  "sealed_vs_mean": r2["sealed_res"], "interval_method": r2["interval_method"]}
                if cross_route == "MODEL_CROSS":
                    # 하이브리드: 신선한 자기 앵커가 있는 사용자는 직전값(CF)이 더 정확 -> 서빙에서 CF 우선
                    if rule.get("route") == "CARRY_FORWARD":
                        rule["cf_interval_offsets"] = rule.get("interval_offsets")
                    rule.update({"route": "MODEL_CROSS", "reason": "cross_promoted(" + r2["reason"] + ")",
                                 "model": r2["best_name"], "model_file": r2["model_file"],
                                 "interval_method": r2["interval_method"], "cqr_Q": round(r2["cqr"]["Q"], 3),
                                 "interval_offsets": [round(r2["best"]["resid_q_lo"], 3), round(r2["best"]["resid_q_hi"], 3)],
                                 "cv_mae": round(r2["best"]["cv_mae"], 3), "cv_mean_baseline_mae": round(r2["best"]["base_mae"], 3),
                                 "sealed_picp": r2["sealed_res"]["cqr" if r2["interval_method"] == "cqr" else "constant"]["picp"]})
        report["targets"][t] = entry
        rules[t] = rule

    with open(out_dir / "m1_report.json", "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(RULES_PATH, "w") as f:
        json.dump({"version": version, "rules": rules}, f, ensure_ascii=False, indent=2)
    _record_lineage(version, report)
    return report


def _record_lineage(version: str, report: dict) -> None:
    trained = [t for t, e in report["targets"].items() if e.get("status") == "TRAINED"]
    entry = {"version": version, "track": "M1_personalized", "source": "own_only",
             "trained_at": report["trained_at"], "targets_trained": trained,
             "routes": {t: report["targets"][t].get("route") for t in trained}}
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
