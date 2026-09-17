"""봉인셋 성능의 객관적 유의성: 사용자 클러스터 부트스트랩 신뢰구간.
- M1: 모델 MAE - carry-forward MAE 차이의 95% CI (음수면 모델 우세)
- 분류: AUROC 95% CI, 직전상태 AUROC 대비 차이 CI
"""
import json, warnings, numpy as np, pandas as pd, joblib
from sklearn.metrics import mean_absolute_error, roc_auc_score
from sibc_checkup.m1 import build_m1_dataset, _sealed_split, RESULTS_DIR
from sibc_checkup.clinical import THRESHOLDS, OUT_DIR as CDIR
from sibc_checkup.env import PROJECT_ROOT
warnings.filterwarnings("ignore")
rng = np.random.default_rng(0); B = 2000
rules = json.load(open(PROJECT_ROOT/"configs/m1_serving_rules.json"))["rules"]
out = {"m1": {}, "clf": {}}

def boot_users(df, stat):
    users = df["user_key"].unique(); g = {u: d for u, d in df.groupby("user_key")}
    vals = []
    for _ in range(B):
        samp = pd.concat([g[u] for u in rng.choice(users, len(users), replace=True)])
        vals.append(stat(samp))
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))

for t, r in rules.items():
    if r.get("route") not in ("MODEL",): continue
    d, feats = build_m1_dataset(t); d = d[~d["abstain"]]
    _, sealed = _sealed_split(d)
    art = joblib.load(RESULTS_DIR/"m1_v3"/r["model_file"])
    sealed = sealed.copy(); sealed["pred"] = art["model"].predict(sealed[art["features"]])
    sealed["cf"] = sealed[f"anchor_prev_label__{t}"]
    diff = lambda s: mean_absolute_error(s[t], s["pred"]) - mean_absolute_error(s[t], s["cf"])
    lo, hi = boot_users(sealed, diff)
    out["m1"][t] = {"n_users": int(sealed.user_key.nunique()), "mae_model": round(mean_absolute_error(sealed[t], sealed["pred"]),2),
                    "mae_cf": round(mean_absolute_error(sealed[t], sealed["cf"]),2), "diff": round(diff(sealed),2),
                    "diff_ci95": [round(lo,2), round(hi,2)], "significant": hi < 0}

for name, (t, label_fn, prior_fn) in THRESHOLDS.items():
    p = CDIR/f"flag_{name}.joblib"
    if not p.exists(): continue
    d, feats = build_m1_dataset(t); d = d[~d["abstain"]].copy()
    d["y"] = label_fn(d).astype(int); d["prior"] = prior_fn(d).astype(int)
    _, sealed = _sealed_split(d)
    # 봉인 평가와 동일하게 학습 사용자로만 적합한 모델을 재현
    from sklearn.base import clone
    from sibc_checkup.clinical import _clf_candidates
    rep = json.load(open(CDIR/"clinical_report.json"))["thresholds"][name]
    train, _ = _sealed_split(d)
    m = clone(_clf_candidates()[rep["best"]]).fit(train[feats], train["y"])
    sealed = sealed.copy(); sealed["s"] = m.predict_proba(sealed[feats])[:,1]
    auc = lambda s: roc_auc_score(s["y"], s["s"]) if s["y"].nunique()==2 else np.nan
    dauc = lambda s: (roc_auc_score(s["y"], s["s"]) - roc_auc_score(s["y"], s["prior"])) if s["y"].nunique()==2 else np.nan
    lo, hi = boot_users(sealed, auc); dlo, dhi = boot_users(sealed, dauc)
    out["clf"][name] = {"n_users": int(sealed.user_key.nunique()), "auroc": round(auc(sealed),3), "auroc_ci95": [round(lo,3), round(hi,3)],
                        "prior_auroc": round(roc_auc_score(sealed["y"], sealed["prior"]),3),
                        "diff_vs_prior": round(dauc(sealed),3), "diff_ci95": [round(dlo,3), round(dhi,3)], "significant": dlo > 0}
json.dump(out, open(PROJECT_ROOT/"01_Results/significance.json","w"), ensure_ascii=False, indent=2)
print(json.dumps(out, ensure_ascii=False, indent=1))
