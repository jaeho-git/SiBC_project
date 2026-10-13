#!/usr/bin/env python3
"""데이터 현황 스냅샷: 이전 캐시 대비 웨어러블·검진·'착용 뒤 검진' 정답지 증감 (집계만, 가명키).

사용: uv run python scripts/data_status.py [--prev 00_Data/processed/daily_features_YYYY-MM-DD.parquet]
출력: 01_Results/data_status_<today>.json
"""
from __future__ import annotations
import json, sys, glob
from datetime import date
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from sibc_checkup.features_own import fetch_daily_features  # noqa: E402
from sibc_checkup.labels import build_label_table  # noqa: E402
from sibc_checkup.schema import target_names  # noqa: E402

def daily_stats(d: pd.DataFrame) -> dict:
    d = d.copy(); d["d"] = pd.to_datetime(d["d"])
    per = d.groupby("feature").agg(users=("user_key", "nunique"), user_days=("d", "size"),
                                   first=("d", "min"), last=("d", "max"))
    ud = d.drop_duplicates(["user_key", "d"])
    days_per_user = ud.groupby("user_key").size()
    return {"users": int(d["user_key"].nunique()), "user_days": int(len(ud)),
            "first_day": str(d["d"].min().date()), "last_day": str(d["d"].max().date()),
            "days_per_user_median": float(days_per_user.median()),
            "users_ge30days": int((days_per_user >= 30).sum()), "users_ge90days": int((days_per_user >= 90).sum()),
            "by_feature": {k: {"users": int(v.users), "user_days": int(v.user_days),
                               "first": str(v["first"].date()), "last": str(v["last"].date())} for k, v in per.iterrows()}}

def forward_stats(daily: pd.DataFrame, labels: pd.DataFrame) -> dict:
    """검진일 이전 90일 안에 웨어러블 관측이 있는 검진(정답지)."""
    dd = daily.drop_duplicates(["user_key", "d"])[["user_key", "d"]].copy(); dd["d"] = pd.to_datetime(dd["d"])
    lab = labels[["user_key", "event_date"]].copy(); lab["event_date"] = pd.to_datetime(lab["event_date"])
    m = lab.merge(dd, on="user_key", how="inner")
    gap = (m["event_date"] - m["d"]).dt.days
    m = m[(gap >= 1) & (gap <= 90)]
    cnt = m.groupby(["user_key", "event_date"]).size().rename("wear_days_90").reset_index()
    out = {}
    for thr in (1, 7, 21):
        c = cnt[cnt["wear_days_90"] >= thr]
        out[f"pairs_ge{thr}d"] = int(len(c)); out[f"users_ge{thr}d"] = int(c["user_key"].nunique())
    # 직전 검진도 있는(=M1+웨어러블 학습 가능) 정답지
    lab = lab.sort_values(["user_key", "event_date"]); lab["has_prev"] = lab.groupby("user_key").cumcount() > 0
    c = cnt.merge(lab, on=["user_key", "event_date"])
    out["pairs_with_prev_checkup"] = int(c["has_prev"].sum()); out["users_with_prev_checkup"] = int(c[c["has_prev"]]["user_key"].nunique())
    return out

def main() -> None:
    prev_path = None
    if "--prev" in sys.argv: prev_path = Path(sys.argv[sys.argv.index("--prev") + 1])
    else:
        olds = sorted(p for p in glob.glob(str(ROOT / "00_Data/processed/daily_features_*.parquet")) if date.today().isoformat() not in p)
        prev_path = Path(olds[-1]) if olds else None
    daily = fetch_daily_features(use_cache=True)
    labels = build_label_table()
    tcols = [t for t in target_names() if t in labels.columns]
    lab_stats = {"users": int(labels["user_key"].nunique()), "events": int(len(labels)),
                 "last_event": str(pd.to_datetime(labels["event_date"]).max().date()),
                 "events_2026": int((pd.to_datetime(labels["event_date"]).dt.year == 2026).sum()),
                 "events_since_2025_12": int((pd.to_datetime(labels["event_date"]) >= "2025-12-01").sum()),
                 "non_null_by_target": {t: int(labels[t].notna().sum()) for t in tcols}}
    res = {"as_of": date.today().isoformat(), "wearable_now": daily_stats(daily), "labels_now": lab_stats,
           "forward_now": forward_stats(daily, labels)}
    if prev_path and prev_path.is_file():
        prev = pd.read_parquet(prev_path)
        res["prev_file"] = prev_path.name; res["wearable_prev"] = daily_stats(prev)
        res["forward_prev_with_current_labels"] = forward_stats(prev, labels)
    out = ROOT / "01_Results" / f"data_status_{date.today().isoformat()}.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1)); print("wrote", out)
    w = res["wearable_now"]; print("wearable now:", {k: w[k] for k in ("users", "user_days", "first_day", "last_day", "users_ge30days", "users_ge90days")})
    if "wearable_prev" in res:
        p = res["wearable_prev"]; print("wearable prev:", {k: p[k] for k in ("users", "user_days", "first_day", "last_day", "users_ge30days", "users_ge90days")})
    print("labels:", lab_stats); print("forward now:", res["forward_now"]); print("forward prev:", res.get("forward_prev_with_current_labels"))
if __name__ == "__main__":
    main()
