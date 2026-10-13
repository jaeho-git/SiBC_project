"""M2 고도화: 웨어러블 '직접 측정값'을 검진 추정에 융합 + 고위험 안내 기준점 + 시간 순서 검증.

배경(2026-09-17 데이터 점검): '착용 뒤 검진' 정답지는 15명으로 여전히 게이트(30명) 미달이라
걸음·심박·수면 같은 간접 신호는 학습·검증할 수 없다. 반면 웨어러블 혈압계·체중계 측정값은
415명/373명에게 쌓여 있고, 검진일 전후로 짝지을 수 있는 쌍이 수십~백여 개 있다.
→ 현실적으로 검증 가능한 고도화는 '측정값 융합(nowcast)'이다.

구성
  1) crossfit_base      : M1 서빙 경로(모델/직전값)의 교차적합(out-of-fold) 예측
  2) calibration_check  : 고위험 과소예측이 '보정 가능한 편향'인지 '평균 회귀'인지 진단
  3) fusion             : base + 측정 중앙값 → 검진값 (사용자 단위 반복 교차검증, 부트스트랩 CI)
  4) referral           : 기준 초과 플래그의 안내 기준점(민감도 >= 0.85 사전 고정)과 최종 검증
  5) temporal           : 2025-01-01 이전 학습 → 이후 검진 평가
  6) m0_floor           : 검진 이력 없는 사용자용 경로(측정값 단독, 한국인 성·연령 기준) 오차
  7) serve_m2           : 사용자당 1행 M2 산출

평가 원칙: 선택(가중치·기준점)은 학습 사용자/교차검증 안에서만 하고, 최종 검증 사용자는 1회만 본다.
융합 쌍은 검진 '전후' 대칭 창(±PAIR_WINDOW일)을 쓴다 — 예측(forecast)이 아니라 '현재값 추정(nowcast)'의
일치도 검증이며, 엄밀한 정방향(측정→검진) 쌍 결과는 참고로 함께 기록한다.
"""
from __future__ import annotations

import json
import warnings
from datetime import date, datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GroupKFold

from .env import PROJECT_ROOT
from .m1 import RESULTS_DIR as M1_DIR
from .m1 import RULES_PATH, _candidates, _sealed_split, build_m1_dataset
from .unified import load_unified

warnings.filterwarnings("ignore")
OUT_DIR = PROJECT_ROOT / "01_Results" / "m2"
RULES_M2 = PROJECT_ROOT / "configs" / "m2_rules.json"
PAIR_WINDOW = 180            # 사전 고정(민감도 분석: 90, 365)
SERVE_LOOKBACK = 180         # 서빙 시 기준일 이전 측정 사용 기간
TARGET_SENSITIVITY = 0.85    # 안내 기준점 사전 고정
TEMPORAL_CUTOFF = "2025-01-01"
INTERVAL = (0.075, 0.925)
FUSE = {"sbp": "bp_systolic_measured", "dbp": "bp_diastolic_measured", "weight": "body_weight_measured"}
HIGH = {"sbp": 140, "dbp": 90, "fasting_glucose": 126}
AGE_BINS, AGE_LABELS = [0, 30, 40, 50, 60, 70, 200], ["<30", "30s", "40s", "50s", "60s", "70+"]


def _m1_rules() -> dict:
    return json.loads(RULES_PATH.read_text())


def _mae(a, b) -> float:
    return float(np.mean(np.abs(np.asarray(a, float) - np.asarray(b, float))))


def _boot_diff(df: pd.DataFrame, a: str, b: str, y: str = "y", B: int = 2000, seed: int = 42) -> list[float]:
    """사용자 단위 부트스트랩: MAE(a) - MAE(b) 의 95% CI (음수면 a가 더 정확)."""
    rng = np.random.default_rng(seed)
    users = df["user_key"].unique()
    ea = (df[a] - df[y]).abs().groupby(df["user_key"]).agg(["sum", "size"])
    eb = (df[b] - df[y]).abs().groupby(df["user_key"]).sum()
    sa, n, sb = ea["sum"].reindex(users).to_numpy(), ea["size"].reindex(users).to_numpy(), eb.reindex(users).to_numpy()
    out = []
    for _ in range(B):
        i = rng.integers(0, len(users), len(users))
        out.append(sa[i].sum() / n[i].sum() - sb[i].sum() / n[i].sum())
    return [round(float(np.percentile(out, 2.5)), 2), round(float(np.percentile(out, 97.5)), 2)]


# ---------------------------------------------------------------- 1) 교차적합 base

def crossfit_base(t: str, seed: int = 42) -> pd.DataFrame:
    """M1 서빙 경로와 동일한 base 예측을 모든 자체 행에 out-of-fold로 부여."""
    rule = _m1_rules()["rules"].get(t, {})
    d, feats = build_m1_dataset(t)
    d = d[~d["abstain"]].copy().reset_index(drop=True)
    anchor = d[f"anchor_prev_label__{t}"].to_numpy(float)
    d["cf"] = anchor
    if rule.get("route") == "MODEL":
        rep = json.loads((M1_DIR / _m1_rules()["version"] / "m1_report.json").read_text())
        best = rep["targets"][t]["best_model"]
        users = d["user_key"].unique()
        rng = np.random.default_rng(seed); rng.shuffle(users)
        fold = {u: i % 5 for i, u in enumerate(users)}
        f = d["user_key"].map(fold).to_numpy()
        oof = np.full(len(d), np.nan)
        for k in range(5):
            m = clone(_candidates(t)[best]).fit(d.loc[f != k, feats], d.loc[f != k, t])
            oof[f == k] = m.predict(d.loc[f == k, feats])
        d["base"], d["base_kind"] = oof, f"M1:{best}"
    else:
        d["base"], d["base_kind"] = anchor, "CARRY_FORWARD"
    d["y"] = d[t].to_numpy(float)
    return d[["user_key", "event_date", "y", "cf", "base", "base_kind", "demo_sex", "demo_age"]]


