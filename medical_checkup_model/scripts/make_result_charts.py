"""결과 보고서(첫 보고용) 그림 5종 — 과거 비교 없이 현재 데이터셋·현재 모델 기준. 실행: uv run --with matplotlib python scripts/make_result_charts.py"""
import json, matplotlib, numpy as np, pandas as pd
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT/"scripts/result_assets"; OUT.mkdir(exist_ok=True)
for cand in ["Pretendard", "Pretendard Variable", "Apple SD Gothic Neo", "AppleGothic", "NanumGothic"]:
    if any(f.name == cand for f in fm.fontManager.ttflist): plt.rcParams["font.family"] = cand; break
plt.rcParams["axes.unicode_minus"] = False
NAVY, BLUE, LIGHT, GRAY, RED, GREEN, AMBER, LINE, TXT = "#0A3D9A", "#0A64FC", "#8FB4F5", "#6B7280", "#D92D20", "#15803D", "#D97706", "#E5E7EB", "#111827"
ds = json.load(open(ROOT/"01_Results/data_status_2026-09-17.json")); m2 = json.load(open(ROOT/"01_Results/m2/m2_report.json")); sig = json.load(open(ROOT/"01_Results/significance.json"))
def style(ax, grid="y"):
    [s.set_visible(False) for k, s in ax.spines.items() if k in ("top", "right")]; ax.spines["left"].set_color(LINE); ax.spines["bottom"].set_color(LINE)
    ax.tick_params(colors=TXT, labelsize=13); ax.grid(axis=grid, color=LINE, lw=0.8); ax.set_axisbelow(True)
def title(ax, t, size=17): ax.set_title(t, loc="left", fontsize=size, color=NAVY, fontweight="bold", pad=12)

# R1. 데이터 현황과 병목
f, (a1, a2) = plt.subplots(1, 2, figsize=(14, 8), dpi=100, gridspec_kw={"width_ratios": [1.5, 1]}); f.patch.set_facecolor("white")
wn = ds["wearable_now"]; bf = wn["by_feature"]
labs = ["웨어러블 사용자", "혈압 측정 사용자", "체중 측정 사용자", "걸음 기록 사용자", "심박 기록 사용자", "검진 보유 사용자"]
vals = [wn["users"], bf["bp_systolic_measured"]["users"], bf["body_weight_measured"]["users"], bf["step_count"]["users"], bf["heartrate_median"]["users"], ds["labels_now"]["users"]]
cols = [NAVY, BLUE, BLUE, LIGHT, LIGHT, GRAY]; y = np.arange(len(labs)); a1.barh(y, vals, 0.6, color=cols)
for i, v in enumerate(vals): a1.text(v+6, i, f"{v}명", va="center", fontsize=13, color=TXT, fontweight="bold")
a1.set_yticks(y); a1.set_yticklabels(labs, fontsize=13); a1.invert_yaxis(); a1.set_xlim(0, 580); style(a1, "x"); title(a1, "보유 데이터 (2026-09-17 기준, 명)", 15)
fn = ds["forward_now"]
a2.barh(["'착용 뒤 검진'\n정답지 (현재)", "검증 시작 기준\n(정책)"], [fn["users_ge1d"], 30], 0.55, color=[RED, GRAY])
for i, v in enumerate([fn["users_ge1d"], 30]): a2.text(v+0.6, i, f"{v}명", va="center", fontsize=14, color=TXT, fontweight="bold")
a2.invert_yaxis(); a2.set_xlim(0, 38); style(a2, "x"); title(a2, "걸음·심박·수면 검증에 필요한 데이터", 15)
f.tight_layout(); f.savefig(OUT/"R1_data.png"); plt.close(f)

# R2. 수치 예측 정확도: 직전값 / 모델 / 하한
f, ax = plt.subplots(figsize=(14, 8), dpi=100); f.patch.set_facecolor("white"); style(ax)
items = [("수축기혈압\n(mmHg)", "sbp"), ("이완기혈압\n(mmHg)", "dbp"), ("공복혈당\n(mg/dL)", "fasting_glucose")]
x = np.arange(3); cf = [sig["m1"][k]["mae_cf"] for _, k in items]; md = [sig["m1"][k]["mae_model"] for _, k in items]; fl = [m2["noise_ceiling"][k]["mae_floor_estimate"] for _, k in items]
ax.bar(x-0.27, cf, 0.26, color=LIGHT, label="직전 검진값 그대로(비교 기준)"); ax.bar(x, md, 0.26, color=NAVY, label="예측 모델"); ax.bar(x+0.27, fl, 0.26, color=GRAY, label="검진값 자연 변동이 허용하는 하한(추정)")
for i in range(3):
    for dx, v, b in ((-0.27, cf[i], False), (0, md[i], True), (0.27, fl[i], False)): ax.text(x[i]+dx, v+0.2, f"{v:.1f}", ha="center", fontsize=12.5, color=TXT, fontweight="bold" if b else "normal")
    ax.text(x[i]-0.135, max(cf[i], md[i])+1.1, f"−{100*(1-md[i]/cf[i]):.0f}%", ha="center", fontsize=13, color=GREEN, fontweight="bold")
