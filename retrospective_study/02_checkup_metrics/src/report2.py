# -*- coding: utf-8 -*-
"""Study 02 report: tables (xlsx), figures (PNG <= 1200 px, English labels) and a JSON summary from ana2.py outputs.

Run from retrospective_study/ after ana2.py:  python3 02_checkup_metrics/src/report2.py
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "02_checkup_metrics/src")); sys.path.insert(0, str(ROOT / "00_common/src"))
import ana2 as A2  # noqa: E402
import statlib as S  # noqa: E402

OUT = A2.OUT
E = pd.read_pickle(OUT / "est_point.pkl")
B = [b for b in pd.read_pickle(OUT / "est_boot.pkl") if "error" not in b]
U = A2.U
C_HI, C_LO = "#0072B2", "#D55E00"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
EN = {"height": "Height (per SD)", "weight": "Weight (per SD)", "bmi": "BMI >=25", "waist": "Waist above cutoff", "sbp": "Systolic BP >=130",
      "dbp": "Diastolic BP >=85", "fbg": "Fasting glucose >=100", "tc": "Total cholesterol >=200", "hdl": "Low HDL", "ldl": "LDL >=130",
      "tg": "Triglycerides >=150", "hb": "Low haemoglobin", "ast": "AST >40", "alt": "ALT >35", "ggt": "High GGT", "cr": "Creatinine >1.5",
      "gfr": "eGFR <60", "uprot": "Urine protein positive", "sight": "Low visual acuity", "hearing": "Hearing abnormal",
      "chest": "Chest X-ray finding", "judge": "Overall judgement abnormal"}
KO = {"height": "키(1 SD당)", "weight": "체중(1 SD당)", "bmi": "체질량지수 25 이상", "waist": "허리둘레 기준 밖", "sbp": "수축기 혈압 130 이상",
      "dbp": "이완기 혈압 85 이상", "fbg": "공복혈당 100 이상", "tc": "총콜레스테롤 200 이상", "hdl": "HDL 낮음", "ldl": "LDL 130 이상",
      "tg": "중성지방 150 이상", "hb": "혈색소 낮음", "ast": "AST 40 초과", "alt": "ALT 35 초과", "ggt": "감마지티피 높음", "cr": "크레아티닌 1.5 초과",
      "gfr": "사구체여과율 60 미만", "uprot": "요단백 양성", "sight": "시력 낮음", "hearing": "청력 이상", "chest": "흉부 소견 있음", "judge": "종합판정 이상"}
EN_ALT = {"bmi": "BMI >=30", "sbp": "Systolic BP >=140", "dbp": "Diastolic BP >=90", "fbg": "Fasting glucose >=126", "tc": "Total cholesterol >=240",
          "ldl": "LDL >=160", "tg": "Triglycerides >=200", "uprot": "Urine protein trace or positive"}
KO_ALT = {"bmi": "체질량지수 30 이상", "sbp": "수축기 혈압 140 이상", "dbp": "이완기 혈압 90 이상", "fbg": "공복혈당 126 이상", "tc": "총콜레스테롤 240 이상",
          "ldl": "LDL 160 이상", "tg": "중성지방 200 이상", "uprot": "요단백 약양성 이상"}
DOMAIN = [("Body measures", ["height", "weight", "bmi", "waist"]), ("Blood pressure", ["sbp", "dbp"]), ("Glucose", ["fbg"]),
          ("Lipids", ["tc", "hdl", "ldl", "tg"]), ("Blood", ["hb"]), ("Liver", ["ast", "alt", "ggt"]), ("Kidney", ["cr", "gfr", "uprot"]),
          ("Senses, imaging, overall", ["sight", "hearing", "chest", "judge"])]
FIG = {}


def savefig(fig, name):
	fig.savefig(OUT / name, dpi=150); plt.close(fig); FIG[name] = str(OUT / name)


def boot_stats(block, item, field="diff"):
	v = np.array([b[block][item].get(field, np.nan) for b in B if b[block][item].get("tested") and b[block][item].get("conv", False)], float)
	v = v[np.isfinite(v)]
	if len(v) < 900:
		return np.nan, np.nan, np.nan, len(v)
	return np.percentile(v, 2.5), np.percentile(v, 97.5), np.std(v, ddof=1), len(v)


def item_table(block, field="diff"):
	rows = []
	for it in A2.ITEMS if block != "alt" else list(A2.ITEMF_ALT):
		r = E[block].get(it, {})
		lab_ko, lab_en = (KO_ALT.get(it, KO[it]), EN_ALT.get(it, EN[it])) if block == "alt" else (KO[it], EN[it])
		row = dict(item=it, label_ko=lab_ko, label_en=lab_en, n=r.get("n"), n_abn=r.get("n1"), n_norm=r.get("n0"), tested=bool(r.get("tested")),
		           conv=r.get("conv"), est=r.get(field, np.nan), m_abn=r.get("m1", np.nan), m_norm=r.get("m0", np.nan))
		if row["tested"] and r.get("conv") is False:  # point fit did not converge: no inference
			row["tested"] = False; row["not_reported"] = "original-data fit did not converge"
		elif not row["tested"]:
			row["not_reported"] = "N/A - minimum n not met in the original data"
		if row["tested"]:
			lo, hi, se, nb = boot_stats(block, it, field)
			if field == "rr":  # ratio: Wald P on the log scale against log(1) = 0
				v = np.array([b[block][it].get("rr", np.nan) for b in B if b[block][it].get("tested") and b[block][it].get("conv", False)], float); v = v[np.isfinite(v) & (v > 0)]
				p = S.wald_p(np.log(row["est"]), np.std(np.log(v), ddof=1)) if len(v) >= 900 and row["est"] > 0 else np.nan
			else:
				p = S.wald_p(row["est"], se)
			row.update(lo=lo, hi=hi, p=p, boot_valid=nb)
			if nb < 900:
				row["not_reported"] = "fewer than 900 valid resamples"
		rows.append(row)
	t = pd.DataFrame(rows)
	for c in ["lo", "hi", "p", "boot_valid"]:
		if c not in t:
			t[c] = np.nan
	m = t.tested & t.p.notna()
	t["q"] = np.nan; t.loc[m, "q"] = S.bh(t.loc[m, "p"].values)
	return t


MAIN = item_table("main")
# observed (unadjusted) mean login days by status
for i, it in MAIN.iterrows():
	f = A2.ITEMF[it["item"]]
	if it["item"] in A2.CONT:
		continue
	x = f.x
	MAIN.loc[i, "obs_abn"] = U.y[x == 1].mean(); MAIN.loc[i, "obs_norm"] = U.y[x == 0].mean()
SD_Y = U.y.std(ddof=1)
for i, r in MAIN.iterrows():
	if r.tested:
		d = abs(r.est) / SD_Y; lo_d = min(abs(r.lo), abs(r.hi)) / SD_Y if np.sign(r.lo) == np.sign(r.hi) else 0.0
		MAIN.loc[i, "evalue"] = S.evalue_rr(np.exp(0.91 * d))[0]; MAIN.loc[i, "evalue_ci"] = S.evalue_rr(np.exp(0.91 * lo_d))[0] if lo_d > 0 else 1.0
# entry of baseline results into the service relative to registration (post hoc; insert timestamp of each selected result)
_B = A2.BSEL.merge(A2.C[["d0"]], left_on="user_id", right_index=True)
_B["lag"] = (pd.to_datetime(_B.ins_ts, errors="coerce").dt.normalize() - pd.to_datetime(_B.d0).dt.normalize()).dt.days
_ul = _B.groupby("user_id").lag.max()
ENTRY = pd.DataFrame([
	dict(measure="users with a baseline checkup", value=int(_ul.size)),
	dict(measure="users with every selected baseline result entered by the registration day", value=int((_ul <= 0).sum())),
	dict(measure="users with at least one selected result entered after the registration day", value=int((_ul > 0).sum())),
	dict(measure="largest entry delay after registration, days", value=int(_ul.max())),
	dict(measure="selected results entered before the registration day", value=int((_B.lag < 0).sum())),
] + [dict(measure=f"analysed users with the item entered by the registration day: {it}", value=int((A2.ITEMF[it].entry_reg.values == 1).sum())) for it in A2.ITEMS])
SENS = {k: item_table(k) for k in ["quasi", "alt", "year1", "src101", "src104", "susp1", "susp2", "entry_reg"]}  # no site-stratified results in paper outputs
FITLOG = pd.DataFrame([dict(item=it, bb_fallback_to_quasi=sum(bool(b["main"][it].get("fallback")) for b in B), not_converged=sum(b["main"][it].get("tested", False) and not b["main"][it].get("conv", False) for b in B),
                            theta_at_bound=sum(bool(b["main"][it].get("at_bound")) for b in B), not_tested_min_n=sum(not b["main"][it].get("tested", False) for b in B)) for it in A2.ITEMS])


# ---------------------------------------------------------------- model diagnostics (main beta-binomial fits on the full data)
def bb_diag(item):
	f = A2.ITEMF[item]
	X = np.column_stack([f.x.values, U[A2.BASECOV].values, f.k.values, f.src104.values]); y = U.y.values.astype(float)
	ok = np.isfinite(X).all(axis=1); X, y = X[ok], y[ok]; X = X[:, S.independent_columns(X, protect=1)]
	b, lt, conv = S.betabinom_fit(S.add_const(X), y, 28.0)
	mu = S.expit(S.add_const(X) @ b); th = np.exp(lt); a_, b_ = mu * th, (1 - mu) * th
	from scipy import special
	p0 = np.exp(special.betaln(a_, 28 + b_) - special.betaln(a_, b_)); p28 = np.exp(special.betaln(28 + a_, b_) - special.betaln(a_, b_))
	bq, _ = S.glm_logit(S.add_const(X), y / 28)
	mq = S.expit(S.add_const(X) @ bq); phi = np.sum((y / 28 - mq) ** 2 / (mq * (1 - mq) / 28)) / (len(y) - X.shape[1] - 1)
	return dict(item=item, n=len(y), theta=th, icc_rho=1 / (1 + th), obs_0=int((y == 0).sum()), exp_0=p0.sum(), obs_28=int((y == 28).sum()), exp_28=p28.sum(),
	            quasi_dispersion=phi, conv=conv)


DIAG = pd.DataFrame([bb_diag(it) for it in A2.ITEMS if MAIN.set_index("item").loc[it, "tested"]])

# selection: analysed users vs the rest of the common cohort
_lgc = pd.read_csv(A2.EX / "login_hours_days.csv", parse_dates=["d"]).merge(A2.C[["d0"]], left_on="user_id", right_index=True)
_lgc = _lgc[(_lgc.d > _lgc.d0) & (_lgc.d <= _lgc.d0 + pd.Timedelta(days=28))]
_yc = _lgc.groupby("user_id").size().reindex(A2.C.index).fillna(0)
_an = A2.C.index.isin(U.index)
SEL = []
for lab, x, kind in [("Age, years", pd.to_numeric(A2.C.age, errors="coerce"), "mean"), ("Female", (A2.C.sex == "F").astype(float), "pct"),
                     ("Login days in days 1-28", _yc, "med")]:
	row = dict(variable=lab)
	for g, m in [("analysed", _an), ("not analysed", ~_an)]:
		v = x[m].astype(float).dropna()
		row[g] = (f"{v.mean():.1f} ({v.std(ddof=1):.1f})" if kind == "mean" else f"{int(v.sum())} ({100 * v.mean():.1f})" if kind == "pct"
		          else f"{v.median():.0f} ({v.quantile(.25):.0f}-{v.quantile(.75):.0f})")
	row["n_analysed"], row["n_not"] = int(_an.sum()), int((~_an).sum())
	SEL.append(row)
SEL = pd.DataFrame(SEL)
# by exclusion reason
_valid = set(A2._L[A2._L.used & A2._L.ok].user_id)
_reason = pd.Series("analysed", index=A2.C.index)
_reason[~A2.C.index.isin(list(_valid))] = "no valid checkup"
_reason[A2.C.index.isin(list(_valid)) & ~A2.C.index.isin(A2.BSEL.user_id.unique())] = "checkup outside the baseline window"
_reason[A2.C.index.isin(A2.BSEL.user_id.unique()) & ~A2.C.index.isin(U.index)] = "age or sex missing"
SEL_R = []
for g in ["analysed", "no valid checkup", "checkup outside the baseline window", "age or sex missing"]:
	m = (_reason == g).values
	a_ = pd.to_numeric(A2.C.age, errors="coerce")[m]
	SEL_R.append(dict(group=g, n=int(m.sum()), age=f"{a_.mean():.1f} ({a_.std(ddof=1):.1f})" if m.sum() > 1 else "", female=f"{100 * (A2.C.sex[m] == 'F').mean():.1f}%",
	                  login_days=f"{_yc[m].median():.0f} ({_yc[m].quantile(.25):.0f}-{_yc[m].quantile(.75):.0f})"))
SEL_R = pd.DataFrame(SEL_R)
# item measured vs not measured among the analysed users
MISS = []
for it in ["sbp", "fbg", "tc", "hb", "ast", "gfr", "uprot", "chest", "judge"]:
	m = np.isfinite(A2.ITEMF[it].x.values)
	MISS.append(dict(item=it, measured=int(m.sum()), not_measured=int((~m).sum()), login_measured=float(U.y[m].median()), login_not=float(U.y[~m].median()) if (~m).sum() else np.nan,
	                 age_measured=float(U.age[m].mean()), age_not=float(U.age[~m].mean()) if (~m).sum() else np.nan))
MISS = pd.DataFrame(MISS)


# calibration of the main beta-binomial fit (BMI item model): observed vs predicted mean login days by group, and the full distribution
_QL = {q: f"{i + 1}" for i, q in enumerate(sorted(U.d0.dt.to_period("Q").astype(str).unique()))}  # registration quarter order (1 = earliest)


def calib():
	f = A2.ITEMF["bmi"]
	X = np.column_stack([f.x.values, U[A2.BASECOV].values, f.k.values, f.src104.values]); y = U.y.values.astype(float)
	X = X[:, S.independent_columns(X, protect=1)]; Xc = S.add_const(X)
	b, lt, conv = S.betabinom_fit(Xc, y, 28.0)
	mu = S.expit(Xc @ b); th = np.exp(lt)
	from scipy import special, stats
	pmf = np.array([np.exp(special.gammaln(29) - special.gammaln(k + 1) - special.gammaln(29 - k) + special.betaln(k + mu * th, 28 - k + (1 - mu) * th) - special.betaln(mu * th, (1 - mu) * th)) for k in range(29)])
	dist = pd.DataFrame({"days": range(29), "observed": np.bincount(y.astype(int), minlength=29), "expected": pmf.sum(axis=1)})
	grp = {"quarter": np.array([_QL[q] for q in U.d0.dt.to_period("Q").astype(str).values]), "BMI >=25": np.where(f.x.values == 1, "yes", "no")}
	rows = []
	for gname, g in grp.items():
		for lev in sorted(set(g)):
			m = g == lev
			rows.append(dict(grouping=gname, level=lev, n=int(m.sum()), observed=float(y[m].mean()), predicted=float(28 * mu[m].mean())))
	return dist, pd.DataFrame(rows)


DIST, CALIB = calib()
HIGH = item_table("high", "rd")
HIGH_RR = item_table("high", "rr")


def summ(key):
	e = E[key]; v = np.array([b[key]["ame"] for b in B if b[key].get("conv")], float); v = v[np.isfinite(v)]
	if len(v) < 900 or not e.get("conv", False):  # raw fit must converge; >= 900 valid resamples
		return dict(ame=e["ame"], lo=np.nan, hi=np.nan, p=np.nan, n=e["n"], boot_valid=len(v))
	return dict(ame=e["ame"], lo=np.percentile(v, 2.5), hi=np.percentile(v, 97.5), p=S.wald_p(e["ame"], np.std(v, ddof=1)), n=e["n"], boot_valid=len(v))


SUMM = {k: summ(k) for k in ["summary", "summary_prop10", "summary_s1", "summary_adj"]}
curve_bs = np.array([b["summary"]["curve"] for b in B if b["summary"].get("conv")])

# ---------------------------------------------------------------- Table 1
hiE = U.y >= A2.MED
bm = A2.ITEMF["bmi"]
T1V = [("Age, years", U.age, "mean"), ("Female", U.female, "pct"),
       ("Days from baseline checkup to registration", bm.k, "med"), ("Checkup source code 20101104", bm.src104, "pct"),
       ("Checkup items available (of 22)", pd.Series([sum(np.isfinite(A2.ITEMF[it].x[u]) for it in A2.ITEMS) for u in U.index], index=U.index), "med"),
       ("All 11 summary-panel components measured", pd.Series(A2.N_MEAS == 11, index=U.index).astype(float), "pct"),
       ("Login days in the first 28 days", U.y, "med")]
QLAB = {q: f"quarter {i + 1}" + (" (earliest)" if i == 0 else "") for i, q in enumerate(sorted(U.d0.dt.to_period("Q").astype(str).unique()))}  # no calendar labels
for qq in sorted(QLAB, reverse=True):  # descriptive: original quarters (the model merges quarters with < 10 users)
	T1V.insert(3, (f"Registered in {QLAB[qq]}", (U.d0.dt.to_period("Q").astype(str) == qq).astype(float), "pct"))
t1 = []
for lab, x, kind in T1V:
	x = pd.Series(x, index=U.index).astype(float)
	def fmt(s):
		s = s.dropna()
		if kind == "mean":
			return f"{s.mean():.1f} ({s.std(ddof=1):.1f})"
		if kind == "pct":
			return f"{int(s.sum())} ({100 * s.mean():.1f})"
		return f"{s.median():.0f} ({s.quantile(.25):.0f}-{s.quantile(.75):.0f})"
	t1.append(dict(variable=lab, overall=fmt(x), high=fmt(x[hiE]), low=fmt(x[~hiE])))
T1 = pd.DataFrame(t1)

# ---------------------------------------------------------------- flow counts
L = A2._L
C = A2.C
valid_users = set(L[L.used & L.ok].user_id)
FLOW = dict(common=len(C), any_valid_checkup=len(valid_users & set(C.index)), baseline=A2.N_BASELINE, missing_demo=A2.N_DEMO_MISSING, analysed=len(U),
            panel11=int((A2.N_MEAS == 11).sum()), panel10=int((A2.N_MEAS >= 10).sum()))
FLOW["no_checkup"] = FLOW["common"] - FLOW["any_valid_checkup"]; FLOW["outside_window"] = FLOW["any_valid_checkup"] - FLOW["baseline"]


def fig_flow():
	fig = plt.figure(figsize=(8, 7))
	axa = fig.add_axes([0.03, 0.78, 0.94, 0.2]); axb = fig.add_axes([0.03, 0.02, 0.94, 0.74])
	axa.set_xlim(0, 100); axa.set_ylim(0, 10); axa.axis("off"); axa.text(0, 9.3, "A", fontsize=13, fontweight="bold")
	for a_, b_, t_, c_ in [(2, 44, "Baseline health checkup\nlatest valid result per item,\n24 months before registration to registration", "#E8E8E8"),
	                       (56, 98, "Outcome\nlogin days on days 1-28\nafter registration", "#CFE3F2")]:
		axa.add_patch(FancyBboxPatch((a_, 3.2), b_ - a_, 5.0, boxstyle="round,pad=0.3", fc=c_, ec="#555555"))
		axa.text((a_ + b_) / 2, 5.7, t_, ha="center", va="center", fontsize=8)
	axa.annotate("", xy=(99, 1.6), xytext=(1, 1.6), arrowprops=dict(arrowstyle="->", color="#333333"))
	axa.text(50, 0.0, "Registration (first login)", fontsize=7.5, ha="center")
	axb.set_xlim(0, 100); axb.set_ylim(0, 100); axb.axis("off"); axb.text(0, 97, "B", fontsize=13, fontweight="bold")
	main = [f"Common cohort (n={FLOW['common']})", f"Baseline checkup available (n={FLOW['baseline']})", f"Analysed (n={FLOW['analysed']})"]
	exc = [f"No valid checkup, {FLOW['no_checkup']}\nCheckups only outside the baseline window, {FLOW['outside_window']}",
	       f"Age and sex missing, {FLOW['missing_demo']}"]
	ys = [85, 55, 25]
	for i, (txt, y) in enumerate(zip(main, ys)):
		axb.add_patch(FancyBboxPatch((2, y - 5), 46, 10, boxstyle="round,pad=0.6", fc="white", ec="#333333")); axb.text(25, y, txt, ha="center", va="center", fontsize=8.5)
		if i < 2:
			axb.annotate("", xy=(25, ys[i + 1] + 5.8), xytext=(25, y - 5.8), arrowprops=dict(arrowstyle="->", color="#333333"))
			ym = (y + ys[i + 1]) / 2
			axb.add_patch(FancyBboxPatch((55, ym - 6), 43, 12, boxstyle="round,pad=0.6", fc="#F5F5F5", ec="#888888")); axb.text(76.5, ym, exc[i], ha="center", va="center", fontsize=7.5)
			axb.annotate("", xy=(54.4, ym), xytext=(25, ym), arrowprops=dict(arrowstyle="->", color="#888888"))
	n_items = MAIN.set_index("item").n
	axb.text(2, 8, f"Per-item analysis sets: {int(n_items.min())}-{int(n_items.max())} users. Summary panel: all 11 components measured {FLOW['panel11']}, "
	               f">=10 measured {FLOW['panel10']}.", fontsize=7.5)
	savefig(fig, "fig2_timeline_flow.png")


def fig_engagement():
	lg = A2.lg.copy(); lg["day"] = (lg.d - lg.d0).dt.days
	fig, (a1, a2) = plt.subplots(1, 2, figsize=(8, 3.6))
	n = len(U)  # all analysed users together (no site breakdown in paper outputs)
	share = lg.groupby("day").user_id.nunique().reindex(range(1, 29)).fillna(0) / n
	a1.plot(share.index, 100 * share.values, marker="o", ms=3, color=C_HI, label=f"All analysed users (n={n})")
	y = np.sort(U.y.values); a2.step(y, np.arange(1, len(y) + 1) / len(y), where="post", color=C_HI)
	a2.axvline(A2.MED, color="#888888", ls=":", lw=0.8); a2.text(A2.MED + 0.4, 0.05, f"median {A2.MED:.0f}", fontsize=7, color="#555555")
	a1.set_xlabel("Day after registration"); a1.set_ylabel("Users logging in, %"); a1.set_ylim(0, 100); a1.legend(frameon=False, fontsize=7.5); a1.set_title("A", loc="left")
	a2.set_xlabel("Login days in days 1-28"); a2.set_ylabel("Cumulative share of users"); a2.set_title("B", loc="left")
	fig.tight_layout(); savefig(fig, "fig3_engagement.png")


def fig_forest():
	fig = plt.figure(figsize=(8, 8))
	a1 = fig.add_axes([0.30, 0.36, 0.56, 0.6]); a2 = fig.add_axes([0.30, 0.06, 0.56, 0.22])
	rows, labels = [], []
	for dom, items in DOMAIN:
		labels.append(("h", dom)); rows.append(None)
		for it in items:
			labels.append(("i", it)); rows.append(MAIN.set_index("item").loc[it])
	yy = np.arange(len(rows))[::-1]
	a1.axvline(0, color="#888888", lw=0.8)
	for yv, (kind, lab), r in zip(yy, labels, rows):
		if kind == "h":
			continue
		if not r.tested:
			a1.text(0, yv, "descriptive only", fontsize=6.5, ha="center", va="center", color="#777777"); continue
		a1.plot([r.lo, r.hi], [yv, yv], color="#333333", lw=0.9)
		a1.plot(r.est, yv, "o", ms=5, mfc=C_HI if r.q < 0.05 else "white", mec="#333333")
	for yv, (kind, lab), r in zip(yy, labels, rows):
		if kind == "i":
			txt = f"{int(r.n)}" if lab in A2.CONT else f"{int(r.n)} ({100 * r.n_abn / r.n:.0f}%)"
			a1.text(1.01, yv, txt, transform=a1.get_yaxis_transform(), fontsize=6.3, va="center")
	a1.text(1.01, len(rows) - 0.2, "n (out of\nrange, %)", transform=a1.get_yaxis_transform(), fontsize=6.3, va="bottom")
	a1.set_yticks(yy); a1.set_yticklabels([(l if k == "h" else "   " + EN[l]) for k, l in labels], fontsize=7)
	for t, (k, _) in zip(a1.get_yticklabels(), labels):
		if k == "h":
			t.set_fontweight("bold")
	a1.set_xlabel("Adjusted difference in login days (out of 28)"); a1.set_title("A", loc="left")
	g = np.arange(8); cv = np.array(E["summary"]["curve"])
	if len(curve_bs) >= 900 and E["summary"].get("conv", False):
		lo_, hi_ = np.percentile(curve_bs, 2.5, axis=0), np.percentile(curve_bs, 97.5, axis=0)
		a2.fill_between(g, lo_, hi_, color="#CCCCCC", label="95% CI (pointwise)")
	a2.plot(g, cv, color="#333333", label="Standardized mean")
	ok = A2.N_MEAS == 11
	obs = pd.DataFrame({"k": np.minimum(A2.N_OUT[ok], 7), "y": U.y.values[ok]}).groupby("k").y.agg(["mean", "size"])
	a2.scatter(obs.index, obs["mean"], s=np.clip(obs["size"], 5, 80), facecolors="white", edgecolors="#333333", label="Observed mean (size = n)")
	a2.set_xticks(g); a2.set_xticklabels([str(i) for i in g[:-1]] + ["7+"]); a2.set_xlabel("Out-of-range summary-panel components (of 11)")
	a2.set_ylabel("Login days"); a2.legend(frameon=False, fontsize=6.5, loc="upper right"); a2.set_title("B", loc="left")
	fig.text(0.01, 0.005, "Filled marker: q < .05 (Benjamini-Hochberg over tested items).", fontsize=6.5)
	savefig(fig, "fig4_forest_summary.png")


def fig_fit():
	fig, (a1, a2) = plt.subplots(1, 2, figsize=(8, 3.4), gridspec_kw={"width_ratios": [1.6, 1]})
	a1.plot(DIST.days, DIST.observed, "o", mfc="white", mec="#333333", ms=4, label="Observed")
	a1.plot(DIST.days, DIST.expected, "-", color=C_HI, lw=1.2, label="Beta-binomial expected")
	a1.set_xlabel("Login days in days 1-28"); a1.set_ylabel("Users"); a1.legend(frameon=False, fontsize=7.5); a1.set_title("A", loc="left")
	c = CALIB.copy(); yy = np.arange(len(c))[::-1]
	a2.plot(c.observed, yy, "o", mfc="white", mec="#333333", ms=4, label="Observed mean"); a2.plot(c.predicted, yy, "x", color=C_HI, ms=5, label="Predicted mean")
	a2.set_yticks(yy); a2.set_yticklabels([f"{g}: {l} (n={n})" for g, l, n in zip(c.grouping, c.level, c.n)], fontsize=6.5)
	a2.set_xlabel("Login days"); a2.legend(frameon=False, fontsize=6.5, loc="lower right"); a2.set_title("B", loc="left")
	fig.tight_layout(); savefig(fig, "figS4_model_fit.png")


def fig_sensitivity():
	cols = [("main", "Main"), ("quasi", "Quasi-\nbinomial"), ("alt", "Disease-\nsuspect\ncutoffs"), ("year1", "Checkup\nwithin\n1 year"),
	        ("src101", "Source\n20101101\nonly"), ("susp1", "Suspect login\ndays removed\n(rule 1)")]
	tabs = {"main": MAIN.set_index("item")}; tabs.update({k: SENS[k].set_index("item") for k, _ in cols[1:]})
	fig, axes = plt.subplots(1, len(cols), figsize=(8, 6.5), sharey=True)
	yy = np.arange(len(A2.ITEMS))[::-1]
	for ax, (k, lab) in zip(axes, cols):
		ax.axvline(0, color="#888888", lw=0.7)
		t = tabs[k]
		for yv, it in zip(yy, A2.ITEMS):
			if it not in t.index or not t.loc[it, "tested"]:
				continue
			r = t.loc[it]
			if np.isfinite(r.lo):
				ax.plot([r.lo, r.hi], [yv, yv], color="#333333", lw=0.7)
			ax.plot(r.est, yv, "o", ms=3, mfc="white" if not (r.q < 0.05) else C_HI, mec="#333333")
		ax.set_title(lab, fontsize=6.8); ax.set_xlim(-12, 12); ax.tick_params(axis="x", labelsize=6.5)
	axes[0].set_yticks(yy); axes[0].set_yticklabels([EN[i] for i in A2.ITEMS], fontsize=6.5)
	fig.text(0.01, 0.034, "Adjusted difference in login days (out of 28). Disease-suspect cutoffs: BMI>=30, BP>=140/90, glucose>=126, total cholesterol>=240, LDL>=160,",
	         fontsize=6.5)
	fig.text(0.01, 0.014, "triglycerides>=200, urine protein including trace (rows keep the main labels). No line: CI not reported (<900 valid resamples). Rule 2: Table S6.",
	         fontsize=6.5)
	fig.tight_layout(rect=(0, 0.055, 1, 1)); savefig(fig, "figS2_sensitivity.png")


def fig_spline():
	f = OUT / "spline_curves.csv"
	if not f.exists():
		return
	R = pd.read_csv(f)
	its = [i for i in A2.ITEMS if i in set(R.item)]
	unit = {"height": "cm", "weight": "kg", "bmi": "kg/m2", "waist": "cm", "sbp": "mmHg", "dbp": "mmHg", "fbg": "mg/dL", "tc": "mg/dL", "hdl": "mg/dL",
	        "ldl": "mg/dL", "tg": "mg/dL", "hb": "g/dL", "ast": "U/L", "alt": "U/L", "ggt": "U/L", "cr": "mg/dL", "gfr": "mL/min/1.73m2"}
	name = {"height": "Height", "weight": "Weight", "bmi": "BMI", "waist": "Waist", "sbp": "Systolic BP", "dbp": "Diastolic BP", "fbg": "Fasting glucose",
	        "tc": "Total cholesterol", "hdl": "HDL", "ldl": "LDL", "tg": "Triglycerides", "hb": "Haemoglobin", "ast": "AST", "alt": "ALT", "ggt": "GGT",
	        "cr": "Creatinine", "gfr": "eGFR"}
	nc = 4; nr = int(np.ceil(len(its) / nc))
	fig, axes = plt.subplots(nr, nc, figsize=(8, 1.9 * nr), sharey=True); axes = axes.ravel()
	for ax, it in zip(axes, its):
		r = R[R.item == it]
		ax.fill_between(r.value, r.lo, r.hi, color="#DDDDDD"); ax.plot(r.value, r.est, color="#333333", lw=1)
		ax.set_title(f"{name[it]} (n={int(r.n.iloc[0])})", fontsize=7.5, loc="left"); ax.tick_params(labelsize=6.5)
		ax.set_xlabel(unit[it], fontsize=6.5); ax.set_ylim(8, 24)
	for ax in axes[len(its):]:
		ax.axis("off")
	for ax in axes[::nc]:
		ax.set_ylabel("Login days", fontsize=7)
	fig.text(0.01, 0.003, "Standardized mean login days (days 1-28) by the continuous checkup value, 5th-95th percentile range; grey band: pointwise 95% CI.",
	         fontsize=6.5)
	fig.tight_layout(rect=(0, 0.02, 1, 1)); savefig(fig, "figS1_spline.png")


def fig_timing():
	fig, ax = plt.subplots(figsize=(6, 3.4))
	k = A2.ITEMF["bmi"].k
	v = np.sort(k.dropna().values)
	ax.step(v, np.arange(1, len(v) + 1) / len(v), where="post", color=C_HI, label=f"All analysed users (n={len(v)})")
	ax.set_xlabel("Days from the baseline checkup (BMI item) to registration"); ax.set_ylabel("Cumulative share of users")
	ax.axvline(365, color="#BBBBBB", lw=0.8, ls=":"); ax.text(368, 0.05, "1 year", fontsize=7, color="#777777"); ax.legend(frameon=False, fontsize=7.5)
	fig.tight_layout(); savefig(fig, "figS3_checkup_timing.png")


fig_flow(); fig_engagement(); fig_forest(); fig_sensitivity(); fig_spline(); fig_timing(); fig_fit()

NOTES2 = [
	"Estimates: adjusted difference in mean login days (days 1-28 after registration) between users out of and within range (per SD for height and weight), from a beta-binomial regression (logit mean, common overdispersion) standardized over the users with the item. Adjusted for age, sex, enrolment site (two sites, not shown separately), registration quarter (quarters with < 10 users merged), days from the checkup to registration and checkup source.",
	"95% CI: percentile interval from 1,000 user-level bootstrap resamples. P: Wald test with the bootstrap SE (risk ratios on the log scale against 1). P and the percentile CI can disagree when the bootstrap distribution is skewed.",
	"Only resamples in which the fit converged are used, and the original-data fit must converge; with fewer than 900 valid resamples no CI, P or q is reported.",
	f"q: Benjamini-Hochberg over the items with a valid P in that table (main analysis: {int(MAIN.tested.sum())} items).",
	"Blank cells / not tested: fewer than 30 users, or fewer than 10 users out of or within range (resampling frequencies counted), or no CI (fewer than 900 valid resamples).",
	"S_high_rd / S_high_rr: logistic regression for high engagement (login days >= median); risk difference and risk ratio standardized over the users with the item.",
	"Registration quarters are shown as order numbers (1 = earliest); no calendar labels.",
	"E-value: from exp(0.91 x d), d = |difference| / SD of login days; CI E-value is 1 when the CI includes 0.",
	"Sheet-specific methods: S_quasi = quasi-binomial (fractional logit) model with the same covariates; S_alt = disease-suspect cutoffs; S_year1 / S_src101 / S_src104 = main model in that subset (covariates constant in a subset dropped); S_susp1 / S_susp2 = outcome without suspect login days; S_entry_reg (post hoc) = main model among users whose selected result for the item had been entered into the service by the registration day; S_summary = beta-binomial on the count of out-of-range components (summary_adj adds the mean checkup-to-registration days and any source-20101104 component); S_spline = beta-binomial with a restricted cubic spline of the raw value (descriptive).",
]
with pd.ExcelWriter(OUT / "tables_02.xlsx") as xw:
	pd.DataFrame({"note": NOTES2}).to_excel(xw, sheet_name="Notes", index=False)
	T1.to_excel(xw, sheet_name="Table1", index=False)
	MAIN.to_excel(xw, sheet_name="Table2", index=False)
	for k, t in SENS.items():
		t.to_excel(xw, sheet_name=f"S_{k}", index=False)
	HIGH.to_excel(xw, sheet_name="S_high_rd", index=False); HIGH_RR.to_excel(xw, sheet_name="S_high_rr", index=False)
	DIAG.to_excel(xw, sheet_name="S_diagnostics", index=False); SEL.to_excel(xw, sheet_name="S_selection", index=False)
	SEL_R.to_excel(xw, sheet_name="S_selection_reason", index=False); MISS.to_excel(xw, sheet_name="S_item_missing", index=False)
	ENTRY.to_excel(xw, sheet_name="S_entry_timing", index=False)
	DIST.to_excel(xw, sheet_name="S_fit_distribution", index=False); CALIB.to_excel(xw, sheet_name="S_fit_calibration", index=False)
	FITLOG.to_excel(xw, sheet_name="S_fit_log", index=False)
	pd.DataFrame([dict(analysis=k, **v) for k, v in SUMM.items()]).to_excel(xw, sheet_name="S_summary", index=False)
	if (OUT / "spline_curves.csv").exists():
		pd.read_csv(OUT / "spline_curves.csv").to_excel(xw, sheet_name="S_spline", index=False)
SUM = dict(flow=FLOW, median_login=A2.MED, summary=SUMM, tested=int(MAIN.tested.sum()), selected=MAIN.loc[MAIN.q < 0.05, "item"].tolist(),
           fallback={k: int(sum(E[k][it].get("fallback", False) for it in E[k])) for k in ["main"]}, boot_valid=len(B), figures=FIG)
json.dump(SUM, open(OUT / "summary_02.json", "w"), indent=1, default=float)
pd.set_option("display.width", 220)
print(MAIN[["item", "n", "n_abn", "n_norm", "tested", "est", "lo", "hi", "p", "q", "m_abn", "m_norm", "obs_abn", "obs_norm", "boot_valid"]].round(3).to_string(index=False))
print(json.dumps({k: v for k, v in SUM.items() if k != "figures"}, indent=1, default=float))
for k, t in SENS.items():
	print(k, t[["item", "n", "tested", "est", "lo", "hi", "p"]].round(2).to_string(index=False).replace("\n", " | ")[:1500])
print(T1.to_string(index=False))
print(DIAG.round(3).to_string(index=False)); print(SEL.to_string(index=False))
print(SEL_R.to_string(index=False)); print(MISS.round(2).to_string(index=False)); print(CALIB.round(2).to_string(index=False)); print(FITLOG.to_string(index=False))
print(MAIN[["item", "evalue", "evalue_ci"]].round(2).to_string(index=False).replace("\n", " | "))
