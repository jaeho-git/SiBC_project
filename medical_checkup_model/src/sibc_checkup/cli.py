"""CLI: python -m sibc_checkup.cli <command>

commands:
  build-table : 자체 라벨/특징 + NHANES 공공 행 -> 통합 학습 테이블 생성·저장
  train       : v1 baseline 학습 (공공 지배 버전) + 계보 기록
  all         : build-table + train
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from .schema import target_names


def build_own_rows() -> pd.DataFrame:
    from .features_own import build_windows, fetch_daily_features
    from .labels import build_label_table

    labels = build_label_table()
    keep = ["user_key", "event_date"] + [t for t in target_names() if t in labels.columns]
    labels = labels[keep]

    daily = fetch_daily_features()
    feats = build_windows(daily, labels[["user_key", "event_date"]])
    own = labels.merge(feats, on=["user_key", "event_date"], how="left")
    own = _add_anchors(own)

    from .features_demo import add_demo_features
    own = add_demo_features(own)
    own = _add_ssl_embeddings(own)
    return own


def _add_ssl_embeddings(own: pd.DataFrame) -> pd.DataFrame:
    """자기지도 임베딩(ssl_emb__0..15)을 누출 방지로 부여.

    임베딩은 사용자별 웨어러블 전체(2025-12~) 요약이므로, 검진일 이전에 실제
    웨어러블 관측창이 있는 행(=관측창 특징 보유)에만 부여한다. 그 외에는 결측.
    """
    import re

    from .env import PROJECT_ROOT

    emb_path = PROJECT_ROOT / "01_Results" / "pretrain" / "user_embeddings.parquet"
    if not emb_path.is_file():
        return own
    emb = pd.read_parquet(emb_path)
    emb = emb[~emb["user_key"].str.startswith("lifesnaps_")].copy()
    emb = emb.rename(columns={c: c.replace("ssl_emb_", "ssl_emb__")
                              for c in emb.columns if c.startswith("ssl_emb_")})
    emb_cols = [c for c in emb.columns if c.startswith("ssl_emb__")]

    win_re = re.compile(r"__w(7|30|90)__")
    win_cols = [c for c in own.columns if win_re.search(c)]
    has_wear = own[win_cols].notna().any(axis=1) if win_cols else pd.Series(False, index=own.index)

    own = own.merge(emb, on="user_key", how="left")
    # 누출 방지: 관측창 없는 행의 임베딩은 제거
    own.loc[~has_wear.values, emb_cols] = pd.NA
    return own


def _add_anchors(own: pd.DataFrame) -> pd.DataFrame:
    """M1 개인 앵커: 동일 사용자·동일 항목의 직전 검진값과 경과일."""
    own = own.sort_values(["user_key", "event_date"]).reset_index(drop=True)
    ed = pd.to_datetime(own["event_date"])
    for t in target_names():
        if t not in own.columns:
            continue
        prev_val = own.groupby("user_key")[t].shift(1)
        prev_date = ed.groupby(own["user_key"]).shift(1)
        own[f"anchor_prev_label__{t}"] = prev_val
        own[f"anchor_days_since__{t}"] = (ed - prev_date).dt.days
    return own


def cmd_build_table() -> None:
    from .knhanes import build_public_rows as build_knhanes
    from .knhanes import korean_calibration_reference
    from .nhanes import build_public_rows as build_nhanes
    from .unified import PROCESSED_DIR, build_unified, save_unified

    own = build_own_rows()
    print(f"own rows: {len(own)} events, {own['user_key'].nunique()} users")
    nhanes = build_nhanes()
    print(f"public rows (NHANES, US): {len(nhanes)}")
    knhanes = build_knhanes()
    print(f"public rows (KNHANES, KR 2014-2017 활동+검진): {len(knhanes)}")
    unified = build_unified(own, nhanes, knhanes)
    path = save_unified(unified)
    print(f"unified table -> {path} ({len(unified)} rows, {len(unified.columns)} cols)")

    # 한국인 보정 기준 분포 저장
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    ref = korean_calibration_reference()
    ref.to_parquet(PROCESSED_DIR / "korean_calibration_reference.parquet", index=False)
    print(f"korean calibration reference -> {len(ref)} (sex x age_band x target) cells")


def cmd_train() -> None:
    import json

    from .train import train_v1

    report = train_v1()
    print(json.dumps(report, ensure_ascii=False, indent=2))


def cmd_pretrain() -> None:
    import json

    from .pretrain import pretrain

    print(json.dumps(pretrain(), ensure_ascii=False, indent=2))


def cmd_benchmark() -> None:
    import json

    from .benchmark import run

    print(json.dumps(run(), ensure_ascii=False, indent=2))


def cmd_tune() -> None:
    import json

    from .tune import tune

    print(json.dumps(tune(), ensure_ascii=False, indent=2))


def cmd_train_m1() -> None:
    import json

    from .m1 import train_m1

    print(json.dumps(train_m1(), ensure_ascii=False, indent=2))


def cmd_serve_m1(index_time: str | None, no_wearable: bool) -> None:
    import json
    from datetime import date

    from .serve import serve_all, serve_summary

    it = date.fromisoformat(index_time) if index_time else date.today()
    out = serve_all(it, with_wearable=not no_wearable)
    print(json.dumps(serve_summary(out), ensure_ascii=False, indent=2))
    print(f"-> 01_Results/serving/m1_predictions_{it.isoformat()}.(parquet|csv)")


def cmd_predict(index_time: str | None) -> None:
    import json
    from datetime import date

    from .predict import predict_all, write_schema

    it = date.fromisoformat(index_time) if index_time else date.today()
    L, W = predict_all(it); write_schema()
    print(json.dumps({"users": int(W.shape[0]), "rows": int(L.shape[0]), "routes": L.groupby("item")["route"].value_counts().unstack(fill_value=0).to_dict("index")}, ensure_ascii=False, indent=1))
    print(f"-> 01_Results/predictions/predictions_(long|wide)_{it.isoformat()}.(parquet|csv), configs/prediction_output_schema.json")


def cmd_eval_m0_forward() -> None:
    import json

    from .m0_forward_eval import evaluate

    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="sibc_checkup")
    parser.add_argument("command",
                        choices=["build-table", "benchmark", "tune", "train",
                                 "train-m1", "serve-m1", "predict", "eval-m0-forward", "pretrain", "all"])
    parser.add_argument("--index-time", default=None, help="serve-m1: 예측 기준일 YYYY-MM-DD")
    parser.add_argument("--no-wearable", action="store_true", help="serve-m1: 웨어러블 조회 생략")
    args = parser.parse_args()
    if args.command == "train-m1":
        cmd_train_m1()
        return
    if args.command == "predict":
        cmd_predict(args.index_time)
        return
    if args.command == "serve-m1":
        cmd_serve_m1(args.index_time, args.no_wearable)
        return
    if args.command == "eval-m0-forward":
        cmd_eval_m0_forward()
        return
    if args.command in ("build-table", "all"):
        cmd_build_table()
    if args.command in ("benchmark", "all"):
        cmd_benchmark()
    if args.command in ("tune", "all"):
        cmd_tune()
    if args.command in ("train", "all"):
        cmd_train()
    if args.command == "pretrain":
        cmd_pretrain()


if __name__ == "__main__":
    sys.exit(main())