ax.set_xticks(x); ax.set_xticklabels([n for n, _ in items], fontsize=14); ax.set_ylabel("평균 오차 (낮을수록 정확)", fontsize=13, color=GRAY); ax.set_ylim(0, max(cf)+3.2)
ax.legend(frameon=False, fontsize=13, loc="upper left"); title(ax, "수치 예측 정확도 (검증 사용자 61명)")
f.tight_layout(); f.savefig(OUT/"R2_accuracy.png"); plt.close(f)

# R3. 기준 초과자를 찾아낸 비율: 안내 규칙 비교
f, ax = plt.subplots(figsize=(14, 8), dpi=100); f.patch.set_facecolor("white"); style(ax)
names = [("고혈압\n≥140/90", "hypertension_140_90"), ("공복혈당장애\n≥100", "fasting_glucose_ge100"), ("비만\nBMI≥25", "obesity_bmi_ge25"), ("복부비만", "abdominal_obesity")]
x = np.arange(4); rules = [("rule_prior_status", "직전 검진 상태 그대로", LIGHT), ("rule_prob_ge_0.5", "일반 기준(확률 0.5 이상)", GRAY), ("rule_referral_threshold", "적용한 안내 기준점", NAVY)]
for j, (rk, lab, c) in enumerate(rules):
    v = [m2["referral"][k]["final_validation"][rk]["sensitivity"]*100 for _, k in names]; ms = [m2["referral"][k]["final_validation"][rk]["missed"] for _, k in names]; ps = [m2["referral"][k]["final_validation"][rk]["positives"] for _, k in names]
    ax.bar(x+(j-1)*0.27, v, 0.26, color=c, label=lab)
    for i in range(4): ax.text(x[i]+(j-1)*0.27, v[i]+1.2, f"{v[i]:.0f}%\n놓침 {ms[i]}/{ps[i]}", ha="center", fontsize=10.5, color=(NAVY if j == 2 else TXT), fontweight="bold" if j == 2 else "normal")
ax.axhline(85, color=GREEN, lw=1, ls="--"); ax.text(-0.5, 86, "목표 85%", fontsize=11, color=GREEN, ha="left")
ax.set_xticks(x); ax.set_xticklabels([n for n, _ in names], fontsize=14); ax.set_ylabel("기준 초과자를 찾아낸 비율 (%)", fontsize=13, color=GRAY); ax.set_ylim(0, 118)
ax.legend(frameon=False, fontsize=12.5, loc="upper left", ncol=3); title(ax, "기준 초과자를 찾아낸 비율 — 안내 규칙별 (검증 사용자)")
f.tight_layout(); f.savefig(OUT/"R3_referral.png"); plt.close(f)

# R4. 웨어러블 측정값 활용 효과
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
f.tight_layout(); f.savefig(OUT/"R4_wearable.png"); plt.close(f)

# R5. 서비스 산출 범위(현재)
import glob
o = pd.read_parquet(sorted(glob.glob(str(ROOT/"01_Results/serving/m2_predictions_*.parquet")))[-1]); m1 = pd.read_parquet(sorted(glob.glob(str(ROOT/"01_Results/serving/m1_predictions_*.parquet")))[-1])
f, ax = plt.subplots(figsize=(14, 8), dpi=100); f.patch.set_facecolor("white"); style(ax, "x")
rows = []
for t, kor in (("sbp", "수축기혈압"), ("dbp", "이완기혈압"), ("weight", "체중"), ("bmi", "BMI")):
    rc = o[f"m2_route_{t}"].value_counts().to_dict()
    rows.append((kor, {"검진 이력 기반 예측": rc.get("M1_ONLY", 0), "웨어러블 측정값 융합": rc.get("FUSION", 0)+rc.get("FUSION_DERIVED", 0), "검진 이력 없음·오래됨(측정값 기반)": rc.get("M0_MEASURED", 0), "보류": rc.get("ABSTAIN", 0)}))
for t, kor in (("fasting_glucose", "공복혈당"), ("total_cholesterol", "총콜레스테롤 등 지질")):
    n = int(m1[f"pred_{t}"].notna().sum()); rows.append((kor, {"검진 이력 기반 예측": n, "보류": len(o)-n}))
cmap = {"검진 이력 기반 예측": LIGHT, "웨어러블 측정값 융합": NAVY, "검진 이력 없음·오래됨(측정값 기반)": BLUE, "보류": LINE}; left = np.zeros(len(rows)); ylab = [r[0] for r in rows]
for key, c in cmap.items():
    v = np.array([r[1].get(key, 0) for r in rows]); ax.barh(ylab, v, left=left, color=c, label=key)
    for i, (l, w) in enumerate(zip(left, v)):
        if w >= 25: ax.text(l+w/2, i, str(int(w)), ha="center", va="center", fontsize=12, color=("white" if c in (NAVY, BLUE) else TXT))
    left += v