# ---------------------------------------------------------------- 2) 보정 진단

def calibration_check(t: str) -> dict:
    """'실제값이 높은 사람'에서의 음의 편향이 고칠 수 있는 편향인지 진단.

    - slope(y ~ pred): 1에 가까우면 예측값 기준으로는 보정돼 있음(=평균 회귀 현상)
    - 예측 상위 10% 구간의 (실제-예측): 0에 가까우면 '높게 예측한 사람'은 맞게 예측
    """
    d = crossfit_base(t)
    lr = LinearRegression().fit(d[["base"]], d["y"])
    top = d[d["base"] >= d["base"].quantile(0.9)]
    out = {"n": int(len(d)), "slope_y_on_pred": round(float(lr.coef_[0]), 3), "intercept": round(float(lr.intercept_), 2),
           "top_decile_pred": {"n": int(len(top)), "mean_pred": round(float(top["base"].mean()), 1),
                               "mean_actual": round(float(top["y"].mean()), 1),
                               "gap_actual_minus_pred": round(float((top["y"] - top["base"]).mean()), 2)}}
    if t in HIGH:
        hi = d[d["y"] >= HIGH[t]]
        out["actual_high"] = {"n": int(len(hi)), "bias_pred_minus_actual": round(float((hi["base"] - hi["y"]).mean()), 2),
                              "bias_carry_forward": round(float((hi["cf"] - hi["y"]).mean()), 2)}
        # 기울기 확대 재보정(y = a + b*pred)의 효과: 교차적합 안에서 다시 교차검증
        users = d["user_key"].unique(); fold = {u: i % 5 for i, u in enumerate(users)}
        f = d["user_key"].map(fold).to_numpy(); rec = np.full(len(d), np.nan)
        for k in range(5):
            m = LinearRegression().fit(d.loc[f != k, ["base"]], d.loc[f != k, "y"])
            rec[f == k] = m.predict(d.loc[f == k, ["base"]])
        d["recal"] = rec; hi = d[d["y"] >= HIGH[t]]
        out["linear_recalibration"] = {"mae_before": round(_mae(d["base"], d["y"]), 2), "mae_after": round(_mae(d["recal"], d["y"]), 2),
                                       "high_bias_after": round(float((hi["recal"] - hi["y"]).mean()), 2)}
    return out


# ---------------------------------------------------------------- 3) 측정값 융합

def _pairs(t: str, daily: pd.DataFrame, window: int, forward_only: bool = False) -> pd.DataFrame:
    """검진 행 × 검진일 ±window일(또는 이전 window일) 안의 측정 중앙값."""
    own = load_unified(); own = own[(own["source"] == "own") & own[t].notna()][["user_key", "event_date", t, "demo_sex", "demo_age"]].copy()
    own["event_date"] = pd.to_datetime(own["event_date"])
    m = daily[daily["feature"] == FUSE[t]][["user_key", "d", "value"]]
    j = own.merge(m, on="user_key")
    gap = (j["d"] - j["event_date"]).dt.days
    j = j[(gap >= -window) & (gap <= (-1 if forward_only else window))]
    g = j.groupby(["user_key", "event_date"]).agg(meas=("value", "median"), n_meas=("value", "size")).reset_index()
    base = crossfit_base(t); base["event_date"] = pd.to_datetime(base["event_date"])
    out = own.rename(columns={t: "y"}).merge(g, on=["user_key", "event_date"]).merge(
        base[["user_key", "event_date", "cf", "base"]], on=["user_key", "event_date"], how="left")
    return out


def _kr_ref(df: pd.DataFrame, t: str) -> np.ndarray:
    ref = pd.read_parquet(PROJECT_ROOT / "00_Data" / "processed" / "korean_calibration_reference.parquet")
    ref = ref[ref["target"] == t]
    key = {(float(r.sex), r.age_band): r.mean for r in ref.itertuples()}
    band = pd.cut(df["demo_age"], AGE_BINS, labels=AGE_LABELS).astype(str)
    glob = float(np.average(ref["mean"], weights=ref["n"]))
    return np.array([key.get((float(s) if pd.notna(s) else np.nan, b), glob) for s, b in zip(df["demo_sex"], band)], float)


def _repeated_cv(df: pd.DataFrame, cols: list[str], repeats: int = 10) -> np.ndarray:
    """사용자 단위 5겹 교차검증을 반복해 행별 out-of-fold 예측 평균을 돌려준다."""
    users = df["user_key"].unique(); acc = np.zeros(len(df))
    for r in range(repeats):
        rng = np.random.default_rng(100 + r); u = users.copy(); rng.shuffle(u)
        fold = {x: i % 5 for i, x in enumerate(u)}; f = df["user_key"].map(fold).to_numpy()
        p = np.full(len(df), np.nan)
        for k in range(5):
            m = LinearRegression(positive=True).fit(df.loc[f != k, cols], df.loc[f != k, "y"])
            p[f == k] = m.predict(df.loc[f == k, cols])
        acc += p
    return acc / repeats


