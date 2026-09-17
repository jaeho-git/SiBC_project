"""알고리즘 파일럿 벤치마크 (구축가이드 v1.3).

목적: 항목별로 여러 ML/DL 알고리즘을 사용자 단위 그룹 교차검증으로 비교하고,
가장 성능이 좋은 알고리즘을 선택한다. 두 파일럿으로 분리한다.

- Pilot A (알고리즘 선택): 공공데이터(NHANES+KNHANES) "활동·악력·인구통계 →
  검진값". 표본이 커서 알고리즘 계열 선택의 근거가 된다.
- Pilot B (자체 M1 경로): 자체 데이터 "직전 검진 앵커 → 다음 검진".
  carry-forward 기준선 대비 개선 여부를 실제 자체 라벨로 검증한다.

원칙: GroupKFold(user_key), 항목별 비교, 기준선 필수 포함, 봉인셋 튜닝 금지.
"""
from __future__ import annotations

import json
import re
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .env import PROJECT_ROOT
from .schema import target_names
from .unified import load_unified

warnings.filterwarnings("ignore")
RESULTS_DIR = PROJECT_ROOT / "01_Results" / "benchmark"

WINDOW_RE = re.compile(r"__w(7|30|90)__")


def _algorithms() -> dict:
    """비교 대상 알고리즘. 결측은 각 파이프라인에서 처리."""
    return {
        "baseline_mean": DummyRegressor(strategy="mean"),
        "elasticnet": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("model", ElasticNet(alpha=0.5, l1_ratio=0.5, max_iter=5000)),
        ]),
        "random_forest": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("model", RandomForestRegressor(n_estimators=200, max_depth=8,
                                            n_jobs=-1, random_state=42)),
        ]),
        "hist_gbm": Pipeline([  # 임퓨터가 폴드내 전부-결측 컬럼 제거
            ("impute", SimpleImputer(strategy="median")),
            ("model", HistGradientBoostingRegressor(max_depth=4,
                                                    l2_regularization=1.0, random_state=42)),
        ]),
        "mlp": Pipeline([  # 표 형태 딥러닝 대표 (소규모)
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("model", MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=500,
                                   early_stopping=True, random_state=42)),
        ]),
    }


def _cv_scores(X, y, groups, estimator, n_splits=5) -> dict:
    gkf = GroupKFold(n_splits=min(n_splits, len(np.unique(groups))))
    maes, rmses, r2s = [], [], []
    for tr, te in gkf.split(X, y, groups):
        est = _clone(estimator)
        est.fit(X.iloc[tr], y.iloc[tr])
        pred = est.predict(X.iloc[te])
        maes.append(mean_absolute_error(y.iloc[te], pred))
        rmses.append(np.sqrt(mean_squared_error(y.iloc[te], pred)))
        r2s.append(r2_score(y.iloc[te], pred))
    return {"mae": float(np.mean(maes)), "mae_std": float(np.std(maes)),
            "rmse": float(np.mean(rmses)), "r2": float(np.mean(r2s))}


def _clone(estimator):
    from sklearn.base import clone
    return clone(estimator)


def _feature_cols(df: pd.DataFrame, kind: str) -> list[str]:
    drop = set(target_names()) | {"user_key", "event_date", "source", "sample_weight"}
    num = [c for c in df.columns if c not in drop and df[c].dtype.kind in "if"]
    if kind == "public":  # 관측창 특징 + demo (앵커 제외: 공공은 단면)
        num = [c for c in num if not c.startswith("anchor_")]
    # 커버리지 5% 이상 컬럼만 (폴드 내 전부-결측/상수 컬럼 방지)
    return [c for c in num if df[c].notna().mean() >= 0.05]


def pilot_a_public() -> dict:
    """공공데이터에서 알고리즘 비교 (항목별)."""
    df = load_unified()
    pub = df[df["source"] != "own"].copy()
    algos = _algorithms()
    report = {"pilot": "A_public_activity_to_checkup", "n_rows": len(pub),
              "targets": {}}
    for t in target_names():
        d = pub[pub[t].notna()]
        if len(d) < 300:
            report["targets"][t] = {"status": "SKIP_few_rows", "n": len(d)}
            continue
        feats = _feature_cols(d, "public")
        X, y, g = d[feats], d[t], d["user_key"]
        scores = {name: _cv_scores(X, y, g, est) for name, est in algos.items()}
        best = min((k for k in scores if k != "baseline_mean"),
                   key=lambda k: scores[k]["mae"])
        report["targets"][t] = {"n": len(d), "scores": scores, "best": best,
                                "beats_baseline": scores[best]["mae"] < scores["baseline_mean"]["mae"]}
    return report


