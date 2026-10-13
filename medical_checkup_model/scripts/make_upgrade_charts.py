"""고도화 결과 보고서 그림 5종 (1400x800, 분석 보고서와 같은 팔레트). 실행: uv run --with matplotlib python scripts/make_upgrade_charts.py"""
import json, matplotlib, numpy as np, pandas as pd
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT/"scripts/upgrade_assets"; OUT.mkdir(exist_ok=True)
for cand in ["Pretendard", "Pretendard Variable", "Apple SD Gothic Neo", "AppleGothic", "NanumGothic"]:
    if any(f.name == cand for f in fm.fontManager.ttflist): plt.rcParams["font.family"] = cand; break
plt.rcParams["axes.unicode_minus"] = False
NAVY, BLUE, LIGHT, GRAY, RED, GREEN, AMBER, LINE, TXT = "#0A3D9A", "#0A64FC", "#8FB4F5", "#6B7280", "#D92D20", "#15803D", "#D97706", "#E5E7EB", "#111827"
ds = json.load(open(ROOT/"01_Results/data_status_2026-09-17.json")); m2 = json.load(open(ROOT/"01_Results/m2/m2_report.json"))
sig = json.load(open(ROOT/"01_Results/significance.json"))
def style(ax, grid="y"):
    [s.set_visible(False) for k, s in ax.spines.items() if k in ("top", "right")]; ax.spines["left"].set_color(LINE); ax.spines["bottom"].set_color(LINE)
    ax.tick_params(colors=TXT, labelsize=13); ax.grid(axis=grid, color=LINE, lw=0.8); ax.set_axisbelow(True)
def title(ax, t, size=17): ax.set_title(t, loc="left", fontsize=size, color=NAVY, fontweight="bold", pad=12)

# 그림 1. 데이터 변동: 이전 데이터셋(직전 모델 구축 시 사용) → 현재 데이터셋(2026-09-17 기준), 그리고 정답지 병목
f, (a1, a2) = plt.subplots(1, 2, figsize=(14, 8), dpi=100, gridspec_kw={"width_ratios": [1.5, 1]}); f.patch.set_facecolor("white")
wp, wn = ds["wearable_prev"], ds["wearable_now"]
labs = ["웨어러블 사용자", "30일 이상 착용자", "혈압 측정 사용자", "체중 측정 사용자", "검진 보유 사용자"]
prev = [wp["users"], wp["users_ge30days"], wp["by_feature"]["bp_systolic_measured"]["users"], wp["by_feature"]["body_weight_measured"]["users"], 394]
now = [wn["users"], wn["users_ge30days"], wn["by_feature"]["bp_systolic_measured"]["users"], wn["by_feature"]["body_weight_measured"]["users"], ds["labels_now"]["users"]]
y = np.arange(len(labs)); a1.barh(y-0.2, prev, 0.38, color=LIGHT, label="이전 데이터셋"); a1.barh(y+0.2, now, 0.38, color=NAVY, label="현재 데이터셋 (9/17 기준)")
for i in range(len(labs)): a1.text(prev[i]+6, y[i]-0.2, str(prev[i]), va="center", fontsize=12, color=TXT); a1.text(now[i]+6, y[i]+0.2, f"{now[i]}  (+{now[i]-prev[i]}, +{100*(now[i]-prev[i])/prev[i]:.0f}%)", va="center", fontsize=12, color=TXT, fontweight="bold")
a1.set_yticks(y); a1.set_yticklabels(labs, fontsize=13); a1.invert_yaxis(); a1.set_xlim(0, 680); style(a1, "x"); a1.legend(frameon=False, fontsize=12, loc="upper center", bbox_to_anchor=(0.5, -0.06), ncol=2); title(a1, "이전 대비 현재 데이터셋의 변동 (명)", 15)
fp, fn = ds["forward_prev_with_current_labels"], ds["forward_now"]
a2.barh(["'착용 뒤 검진' 정답지\n이전 데이터셋", "'착용 뒤 검진' 정답지\n현재 데이터셋", "검증 시작 기준\n(정책)"], [fp["users_ge1d"], fn["users_ge1d"], 30], color=[LIGHT, RED, GRAY])
for i, v in enumerate([fp["users_ge1d"], fn["users_ge1d"], 30]): a2.text(v+0.6, i, f"{v}명", va="center", fontsize=13, color=TXT, fontweight="bold")
a2.invert_yaxis(); a2.set_xlim(0, 38); style(a2, "x"); title(a2, "간접 신호 검증의 병목은 그대로", 15)
f.tight_layout(); f.savefig(OUT/"U1_data.png"); plt.close(f)

