# -*- coding: utf-8 -*-
"""Builds the IRS crosswalk methods document (markdown -> SiBC docx). Numbers are read from the final result files."""
import re, json, os, subprocess, sys
import pandas as pd, numpy as np
# Run from the work folder that holds the result files (see 03_irs_risk_rank/README.md); paths are not hard-coded.
HERE = os.path.dirname(os.path.abspath(__file__))
S = os.environ.get("RETRO03_WORK", os.getcwd())
os.chdir(S)
OUTDIR = sys.argv[1]
CONV = os.environ.get("SIBC_MD2DOCX", os.path.join(HERE, "..", "..", "00_common", "src", "md2docx_sibc_ref.js"))
NODE_PATH = os.environ.get("NODE_PATH", os.path.join(HERE, "..", "..", "..", "medical_checkup_model", "node_modules"))
ST = json.load(open("stats2.json"))          # written by x8.py / x8b.py / xl.py
MET = pd.read_pickle("MET.pkl"); DIS = pd.read_pickle("DIS.pkl"); info = pd.read_csv("dis_info.csv").set_index("disease_id")
SCN = {"irs": "IRS", "mrs": "MRS", "lrs": "LRS", "prs": "PRS"}
pct = lambda x: f"{100*x:.1f}%"
EXTRA_NM = {"cardiac_arrhythmia": "부정맥", "endometrial_cancer": "자궁내막암", "endometriosis": "자궁내막증", "polycystic_ovary_syndrome": "다낭성 난소 증후군"}
nm = lambda d: info.disease_nm.get(d, EXTRA_NM.get(d, d))

REF = {
 "patent": "인바이츠지노믹스 주식회사, 씨지인바이츠 주식회사. 질병 위험도에 기초한 생체 나이 예측 장치 및 방법. 대한민국 등록특허 제10-2909711호. 등록일 2026-01-05.",
 "selvin": "Selvin E, Manzi J, Stevens LA, et al. Calibration of serum creatinine in the National Health and Nutrition Examination Surveys (NHANES) 1988-1994, 1999-2004. Am J Kidney Dis. 2007;50(6):918-926. doi:10.1053/j.ajkd.2007.08.020",
 "coresh": "Coresh J, Astor BC, McQuillan G, et al. Calibration and random variation of the serum creatinine assay as critical elements of using equations to estimate glomerular filtration rate. Am J Kidney Dis. 2002;39(5):920-929. doi:10.1053/ajkd.2002.32765",
 "kolen": "Kolen MJ, Brennan RL. Test Equating, Scaling, and Linking: Methods and Practices. 3rd ed. New York: Springer; 2014. doi:10.1007/978-1-4939-0317-7",
 "janssen": "Janssen KJM, Moons KGM, Kalkman CJ, Grobbee DE, Vergouwe Y. Updating methods improved the performance of a clinical prediction model in new patients. J Clin Epidemiol. 2008;61(1):76-86. doi:10.1016/j.jclinepi.2007.04.018",
 "steyerberg": "Steyerberg EW. Clinical Prediction Models: A Practical Approach to Development, Validation, and Updating. 2nd ed. Cham: Springer; 2019. doi:10.1007/978-3-030-16399-0",
 "vancalster": "Van Calster B, Nieboer D, Vergouwe Y, De Cock B, Pencina MJ, Steyerberg EW. A calibration hierarchy for risk models was defined: from utopia to empirical data. J Clin Epidemiol. 2016;74:167-176. doi:10.1016/j.jclinepi.2015.12.005",
 "barlow": "Barlow RE, Bartholomew DJ, Bremner JM, Brunk HD. Statistical Inference under Order Restrictions: The Theory and Application of Isotonic Regression. London: Wiley; 1972.",
 "zadrozny": "Zadrozny B, Elkan C. Transforming classifier scores into accurate multiclass probability estimates. In: Proceedings of the 8th ACM SIGKDD International Conference on Knowledge Discovery and Data Mining. 2002:694-699. doi:10.1145/775047.775151",
 "roberts": "Roberts DR, Bahn V, Ciuti S, et al. Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure. Ecography. 2017;40(8):913-929. doi:10.1111/ecog.02881",
 "cohen68": "Cohen J. Weighted kappa: nominal scale agreement with provision for scaled disagreement or partial credit. Psychol Bull. 1968;70(4):213-220. doi:10.1037/h0026256",
 "landis": "Landis JR, Koch GG. The measurement of observer agreement for categorical data. Biometrics. 1977;33(1):159-174. doi:10.2307/2529310",
 "efron": "Efron B, Tibshirani RJ. An Introduction to the Bootstrap. New York: Chapman & Hall; 1993. doi:10.1201/9780429246593",
 "grras": "Kottner J, Audigé L, Brorson S, et al. Guidelines for Reporting Reliability and Agreement Studies (GRRAS) were proposed. J Clin Epidemiol. 2011;64(1):96-106. doi:10.1016/j.jclinepi.2010.03.002",
 "pullen": "Pullenayegum EM, Lim LSH. Longitudinal data subject to irregular observation: a review of methods with a focus on visit processes, assumptions, and study design. Stat Methods Med Res. 2016;25(6):2992-3014. doi:10.1177/0962280214536537",
 "eldridge": "Eldridge SM, Ashby D, Kerry S. Sample size for cluster randomized trials: effect of coefficient of variation of cluster size and analysis method. Int J Epidemiol. 2006;35(5):1292-1300. doi:10.1093/ije/dyl129",
 "tripod": "Collins GS, Moons KGM, Dhiman P, et al. TRIPOD+AI statement: updated guidance for reporting clinical prediction models that use regression or machine learning methods. BMJ. 2024;385:e078378. doi:10.1136/bmj-2023-078378",
}

