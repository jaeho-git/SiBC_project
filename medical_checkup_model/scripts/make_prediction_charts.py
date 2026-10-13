"""수치 예측 전용 결과 보고서 그림. 실행: uv run --with matplotlib python scripts/make_prediction_charts.py"""
import glob, json, matplotlib, numpy as np, pandas as pd
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT/"scripts/prediction_assets"; OUT.mkdir(exist_ok=True)
for cand in ["Pretendard", "Pretendard Variable", "Apple SD Gothic Neo", "AppleGothic", "NanumGothic"]:
    if any(f.name == cand for f in fm.fontManager.ttflist): plt.rcParams["font.family"] = cand; break
plt.rcParams["axes.unicode_minus"] = False
NAVY, BLUE, LIGHT, GRAY, RED, GREEN, AMBER, LINE, TXT = "#0A3D9A", "#0A64FC", "#8FB4F5", "#6B7280", "#D92D20", "#15803D", "#D97706", "#E5E7EB", "#111827"
ds = json.load(open(ROOT/"01_Results/data_status_2026-09-17.json")); m2 = json.load(open(ROOT/"01_Results/m2/m2_report.json")); sig = json.load(open(ROOT/"01_Results/significance.json"))
m1v = json.load(open(ROOT/"configs/m1_serving_rules.json"))["version"]; m1r = json.load(open(ROOT/f"01_Results/m1/{m1v}/m1_report.json"))["targets"]
L = pd.read_parquet(sorted(glob.glob(str(ROOT/"01_Results/predictions/predictions_long_*.parquet")))[-1])
def style(ax, grid="y"):
    [s.set_visible(False) for k, s in ax.spines.items() if k in ("top", "right")]; ax.spines["left"].set_color(LINE); ax.spines["bottom"].set_color(LINE)
    ax.tick_params(colors=TXT, labelsize=13); ax.grid(axis=grid, color=LINE, lw=0.8); ax.set_axisbelow(True)
def title(ax, t, size=17): ax.set_title(t, loc="left", fontsize=size, color=NAVY, fontweight="bold", pad=12)
KOR = {"sbp": "수축기혈압", "dbp": "이완기혈압", "fasting_glucose": "공복혈당", "weight": "체중", "bmi": "BMI", "waist": "허리둘레", "total_cholesterol": "총콜레스테롤", "hdl": "HDL", "ldl": "LDL", "triglyceride": "중성지방"}
ORDER = ["sbp", "dbp", "fasting_glucose", "weight", "bmi", "waist", "total_cholesterol", "hdl", "ldl", "triglyceride"]

# P1. 데이터 현황과 병목
f, (a1, a2) = plt.subplots(1, 2, figsize=(14, 8), dpi=100, gridspec_kw={"width_ratios": [1.5, 1]}); f.patch.set_facecolor("white")
wn = ds["wearable_now"]; bf = wn["by_feature"]
labs = ["웨어러블 사용자", "혈압 측정 사용자", "체중 측정 사용자", "걸음 기록 사용자", "심박 기록 사용자", "검진 보유 사용자"]
vals = [wn["users"], bf["bp_systolic_measured"]["users"], bf["body_weight_measured"]["users"], bf["step_count"]["users"], bf["heartrate_median"]["users"], ds["labels_now"]["users"]]
y = np.arange(len(labs)); a1.barh(y, vals, 0.6, color=[NAVY, BLUE, BLUE, LIGHT, LIGHT, GRAY])
for i, v in enumerate(vals): a1.text(v+6, i, f"{v}명", va="center", fontsize=13, color=TXT, fontweight="bold")
a1.set_yticks(y); a1.set_yticklabels(labs, fontsize=13); a1.invert_yaxis(); a1.set_xlim(0, 580); style(a1, "x"); title(a1, "보유 데이터 (2026-09-17 기준, 명)", 15)
fn = ds["forward_now"]; a2.barh(["'착용 뒤 검진'\n기록 (현재)", "학습·검증 시작 기준\n(정책)"], [fn["users_ge1d"], 30], 0.55, color=[RED, GRAY])
for i, v in enumerate([fn["users_ge1d"], 30]): a2.text(v+0.6, i, f"{v}명", va="center", fontsize=14, color=TXT, fontweight="bold")
a2.invert_yaxis(); a2.set_xlim(0, 38); style(a2, "x"); title(a2, "걸음·심박·수면을 쓰기 위해 필요한 데이터", 15)
f.tight_layout(); f.savefig(OUT/"P1_data.png"); plt.close(f)

