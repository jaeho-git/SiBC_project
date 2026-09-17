"""v1 baseline 학습 (공공 지배 버전).

- 모델: HistGradientBoosting (결측 마스크 자연 처리) — 통합 테이블로 항목별 학습
- 평가 원칙 (modeling_policy):
  * 자체(own) 라벨 평가는 "참고용"으로만 출력 (현재 소량)
  * 공공 내부 홀드아웃 지표는 public-internal로 명확히 라벨링 —
    우리 사용자 성능이 아니며 어떤 보고서에도 성능으로 기재 금지
- 계보: 01_Results/model_registry.jsonl 에 버전별 공공/자체 구성 기록
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline

from .env import PROJECT_ROOT
from .schema import target_names
from .unified import load_unified

RESULTS_DIR = PROJECT_ROOT / "01_Results"
REGISTRY = RESULTS_DIR / "model_registry.jsonl"
BEST_PARAMS_PATH = PROJECT_ROOT / "configs" / "best_params.json"


def _load_best_params() -> dict:
    """튜닝된 항목별 HistGBM 파라미터. 없으면 기본값."""
    if BEST_PARAMS_PATH.is_file():
        return json.load(open(BEST_PARAMS_PATH)).get("best_params", {})
    return {}


def _make_model(params: dict) -> Pipeline:
    return Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("model", HistGradientBoostingRegressor(random_state=42, **params)),
    ])


DOMAIN_DUMMIES = ["src_own", "src_knhanes", "src_nhanes"]


def _add_domain_dummies(df: pd.DataFrame) -> pd.DataFrame:
    """출처 표시 변수(domain indicator)를 수치 특징으로 추가.

    schema.yaml 밖 컬럼이지만 unified 테이블이 아니라 학습 시점에만 생성되므로
    앵커링 검사(=unified 대상) 대상이 아니다. 서비스 시 own 도메인으로 고정.
    """
    df = df.copy()
    for d in DOMAIN_DUMMIES:
        df[d] = (df["source"] == d.split("_", 1)[1]).astype(float)
    return df


def _feature_columns(df: pd.DataFrame) -> list[str]:
    drop = set(target_names()) | {"user_key", "event_date", "source", "sample_weight"}
    return [c for c in df.columns if c not in drop and df[c].dtype.kind in "if"]


def train_v1(version: str = "v1") -> dict:
    df = load_unified()
    df = _add_domain_dummies(df)
    feats = _feature_columns(df)
    out_dir = RESULTS_DIR / version
    out_dir.mkdir(parents=True, exist_ok=True)
    best_params = _load_best_params()

    report: dict = {"version": version, "features_used": len(feats),
                    "tuned": bool(best_params), "targets": {}}
    for target in target_names():
        d = df[df[target].notna()].copy()
        n_own = int((d["source"] == "own").sum())
        n_pub = int((d["source"] != "own").sum())
        entry: dict = {"rows_public": n_pub, "rows_own": n_own}
        if n_pub < 200:
            entry["status"] = "SKIPPED_TOO_FEW_ROWS"
            report["targets"][target] = entry
            continue

        pub = d[d["source"] != "own"]
        splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
        tr_idx, te_idx = next(splitter.split(pub, groups=pub["user_key"]))
        pub_tr, pub_te = pub.iloc[tr_idx], pub.iloc[te_idx]
        own = d[d["source"] == "own"]

        train_df = pd.concat([pub_tr, own], ignore_index=True)
        # 전부 결측인 특징은 binning 불가 -> 항목별로 유효값 있는 특징만 사용
        feats_t = [c for c in feats if train_df[c].notna().sum() >= 20]
        params = best_params.get(target) or {"max_depth": 4, "l2_regularization": 1.0}
        model = _make_model(params)  # 튜닝된 파라미터(있으면) + 임퓨터
        model.fit(train_df[feats_t], train_df[target],
                  model__sample_weight=train_df["sample_weight"])
        joblib.dump({"model": model, "features": feats_t, "params": params},
                    out_dir / f"{target}.joblib")
        entry["features_used"] = len(feats_t)
        entry["params"] = params

        pred_te = model.predict(pub_te[feats_t])
        baseline = np.full(len(pub_te), pub_tr[target].mean())
        entry["public_internal"] = {
            "note": "NHANES 내부 홀드아웃 — 개발 참고용. 우리 사용자 성능이 아님",
            "mae": round(float(mean_absolute_error(pub_te[target], pred_te)), 3),
            "mae_baseline_mean": round(float(mean_absolute_error(pub_te[target], baseline)), 3),
            "r2": round(float(r2_score(pub_te[target], pred_te)), 3),
        }
        if n_own > 0:
            pred_own = model.predict(own[feats_t])
            entry["own_reference_only"] = {
                "note": f"자체 라벨 {n_own}건 — 표본 부족으로 참고용, 성능 주장 금지",
                "mae": round(float(mean_absolute_error(own[target], pred_own)), 3),
            }
        entry["status"] = "TRAINED"
        report["targets"][target] = entry

    _record_lineage(version, df)
    with open(out_dir / "train_report.json", "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return report


def _record_lineage(version: str, df: pd.DataFrame) -> None:
    """버전별 데이터 계보 — '검증·완성은 자체 데이터' 주장의 증거 사슬."""
    entry = {
        "version": version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "rows_public": int((df["source"] != "own").sum()),
        "rows_own": int((df["source"] == "own").sum()),
        "users_public": int(df.loc[df["source"] != "own", "user_key"].nunique()),
        "users_own": int(df.loc[df["source"] == "own", "user_key"].nunique()),
        "own_weight": float(df.loc[df["source"] == "own", "sample_weight"].max())
        if (df["source"] == "own").any() else 0.0,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
