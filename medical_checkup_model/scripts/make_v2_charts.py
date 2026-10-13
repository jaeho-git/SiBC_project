"""산출 v2(실측·예측 분리) 보고서 그림 + 요약 JSON. 실행: uv run --with matplotlib python scripts/make_v2_charts.py"""
import glob, json, re, sys, warnings, matplotlib, numpy as np, pandas as pd
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT/"scripts/v2_assets"; OUT.mkdir(exist_ok=True); sys.path.insert(0, str(ROOT/"src")); warnings.filterwarnings("ignore")
for cand in ["Pretendard", "Pretendard Variable", "Apple SD Gothic Neo", "AppleGothic", "NanumGothic"]:
    if any(f.name == cand for f in fm.fontManager.ttflist): plt.rcParams["font.family"] = cand; break
plt.rcParams["axes.unicode_minus"] = False
NAVY, BLUE, LIGHT, GRAY, RED, GREEN, AMBER, LINE, TXT = "#0A3D9A", "#0A64FC", "#8FB4F5", "#6B7280", "#D92D20", "#15803D", "#D97706", "#E5E7EB", "#111827"
ds = json.load(open(ROOT/"01_Results/data_status_2026-09-17.json")); m2 = json.load(open(ROOT/"01_Results/m2/m2_report.json")); sig = json.load(open(ROOT/"01_Results/significance.json"))
wc = json.load(open(ROOT/"01_Results/wearable_contribution.json"))
L = pd.read_parquet(sorted(glob.glob(str(ROOT/"01_Results/predictions/predictions_long_*.parquet")))[-1])
KOR = {"sbp": "수축기혈압", "dbp": "이완기혈압", "fasting_glucose": "공복혈당", "weight": "체중", "bmi": "BMI", "waist": "허리둘레", "total_cholesterol": "총콜레스테롤", "hdl": "HDL", "ldl": "LDL", "triglyceride": "중성지방"}
ORDER = ["sbp", "dbp", "fasting_glucose", "weight", "bmi", "waist", "total_cholesterol", "hdl", "ldl", "triglyceride"]
def style(ax, grid="y"):
    [s.set_visible(False) for k, s in ax.spines.items() if k in ("top", "right")]; ax.spines["left"].set_color(LINE); ax.spines["bottom"].set_color(LINE)
    ax.tick_params(colors=TXT, labelsize=13); ax.grid(axis=grid, color=LINE, lw=0.8); ax.set_axisbelow(True)
def title(ax, t, size=17): ax.set_title(t, loc="left", fontsize=size, color=NAVY, fontweight="bold", pad=12)

# Q1. 데이터 현황·병목
f, (a1, a2) = plt.subplots(1, 2, figsize=(14, 8), dpi=100, gridspec_kw={"width_ratios": [1.5, 1]}); f.patch.set_facecolor("white")
wn = ds["wearable_now"]; bf = wn["by_feature"]
labs = ["웨어러블 사용자", "걸음 기록", "심박 기록", "수면 기록", "혈압계 측정", "체중계 측정", "검진 기록 보유"]
vals = [wn["users"], bf["step_count"]["users"], bf["heartrate_median"]["users"], bf["sleep_duration_min"]["users"], bf["bp_systolic_measured"]["users"], bf["body_weight_measured"]["users"], ds["labels_now"]["users"]]
cols = [NAVY, BLUE, BLUE, BLUE, LIGHT, LIGHT, GRAY]; y = np.arange(len(labs)); a1.barh(y, vals, 0.6, color=cols)
for i, v in enumerate(vals): a1.text(v+6, i, f"{v}명", va="center", fontsize=13, color=TXT, fontweight="bold")
a1.set_yticks(y); a1.set_yticklabels(labs, fontsize=13); a1.invert_yaxis(); a1.set_xlim(0, 580); style(a1, "x"); title(a1, "보유 데이터 (명) — 파랑: 간접 신호, 연청: 직접 측정", 14)
fn = ds["forward_now"]; a2.barh(["'착용 뒤 검진'\n기록 (현재)", "학습·검증 시작 기준\n(정책)"], [fn["users_ge1d"], 30], 0.55, color=[RED, GRAY])
for i, v in enumerate([fn["users_ge1d"], 30]): a2.text(v+0.6, i, f"{v}명", va="center", fontsize=14, color=TXT, fontweight="bold")
a2.invert_yaxis(); a2.set_xlim(0, 38); style(a2, "x"); title(a2, "간접 신호로 예측을 학습·검증하는 데 필요한 데이터", 14)
f.tight_layout(); f.savefig(OUT/"Q1_data.png"); plt.close(f)