# P2. 수치 예측 정확도
f, ax = plt.subplots(figsize=(14, 8), dpi=100); f.patch.set_facecolor("white"); style(ax)
items = [("수축기혈압\n(mmHg)", "sbp"), ("이완기혈압\n(mmHg)", "dbp"), ("공복혈당\n(mg/dL)", "fasting_glucose")]
x = np.arange(3); cf = [sig["m1"][k]["mae_cf"] for _, k in items]; md = [sig["m1"][k]["mae_model"] for _, k in items]; fl = [m2["noise_ceiling"][k]["mae_floor_estimate"] for _, k in items]
ax.bar(x-0.27, cf, 0.26, color=LIGHT, label="직전 검진값 그대로(비교 기준)"); ax.bar(x, md, 0.26, color=NAVY, label="예측 모델"); ax.bar(x+0.27, fl, 0.26, color=GRAY, label="검진값 자연 변동이 허용하는 하한(추정)")
for i in range(3):
    for dx, v, b in ((-0.27, cf[i], False), (0, md[i], True), (0.27, fl[i], False)): ax.text(x[i]+dx, v+0.2, f"{v:.1f}", ha="center", fontsize=12.5, color=TXT, fontweight="bold" if b else "normal")
    ax.text(x[i]-0.135, max(cf[i], md[i])+1.1, f"−{100*(1-md[i]/cf[i]):.0f}%", ha="center", fontsize=13, color=GREEN, fontweight="bold")
ax.set_xticks(x); ax.set_xticklabels([n for n, _ in items], fontsize=14); ax.set_ylabel("평균 오차 (낮을수록 정확)", fontsize=13, color=GRAY); ax.set_ylim(0, max(cf)+3.2)
ax.legend(frameon=False, fontsize=13, loc="upper left"); title(ax, "수치 예측 정확도 (검증 사용자 61명)")
f.tight_layout(); f.savefig(OUT/"P2_accuracy.png"); plt.close(f)

# P3. 예측 구간 적중률·폭
f, (a1, a2) = plt.subplots(1, 2, figsize=(14, 8), dpi=100, gridspec_kw={"width_ratios": [1, 1]}); f.patch.set_facecolor("white")
picp, width = [], []
for k in ORDER:
    s = m1r[k]["sealed"]; meth = m1r[k].get("interval_method", "constant"); picp.append(s[meth]["picp"]); width.append(s[meth]["width"])
y = np.arange(len(ORDER)); a1.barh(y, [p*100 for p in picp], 0.6, color=[GREEN if p >= 0.8 else AMBER for p in picp]); a1.axvline(85, color=NAVY, ls="--", lw=1); a1.text(85.5, -0.6, "명목 85%", color=NAVY, fontsize=11)
for i, p in enumerate(picp): a1.text(p*100+1, i, f"{p*100:.0f}%", va="center", fontsize=12, color=TXT, fontweight="bold")
a1.set_yticks(y); a1.set_yticklabels([KOR[k] for k in ORDER], fontsize=12.5); a1.invert_yaxis(); a1.set_xlim(0, 108); style(a1, "x"); title(a1, "85% 예측 구간의 실제 적중률 (검증 사용자)", 15)
unit = {"sbp": "mmHg", "dbp": "mmHg", "fasting_glucose": "mg/dL", "weight": "kg", "bmi": "kg/m²", "waist": "cm", "total_cholesterol": "mg/dL", "hdl": "mg/dL", "ldl": "mg/dL", "triglyceride": "mg/dL"}
a2.barh(y, width, 0.6, color=LIGHT)
for i, w in enumerate(width): a2.text(w+1.5, i, f"±{w/2:.1f} {unit[ORDER[i]]}", va="center", fontsize=12, color=TXT)
a2.set_yticks(y); a2.set_yticklabels([KOR[k] for k in ORDER], fontsize=12.5); a2.invert_yaxis(); a2.set_xlim(0, max(width)*1.35); a2.set_xlabel("구간 전체 폭", fontsize=12, color=GRAY); style(a2, "x"); title(a2, "예측 구간의 폭 (평균)", 15)
f.tight_layout(); f.savefig(OUT/"P3_interval.png"); plt.close(f)

# P4. 웨어러블 측정값 활용 효과
f, (a1, a2) = plt.subplots(1, 2, figsize=(14, 8), dpi=100); f.patch.set_facecolor("white")
fu = m2["fusion"]; T = [("수축기혈압", "sbp"), ("이완기혈압", "dbp"), ("체중(kg)", "weight")]; x = np.arange(3)
gl = {"ADOPT": ("채택", GREEN), "PROVISIONAL": ("조건부 채택", AMBER), "REJECT": ("효과 없음 → 미채택", RED)}
b = [fu[k]["with_prior_checkup"]["mae_base"] for _, k in T]; fz = [fu[k]["with_prior_checkup"]["mae_fused"] for _, k in T]
a1.bar(x-0.2, b, 0.38, color=LIGHT, label="검진 이력만 사용"); a1.bar(x+0.2, fz, 0.38, color=NAVY, label="웨어러블 측정값 추가")
for i, (_, k) in enumerate(T):
    a1.text(x[i]-0.2, b[i]+0.15, f"{b[i]:.2f}", ha="center", fontsize=12); a1.text(x[i]+0.2, fz[i]+0.15, f"{fz[i]:.2f}", ha="center", fontsize=12, fontweight="bold")
    g = gl[fu[k]["gate_with_prior"]]; a1.text(x[i], max(b[i], fz[i])+1.0, g[0], ha="center", fontsize=12.5, color=g[1], fontweight="bold")