# 그림 2. 오차의 바닥: 직전값 / 우리 모델 / 개인 내 변동이 허용하는 하한
f, ax = plt.subplots(figsize=(14, 8), dpi=100); f.patch.set_facecolor("white"); style(ax)
items = [("수축기혈압\n(mmHg)", "sbp"), ("이완기혈압\n(mmHg)", "dbp"), ("공복혈당\n(mg/dL)", "fasting_glucose")]
x = np.arange(3); cf = [sig["m1"][k]["mae_cf"] for _, k in items]; md = [sig["m1"][k]["mae_model"] for _, k in items]; fl = [m2["noise_ceiling"][k]["mae_floor_estimate"] for _, k in items]
ax.bar(x-0.27, cf, 0.26, color=LIGHT, label="직전 검진값 그대로"); ax.bar(x, md, 0.26, color=NAVY, label="우리 모델(M1, 최종 검증)"); ax.bar(x+0.27, fl, 0.26, color=GRAY, label="개인 내 변동이 허용하는 하한(추정)")
for i in range(3):
    for dx, v, b in ((-0.27, cf[i], False), (0, md[i], True), (0.27, fl[i], False)): ax.text(x[i]+dx, v+0.2, f"{v:.1f}", ha="center", fontsize=12.5, color=TXT, fontweight="bold" if b else "normal")
ax.set_xticks(x); ax.set_xticklabels([n for n, _ in items], fontsize=14); ax.set_ylabel("평균 오차 (낮을수록 정확)", fontsize=13, color=GRAY); ax.set_ylim(0, max(cf)+3)
ax.legend(frameon=False, fontsize=13, loc="upper left"); title(ax, "남은 개선 여지 — 같은 사람도 검진마다 값이 흔들린다")
f.tight_layout(); f.savefig(OUT/"U2_floor.png"); plt.close(f)

# 그림 3. 고위험자를 놓치는 비율: 세 가지 안내 규칙 비교 (최종 검증)
f, ax = plt.subplots(figsize=(14, 8), dpi=100); f.patch.set_facecolor("white"); style(ax)
names = [("고혈압\n≥140/90", "hypertension_140_90"), ("공복혈당장애\n≥100", "fasting_glucose_ge100"), ("비만\nBMI≥25", "obesity_bmi_ge25"), ("복부비만", "abdominal_obesity")]
x = np.arange(4); rules = [("rule_prior_status", "직전 검진 상태 그대로", LIGHT), ("rule_prob_ge_0.5", "기존 플래그(확률 0.5 이상)", GRAY), ("rule_referral_threshold", "새 안내 기준점(민감도 85% 목표)", NAVY)]
for j, (rk, lab, c) in enumerate(rules):
    v = [m2["referral"][k]["final_validation"][rk]["sensitivity"]*100 for _, k in names]; ms = [m2["referral"][k]["final_validation"][rk]["missed"] for _, k in names]; ps = [m2["referral"][k]["final_validation"][rk]["positives"] for _, k in names]
    ax.bar(x+(j-1)*0.27, v, 0.26, color=c, label=lab)
    for i in range(4): ax.text(x[i]+(j-1)*0.27, v[i]+1.2, f"{v[i]:.0f}%\n놓침 {ms[i]}/{ps[i]}", ha="center", fontsize=10.5, color=(NAVY if j == 2 else TXT), fontweight="bold" if j == 2 else "normal")
ax.axhline(85, color=GREEN, lw=1, ls="--"); ax.text(-0.5, 86, "목표 85%", fontsize=11, color=GREEN, ha="left")
ax.set_xticks(x); ax.set_xticklabels([n for n, _ in names], fontsize=14); ax.set_ylabel("기준 초과자를 찾아낸 비율(민감도, %)", fontsize=13, color=GRAY); ax.set_ylim(0, 118)
ax.legend(frameon=False, fontsize=12.5, loc="upper left", ncol=3); title(ax, "고위험자 놓침 — 안내 규칙별 비교 (최종 검증)")
f.tight_layout(); f.savefig(OUT/"U3_referral.png"); plt.close(f)

# 그림 4. 측정값 융합: 직전 검진 보유(좌) / 검진 이력 없음(우)
f, (a1, a2) = plt.subplots(1, 2, figsize=(14, 8), dpi=100); f.patch.set_facecolor("white")
fu = m2["fusion"]; T = [("수축기혈압", "sbp"), ("이완기혈압", "dbp"), ("체중(kg)", "weight")]
x = np.arange(3); b = [fu[k]["with_prior_checkup"]["mae_base"] for _, k in T]; fz = [fu[k]["with_prior_checkup"]["mae_fused"] for _, k in T]
a1.bar(x-0.2, b, 0.38, color=LIGHT, label="기존 예측(M1 또는 직전값)"); a1.bar(x+0.2, fz, 0.38, color=NAVY, label="측정값 융합")
gl = {"ADOPT": ("채택", GREEN), "PROVISIONAL": ("조건부 채택", AMBER), "REJECT": ("효과 없음 → 미채택", RED)}
for i, (_, k) in enumerate(T):
    a1.text(x[i]-0.2, b[i]+0.15, f"{b[i]:.2f}", ha="center", fontsize=12); a1.text(x[i]+0.2, fz[i]+0.15, f"{fz[i]:.2f}", ha="center", fontsize=12, fontweight="bold")
    g = gl[fu[k]["gate_with_prior"]]; a1.text(x[i], max(b[i], fz[i])+1.0, g[0], ha="center", fontsize=12.5, color=g[1], fontweight="bold")
