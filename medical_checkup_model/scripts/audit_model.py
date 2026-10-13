"""모델 분석 보고서용 진단: 실사용 준비도 감사.
1) 서빙 산출 실효 커버리지  2) M1 특징 중요도(퍼뮤테이션)  3) 하위집단(성별·연령·앵커 경과일) 잔차 편향
4) 통합 모델 v1.3의 자체 forward 쌍 성능(웨어러블 반영 시)  5) 재현성(시드 변경 시 승격 안정성)
"""
import json, re, warnings, numpy as np, pandas as pd, joblib

import json as _json, re as _re
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parents[1]
M1_VERSION = _json.loads((_ROOT/"configs/m1_serving_rules.json").read_text())["version"]
JOINT_VERSION = sorted([d.name for d in (_ROOT/"01_Results").glob("v*") if (d/"train_report.json").is_file()], key=lambda v: [int(x) for x in _re.findall(r"\d+", v)])[-1]
from sklearn.metrics import mean_absolute_error
from sklearn.inspection import permutation_importance
from sibc_checkup.m1 import build_m1_dataset, _sealed_split, RESULTS_DIR, _cv_compare, _promotion_rule
from sibc_checkup.env import PROJECT_ROOT
warnings.filterwarnings("ignore")
out = {}

# 1) 서빙 산출 커버리지
srv = sorted((PROJECT_ROOT/"01_Results/serving").glob("m1_predictions_*.parquet"))[-1]
o = pd.read_parquet(srv); n=len(o)
cov = {}
for t in ["sbp","dbp","fasting_glucose","weight","bmi","waist","total_cholesterol","hdl","ldl","triglyceride"]:
    r = o[f"route_{t}"].value_counts().to_dict()
    cov[t] = {k:int(v) for k,v in r.items()}
flags = {c: int(o[c].notna().sum()) for c in o.columns if c.startswith("flag_") and c.endswith("_prob")}
out["serving"] = {"file": srv.name, "n_users": n, "route_counts": cov, "flag_rows": flags,
                  "measured_coverage": {c: round(float(o[c].notna().mean()),3) for c in o.columns if c.startswith("measured_")},
                  "coverage_grade": o["coverage_grade"].value_counts().to_dict(),
                  "abstain_reasons_sbp": o["abstain_reason_sbp"].dropna().str.replace(r"\(\d+d\)","",regex=True).value_counts().to_dict()}

# 2) 특징 중요도 + 3) 하위집단 편향 (봉인셋)
imp, sub = {}, {}
for t in ["sbp","dbp","fasting_glucose"]:
    d, feats = build_m1_dataset(t); d = d[~d["abstain"]]
    _, sealed = _sealed_split(d)
    art = joblib.load(RESULTS_DIR/M1_VERSION/f"{t}.joblib"); m = art["model"]; F = art["features"]
    X = sealed[F]; y = sealed[t]
    pi = permutation_importance(m, X, y, n_repeats=20, random_state=0, scoring="neg_mean_absolute_error")
    top = sorted(zip(F, pi.importances_mean), key=lambda z:-z[1])[:6]
    imp[t] = [(f, round(float(v),3)) for f,v in top]
    s = sealed.copy(); s["res"] = m.predict(X) - y; s["abs"] = s["res"].abs(); s["cf_abs"] = (s[f"anchor_prev_label__{t}"]-y).abs()
    grp = {}
    grp["sex"] = s.groupby("demo_sex").agg(n=("res","size"), bias=("res","mean"), mae=("abs","mean"), cf_mae=("cf_abs","mean")).round(2).to_dict("index")
    s["age_band"] = pd.cut(s["demo_age"], [0,40,50,60,70,200], labels=["<40","40s","50s","60s","70+"])
    grp["age"] = s.groupby("age_band", observed=True).agg(n=("res","size"), bias=("res","mean"), mae=("abs","mean"), cf_mae=("cf_abs","mean")).round(2).to_dict("index")
    s["gap"] = pd.cut(s[f"anchor_days_since__{t}"], [0,400,800,1200], labels=["<=400d","400-800d","800-1200d"])
    grp["anchor_gap"] = s.groupby("gap", observed=True).agg(n=("res","size"), bias=("res","mean"), mae=("abs","mean"), cf_mae=("cf_abs","mean")).round(2).to_dict("index")
    # 극단값(고혈압/고혈당 영역)에서의 오차
    hi = s[y >= (140 if t=="sbp" else 90 if t=="dbp" else 126)]
    grp["high_range"] = {"n": int(len(hi)), "bias": round(float(hi["res"].mean()),2) if len(hi) else None, "mae": round(float(hi["abs"].mean()),2) if len(hi) else None}
    sub[t] = {k:{str(kk):vv for kk,vv in v.items()} if isinstance(v,dict) else v for k,v in grp.items()}
out["importance"] = imp; out["subgroup"] = sub

# 4) 통합 모델 v1.3 — 자체 forward 쌍(웨어러블 보유)에서의 성능 (참고)
from sibc_checkup.unified import load_unified
from sibc_checkup.train import _add_domain_dummies
df = _add_domain_dummies(load_unified()); own = df[df["source"]=="own"]
win = [c for c in own.columns if re.search(r"__w(7|30|90)__", c) and not c.startswith(("anchor_","trend_","ssl_emb"))]
fwd = own[own[win].notna().any(axis=1)]
joint = {}
for t in ["sbp","dbp","weight","bmi","fasting_glucose"]:
    d = fwd[fwd[t].notna()]
    if len(d) < 5: joint[t] = {"n": int(len(d)), "status":"too_few"}; continue
    art = joblib.load(PROJECT_ROOT/f"01_Results/{JOINT_VERSION}"/f"{t}.joblib")
    p = art["model"].predict(d.reindex(columns=art["features"]))
    e = {"n": int(len(d)), "mae_joint": round(mean_absolute_error(d[t], p),2)}
    a = f"anchor_prev_label__{t}"
    if a in d and d[a].notna().any():
        mk = d[a].notna(); e["mae_carry_forward"] = round(mean_absolute_error(d.loc[mk,t], d.loc[mk,a]),2); e["n_with_anchor"]=int(mk.sum())
    joint[t] = e
out["joint_on_forward_pairs"] = joint

# 5) 재현성: 봉인 분할 시드 3종에서 승격 결과 안정성 (sbp/dbp/glucose)
stab = {}
for t in ["sbp","dbp","fasting_glucose","weight"]:
    d, feats = build_m1_dataset(t); d = d[~d["abstain"]]
    res = []
    for seed in (42, 7, 2024):
        tr, se = _sealed_split(d, seed); cv = _cv_compare(tr, feats, t); cv.pop("_cqr")
        best = min(cv, key=lambda k: cv[k]["cv_mae"]); b = cv[best]
        res.append({"seed":seed, "best":best, "route":_promotion_rule(b, tr.user_key.nunique(), se.user_key.nunique()),
                    "cv_mae":round(b["cv_mae"],2), "cf_mae":round(b["base_mae"],2)})
    stab[t] = res
out["stability"] = stab
json.dump(out, open(PROJECT_ROOT/"01_Results/model_audit.json","w"), ensure_ascii=False, indent=2, default=str)
print(json.dumps(out, ensure_ascii=False, indent=1, default=str)[:6000])
