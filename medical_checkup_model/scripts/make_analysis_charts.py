"""분석 보고서 시각화 6종 (1400x800, 템플릿 팔레트). matplotlib은 --with로 주입."""
import json, matplotlib, numpy as np
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT/"scripts/report_assets"; OUT.mkdir(exist_ok=True)
# 한글 폰트: Pretendard > AppleGothic > NanumGothic
for cand in ["Pretendard", "Pretendard Variable", "Apple SD Gothic Neo", "AppleGothic", "NanumGothic"]:
    if any(f.name == cand for f in fm.fontManager.ttflist): plt.rcParams["font.family"] = cand; break
plt.rcParams["axes.unicode_minus"] = False
NAVY, BLUE, LIGHT, GRAY, RED, GREEN, AMBER, LINE, TXT = "#0A3D9A", "#0A64FC", "#8FB4F5", "#6B7280", "#D92D20", "#15803D", "#D97706", "#E5E7EB", "#111827"
sig = json.load(open(ROOT/"01_Results/significance.json")); au = json.load(open(ROOT/"01_Results/model_audit.json"))
def fig(): f, ax = plt.subplots(figsize=(14, 8), dpi=100); f.patch.set_facecolor("white"); [s.set_visible(False) for k,s in ax.spines.items() if k in ("top","right")]; ax.spines["left"].set_color(LINE); ax.spines["bottom"].set_color(LINE); ax.tick_params(colors=TXT, labelsize=14); ax.grid(axis="y", color=LINE, lw=0.8); ax.set_axisbelow(True); return f, ax

# A. 실사용 준비도 판정 매트릭스 (항목 x 상태)
f, ax = plt.subplots(figsize=(14,8), dpi=100); f.patch.set_facecolor("white"); ax.axis("off")
rows = [("혈압(수축·이완) 개인화 예측","제한적 사용 가능", GREEN), ("공복혈당 개인화 예측","제한적 사용 가능", GREEN), ("비만·복부비만 플래그","제한적 사용 가능", GREEN),
        ("고혈압·혈당장애 플래그","참고용", AMBER), ("지질 4항목 (교차 모델)","참고용", AMBER), ("변화 방향(악화/유지/개선)","참고용", AMBER),
        ("체중·BMI·허리둘레","직전값 유지", GRAY), ("검진 이력 없는 사용자 (M0)","미검증 — 사용 불가", RED), ("웨어러블 반영 예측 (핵심 목적)","미충족 — 특징 0개", RED)]
levels = ["미검증/미충족","직전값 유지","참고용","제한적 사용 가능"]; colmap={"제한적 사용 가능":3,"참고용":2,"직전값 유지":1}
ax.set_xlim(0, 10); ax.set_ylim(-0.5, len(rows)-0.5)
for i,(name,status,c) in enumerate(rows):
    y = len(rows)-1-i; lvl = colmap.get(status, 0)
    ax.text(0.05, y, name, va="center", ha="left", fontsize=15, color=TXT)
    for k in range(4):
        ax.add_patch(plt.Rectangle((4.2+k*1.35, y-0.36), 1.25, 0.72, color=(c if k==lvl else "#F3F4F6"), ec="white", lw=2))
    ax.text(9.75, y, status, va="center", ha="right", fontsize=13, color=c, fontweight="bold")
for k,l in enumerate(levels): ax.text(4.2+k*1.35+0.62, len(rows)-0.35, l, ha="center", va="bottom", fontsize=11, color=GRAY)
ax.set_title("항목별 실사용 준비도 판정 (보고서 미수록)", loc="left", fontsize=18, color=NAVY, fontweight="bold", pad=28)
f.tight_layout(); f.savefig(OUT/"A_readiness.png"); plt.close(f)

# B(그림 3). 최종 검증 MAE — 모델 vs 직전값 (+95% CI 개선폭)
f, ax = fig(); items=[("수축기혈압\n(mmHg)","sbp"),("이완기혈압\n(mmHg)","dbp"),("공복혈당\n(mg/dL)","fasting_glucose")]
x=np.arange(3); cf=[sig["m1"][k]["mae_cf"] for _,k in items]; md=[sig["m1"][k]["mae_model"] for _,k in items]
ax.bar(x-0.2, cf, 0.38, color=LIGHT, label="직전 검진값 그대로"); ax.bar(x+0.2, md, 0.38, color=NAVY, label="우리 모델(개인화 M1)")
for i in range(3):
    ax.text(x[i]-0.2, cf[i]+0.25, f"{cf[i]:.1f}", ha="center", fontsize=13, color=TXT); ax.text(x[i]+0.2, md[i]+0.25, f"{md[i]:.1f}", ha="center", fontsize=13, color=TXT, fontweight="bold")
    d=sig["m1"][items[i][1]]; ax.text(x[i], max(cf[i],md[i])+1.6, f"개선 {d['diff']:+.2f}  [95% CI {d['diff_ci95'][0]:.2f}, {d['diff_ci95'][1]:.2f}]", ha="center", fontsize=11.5, color=GREEN, fontweight="bold")