def fusion(t: str, daily: pd.DataFrame, window: int = PAIR_WINDOW, fit_artifact: bool = True) -> dict:
    p = _pairs(t, daily, window).reset_index(drop=True)
    p["kr_ref"] = _kr_ref(p, t)
    res: dict = {"window_days": window, "n_pairs": int(len(p)), "n_users": int(p["user_key"].nunique())}
    # (a) 직전 검진 보유: base + meas
    a = p[p["base"].notna()].reset_index(drop=True)
    if len(a) >= 40:
        a["fused"] = _repeated_cv(a, ["base", "meas"])
        a["meas_cal"] = _repeated_cv(a, ["meas"])
        e = {"n": int(len(a)), "users": int(a["user_key"].nunique()),
             "mae_carry_forward": round(_mae(a["cf"], a["y"]), 2), "mae_base": round(_mae(a["base"], a["y"]), 2),
             "mae_measured_only": round(_mae(a["meas_cal"], a["y"]), 2), "mae_fused": round(_mae(a["fused"], a["y"]), 2),
             "fused_vs_base_ci95": _boot_diff(a, "fused", "base"), "fused_vs_cf_ci95": _boot_diff(a, "fused", "cf"),
             "r2_fused": round(float(1 - ((a["fused"] - a["y"]) ** 2).sum() / ((a["y"] - a["y"].mean()) ** 2).sum()), 3),
             "r2_base": round(float(1 - ((a["base"] - a["y"]) ** 2).sum() / ((a["y"] - a["y"].mean()) ** 2).sum()), 3)}
        e["improve_pct_vs_base"] = round(100 * (1 - e["mae_fused"] / e["mae_base"]), 1)
        if t in HIGH:
            hi = a[a["y"] >= HIGH[t]]
            if len(hi) >= 5:
                e["actual_high"] = {"n": int(len(hi)), "bias_base": round(float((hi["base"] - hi["y"]).mean()), 2),
                                    "bias_fused": round(float((hi["fused"] - hi["y"]).mean()), 2)}
        res["with_prior_checkup"] = e
        resid = (a["y"] - a["fused"]).to_numpy()
        m = LinearRegression(positive=True).fit(a[["base", "meas"]], a["y"])
        art_a = {"coef": [float(c) for c in m.coef_], "intercept": float(m.intercept_), "cols": ["base", "meas"],
                 "resid_q": [float(np.quantile(resid, INTERVAL[0])), float(np.quantile(resid, INTERVAL[1]))]}
        res["with_prior_checkup"]["weights"] = {"base": round(art_a["coef"][0], 3), "measured": round(art_a["coef"][1], 3)}
    else:
        art_a = None; res["with_prior_checkup"] = {"n": int(len(a)), "status": "TOO_FEW"}
    # (b) 검진 이력 없음 가정: 측정값 + 한국인 성·연령 기준 (모든 쌍에서 직전 검진을 '모르는 척')
    b = p[p["kr_ref"].notna()].reset_index(drop=True)
    if len(b) >= 40:
        b["m0"] = _repeated_cv(b, ["meas", "kr_ref"])
        e = {"n": int(len(b)), "users": int(b["user_key"].nunique()), "mae_korean_reference_only": round(_mae(b["kr_ref"], b["y"]), 2),
             "mae_measured_raw": round(_mae(b["meas"], b["y"]), 2), "mae_m0_measured": round(_mae(b["m0"], b["y"]), 2),
             "m0_vs_reference_ci95": _boot_diff(b, "m0", "kr_ref"),
             "r2_m0": round(float(1 - ((b["m0"] - b["y"]) ** 2).sum() / ((b["y"] - b["y"].mean()) ** 2).sum()), 3)}
        res["no_prior_checkup"] = e
        resid = (b["y"] - b["m0"]).to_numpy()
        m = LinearRegression(positive=True).fit(b[["meas", "kr_ref"]], b["y"])
        art_b = {"coef": [float(c) for c in m.coef_], "intercept": float(m.intercept_), "cols": ["meas", "kr_ref"],
                 "resid_q": [float(np.quantile(resid, INTERVAL[0])), float(np.quantile(resid, INTERVAL[1]))]}
    else:
        art_b = None; res["no_prior_checkup"] = {"n": int(len(b)), "status": "TOO_FEW"}
    # 참고: 엄밀한 정방향(측정이 검진 '이전' window일) 쌍
    fw = _pairs(t, daily, 90, forward_only=True); fw = fw[fw["base"].notna()]
    res["forward_only_reference"] = {"n": int(len(fw))}
    if len(fw) >= 5 and art_a:
        fw = fw.copy(); fw["fused"] = art_a["intercept"] + art_a["coef"][0] * fw["base"] + art_a["coef"][1] * fw["meas"]
        res["forward_only_reference"].update({"mae_base": round(_mae(fw["base"], fw["y"]), 2), "mae_fused": round(_mae(fw["fused"], fw["y"]), 2),
                                              "note": "융합 가중치 학습에 포함된 행이 섞여 있어 참고용"})
    if fit_artifact:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump({"target": t, "window": window, "with_prior": art_a, "no_prior": art_b}, OUT_DIR / f"fusion_{t}.joblib")
    return res


# ---------------------------------------------------------------- 4) 안내 기준점

def _wilson(k: int, n: int) -> list[float]:
    if n == 0:
        return [float("nan"), float("nan")]
    z = 1.96; ph = k / n; den = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / den; h = z * np.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return [round(float(c - h), 3), round(float(c + h), 3)]


def _confusion(y: np.ndarray, pred: np.ndarray) -> dict:
    tp, fn = int(((y == 1) & pred).sum()), int(((y == 1) & ~pred).sum())
    fp, tn = int(((y == 0) & pred).sum()), int(((y == 0) & ~pred).sum())
    return {"sensitivity": round(tp / max(tp + fn, 1), 3), "sens_ci95": _wilson(tp, tp + fn), "missed": fn, "positives": tp + fn,
            "specificity": round(tn / max(tn + fp, 1), 3), "ppv": round(tp / max(tp + fp, 1), 3),
            "npv": round(tn / max(tn + fn, 1), 3), "flagged_rate": round(float(pred.mean()), 3)}