def pilot_b_own_m1() -> dict:
    """자체 데이터 M1 경로: 직전 검진 앵커 -> 다음 검진. carry-forward 대비."""
    df = load_unified()
    own = df[df["source"] == "own"].copy()
    algos = _algorithms()
    report = {"pilot": "B_own_m1_anchor_to_checkup", "targets": {}}
    for t in target_names():
        anchor = f"anchor_prev_label__{t}"
        if anchor not in own.columns:
            continue
        d = own[own[t].notna() & own[anchor].notna()]
        if len(d) < 50:
            report["targets"][t] = {"status": "SKIP_few_labels", "n": len(d)}
            continue
        feats = _feature_cols(d, "own_m1")
        X, y, g = d[feats], d[t], d["user_key"]
        # carry-forward 기준선: 예측 = 직전 검진값
        cf_mae = float(mean_absolute_error(y, d[anchor]))
        scores = {name: _cv_scores(X, y, g, est) for name, est in algos.items()}
        best = min((k for k in scores if k != "baseline_mean"),
                   key=lambda k: scores[k]["mae"])
        report["targets"][t] = {
            "n": len(d), "carry_forward_mae": round(cf_mae, 3),
            "scores": scores, "best": best,
            "beats_carry_forward": scores[best]["mae"] < cf_mae,
        }
    return report


def pilot_c_embedding() -> dict:
    """자기지도 임베딩(ssl_emb__*)의 검진 예측 기여를 임베딩 보유 행에서 검증.

    누출 방지로 임베딩은 관측창 보유 own 행에만 존재(현재 극소수). 표본이
    작아 LeaveOneOut로 특징집합 비교: (앵커+demo) vs (앵커+demo+임베딩) vs
    (임베딩만). n이 작으므로 결과는 방향성 참고용이며 성능 주장에 쓰지 않는다.
    """
    from sklearn.model_selection import LeaveOneOut

    df = load_unified()
    own = df[df["source"] == "own"].copy()
    emb_cols = [c for c in own.columns if c.startswith("ssl_emb__")]
    has_emb = own[emb_cols].notna().any(axis=1)
    d0 = own[has_emb].copy()
    report = {"pilot": "C_ssl_embedding_contribution",
              "n_rows_with_embedding": int(len(d0)), "targets": {}}
    if len(d0) < 8:
        report["note"] = f"임베딩 보유 행 {len(d0)}개 — 통계적 비교 불가(라벨 축적 필요)"
        return report

    def loo_mae(X, y):
        if X.shape[1] == 0 or len(y) < 8:
            return None
        loo, preds, ys = LeaveOneOut(), [], []
        for tr, te in loo.split(X):
            m = Pipeline([("impute", SimpleImputer(strategy="median")),
                          ("scale", StandardScaler()),
                          ("model", ElasticNet(alpha=0.5, max_iter=5000))])
            m.fit(X.iloc[tr], y.iloc[tr])
            preds.append(m.predict(X.iloc[te])[0]); ys.append(y.iloc[te].iloc[0])
        return float(mean_absolute_error(ys, preds))

    for t in target_names():
        anchor = f"anchor_prev_label__{t}"
        d = d0[d0[t].notna()]
        if len(d) < 10:
            report["targets"][t] = {"status": "SKIP", "n": int(len(d))}
            continue
        base_feats = [c for c in d.columns if (c.startswith("anchor_") or c in
                      ("demo_age", "demo_sex")) and d[c].notna().any()]
        y = d[t]
        report["targets"][t] = {
            "n": int(len(d)),
            "mae_anchor_demo": _r(loo_mae(d[base_feats], y)),
            "mae_anchor_demo_plus_emb": _r(loo_mae(d[base_feats + emb_cols], y)),
            "mae_emb_only": _r(loo_mae(d[emb_cols], y)),
            "carry_forward_mae": _r(float(mean_absolute_error(y, d[anchor]))
                                    if anchor in d and d[anchor].notna().all() else None),
        }
    return report


def _r(x):
    return round(x, 3) if isinstance(x, (int, float)) else None


def run() -> dict:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = {"run_at": datetime.now(timezone.utc).isoformat(),
           "pilot_a": pilot_a_public(), "pilot_b": pilot_b_own_m1(),
           "pilot_c": pilot_c_embedding()}
    with open(RESULTS_DIR / "benchmark_report.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return out