ax.set_xticks(x); ax.set_xticklabels([n for n,_ in items], fontsize=14); ax.set_ylabel("평균절대오차 (낮을수록 정확)", fontsize=13, color=GRAY); ax.set_ylim(0, max(cf)+3.5)
ax.legend(frameon=False, fontsize=13, loc="upper left"); ax.set_title("그림 2. 개인화 예측 정확도 — 최종 검증(따로 떼어 둔 사용자 59명)", loc="left", fontsize=18, color=NAVY, fontweight="bold", pad=14)
f.tight_layout(); f.savefig(OUT/"B_m1_mae.png"); plt.close(f)

# C. 판별 AUROC — 모델 vs 직전상태 (+CI 유의 표시)
f, ax = fig(); names=[("고혈압\n≥140/90","hypertension_140_90"),("공복혈당장애\n≥100","fasting_glucose_ge100"),("비만\nBMI≥25","obesity_bmi_ge25"),("복부비만","abdominal_obesity")]
x=np.arange(4); pr=[sig["clf"][k]["prior_auroc"] for _,k in names]; mo=[sig["clf"][k]["auroc"] for _,k in names]; ci=[sig["clf"][k]["auroc_ci95"] for _,k in names]
ax.bar(x-0.2, pr, 0.38, color=LIGHT, label="직전 상태 유지(기준선)"); ax.bar(x+0.2, mo, 0.38, color=NAVY, label="우리 모델")
ax.errorbar(x+0.2, mo, yerr=[[m-c[0] for m,c in zip(mo,ci)],[c[1]-m for m,c in zip(mo,ci)]], fmt="none", ecolor=TXT, capsize=5, lw=1.5)
for i in range(4):
    ax.text(x[i]-0.2, pr[i]+0.008, f"{pr[i]:.2f}", ha="center", fontsize=12, color=TXT); s=sig["clf"][names[i][1]]
    ax.text(x[i]+0.2, ci[i][1]+0.012, f"{mo[i]:.2f}", ha="center", fontsize=12, color=TXT, fontweight="bold")
    ax.text(x[i], 0.462, "개선 유의" if s["significant"] else "개선 미확정", ha="center", fontsize=11.5, color=(GREEN if s["significant"] else AMBER), fontweight="bold")
ax.axhline(0.5, color=GRAY, lw=1, ls="--"); ax.text(-0.45, 0.503, "동전 던지기 0.5", fontsize=10, color=GRAY, ha="left")
ax.set_ylim(0.44, 1.02); ax.set_xticks(x); ax.set_xticklabels([n for n,_ in names], fontsize=14); ax.set_ylabel("AUROC (1.0 = 완벽)", fontsize=13, color=GRAY)
ax.legend(frameon=False, fontsize=13, loc="upper left"); ax.set_title("그림 3. 기준 초과 판별력 — 최종 검증, 오차막대 = 95% 신뢰구간", loc="left", fontsize=18, color=NAVY, fontweight="bold", pad=14)
f.tight_layout(); f.savefig(OUT/"C_auroc.png"); plt.close(f)

# D. 고위험 영역 과소예측 편향
f, ax = fig(); sub=au["subgroup"]
lab=["수축기혈압\n(실제 ≥140)","이완기혈압\n(실제 ≥90)","공복혈당\n(실제 ≥126)"]; keys=["sbp","dbp","fasting_glucose"]
bias=[sub[k]["high_range"]["bias"] for k in keys]; n=[sub[k]["high_range"]["n"] for k in keys]
normal=[np.mean([v["bias"] for v in sub[k]["sex"].values()]) for k in keys]
x=np.arange(3); ax.bar(x-0.2, normal, 0.38, color=LIGHT, label="전체 사용자 평균 편향"); ax.bar(x+0.2, bias, 0.38, color=RED, label="고위험 영역(기준 초과자) 편향")
for i in range(3): ax.text(x[i]+0.2, bias[i]-1.8, f"{bias[i]:+.1f}\n(n={n[i]})", ha="center", va="top", fontsize=12.5, color=RED, fontweight="bold"); ax.text(x[i]-0.2, normal[i]+0.6, f"{normal[i]:+.1f}", ha="center", fontsize=12, color=TXT)
ax.axhline(0, color=TXT, lw=1); ax.set_xticks(x); ax.set_xticklabels(lab, fontsize=14); ax.set_ylabel("편향 = 예측 − 실제 (음수: 낮게 예측)", fontsize=13, color=GRAY); ax.set_ylim(min(bias)-9, 6)
ax.legend(frameon=False, fontsize=13, loc="lower left"); ax.set_title("그림 4. 고위험 영역에서의 과소예측 — 병원 안내 목적에 위험한 방향", loc="left", fontsize=18, color=NAVY, fontweight="bold", pad=14)
f.tight_layout(); f.savefig(OUT/"D_bias.png"); plt.close(f)

