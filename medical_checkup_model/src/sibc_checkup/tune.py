"""하이퍼파라미터 튜닝 (파일럿 승자 = HistGradientBoosting).

파일럿 벤치마크에서 그래디언트 부스팅이 공공 활동→검진에서 최다 1위였다.
항목별로 GroupKFold(user_key) 랜덤서치로 HistGBM 하이퍼파라미터를 최적화하고
configs/best_params.json에 저장한다. 봉인 테스트는 사용하지 않는다(튜닝 누출 금지).
"""
from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline

from .benchmark import _feature_cols
from .env import PROJECT_ROOT
from .schema import target_names
from .unified import load_unified

warnings.filterwarnings("ignore")
BEST_PARAMS_PATH = PROJECT_ROOT / "configs" / "best_params.json"

# 랜덤서치 탐색공간
SEARCH_SPACE = {
    "learning_rate": [0.03, 0.05, 0.1, 0.2],
    "max_depth": [3, 4, 6, None],
    "max_leaf_nodes": [15, 31, 63],
    "l2_regularization": [0.0, 1.0, 5.0],
    "max_iter": [200, 400, 600],
    "min_samples_leaf": [20, 50, 100],
}


def _sample_params(rng) -> dict:
    return {k: rng.choice(v).item() if hasattr(rng.choice(v), "item") else rng.choice(v)
            for k, v in SEARCH_SPACE.items()}


def _make(params: dict) -> Pipeline:
    return Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("model", HistGradientBoostingRegressor(random_state=42, **params)),
    ])


def _cv_mae(X, y, groups, params, n_splits=5) -> float:
    gkf = GroupKFold(n_splits=min(n_splits, len(np.unique(groups))))
    maes = []
    for tr, te in gkf.split(X, y, groups):
        est = _make(params)
        est.fit(X.iloc[tr], y.iloc[tr])
        maes.append(mean_absolute_error(y.iloc[te], est.predict(X.iloc[te])))
    return float(np.mean(maes))


def tune(n_iter: int = 25, seed: int = 42) -> dict:
    df = load_unified()
    pub = df[df["source"] != "own"].copy()
    rng = np.random.default_rng(seed)
    out = {"tuned_at": datetime.now(timezone.utc).isoformat(),
           "algorithm": "HistGradientBoostingRegressor",
           "n_iter": n_iter, "targets": {}}
    best_params = {}
    for t in target_names():
        d = pub[pub[t].notna()]
        if len(d) < 300:
            out["targets"][t] = {"status": "SKIP_few_rows", "n": len(d)}
            continue
        feats = _feature_cols(d, "public")
        X, y, g = d[feats], d[t], d["user_key"]
        # 기본값 성능
        default = {"max_depth": 4, "l2_regularization": 1.0}
        best = {"params": default, "mae": _cv_mae(X, y, g, default)}
        for _ in range(n_iter):
            p = {k: (None if v == "None" else v) for k, v in _sample_params(rng).items()}
            mae = _cv_mae(X, y, g, p)
            if mae < best["mae"]:
                best = {"params": p, "mae": mae}
        best_params[t] = best["params"]
        out["targets"][t] = {"n": len(d), "best_mae": round(best["mae"], 3),
                             "best_params": best["params"]}
    out["best_params"] = best_params
    with open(BEST_PARAMS_PATH, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=lambda o: None)
    return out
