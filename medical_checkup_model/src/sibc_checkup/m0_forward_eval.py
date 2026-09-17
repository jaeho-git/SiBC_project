"""트랙 2(M0 웨어러블 전용) — 자체 forward 쌍 자동 평가.

- forward 쌍: own 행 중 검진일 '이전' 웨어러블 관측창 특징이 있는 행
  (누출 없는 유일한 자체 평가행; 라벨 유입에 따라 자동 증가)
- 평가용 M0 모델은 **공공 행만으로** 학습한다. own forward 행이 학습에 섞이면
  평가가 누출되므로 통합 학습 모델(v1.x)을 그대로 쓰지 않는다.
- 특징은 공공·forward 양쪽 커버리지 >=5% 교집합만 (현재 demo + 걸음 w7:
  NHANES 가속도(MIMS)->자체 걸음 브리징 미구현이 구조적 제약)
- 게이트: forward 사용자 >= sealed_test_min_users 전에는 BLOCKED_BY_DATA
  (지표는 참고용, 성능 주장 금지)
- 실행마다 01_Results/m0_forward_eval.jsonl 에 append → 라벨 유입 추적 자동화
"""
from __future__ import annotations

import json
import re
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline

from .env import PROJECT_ROOT
from .m1 import _policy_thresholds
from .schema import target_names
from .train import _load_best_params
from .unified import load_unified

warnings.filterwarnings("ignore")
HISTORY = PROJECT_ROOT / "01_Results" / "m0_forward_eval.jsonl"
WINDOW_RE = re.compile(r"__w(7|30|90)__")
MIN_COVERAGE = 0.05


def forward_rows(own: pd.DataFrame) -> pd.DataFrame:
    win_cols = [c for c in own.columns if WINDOW_RE.search(c)
                and not c.startswith(("anchor_", "trend_"))]
    return own[own[win_cols].notna().any(axis=1)].copy()


def _shared_features(pub: pd.DataFrame, fwd: pd.DataFrame) -> list[str]:
    drop = set(target_names()) | {"user_key", "event_date", "source", "sample_weight"}
    cands = [c for c in pub.columns if c not in drop and pub[c].dtype.kind in "if"
             and not c.startswith(("anchor_", "trend_", "ssl_emb__"))]
    return [c for c in cands if c in fwd.columns
            and pub[c].notna().mean() >= MIN_COVERAGE and fwd[c].notna().mean() >= MIN_COVERAGE]


def evaluate() -> dict:
    df = load_unified()
    own, pub = df[df["source"] == "own"], df[df["source"] != "own"]
    fwd = forward_rows(own)
    _, min_sealed = _policy_thresholds()
    n_users = int(fwd["user_key"].nunique())
    gate = "EVALUABLE" if n_users >= min_sealed else "BLOCKED_BY_DATA"
    best_params = _load_best_params()
    rep = {"run_at": datetime.now(timezone.utc).isoformat(), "track": "M0_forward",
           "n_forward_rows": int(len(fwd)), "n_forward_users": n_users,
           "gate": gate, "gate_rule": f"forward_users>={min_sealed}", "targets": {}}

    for t in target_names():
        d_pub, d_fwd = pub[pub[t].notna()], fwd[fwd[t].notna()]
        feats = _shared_features(d_pub, d_fwd)
        entry: dict = {"n_forward": int(len(d_fwd)), "shared_features": feats}
        if len(d_fwd) < 3 or not feats:
            entry["status"] = "SKIP"
            rep["targets"][t] = entry
            continue
        params = best_params.get(t) or {"max_depth": 4, "l2_regularization": 1.0}
        model = Pipeline([("impute", SimpleImputer(strategy="median")),
                          ("model", HistGradientBoostingRegressor(random_state=42, **params))])
        model.fit(d_pub[feats], d_pub[t], model__sample_weight=d_pub["sample_weight"])
        pred = model.predict(d_fwd[feats])
        y = d_fwd[t].to_numpy()
        entry.update({
            "status": "REFERENCE_ONLY" if gate != "EVALUABLE" else "EVALUATED",
            "mae": round(float(mean_absolute_error(y, pred)), 3),
            "mae_baseline_public_mean": round(float(mean_absolute_error(y, np.full(len(y), d_pub[t].mean()))), 3),
            "r2": round(float(r2_score(y, pred)), 3) if len(y) >= 3 else None,
        })
        anchor = f"anchor_prev_label__{t}"
        if anchor in d_fwd and d_fwd[anchor].notna().any():
            m = d_fwd[anchor].notna()
            entry["carry_forward_mae_where_available"] = round(
                float(mean_absolute_error(y[m.to_numpy()], d_fwd.loc[m, anchor])), 3)
            entry["n_with_anchor"] = int(m.sum())
        rep["targets"][t] = entry

    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY, "a") as f:
        f.write(json.dumps(rep, ensure_ascii=False) + "\n")
    return rep