def referral() -> dict:
    """플래그 확률의 안내 기준점: 학습 사용자 교차적합에서 민감도>=0.85가 되는 최대 기준점을 고정 → 최종 검증 1회."""
    from .clinical import THRESHOLDS, _clf_candidates
    crules = json.loads((PROJECT_ROOT / "configs" / "clinical_rules.json").read_text())
    out = {}
    for name, (t, label_fn, prior_fn) in THRESHOLDS.items():
        r = crules.get("thresholds", {}).get(name, {})
        if not r.get("serve"):
            continue
        d, feats = build_m1_dataset(t); d = d[~d["abstain"]].copy()
        d["yb"] = label_fn(d).astype(int); d["prior"] = prior_fn(d).astype(int)
        train, sealed = _sealed_split(d)
        best = r.get("best", "logistic"); est = _clf_candidates()[best]
        gkf = GroupKFold(n_splits=5); oof = np.full(len(train), np.nan)
        for tr, te in gkf.split(train, groups=train["user_key"]):
            oof[te] = clone(est).fit(train.iloc[tr][feats], train.iloc[tr]["yb"]).predict_proba(train.iloc[te][feats])[:, 1]
        ytr = train["yb"].to_numpy()
        cands = np.unique(np.round(oof, 3))[::-1]
        thr = 0.5
        for c in cands:  # 큰 기준점부터 낮춰가며 처음으로 목표 민감도를 넘는 지점
            if ((oof >= c) & (ytr == 1)).sum() / max((ytr == 1).sum(), 1) >= TARGET_SENSITIVITY:
                thr = float(c); break
        model = clone(est).fit(train[feats], train["yb"])
        s = model.predict_proba(sealed[feats])[:, 1]; y = sealed["yb"].to_numpy()
        out[name] = {"base_target": t, "classifier": best, "referral_threshold": round(thr, 3),
                     "train_oof_at_threshold": _confusion(ytr, oof >= thr),
                     "final_validation": {"n": int(len(y)), "users": int(sealed["user_key"].nunique()),
                                          "rule_prob_ge_0.5": _confusion(y, s >= 0.5),
                                          "rule_referral_threshold": _confusion(y, s >= thr),
                                          "rule_prior_status": _confusion(y, sealed["prior"].to_numpy() == 1),
                                          "tiers": {name_: {"n": int(mask.sum()), "share": round(float(mask.mean()), 3),
                                                            "actual_positive_rate": round(float(y[mask].mean()), 3) if mask.sum() else None}
                                                    for name_, mask in (("low", s < thr), ("caution", (s >= thr) & (s < max(0.5, thr))), ("high", s >= max(0.5, thr)))}}}
    return out


# ---------------------------------------------------------------- 5) 시간 순서 검증

def temporal(t: str) -> dict:
    rule = _m1_rules()["rules"].get(t, {})
    d, feats = build_m1_dataset(t); d = d[~d["abstain"]].copy()
    d["event_date"] = pd.to_datetime(d["event_date"])
    tr, te = d[d["event_date"] < TEMPORAL_CUTOFF], d[d["event_date"] >= TEMPORAL_CUTOFF].copy()
    if len(tr) < 100 or len(te) < 30:
        return {"status": "TOO_FEW", "n_train": int(len(tr)), "n_test": int(len(te))}
    rep = json.loads((M1_DIR / _m1_rules()["version"] / "m1_report.json").read_text())
    best = rep["targets"][t]["best_model"]
    m = clone(_candidates(t)[best]).fit(tr[feats], tr[t])
    te["pred"], te["cf"], te["y"] = m.predict(te[feats]), te[f"anchor_prev_label__{t}"], te[t]
    new_users = ~te["user_key"].isin(tr["user_key"])
    return {"cutoff": TEMPORAL_CUTOFF, "model": best, "serving_route": rule.get("route"), "n_train": int(len(tr)), "n_test": int(len(te)),
            "test_users": int(te["user_key"].nunique()), "test_rows_from_unseen_users": int(new_users.sum()),
            "mae_model": round(_mae(te["pred"], te["y"]), 2), "mae_carry_forward": round(_mae(te["cf"], te["y"]), 2),
            "diff_ci95": _boot_diff(te, "pred", "cf"),
            "improve_pct": round(100 * (1 - _mae(te["pred"], te["y"]) / _mae(te["cf"], te["y"])), 1)}



# ---------------------------------------------------------------- 5b) 잡음 한계·음성 실험·BMI 파생

def noise_ceiling(t: str) -> dict:
    """같은 사람의 연속 검진 차이로 개인 내 변동(측정·일중 변동 포함)을 추정.

    sigma_within = sd(y - 직전값)/sqrt(2). 개인의 참 수준을 완벽히 알아도 남는 평균 오차 하한 ~ 0.798*sigma_within.
    (직전 검진 2년 이내 쌍만 사용해 실제 변화의 혼입을 줄임 — 그래도 실제 변화가 섞여 하한은 다소 과대추정)
    """
    d, _ = build_m1_dataset(t); d = d[~d["abstain"]]
    d = d[d[f"anchor_days_since__{t}"] <= 730]
    diff = (d[t] - d[f"anchor_prev_label__{t}"]).to_numpy(float)
    sw = float(np.nanstd(diff) / np.sqrt(2))
    return {"n_pairs": int(len(d)), "sigma_within": round(sw, 2), "mae_floor_estimate": round(0.798 * sw, 2),
            "sd_between_persons": round(float(np.nanstd(d[t])), 2)}


