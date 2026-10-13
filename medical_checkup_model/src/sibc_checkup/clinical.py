"""임상 임계값 분류 + 변화 방향 예측 (서비스 질문에 맞춘 목표 재정의).

- 분류: 다음 검진에서 임계값 초과 여부 (고혈압, 공복혈당장애, 비만, 복부비만, 고TG)
  지표 AUROC/AUPRC/Brier. 기준선 = '직전 검진 상태 유지'(prior status).
- 방향: delta = 다음값 - 직전값 을 임상 의미 τ로 3분류(악화/유지/개선).
  기준선 = 다수 클래스, '항상 유지'.
- 특징·분할·게이트는 M1과 동일(앵커·추세·demo, 사용자 봉인 20%, 클래스당 >=30).
"""
from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score, brier_score_loss,
                             f1_score, roc_auc_score)
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .env import PROJECT_ROOT
from .m1 import _policy_thresholds, _sealed_split, build_m1_dataset

warnings.filterwarnings("ignore")
OUT_DIR = PROJECT_ROOT / "01_Results" / "clinical"
MIN_CLASS_EVENTS = 30

# 임계값 정의: (기준 항목, 라벨 함수(df)->bool, 직전상태 함수(df)->bool)
def _ge(col: str, v: float):
    return (lambda d: d[col] >= v), (lambda d: d[f"anchor_prev_label__{col}"] >= v)


def _lt(col: str, v: float):
    return (lambda d: d[col] < v), (lambda d: d[f"anchor_prev_label__{col}"] < v)


def _build_thresholds() -> dict:
    """임계값은 configs/clinical_guidelines.yaml(default_tiers)에서 읽는다 — 코드에 수치를 직접 쓰지 않는다."""
    from .guideline import load
    T = load()["default_tiers"]
    bp = lambda c, r: ((lambda d: (d["sbp"] >= T["sbp"][c]) | (d["dbp"] >= T["dbp"][c])),
                       (lambda d: (d["anchor_prev_label__sbp"] >= T["sbp"][c]) | (d["anchor_prev_label__dbp"] >= T["dbp"][c])))
    wc = lambda col: (lambda d: d[col] >= np.where(d["demo_sex"] == 1, T["waist"]["risk_male"], T["waist"]["risk_female"]))
    out = {
        "bp_caution_120_80": ("sbp", *bp("caution", None)),
        "hypertension_140_90": ("sbp", *bp("risk", None)),
        "fasting_glucose_ge100": ("fasting_glucose", *_ge("fasting_glucose", T["fasting_glucose"]["caution"])),
        "fasting_glucose_ge126": ("fasting_glucose", *_ge("fasting_glucose", T["fasting_glucose"]["risk"])),
        "bmi_ge23": ("bmi", *_ge("bmi", T["bmi"]["caution"])),
        "obesity_bmi_ge25": ("bmi", *_ge("bmi", T["bmi"]["risk"])),
        "obesity2_bmi_ge30": ("bmi", *_ge("bmi", 30)),
        "abdominal_obesity": ("waist", wc("waist"), wc("anchor_prev_label__waist")),
        "total_cholesterol_ge200": ("total_cholesterol", *_ge("total_cholesterol", T["total_cholesterol"]["caution"])),
        "total_cholesterol_ge240": ("total_cholesterol", *_ge("total_cholesterol", T["total_cholesterol"]["risk"])),
        "ldl_ge130": ("ldl", *_ge("ldl", T["ldl"]["caution"])),
        "ldl_ge160": ("ldl", *_ge("ldl", T["ldl"]["risk"])),
        "high_triglyceride_ge150": ("triglyceride", *_ge("triglyceride", T["triglyceride"]["caution"])),
        "triglyceride_ge200": ("triglyceride", *_ge("triglyceride", T["triglyceride"]["risk"])),
        "low_hdl_lt40": ("hdl", *_lt("hdl", T["hdl"]["risk_below"])),
    }
    return out


THRESHOLDS = _build_thresholds()
# 변화 방향 τ (임상적으로 의미 있는 최소 변화)
DIRECTION_TAU = {"sbp": 5.0, "dbp": 5.0, "fasting_glucose": 5.0,
                 "weight": 2.0, "bmi": 0.7, "waist": 3.0}


def _clf_candidates() -> dict:
    return {
        "logistic": Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()),
                              ("model", LogisticRegression(C=0.5, max_iter=2000))]),
        "hist_gbm": Pipeline([("impute", SimpleImputer(strategy="median")),
                              ("model", HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05,
                                                                       max_iter=300, l2_regularization=1.0,
                                                                       min_samples_leaf=20, random_state=42))]),
    }