a1.set_xticks(x); a1.set_xticklabels([n for n, _ in T], fontsize=13); a1.set_ylim(0, max(b)+2.6); style(a1); a1.legend(frameon=False, fontsize=11.5, loc="upper right"); title(a1, "검진 이력이 있는 사용자 (평균 오차)", 15)
r = [fu[k]["no_prior_checkup"]["mae_korean_reference_only"] for _, k in T]; m0 = [fu[k]["no_prior_checkup"]["mae_m0_measured"] for _, k in T]
a2.bar(x-0.2, r, 0.38, color=GRAY, label="성별·연령 평균만"); a2.bar(x+0.2, m0, 0.38, color=BLUE, label="웨어러블 측정값 반영")
for i, (_, k) in enumerate(T):
    a2.text(x[i]-0.2, r[i]+0.15, f"{r[i]:.2f}", ha="center", fontsize=12); a2.text(x[i]+0.2, m0[i]+0.15, f"{m0[i]:.2f}", ha="center", fontsize=12, fontweight="bold")
    g = gl[fu[k]["gate_no_prior"]]; a2.text(x[i], max(r[i], m0[i])+1.0, g[0], ha="center", fontsize=12.5, color=g[1], fontweight="bold")
a2.set_xticks(x); a2.set_xticklabels([n for n, _ in T], fontsize=13); a2.set_ylim(0, max(r)+2.6); style(a2); a2.legend(frameon=False, fontsize=11.5, loc="upper right"); title(a2, "검진 이력이 없는 사용자 (평균 오차)", 15)
f.tight_layout(); f.savefig(OUT/"P4_wearable.png"); plt.close(f)

# P5. 산출 범위와 경로
f, ax = plt.subplots(figsize=(14, 8), dpi=100); f.patch.set_facecolor("white"); style(ax, "x")
routes = [("M1_MODEL", "개인화 모델", NAVY), ("FUSION", "검진+웨어러블 융합", "#1D4ED8"), ("FUSION_DERIVED", "융합 체중에서 파생", "#1D4ED8"), ("CARRY_FORWARD", "직전 검진값 유지", LIGHT), ("MODEL_CROSS", "다른 항목 기반(참고)", "#93C5FD"), ("M0_MEASURED", "이력 없음: 측정값 기반", BLUE), ("ABSTAIN", "보류", LINE)]
ct = L.groupby(["item", "route"]).size().unstack(fill_value=0).reindex(ORDER); n_users = L["user_key"].nunique()
left = np.zeros(len(ORDER)); seen = set(); cov = {}
for key, lab, c in routes:
    v = ct[key].to_numpy() if key in ct else np.zeros(len(ORDER)); lbl = lab if lab not in seen else None; seen.add(lab)
    ax.barh([KOR[k] for k in ORDER], v, left=left, color=c, label=lbl)
    for i, (l, w) in enumerate(zip(left, v)):
        if w >= 25: ax.text(l+w/2, i, str(int(w)), ha="center", va="center", fontsize=11.5, color=("white" if c in (NAVY, "#1D4ED8", BLUE) else TXT))
    for k, w in zip(ORDER, v): cov.setdefault(k, {})[key] = int(w)
    left += v
ax.invert_yaxis(); ax.set_xlim(0, n_users); ax.set_xlabel(f"사용자 수 (전체 {n_users}명)", fontsize=13, color=GRAY)
ax.legend(frameon=False, fontsize=11.5, loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=6); title(ax, "항목별 산출 범위와 산출 경로")
f.tight_layout(); f.savefig(OUT/"P5_coverage.png"); plt.close(f)
ev = L[L.route != "ABSTAIN"].groupby("item")["evidence_level"].value_counts().unstack(fill_value=0).reindex(ORDER).fillna(0).astype(int).to_dict("index")
json.dump({"users": int(n_users), "rows": int(len(L)), "with_checkup": int(L.groupby("user_key")["basis_prev_checkup_value"].apply(lambda s: s.notna().any()).sum()),
           "coverage": cov, "evidence": ev, "picp": dict(zip(ORDER, picp)), "width": dict(zip(ORDER, width)),
           "abstain_reasons": L[L.route == "ABSTAIN"]["abstain_reason"].str.replace(r"\(\d+d\)", "", regex=True).value_counts().to_dict()},
          open(ROOT/"01_Results/predictions/prediction_summary.json", "w"), ensure_ascii=False, indent=1)
print(sorted(p.name for p in OUT.glob("*.png")))