def history_ablation() -> dict:
    """음성 실험 기록: 전체 방문 이력 통계·다른 혈액 항목 직전값을 입력에 추가했을 때의 교차검증 MAE(학습 사용자만)."""
    from .labels import build_label_table
    lab = build_label_table(); lab["event_date"] = pd.to_datetime(lab["event_date"]); lab = lab.sort_values(["user_key", "event_date"])
    extra = [c for c in ["ast", "alt", "ggt", "hemoglobin", "creatinine", "egfr"] if c in lab.columns]
    for c in extra:
        lab[f"xprev__{c}"] = lab.groupby("user_key")[c].shift(1)
    out = {}
    for t in ("sbp", "dbp", "fasting_glucose"):
        g = lab.groupby("user_key")[t]; h = lab[["user_key", "event_date"]].copy()
        h[f"hist_mean__{t}"] = g.transform(lambda x: x.shift(1).expanding().mean())
        h[f"hist_n__{t}"] = g.transform(lambda x: x.shift(1).expanding().count())
        h[f"hist_sd__{t}"] = g.transform(lambda x: x.shift(1).expanding().std())
        d, feats = build_m1_dataset(t); d = d[~d["abstain"]].copy(); d["event_date"] = pd.to_datetime(d["event_date"])
        d = d.merge(h, on=["user_key", "event_date"], how="left").merge(
            lab[["user_key", "event_date"] + [f"xprev__{c}" for c in extra]], on=["user_key", "event_date"], how="left")
        train, _ = _sealed_split(d)
        H = [c for c in d.columns if c.startswith("hist_")]; X = [f"xprev__{c}" for c in extra]
        gkf = GroupKFold(5)
        def cv(cols, name="elasticnet"):
            e = []
            for tr, te in gkf.split(train, groups=train["user_key"]):
                m = clone(_candidates(t)[name]).fit(train.iloc[tr][cols], train.iloc[tr][t])
                e.append(_mae(m.predict(train.iloc[te][cols]), train.iloc[te][t]))
            return round(float(np.mean(e)), 3)
        b = min(cv(feats, n) for n in ("elasticnet", "mixed_effects"))   # 현재 입력으로 얻는 최선(서빙 모델 포함)
        h1, h2 = cv(feats + H), cv(feats + H + X)
        out[t] = {"cv_mae_current_best": b, "cv_mae_plus_history": h1, "cv_mae_plus_history_and_labs": h2,
                  "best_gain_pct": round(100 * (1 - min(h1, h2) / b), 1), "adopted": bool(1 - min(h1, h2) / b >= 0.03)}
    return out


def bmi_from_fused_weight(daily: pd.DataFrame, window: int = PAIR_WINDOW) -> dict:
    """융합 체중 → BMI 파생(키 = 직전 검진의 체중/BMI에서 역산). 직전 BMI 유지와 비교."""
    p = _pairs("weight", daily, window); p = p[p["base"].notna()].reset_index(drop=True)
    u = load_unified(); u = u[u["source"] == "own"][["user_key", "event_date", "bmi", "anchor_prev_label__bmi", "anchor_prev_label__weight"]].copy()
    u["event_date"] = pd.to_datetime(u["event_date"])
    p = p.merge(u, on=["user_key", "event_date"], how="left").dropna(subset=["bmi", "anchor_prev_label__bmi", "anchor_prev_label__weight"]).reset_index(drop=True)
    if len(p) < 40:
        return {"n": int(len(p)), "status": "TOO_FEW"}
    p["fused_w"] = _repeated_cv(p, ["base", "meas"])
    p["bmi_fused"] = p["fused_w"] * p["anchor_prev_label__bmi"] / p["anchor_prev_label__weight"]
    q = p.rename(columns={"y": "y_w"}).assign(y=p["bmi"], cf_bmi=p["anchor_prev_label__bmi"])
    return {"n": int(len(q)), "mae_carry_forward": round(_mae(q["cf_bmi"], q["y"]), 3), "mae_fused": round(_mae(q["bmi_fused"], q["y"]), 3),
            "fused_vs_cf_ci95": _boot_diff(q, "bmi_fused", "cf_bmi")}


# ---------------------------------------------------------------- 5c) 가이드라인 3단계 판정의 검증

DOMAINS = {  # 영역: (수치 항목들, 주의 플래그, 위험 플래그)
    "blood_pressure": (["sbp", "dbp"], "bp_caution_120_80", "hypertension_140_90"),
    "fasting_glucose": (["fasting_glucose"], "fasting_glucose_ge100", "fasting_glucose_ge126"),
    "obesity_bmi": (["bmi"], "bmi_ge23", "obesity_bmi_ge25"),
    "abdominal_obesity": (["waist"], None, "abdominal_obesity"),
}


def combine_tier(numeric: list, p_caution, thr_caution, p_risk, thr_risk) -> str | None:
    """최종 3단계 = 수치 판정(예측값+구간 상한)과 확률 판정의 더 나쁜 쪽.

    위험: 수치 판정 위험 또는 위험 플래그 확률 >= 0.5
    주의: 수치 판정 주의, 또는 위험 플래그 확률 >= 안내 기준점, 또는 주의 플래그 확률 >= 안내 기준점
    """
    from .guideline import worst
    t = worst(*numeric)
    ok = lambda v: v is not None and not (isinstance(v, float) and np.isnan(v))
    if ok(p_risk) and p_risk >= 0.5:
        t = worst(t, "위험")
    if (ok(p_risk) and thr_risk is not None and p_risk >= thr_risk) or (ok(p_caution) and thr_caution is not None and p_caution >= thr_caution):
        t = worst(t, "주의")
    if t is None and (ok(p_risk) or ok(p_caution)):
        t = "정상"
    return t