# E. 데이터 구성 + 정답지 병목 (좌: 학습 행 구성, 우: forward 쌍 vs 게이트)
f, (a1, a2) = plt.subplots(1, 2, figsize=(14,8), dpi=100, gridspec_kw={"width_ratios":[1.15,1]}); f.patch.set_facecolor("white")
for ax in (a1,a2): [s.set_visible(False) for k,s in ax.spines.items() if k in ("top","right")]; ax.spines["left"].set_color(LINE); ax.spines["bottom"].set_color(LINE); ax.tick_params(colors=TXT, labelsize=13); ax.grid(axis="x", color=LINE, lw=0.8); ax.set_axisbelow(True)
src=["NHANES\n(미국, 가속도+검진)","자체 검진\n(394명)","KNHANES\n(한국, 걸음+검진)"]; val=[9981,1549,592]
a1.barh(src, val, color=[LIGHT, NAVY, BLUE]); [a1.text(v+150, i, f"{v:,}", va="center", fontsize=13, color=TXT) for i,v in enumerate(val)]
a1.invert_yaxis(); a1.set_xlim(0, 12000); a1.set_title("그림 1-①. 통합 학습 테이블 구성 (행)", loc="left", fontsize=16, color=NAVY, fontweight="bold")
a2.barh(["'웨어러블 뒤 검진'\n정답지 (현재)","검증 시작 기준\n(정책, 30명)","현재 개인화 모델이\n학습한 검진 쌍"], [12, 30, 292], color=[RED, GRAY, NAVY])
for i,v in enumerate([12,30,292]): a2.text(v+4, i, f"{v}명", va="center", fontsize=13, color=TXT, fontweight="bold" if i==0 else "normal")
a2.invert_yaxis(); a2.set_xlim(0, 340); a2.set_title("그림 1-②. 웨어러블 검증의 병목 (사용자 수)", loc="left", fontsize=16, color=NAVY, fontweight="bold")
f.tight_layout(); f.savefig(OUT/"E_data.png"); plt.close(f)

# F. 서빙 커버리지 (394명) — 경로별 스택
f, ax = fig(); rc=au["serving"]["route_counts"]; order=["sbp","dbp","fasting_glucose","weight","bmi","waist","total_cholesterol","hdl","ldl","triglyceride"]
kor={"sbp":"수축기혈압","dbp":"이완기혈압","fasting_glucose":"공복혈당","weight":"체중","bmi":"BMI","waist":"허리둘레","total_cholesterol":"총콜레스테롤","hdl":"HDL","ldl":"LDL","triglyceride":"중성지방"}
routes=[("MODEL","모델 예측",NAVY),("MODEL_CROSS","교차 모델(참고)",BLUE),("CARRY_FORWARD","직전값 유지",LIGHT),("ABSTAIN","보류",LINE)]
left=np.zeros(len(order))
for key,lab_,c in routes:
    v=np.array([rc[o].get(key,0) for o in order]); ax.barh([kor[o] for o in order], v, left=left, color=c, label=lab_)
    for i,(l,w) in enumerate(zip(left,v)):
        if w>=25: ax.text(l+w/2, i, str(int(w)), ha="center", va="center", fontsize=11, color=("white" if c in (NAVY,BLUE) else TXT))
    left+=v
ax.invert_yaxis(); ax.set_xlim(0, 394); ax.set_xlabel("사용자 수 (총 394명, 2026-09-10 산출)", fontsize=13, color=GRAY); ax.grid(axis="y", visible=False); ax.grid(axis="x", color=LINE)
ax.legend(frameon=False, fontsize=12, loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=4); ax.set_title("그림 5. 서비스 산출 범위 — 항목별 산출 경로 (394명)", loc="left", fontsize=18, color=NAVY, fontweight="bold", pad=14)
f.tight_layout(); f.savefig(OUT/"F_coverage.png"); plt.close(f)
print("charts:", sorted(p.name for p in OUT.glob("*.png")))