ax.invert_yaxis(); ax.set_xlim(0, len(o)); ax.set_xlabel(f"사용자 수 (전체 {len(o)}명)", fontsize=13, color=GRAY)
ax.legend(frameon=False, fontsize=12, loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=4); title(ax, "항목별 산출 범위와 산출 방식")
f.tight_layout(); f.savefig(OUT/"R5_coverage.png"); plt.close(f)

# R6. 가이드라인 3단계 판정 검증: 실제 '위험'인 사람을 어떻게 분류했는가
tv = m2["tier_validation"]; doms = [("blood_pressure", "혈압"), ("fasting_glucose", "공복혈당"), ("obesity_bmi", "비만(BMI)"), ("abdominal_obesity", "복부비만")]
f, ax = plt.subplots(figsize=(14, 8), dpi=100); f.patch.set_facecolor("white"); style(ax, "x")
ylab, segs = [], []
for k, kor in doms:
    for col, lab in (("prior_status", "직전 검진 단계 그대로"), ("final", "모델 판정")):
        v = tv[k][col]; n = v["actual_risk_n"]; r = v["actual_risk_called_risk"]; c = v["actual_risk_called_caution_or_risk"] - r; miss = 1 - v["actual_risk_called_caution_or_risk"]
        ylab.append(f"{kor} — {lab}\n(실제 위험 {n}명)"); segs.append((r*100, c*100, miss*100, v["actual_risk_missed_as_normal"]))
y = np.arange(len(ylab)); left = np.zeros(len(ylab))
for j, (lab, c) in enumerate((("'위험'으로 판정", RED), ("'주의'로 판정", AMBER), ("'정상'으로 판정 (놓침)", GRAY))):
    v = np.array([sg_[j] for sg_ in segs]); ax.barh(y, v, left=left, color=c, label=lab, height=0.62)
    for i, (l, w) in enumerate(zip(left, v)):
        if w >= 6: ax.text(l+w/2, i, f"{w:.0f}%" + (f" ({segs[i][3]}명)" if j == 2 else ""), ha="center", va="center", fontsize=12, color="white", fontweight="bold")
    left += v
ax.set_yticks(y); ax.set_yticklabels(ylab, fontsize=12); ax.invert_yaxis(); ax.set_xlim(0, 100); ax.set_xlabel("실제 '위험' 단계였던 검진 중 비율 (%)", fontsize=13, color=GRAY)
ax.legend(frameon=False, fontsize=12.5, loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=3); title(ax, "실제 '위험' 단계인 사람을 어떻게 판정했는가 (검증 사용자)")
f.tight_layout(); f.savefig(OUT/"R6_tier_validation.png"); plt.close(f)

# R7. 전체 사용자 판정 분포
f, ax = plt.subplots(figsize=(14, 8), dpi=100); f.patch.set_facecolor("white"); style(ax, "x")
cols_ = [("tier_pred_blood_pressure", "혈압"), ("tier_pred_fasting_glucose", "공복혈당"), ("tier_pred_obesity_bmi", "비만(BMI)"), ("tier_pred_abdominal_obesity", "복부비만"),
         ("tier_pred_total_cholesterol", "총콜레스테롤 (참고)"), ("tier_pred_ldl", "LDL (참고)"), ("tier_pred_triglyceride", "중성지방 (참고)"), ("tier_pred_hdl", "HDL (참고)")]
left = np.zeros(len(cols_)); dist = {}
for lab, c in (("정상", GREEN), ("주의", AMBER), ("위험", RED), ("보류", LINE)):
    v = np.array([(o[cn] == lab).sum() if lab != "보류" else o[cn].isna().sum() for cn, _ in cols_]); ax.barh([k for _, k in cols_], v, left=left, color=c, label=lab)
    for i, (l, w) in enumerate(zip(left, v)):
        if w >= 22: ax.text(l+w/2, i, str(int(w)), ha="center", va="center", fontsize=12, color=("white" if c != LINE else TXT), fontweight="bold")
    for (cn, k), w in zip(cols_, v): dist.setdefault(k, {})[lab] = int(w)
    left += v
ax.invert_yaxis(); ax.set_xlim(0, len(o)); ax.set_xlabel(f"사용자 수 (전체 {len(o)}명)", fontsize=13, color=GRAY)
ax.legend(frameon=False, fontsize=12.5, loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=4); title(ax, "항목별 판정 분포 (기저질환 미상 기본 기준 적용)")
f.tight_layout(); f.savefig(OUT/"R7_tier_distribution.png"); plt.close(f)
cov = {r[0]: r[1] for r in rows}
(ROOT/"01_Results/m2/result_summary.json").write_text(json.dumps({"users": int(len(o)), "with_checkup": int(o["has_checkup"].sum()), "no_checkup": int((~o["has_checkup"]).sum()), "coverage": cov, "tier_distribution": dist}, ensure_ascii=False, indent=1))
print(sorted(p.name for p in OUT.glob("*.png"))); print(cov)