def tier_validation(referral_rep: dict) -> dict:
    """검증 사용자(학습 미사용)에서 '예측 3단계' 대 '실제 3단계'. 수치 모델·플래그 모두 학습 사용자로만 적합."""
    from .clinical import THRESHOLDS, _clf_candidates
    from .guideline import grade_prediction, grade_value, worst
    crules = json.loads((PROJECT_ROOT / "configs" / "clinical_rules.json").read_text())["thresholds"]
    rep_m1 = json.loads((M1_DIR / _m1_rules()["version"] / "m1_report.json").read_text())
    out = {}
    for dom, (items, f_c, f_r) in DOMAINS.items():
        base_t = items[0]
        d0, _ = build_m1_dataset(base_t); d0 = d0[~d0["abstain"]].copy()
        train, sealed = _sealed_split(d0)
        key = ["user_key", "event_date"]; S = sealed[key + ["demo_sex"]].copy()
        for t in items:  # 수치 예측 + 구간 상한
            d, feats = build_m1_dataset(t); d = d[~d["abstain"]].copy()
            tr, se = d.merge(train[key], on=key), d.merge(sealed[key], on=key)
            if _m1_rules()["rules"].get(t, {}).get("route") == "MODEL":
                est = _candidates(t)[rep_m1["targets"][t]["best_model"]]
                gkf = GroupKFold(5); oof = np.full(len(tr), np.nan)
                for a, b in gkf.split(tr, groups=tr["user_key"]):
                    oof[b] = clone(est).fit(tr.iloc[a][feats], tr.iloc[a][t]).predict(tr.iloc[b][feats])
                q = float(np.nanquantile(tr[t].to_numpy() - oof, INTERVAL[1]))
                pred = clone(est).fit(tr[feats], tr[t]).predict(se[feats])
            else:
                q = float(np.nanquantile(tr[t] - tr[f"anchor_prev_label__{t}"], INTERVAL[1])); pred = se[f"anchor_prev_label__{t}"].to_numpy()
            se = se[key].assign(**{f"pred_{t}": pred, f"upper_{t}": pred + q, f"y_{t}": se[t].to_numpy(), f"prev_{t}": se[f"anchor_prev_label__{t}"].to_numpy()})
            S = S.merge(se, on=key, how="left")
        for fl in (f_c, f_r):  # 플래그 확률
            if fl is None or not crules.get(fl, {}).get("serve"):
                S[f"p_{fl}"] = np.nan; continue
            t, label_fn, _ = THRESHOLDS[fl]; d, feats = build_m1_dataset(t); d = d[~d["abstain"]].copy()
            tr, se = d.merge(train[key], on=key), d.merge(sealed[key], on=key)
            m = clone(_clf_candidates()[referral_rep[fl]["classifier"]]).fit(tr[feats], label_fn(tr).astype(int))
            S = S.merge(se[key].assign(**{f"p_{fl}": m.predict_proba(se[feats])[:, 1]}), on=key, how="left")
        thr = lambda fl: referral_rep.get(fl, {}).get("referral_threshold") if fl else None
        rows = []
        for r in S.itertuples(index=False):
            g = lambda prefix: worst(*[grade_value(t, getattr(r, f"{prefix}_{t}"), r.demo_sex) for t in items])
            num = [grade_prediction(t, getattr(r, f"pred_{t}"), getattr(r, f"upper_{t}"), r.demo_sex) for t in items]
            num_only = worst(*[grade_value(t, getattr(r, f"pred_{t}"), r.demo_sex) for t in items])
            rows.append({"actual": g("y"), "prior": g("prev"), "numeric_only": num_only,
                         "final": combine_tier(num, getattr(r, f"p_{f_c}", np.nan) if f_c else np.nan, thr(f_c), getattr(r, f"p_{f_r}"), thr(f_r))})
        R = pd.DataFrame(rows).dropna(subset=["actual", "final"])
        def summ(col):
            risk = R[R["actual"] == "위험"]; pn = R[R[col] == "정상"]
            return {"actual_risk_n": int(len(risk)),
                    "actual_risk_called_risk": round(float((risk[col] == "위험").mean()), 3) if len(risk) else None,
                    "actual_risk_called_caution_or_risk": round(float((risk[col] != "정상").mean()), 3) if len(risk) else None,
                    "actual_risk_missed_as_normal": int((risk[col] == "정상").sum()),
                    "pred_normal_n": int(len(pn)), "pred_normal_actually_risk": round(float((pn["actual"] == "위험").mean()), 3) if len(pn) else None,
                    "exact_agreement": round(float((R[col] == R["actual"]).mean()), 3),
                    "within_one_tier": round(float((R[col].map(TIER_IDX) - R["actual"].map(TIER_IDX)).abs().le(1).mean()), 3),
                    "pred_distribution": {k: int(v) for k, v in R[col].value_counts().items()}}
        out[dom] = {"n": int(len(R)), "actual_distribution": {k: int(v) for k, v in R["actual"].value_counts().items()},
                    "final": summ("final"), "numeric_only": summ("numeric_only"), "prior_status": summ("prior"),
                    "confusion_final": pd.crosstab(R["actual"], R["final"]).to_dict()}
    return out


TIER_IDX = {"정상": 0, "주의": 1, "위험": 2}


def _gate(primary_ci: list, improve_pct: float, wide_ci: list | None) -> str:
    """ADOPT: 주 분석(±180일) CI 상한<0 / PROVISIONAL: 개선>=3%이고 넓은 창(±365일) CI 상한<0 / 그 외 REJECT."""
    if primary_ci and primary_ci[1] < 0:
        return "ADOPT"
    if improve_pct >= 3.0 and wide_ci and wide_ci[1] < 0:
        return "PROVISIONAL"
    return "REJECT"

# ---------------------------------------------------------------- 6) 실행