def _safe_auc(y, s):
    return float(roc_auc_score(y, s)) if len(np.unique(y)) == 2 else None


# ---------------------------------------------------------------- 분류

def run_thresholds() -> dict:
    min_train, min_sealed = _policy_thresholds()
    out = {}
    for name, (t, label_fn, prior_fn) in THRESHOLDS.items():
        d, feats = build_m1_dataset(t)
        d = d[~d["abstain"]].copy()
        try:
            d["y"] = label_fn(d).astype(int)
            d["prior"] = prior_fn(d).astype(int)
        except KeyError as e:
            out[name] = {"status": f"SKIP_missing_{e}"}; continue
        d = d[d["y"].notna()]
        train, sealed = _sealed_split(d)
        pos, neg = int(train["y"].sum()), int((train["y"] == 0).sum())
        entry: dict = {"target": t, "n_train": len(train), "n_sealed": len(sealed),
                       "train_pos": pos, "train_neg": neg,
                       "prevalence": round(float(d["y"].mean()), 3)}
        gated = (pos < MIN_CLASS_EVENTS or neg < MIN_CLASS_EVENTS
                 or train["user_key"].nunique() < min_train or sealed["user_key"].nunique() < min_sealed)
        if gated:
            entry["status"] = "BLOCKED_BY_POLICY"; out[name] = entry; continue

        gkf = GroupKFold(n_splits=min(5, train["user_key"].nunique()))
        cv = {}
        for cname, est in _clf_candidates().items():
            aucs, aps = [], []
            for tr, te in gkf.split(train, groups=train["user_key"]):
                m = clone(est).fit(train.iloc[tr][feats], train.iloc[tr]["y"])
                s = m.predict_proba(train.iloc[te][feats])[:, 1]
                a = _safe_auc(train.iloc[te]["y"], s)
                if a is not None:
                    aucs.append(a); aps.append(average_precision_score(train.iloc[te]["y"], s))
            cv[cname] = {"auroc": round(float(np.mean(aucs)), 3), "auprc": round(float(np.mean(aps)), 3)}
        best = max(cv, key=lambda k: cv[k]["auroc"])
        model = clone(_clf_candidates()[best]).fit(train[feats], train["y"])
        s = model.predict_proba(sealed[feats])[:, 1]
        y = sealed["y"].to_numpy()
        entry.update({
            "status": "TRAINED", "best": best, "cv": cv,
            "sealed": {
                "auroc": _safe_auc(y, s) and round(_safe_auc(y, s), 3),
                "auprc": round(float(average_precision_score(y, s)), 3),
                "brier": round(float(brier_score_loss(y, s)), 3),
                "accuracy_at_0.5": round(float(accuracy_score(y, s >= 0.5)), 3),
                "baseline_prior_status_auroc": _safe_auc(y, sealed["prior"]) and round(_safe_auc(y, sealed["prior"]), 3),
                "baseline_prior_status_accuracy": round(float(accuracy_score(y, sealed["prior"])), 3),
                "baseline_prevalence": round(float(y.mean()), 3),
            },
        })
        out[name] = entry
    return out


# ---------------------------------------------------------------- 방향