a1.set_xticks(x); a1.set_xticklabels([n for n, _ in T], fontsize=13); a1.set_ylim(0, max(b)+2.6); style(a1); a1.legend(frameon=False, fontsize=11.5, loc="upper right"); title(a1, "직전 검진이 있는 사용자 (평균 오차)", 15)
T2 = [("수축기혈압", "sbp"), ("이완기혈압", "dbp"), ("체중(kg)", "weight")]
r = [fu[k]["no_prior_checkup"]["mae_korean_reference_only"] for _, k in T2]; m0 = [fu[k]["no_prior_checkup"]["mae_m0_measured"] for _, k in T2]
a2.bar(x-0.2, r, 0.38, color=GRAY, label="성별·연령 평균만"); a2.bar(x+0.2, m0, 0.38, color=BLUE, label="웨어러블 측정값 반영")
for i, (_, k) in enumerate(T2):
    a2.text(x[i]-0.2, r[i]+0.15, f"{r[i]:.2f}", ha="center", fontsize=12); a2.text(x[i]+0.2, m0[i]+0.15, f"{m0[i]:.2f}", ha="center", fontsize=12, fontweight="bold")
    g = gl[fu[k]["gate_no_prior"]]; a2.text(x[i], max(r[i], m0[i])+1.0, g[0], ha="center", fontsize=12.5, color=g[1], fontweight="bold")
a2.set_xticks(x); a2.set_xticklabels([n for n, _ in T2], fontsize=13); a2.set_ylim(0, max(r)+2.6); style(a2); a2.legend(frameon=False, fontsize=11.5, loc="upper right"); title(a2, "검진 이력이 없는 사용자 (평균 오차)", 15)
f.tight_layout(); f.savefig(OUT/"U4_fusion.png"); plt.close(f)

# 그림 5. 서비스 산출 범위: 고도화 전(M1) → 후(M2)
o = pd.read_parquet(ROOT/"01_Results/serving/m2_predictions_2026-09-17.parquet"); m1 = pd.read_parquet(ROOT/"01_Results/serving/m1_predictions_2026-09-17.parquet")
f, ax = plt.subplots(figsize=(14, 8), dpi=100); f.patch.set_facecolor("white"); style(ax, "x")
rows = []
for t, kor in (("sbp", "수축기혈압"), ("weight", "체중"), ("bmi", "BMI")):
    before = int(m1[f"pred_{t}"].notna().sum()); rc = o[f"m2_route_{t}"].value_counts().to_dict()
    rows.append((f"{kor} — 고도화 전", {"기존 예측": before})); rows.append((f"{kor} — 고도화 후", {"기존 예측": rc.get("M1_ONLY", 0), "측정값 융합": rc.get("FUSION", 0)+rc.get("FUSION_DERIVED", 0), "검진 이력 없음·오래됨(측정값 기반)": rc.get("M0_MEASURED", 0)}))
cols = {"기존 예측": LIGHT, "측정값 융합": NAVY, "검진 이력 없음·오래됨(측정값 기반)": BLUE}; left = np.zeros(len(rows)); ylab = [r[0] for r in rows]
for key, c in cols.items():
    v = np.array([r[1].get(key, 0) for r in rows]); ax.barh(ylab, v, left=left, color=c, label=key)
    for i, (l, w) in enumerate(zip(left, v)):
        if w >= 25: ax.text(l+w/2, i, str(int(w)), ha="center", va="center", fontsize=12, color=("white" if c != LIGHT else TXT))
    left += v
for i, tot in enumerate(left): ax.text(tot+5, i, f"계 {int(tot)}명", va="center", fontsize=12, color=TXT, fontweight="bold")
ax.invert_yaxis(); ax.set_xlim(0, 560); ax.set_xlabel(f"값을 받는 사용자 수 (전체 {len(o)}명, 2026-09-17 산출)", fontsize=13, color=GRAY)
ax.legend(frameon=False, fontsize=12.5, loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=3); title(ax, "서비스 산출 범위 — 고도화 전과 후")
f.tight_layout(); f.savefig(OUT/"U5_coverage.png"); plt.close(f)
summary = {"m1_users": int(len(m1)), "m2_users": int(len(o)), "no_checkup_users": int((~o["has_checkup"]).sum()),
           "routes": {t: o[f"m2_route_{t}"].value_counts().to_dict() for t in ("sbp", "dbp", "weight", "bmi")},
           "before": {t: int(m1[f"pred_{t}"].notna().sum()) for t in ("sbp", "weight", "bmi")},
           "tiers_served": {c.replace("risk_tier_", ""): o[c].value_counts().to_dict() for c in o.columns if c.startswith("risk_tier_")}}
(ROOT/"01_Results/m2/upgrade_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
print("charts:", sorted(p.name for p in OUT.glob("*.png"))); print(summary)