def run(include_judgment: bool = False) -> dict:
    """수치 예측 고도화 분석. include_judgment=True 일 때만 (구) 안내 기준점·3단계 검증을 수행 — 모델 범위 밖."""
    from .features_own import fetch_daily_features
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    daily = fetch_daily_features(); daily["d"] = pd.to_datetime(daily["d"])
    rep: dict = {"run_at": datetime.now(timezone.utc).isoformat(), "m1_version": _m1_rules()["version"],
                 "policy": {"pair_window_days": PAIR_WINDOW, "target_sensitivity": TARGET_SENSITIVITY,
                            "temporal_cutoff": TEMPORAL_CUTOFF, "interval": INTERVAL}}
    rep["calibration"] = {t: calibration_check(t) for t in ("sbp", "dbp", "fasting_glucose")}
    rep["fusion"] = {t: fusion(t, daily) for t in FUSE}
    rep["fusion_window_sensitivity"] = {t: {str(w): {k: v for k, v in fusion(t, daily, w, fit_artifact=False).get("with_prior_checkup", {}).items()
                                                      if k in ("n", "mae_base", "mae_fused", "fused_vs_base_ci95")} for w in (90, 365)} for t in FUSE}
    rep["referral"] = referral() if include_judgment else {}
    rep["temporal"] = {t: temporal(t) for t in ("sbp", "dbp", "fasting_glucose", "weight", "bmi")}
    rep["noise_ceiling"] = {t: noise_ceiling(t) for t in ("sbp", "dbp", "fasting_glucose", "weight")}
    rep["history_ablation"] = history_ablation()
    rep["bmi_from_fused_weight"] = bmi_from_fused_weight(daily)
    if include_judgment:
        rep["tier_validation"] = tier_validation(rep["referral"])
    # 서빙 규칙: 융합이 base보다 유의하게(CI 상한<0) 정확한 항목만 FUSION 경로 허용
    rules = {"version": "m2_v1", "generated_at": rep["run_at"], "serve_lookback_days": SERVE_LOOKBACK, "fusion": {}, "referral": {}}
    for t, r in rep["fusion"].items():
        a, b = r.get("with_prior_checkup", {}), r.get("no_prior_checkup", {})
        wide = rep["fusion_window_sensitivity"][t].get("365", {}).get("fused_vs_base_ci95")
        ga = _gate(a.get("fused_vs_base_ci95"), a.get("improve_pct_vs_base", 0.0), wide)
        gb = "ADOPT" if b.get("m0_vs_reference_ci95", [0, 1])[1] < 0 else "REJECT"
        r["gate_with_prior"], r["gate_no_prior"] = ga, gb
        rules["fusion"][t] = {"with_prior": ga != "REJECT", "with_prior_gate": ga, "no_prior": gb == "ADOPT", "no_prior_gate": gb,
                              "artifact": f"fusion_{t}.joblib"}
    for name, r in rep.get("referral", {}).items():
        rules["referral"][name] = {"threshold": r["referral_threshold"], "base_target": r["base_target"]}
    RULES_M2.write_text(json.dumps(rules, ensure_ascii=False, indent=1))
    (OUT_DIR / "m2_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    return rep


# ---------------------------------------------------------------- 7) 서빙

def serve_m2(index_time: date | None = None) -> pd.DataFrame:
    """M1 산출(검진 보유자) + 웨어러블만 있는 사용자 → M2 산출(사용자당 1행)."""
    from .features_demo import fetch_birth_year, fetch_sex
    from .features_own import fetch_daily_features
    it = index_time or date.today()
    rules = json.loads(RULES_M2.read_text())
    m1 = pd.read_parquet(PROJECT_ROOT / "01_Results" / "serving" / f"m1_predictions_{it.isoformat()}.parquet")
    daily = fetch_daily_features(); daily["d"] = pd.to_datetime(daily["d"])
    daily = daily[(daily["d"] < pd.Timestamp(it)) & (daily["d"] >= pd.Timestamp(it) - pd.Timedelta(days=rules["serve_lookback_days"]))]
    users = pd.DataFrame({"user_key": sorted(set(m1["user_key"]) | set(daily[daily["feature"].isin(FUSE.values())]["user_key"]))})
    demo = users.merge(fetch_sex(), on="user_key", how="left")
    by = fetch_birth_year()
    demo = demo.merge(by, on="user_key", how="left") if not by.empty else demo.assign(birth_year=np.nan)
    demo["demo_age"] = it.year - demo["birth_year"]
    out = demo[["user_key", "demo_sex", "demo_age"]].merge(m1, on="user_key", how="left")
    out["has_checkup"] = out["user_key"].isin(m1["user_key"])
    for t, ch in FUSE.items():
        art = joblib.load(OUT_DIR / rules["fusion"][t]["artifact"]); ok = rules["fusion"][t]
        g = daily[daily["feature"] == ch].groupby("user_key")["value"].agg(["median", "size"]).rename(columns={"median": f"m2_meas_{t}", "size": f"m2_n_meas_{t}"})
        out = out.merge(g, on="user_key", how="left")
        out["kr_ref"] = _kr_ref(out, t)
        pred, lo, hi, route = [], [], [], []
        for r in out.itertuples(index=False):
            base, meas, kr = getattr(r, f"pred_{t}", np.nan), getattr(r, f"m2_meas_{t}"), r.kr_ref
            if pd.notna(base) and pd.notna(meas) and ok["with_prior"] and art["with_prior"]:
                a = art["with_prior"]; v = a["intercept"] + a["coef"][0] * base + a["coef"][1] * meas; q = a["resid_q"]; rt = "FUSION"
            elif pd.isna(base) and pd.notna(meas) and pd.notna(kr) and ok["no_prior"] and art["no_prior"]:
                a = art["no_prior"]; v = a["intercept"] + a["coef"][0] * meas + a["coef"][1] * kr; q = a["resid_q"]; rt = "M0_MEASURED"
            elif pd.notna(base):
                v, q, rt = base, None, "M1_ONLY"
            else:
                v, q, rt = np.nan, None, "ABSTAIN"
            pred.append(v); route.append(rt)
            lo.append(v + q[0] if q else getattr(r, f"pred_{t}_lower", np.nan)); hi.append(v + q[1] if q else getattr(r, f"pred_{t}_upper", np.nan))
        out[f"m2_pred_{t}"], out[f"m2_lower_{t}"], out[f"m2_upper_{t}"], out[f"m2_route_{t}"] = np.round(pred, 1), np.round(lo, 1), np.round(hi, 1), route
    # BMI 파생: 융합/측정 체중 × (직전 BMI / 직전 체중). 키를 모르는 사용자(검진 이력 없음)는 산출하지 않음
    if {"actual_bmi", "actual_weight"} <= set(out.columns):
        ratio = out["actual_bmi"] / out["actual_weight"]
        use = out["m2_route_weight"].isin(["FUSION"]) & ratio.notna()
        out["m2_pred_bmi"] = np.where(use, np.round(out["m2_pred_weight"] * ratio, 1), out.get("pred_bmi", np.nan))
        out["m2_route_bmi"] = np.where(use, "FUSION_DERIVED", np.where(out.get("pred_bmi", pd.Series(np.nan, index=out.index)).notna(), "M1_ONLY", "ABSTAIN"))
    # 안내 기준점 적용(기존 플래그 확률 재사용)
    for name, r in rules["referral"].items():
        col = f"flag_{name}_prob"
        if col in out.columns:
            out[f"refer_{name}"] = np.where(out[col].notna(), out[col] >= r["threshold"], None)
            out[f"risk_tier_{name}"] = np.where(out[col].isna(), None, np.where(out[col] >= max(0.5, r["threshold"]), "high",
                                                np.where(out[col] >= r["threshold"], "caution", "low")))
    # 측정값 융합 혈압으로 고혈압 안내 보강: 융합 예측이 기준을 넘으면 안내
    if "m2_pred_sbp" in out and "m2_pred_dbp" in out:
        fused_hi = (out["m2_pred_sbp"] >= 140) | (out["m2_pred_dbp"] >= 90)
        prev = out.get("refer_hypertension_140_90")
        out["refer_hypertension_m2"] = np.where(prev.isna() if prev is not None else True, fused_hi, (prev == True) | fused_hi)  # noqa: E712
    # 가이드라인 3단계(정상/주의/위험): 실제 최근 검진값, 예측값(수치+확률 결합)
    from .guideline import bp_stage, grade_prediction, grade_value, stage_by_source, worst
    gl_thr = {k: v["threshold"] for k, v in rules["referral"].items()}
    P = lambda r, t: getattr(r, f"m2_pred_{t}", np.nan) if hasattr(r, f"m2_pred_{t}") and pd.notna(getattr(r, f"m2_pred_{t}")) else getattr(r, f"pred_{t}", np.nan)
    U = lambda r, t: getattr(r, f"m2_upper_{t}", np.nan) if hasattr(r, f"m2_upper_{t}") and pd.notna(getattr(r, f"m2_upper_{t}")) else getattr(r, f"pred_{t}_upper", np.nan)
    recs = []
    for r in out.itertuples(index=False):
        e = {}
        for dom, (items, f_c, f_r) in DOMAINS.items():
            num = [grade_prediction(t, P(r, t), U(r, t), r.demo_sex) for t in items]
            e[f"tier_pred_{dom}"] = combine_tier(num, getattr(r, f"flag_{f_c}_prob", np.nan) if f_c else np.nan, gl_thr.get(f_c),
                                                 getattr(r, f"flag_{f_r}_prob", np.nan), gl_thr.get(f_r))
            e[f"tier_actual_{dom}"] = worst(*[grade_value(t, getattr(r, f"actual_{t}", np.nan), r.demo_sex) for t in items])
        for t in ("total_cholesterol", "ldl", "triglyceride", "hdl"):  # 지질: 분류기 없음 → 수치 판정만(참고)
            e[f"tier_pred_{t}"] = grade_prediction(t, getattr(r, f"pred_{t}", np.nan), getattr(r, f"pred_{t}_upper", np.nan))
            e[f"tier_actual_{t}"] = grade_value(t, getattr(r, f"actual_{t}", np.nan))
        e["stage_pred_bp_KSH2026"] = bp_stage(P(r, "sbp"), P(r, "dbp"))
        e["stage_pred_bmi_KSSO2022"] = stage_by_source("bmi", P(r, "bmi"), "KSSO2022")
        e["stage_pred_bmi_NHS_KR"] = stage_by_source("bmi", P(r, "bmi"), "NHS_KR")
        recs.append(e)
    out = pd.concat([out.reset_index(drop=True), pd.DataFrame(recs)], axis=1)
    out["guideline_version"] = "guideline_v1"; out["disease_profile_applied"] = "default(기저질환 미상)"
    keep = ["user_key", "has_checkup", "guideline_version", "disease_profile_applied"] + [c for c in out.columns if c.startswith(("tier_", "stage_"))] + [c for c in out.columns if c.startswith(("m2_", "refer_", "risk_tier_"))]
    res = out[keep].copy(); res.insert(1, "prediction_index_time", it.isoformat())
    path = PROJECT_ROOT / "01_Results" / "serving" / f"m2_predictions_{it.isoformat()}.parquet"
    res.to_parquet(path, index=False); res.to_csv(path.with_suffix(".csv"), index=False)
    return res