# Q2. 웨어러블 간접 신호의 기여 (공공 홀드아웃 절제)
f, ax = plt.subplots(figsize=(14, 8), dpi=100); f.patch.set_facecolor("white"); style(ax, "x")
ph = wc["public_holdout"]; g = [ph[k]["activity_gain_pct_vs_demo"] for k in ORDER]; g2 = [100*(1-ph[k]["demo_activity_grip"]["mae"]/ph[k]["demo_only"]["mae"]) for k in ORDER]
y = np.arange(len(ORDER)); ax.barh(y-0.18, g, 0.34, color=BLUE, label="+ 걸음·활동량·활동시간"); ax.barh(y+0.18, g2, 0.34, color=NAVY, label="+ 걸음·활동량·활동시간 + 악력")
for i in range(len(ORDER)): ax.text(max(g[i], 0)+0.15, y[i]-0.18, f"{g[i]:+.1f}%", va="center", fontsize=11.5, color=TXT); ax.text(max(g2[i], 0)+0.15, y[i]+0.18, f"{g2[i]:+.1f}%", va="center", fontsize=11.5, color=TXT, fontweight="bold")
ax.axvline(0, color=TXT, lw=1); ax.axvline(3, color=GREEN, ls="--", lw=1); ax.text(3.1, len(ORDER)-0.6, "채택 기준 3%", color=GREEN, fontsize=11)
ax.set_yticks(y); ax.set_yticklabels([KOR[k] for k in ORDER], fontsize=13); ax.invert_yaxis(); ax.set_xlim(-2, 12); ax.set_xlabel("성별·연령만 쓴 모델 대비 오차 감소율 (%)", fontsize=13, color=GRAY)
ax.legend(frameon=False, fontsize=12.5, loc="lower right"); title(ax, f"웨어러블 간접 신호의 예측 기여 — 공공데이터 홀드아웃 {wc['n_public_test']:,}건 (우리 사용자 성능 아님)")
f.tight_layout(); f.savefig(OUT/"Q2_contribution.png"); plt.close(f)

# Q3. 검진 이력 기반 예측 정확도 (검증됨)
f, ax = plt.subplots(figsize=(14, 8), dpi=100); f.patch.set_facecolor("white"); style(ax)
items = [("수축기혈압\n(mmHg)", "sbp"), ("이완기혈압\n(mmHg)", "dbp"), ("공복혈당\n(mg/dL)", "fasting_glucose")]
x = np.arange(3); cf = [sig["m1"][k]["mae_cf"] for _, k in items]; md = [sig["m1"][k]["mae_model"] for _, k in items]; fl = [m2["noise_ceiling"][k]["mae_floor_estimate"] for _, k in items]
ax.bar(x-0.27, cf, 0.26, color=LIGHT, label="직전 검진값 그대로(비교 기준)"); ax.bar(x, md, 0.26, color=NAVY, label="검진 이력 기반 예측(HISTORY)"); ax.bar(x+0.27, fl, 0.26, color=GRAY, label="검진값 자연 변동이 허용하는 하한(추정)")
for i in range(3):
    for dx, v, b in ((-0.27, cf[i], False), (0, md[i], True), (0.27, fl[i], False)): ax.text(x[i]+dx, v+0.2, f"{v:.1f}", ha="center", fontsize=12.5, color=TXT, fontweight="bold" if b else "normal")
    ax.text(x[i]-0.135, max(cf[i], md[i])+1.1, f"−{100*(1-md[i]/cf[i]):.0f}%", ha="center", fontsize=13, color=GREEN, fontweight="bold")
ax.set_xticks(x); ax.set_xticklabels([n for n, _ in items], fontsize=14); ax.set_ylabel("평균 오차 (낮을수록 정확)", fontsize=13, color=GRAY); ax.set_ylim(0, max(cf)+3.2)
ax.legend(frameon=False, fontsize=13, loc="upper left"); title(ax, "검진 이력 기반 예측의 정확도 (자체 검증 사용자 61명, 웨어러블 미사용)")
f.tight_layout(); f.savefig(OUT/"Q3_history.png"); plt.close(f)

