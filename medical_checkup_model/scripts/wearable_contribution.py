#!/usr/bin/env python3
"""웨어러블 간접 신호(걸음·활동량·활동시간·악력)의 예측 기여도 — 정직한 근거 3종을 한 파일로.

1) 공공데이터(NHANES) 홀드아웃 절제 실험: 성별·연령만 vs +활동 신호 vs +악력. 우리 사용자 성능이 아님.
2) 자체 사용자 대리 검증(기존 proxy 결과 인용): 심박·수면·걸음 → 혈압계 측정값. R²≈0.
3) 자체 '착용 뒤 검진' 참고(기존 m0_forward_eval 인용): n=8~18, 성능 주장 불가.
+ 통합 모델(v1.4) 경로의 예측 구간용 공공 홀드아웃 잔차 분위수(q7.5/q92.5).
출력: 01_Results/wearable_contribution.json
"""
from __future__ import annotations
import json, sys, warnings
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.base import clone
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
warnings.filterwarnings("ignore")
from sibc_checkup.schema import target_names  # noqa: E402
from sibc_checkup.train import _load_best_params, _make_model  # noqa: E402
from sibc_checkup.unified import load_unified  # noqa: E402

ACT = ["activity_pct__w7__median", "activity_daily_volume__w7__median", "activity_active_hours__w7__median", "step_count__w7__median"]
GRIP = ["grip_strength_kg__w7__median"]; DEMO = ["demo_sex", "demo_age"]

def main() -> None:
    df = load_unified(); pub = df[df["source"] != "own"].copy(); bp = _load_best_params()
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    tr_i, te_i = next(gss.split(pub, groups=pub["user_key"])); tr, te = pub.iloc[tr_i], pub.iloc[te_i]
    out = {"public_holdout": {}, "interval_quantiles_public": {}, "n_public_train": int(len(tr)), "n_public_test": int(len(te)),
           "note": "공공(NHANES+KNHANES) 내부 홀드아웃. 우리 사용자 성능이 아니며 웨어러블 신호의 '기여 방향'만 보여준다"}
    sets = {"demo_only": DEMO, "demo_activity": DEMO + ACT, "demo_activity_grip": DEMO + ACT + GRIP}
    for t in target_names():
        a, b = tr[tr[t].notna()], te[te[t].notna()]
        if len(a) < 200 or len(b) < 50:
            continue
        res = {}
        for name, cols in sets.items():
            m = _make_model(bp.get(t, {})).fit(a[cols], a[t]); p = m.predict(b[cols])
            res[name] = {"mae": round(float(mean_absolute_error(b[t], p)), 3), "r2": round(float(r2_score(b[t], p)), 3)}
            if name == "demo_activity_grip":
                r = b[t].to_numpy() - p
                out["interval_quantiles_public"][t] = [round(float(np.quantile(r, 0.075)), 3), round(float(np.quantile(r, 0.925)), 3)]
        res["mae_baseline_mean"] = round(float(mean_absolute_error(b[t], np.full(len(b), a[t].mean()))), 3)
        res["activity_gain_pct_vs_demo"] = round(100 * (1 - res["demo_activity"]["mae"] / res["demo_only"]["mae"]), 1)
        res["n_test"] = int(len(b)); out["public_holdout"][t] = res
    # 기존 근거 인용
    px = json.load(open(ROOT / "01_Results/proxy/proxy_report.json"))["targets"]
    out["own_proxy_vs_cuff"] = {t: {"note": "자체 사용자: 심박·수면·걸음 → 웨어러블 혈압계/체중계 측정값(대리 정답). 검진값 아님", **{k: v["sealed"][k] for k in ("n_users", "n_rows", "mae", "r2", "baseline_mean_mae")}} for t, v in px.items() if v.get("sealed")}
    last = json.loads(open(ROOT / "01_Results/m0_forward_eval.jsonl").read().strip().split("\n")[-1])
    out["own_forward_reference"] = {"gate": last["gate"], "n_users": last["n_forward_users"], "targets": {t: {k: v.get(k) for k in ("n_forward", "mae", "mae_baseline_public_mean", "carry_forward_mae_where_available", "status")} for t, v in last["targets"].items()}}
    (ROOT / "01_Results/wearable_contribution.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    for t, r in out["public_holdout"].items():
        print(f"{t:18s} demo={r['demo_only']['mae']} +act={r['demo_activity']['mae']} ({r['activity_gain_pct_vs_demo']:+.1f}%) +grip={r['demo_activity_grip']['mae']} r2={r['demo_activity_grip']['r2']} base={r['mae_baseline_mean']}")

if __name__ == "__main__":
    main()