def run_direction() -> dict:
    min_train, min_sealed = _policy_thresholds()
    out = {}
    for t, tau in DIRECTION_TAU.items():
        d, feats = build_m1_dataset(t)
        d = d[~d["abstain"]].copy()
        delta = d[t] - d[f"anchor_prev_label__{t}"]
        d["dir"] = np.where(delta > tau, 1, np.where(delta < -tau, -1, 0))  # 1 악화(상승), -1 개선, 0 유지
        train, sealed = _sealed_split(d)
        counts = train["dir"].value_counts().to_dict()
        entry: dict = {"tau": tau, "n_train": len(train), "n_sealed": len(sealed),
                       "class_counts_train": {int(k): int(v) for k, v in counts.items()}}
        if min(counts.values()) < MIN_CLASS_EVENTS or train["user_key"].nunique() < min_train \
                or sealed["user_key"].nunique() < min_sealed:
            entry["status"] = "BLOCKED_BY_POLICY"; out[t] = entry; continue
        est = Pipeline([("impute", SimpleImputer(strategy="median")),
                        ("model", HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=300,
                                                                 l2_regularization=1.0, min_samples_leaf=20,
                                                                 random_state=42))])
        gkf = GroupKFold(n_splits=min(5, train["user_key"].nunique()))
        accs, f1s = [], []
        for tr, te in gkf.split(train, groups=train["user_key"]):
            m = clone(est).fit(train.iloc[tr][feats], train.iloc[tr]["dir"])
            p = m.predict(train.iloc[te][feats])
            accs.append(accuracy_score(train.iloc[te]["dir"], p))
            f1s.append(f1_score(train.iloc[te]["dir"], p, average="macro"))
        model = clone(est).fit(train[feats], train["dir"])
        p = model.predict(sealed[feats]); y = sealed["dir"].to_numpy()
        majority = train["dir"].mode().iloc[0]
        entry.update({
            "status": "TRAINED",
            "cv": {"accuracy": round(float(np.mean(accs)), 3), "macro_f1": round(float(np.mean(f1s)), 3)},
            "sealed": {
                "accuracy": round(float(accuracy_score(y, p)), 3),
                "macro_f1": round(float(f1_score(y, p, average="macro")), 3),
                "baseline_majority_accuracy": round(float(np.mean(y == majority)), 3),
                "baseline_always_stable_accuracy": round(float(np.mean(y == 0)), 3),
                "worsen_recall": round(float(np.mean(p[y == 1] == 1)), 3) if (y == 1).any() else None,
                "worsen_precision": round(float(np.mean(y[p == 1] == 1)), 3) if (p == 1).any() else None,
            },
        })
        out[t] = entry
    return out


RULES_PATH = PROJECT_ROOT / "configs" / "clinical_rules.json"


def _persist(rep: dict) -> dict:
    """서빙용 모델 영속화 + 규칙. 서빙 게이트: 봉인셋에서 기준선을 이긴 문제만."""
    import joblib

    rules: dict = {"thresholds": {}, "direction": {}}
    for name, e in rep["thresholds"].items():
        if e.get("status") != "TRAINED":
            rules["thresholds"][name] = {"serve": False, "reason": e.get("status")}; continue
        t, label_fn, _ = THRESHOLDS[name]
        d, feats = build_m1_dataset(t)
        d = d[~d["abstain"]].copy(); d["y"] = label_fn(d).astype(int)
        model = clone(_clf_candidates()[e["best"]]).fit(d[feats], d["y"])  # 전체 데이터로 최종 적합
        joblib.dump({"model": model, "features": feats, "base_target": t}, OUT_DIR / f"flag_{name}.joblib")
        s = e["sealed"]
        serve = (s["auroc"] or 0) > (s["baseline_prior_status_auroc"] or 0)
        rules["thresholds"][name] = {"serve": serve, "base_target": t, "model_file": f"flag_{name}.joblib",
                                     "sealed_auroc": s["auroc"], "baseline_prior_auroc": s["baseline_prior_status_auroc"],
                                     "reason": "beats_prior_status" if serve else "does_not_beat_prior_status"}
    for t, e in rep["direction"].items():
        if e.get("status") != "TRAINED":
            rules["direction"][t] = {"serve": False, "reason": e.get("status")}; continue
        d, feats = build_m1_dataset(t)
        d = d[~d["abstain"]].copy()
        delta = d[t] - d[f"anchor_prev_label__{t}"]; tau = e["tau"]
        d["dir"] = np.where(delta > tau, 1, np.where(delta < -tau, -1, 0))
        est = Pipeline([("impute", SimpleImputer(strategy="median")),
                        ("model", HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=300,
                                                                 l2_regularization=1.0, min_samples_leaf=20,
                                                                 random_state=42))]).fit(d[feats], d["dir"])
        joblib.dump({"model": est, "features": feats, "tau": tau}, OUT_DIR / f"direction_{t}.joblib")
        s = e["sealed"]
        serve = s["accuracy"] > max(s["baseline_majority_accuracy"], s["baseline_always_stable_accuracy"])
        rules["direction"][t] = {"serve": serve, "tau": tau, "model_file": f"direction_{t}.joblib",
                                 "sealed_accuracy": s["accuracy"],
                                 "baseline_accuracy": max(s["baseline_majority_accuracy"], s["baseline_always_stable_accuracy"]),
                                 "reason": "beats_baseline" if serve else "does_not_beat_baseline"}
    with open(RULES_PATH, "w") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)
    return rules


def run() -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rep = {"run_at": datetime.now(timezone.utc).isoformat(),
           "thresholds": run_thresholds(), "direction": run_direction()}
    rep["serving_rules"] = _persist(rep)
    with open(OUT_DIR / "clinical_report.json", "w") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    return rep