# Q4. 산출 범위: 항목 × (실측 / 이력 예측 / 웨어러블 반영 예측)
n_users = L["user_key"].nunique()
def cnt(kind, methods, item): return int(L[(L["kind"] == kind) & L["method"].isin(methods) & (L["item"] == item) & L["value"].notna()]["user_key"].nunique())
rows = {k: {"실측": cnt("MEASURED", ["DEVICE", "DEVICE_DERIVED"], k), "이력 예측(검증됨)": cnt("PREDICTED", ["HISTORY"], k), "이력+웨어러블 예측(참고)": cnt("PREDICTED", ["HISTORY_WEARABLE"], k), "웨어러블만 예측(미검증)": cnt("PREDICTED", ["WEARABLE_ONLY"], k)} for k in ORDER}
f, ax = plt.subplots(figsize=(14, 8), dpi=100); f.patch.set_facecolor("white"); style(ax, "x")
y = np.arange(len(ORDER)); h = 0.2; series = [("실측", GRAY), ("이력 예측(검증됨)", NAVY), ("이력+웨어러블 예측(참고)", BLUE), ("웨어러블만 예측(미검증)", LIGHT)]
for j, (name, c) in enumerate(series):
    v = [rows[k][name] for k in ORDER]; ax.barh(y+(j-1.5)*h, v, h, color=c, label=name)
    for i, w in enumerate(v):
        if w: ax.text(w+4, y[i]+(j-1.5)*h, str(w), va="center", fontsize=10, color=TXT)
ax.set_yticks(y); ax.set_yticklabels([KOR[k] for k in ORDER], fontsize=13); ax.invert_yaxis(); ax.set_xlim(0, n_users+40); ax.set_xlabel(f"값을 받는 사용자 수 (전체 {n_users}명)", fontsize=13, color=GRAY)
ax.legend(frameon=False, fontsize=12, loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=4); title(ax, "항목별 산출 범위 — 실측과 예측을 분리")
f.tight_layout(); f.savefig(OUT/"Q4_coverage.png"); plt.close(f)

# 요약 JSON (+ 실측 대 예측 일치도: 참고)
agree = {}
for t in ("sbp", "dbp", "weight"):
    m = L[(L["item"] == t) & (L["kind"] == "MEASURED")][["user_key", "value"]].rename(columns={"value": "meas"})
    for meth in ("HISTORY", "HISTORY_WEARABLE"):
        p = L[(L["item"] == t) & (L["method"] == meth) & L["value"].notna()][["user_key", "value"]].rename(columns={"value": "pred"})
        j = m.merge(p, on="user_key")
        if len(j): agree[f"{t}_{meth}"] = {"n": int(len(j)), "mae_vs_measured": round(float((j["meas"]-j["pred"]).abs().mean()), 2), "bias_pred_minus_measured": round(float((j["pred"]-j["meas"]).mean()), 2)}
summ = {"users": int(n_users), "rows": int(len(L)), "with_checkup": int(L.groupby("user_key")["basis_prev_checkup_value"].apply(lambda s: s.notna().any()).sum()),
        "coverage": rows, "abstain_reasons": L[(L["kind"] == "PREDICTED") & (L["route"] == "ABSTAIN")]["abstain_reason"].str.replace(r"\(\d+d\)", "", regex=True).value_counts().to_dict(),
        "measured_vs_predicted_agreement_reference": agree, "public_gain": {k: ph[k]["activity_gain_pct_vs_demo"] for k in ORDER}, "public_gain_grip": {k: round(100*(1-ph[k]["demo_activity_grip"]["mae"]/ph[k]["demo_only"]["mae"]), 1) for k in ORDER}}
json.dump(summ, open(ROOT/"01_Results/predictions/prediction_summary_v2.json", "w"), ensure_ascii=False, indent=1)
print(sorted(p.name for p in OUT.glob("*.png"))); print(json.dumps({k: summ[k] for k in ("users", "with_checkup", "abstain_reasons", "measured_vs_predicted_agreement_reference")}, ensure_ascii=False))
print(rows)