MD = open("mdoc2_body.md").read()
# fill {{key}} placeholders from stats.json
fmtv = lambda v: f"{v:,}" if isinstance(v, int) and v >= 1000 else str(v)
MD = re.sub(r"\{\{(\w+)\}\}", lambda m: fmtv(ST[m.group(1)]), MD)
# tables generated from results
A = MET[MET.sex == "all"]; SX = MET[MET.sex != "all"]
def sexpass(c):
    piv = SX[SX.score == c].pivot(index="disease", columns="sex", values="rate"); return (piv.fillna(1) >= 0.95).all(axis=1)
def iqr(v): return f"{pct(v.median())} ({pct(v.quantile(.25))}~{pct(v.quantile(.75))})"
def score_table():
    out = ["| 점수 | 검증 쌍 | 환산 전 일치율 | 환산 후 일치율 | 보류 순위표 | 가중 카파 전→후 | 통과(성별 / 합산 / 안정) |", "|---|---|---|---|---|---|---|"]
    for c in ["irs", "mrs", "lrs", "prs"]:
        a = A[A.score == c]
        out.append(f"| {SCN[c]} | {int(a.n_pairs.median())} | {iqr(a.raw_rate)} | {iqr(a.rate)} | {pct(a.ind_rate.median())} | {a.kw_raw.median():.3f}→{a.kw_cw.median():.3f} | {sexpass(c).sum()} / {(a.rate >= 0.95).sum()} / {(a.pass_share >= 0.8).sum()} (총 {len(a)}) |")
    return "\n".join(out)
def weak_table():
    s = SX[SX.score.isin(["irs", "mrs"]) & (SX.rate < 0.95)].sort_values(["score", "rate"])
    out = ["| 점수 | 질환 | 성별 | 일치/검증 쌍 | 환산 전 | 환산 후 (사용자 재표집 95% 구간) |", "|---|---|---|---|---|---|"]
    for r in s.itertuples():
        out.append(f"| {SCN[r.score]} | {nm(r.disease)} | {'여' if r.sex == 'F' else '남'} | {r.agree}/{r.n_pairs} | {pct(r.raw_rate)} | {pct(r.rate)} ({pct(r.bs_lo)}~{pct(r.bs_hi)}) |")
    return "\n".join(out)
def pooled_table():
    P = ST["pooled_irs"]
    out = ["| 정답 구간 \\ 환산 구간 | 1 | 2 | 3 | 4 | 5 |", "|---|---|---|---|---|---|"]
    for i, row in enumerate(P, 1): out.append(f"| {i} | " + " | ".join(f"{v:,}" for v in row) + " |")
    return "\n".join(out)
def full_table():
    out = ["| 질환 | IRS 여 | IRS 남 | MRS 여 | MRS 남 | LRS 여 | LRS 남 | PRS 여 | PRS 남 | 판정 IRS·MRS |", "|---|---|---|---|---|---|---|---|---|---|"]
    sp = {c: sexpass(c) for c in ["irs", "mrs"]}
    def cell(d, c, s):
        q = SX[(SX.disease == d) & (SX.score == c) & (SX.sex == s)]
        return f"{int(q.agree.iloc[0])}/{int(q.n_pairs.iloc[0])}" if len(q) else "—"
    for d in sorted(DIS, key=nm):
        v = "·".join("통과" if sp[c].get(d, False) else "미달" for c in ["irs", "mrs"])
        out.append(f"| {nm(d)} | " + " | ".join(cell(d, c, s) for c in ["irs", "mrs", "lrs", "prs"] for s in ["F", "M"]) + f" | {v} |")
    return "\n".join(out)
MD = MD.replace("<<SCORE_TABLE>>", score_table()).replace("<<WEAK_TABLE>>", weak_table()).replace("<<POOLED_TABLE>>", pooled_table()).replace("<<FULL_TABLE>>", full_table())

order = []
def cite(mo):
    k = mo.group(1)
    if k == "REFS": return mo.group(0)
    if k not in REF: raise SystemExit(f"missing ref {k}")
    if k not in order: order.append(k)
    return f"[{order.index(k)+1}]"
MD = re.sub(r"«(\w+)»", cite, MD)
MD = MD.replace("«REFS»", "\n\n".join(f"[{i+1}] {REF[k]}" for i, k in enumerate(order)))
unused = set(REF) - set(order)
if unused: print("unused refs:", unused)
# Organisation / author / confidentiality text comes from front_meta.json in the work folder (local only, never committed).
META = json.load(open("front_meta.json", encoding="utf-8")) if os.path.exists("front_meta.json") else {}
FRONT = dict(org=META.get("org", ""), confidential=META.get("confidential", ""),
             eyebrow="METHODS NOTE · IRS BASELINE DEFINITION AND RANK CROSSWALK",
             title="IRS 위험 순위의 기준선 정의와 모델 버전 간 환산 방법 — 완성 IRS 기준선, 연결 쌍 단조 환산, 교차검증",
             author=META.get("author", ""),
             abstract=ST["abstract"])
os.makedirs(OUTDIR, exist_ok=True)
open(f"{S}/mdoc2.md", "w").write(MD); json.dump(FRONT, open(f"{S}/mdoc2_front.json", "w"), ensure_ascii=False)
out = f"{OUTDIR}/SiBC_IRS_기준선정의_환산방법_{ST['n']}명_20261119.docx"  # size read from stats2.json
r = subprocess.run(["node", CONV, f"{S}/mdoc2.md", out, f"{S}/mdoc2_front.json"], capture_output=True, text=True, env={**os.environ, "NODE_PATH": NODE_PATH})
print(len(order), "refs;", r.stdout.strip()[-200:], r.stderr.strip()[-500:])
