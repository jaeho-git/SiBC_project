# -*- coding: utf-8 -*-
"""Study 03 report: tables (xlsx), figures (PNG, <=1200 px) and a JSON summary from ana3.py outputs.

Run from retrospective_study/ after ana3.py:  python3 03_irs_risk_rank/src/report3.py
Writes to 03_irs_risk_rank/01_Results/analysis/ (git-ignored). Figures use English labels for the manuscript.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
from matplotlib.ticker import FixedLocator, FormatStrFormatter  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "03_irs_risk_rank/src"))
sys.path.insert(0, str(ROOT / "00_common/src"))
import ana3 as A3  # noqa: E402
import statlib as S  # noqa: E402

OUT = A3.OUT
E = pd.read_pickle(OUT / "est_point.pkl")
B = [b for b in pd.read_pickle(OUT / "est_boot.pkl") if "error" not in b]
FZ = A3.FZ
INFO = pd.read_csv(FZ / "dis_info.csv").set_index("disease_id")
KO = INFO.disease_nm.to_dict()
EN = {d: d.replace("_", " ").replace("non-alcoholic", "non-alcoholic").capitalize() for d in A3.DIS}
EN.update({"type_2_diabetes": "Type 2 diabetes", "chronic_obstructive_pulmonary_disease": "COPD", "alzheimers_disease": "Alzheimer disease",
           "non-alcoholic_fatty_liver_disease": "NAFLD", "benign_prostatic_hyperplasia": "Benign prostatic hyperplasia"})
C_HI, C_LO = "#0072B2", "#D55E00"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
FIG = {}


def savefig(fig, name):
	fig.savefig(OUT / name, dpi=150)
	plt.close(fig)
	FIG[name] = str(OUT / name)


def logticks(ax):
	ax.xaxis.set_major_locator(FixedLocator([0.1, 0.2, 0.5, 1, 2, 5, 10])); ax.xaxis.set_major_formatter(FormatStrFormatter("%g"))
	ax.xaxis.set_minor_locator(FixedLocator([]))


def draw_ci(ax, lo, hi, y, xmin=0.1, xmax=10):
	"""CI line clipped to the axis, with an arrow head where it continues beyond the axis."""
	a_, b_ = max(lo, xmin * 1.02), min(hi, xmax / 1.02)
	ax.plot([a_, b_], [y, y], color="#333333", lw=0.9)
	if lo < xmin:
		ax.plot(a_, y, marker="<", ms=4, color="#333333")
	if hi > xmax:
		ax.plot(b_, y, marker=">", ms=4, color="#333333")


def ci(vals, est):
	v = np.asarray([x for x in vals if np.isfinite(x)])
	if len(v) < 900:  # same rule everywhere: fewer than 900 valid replicates -> no interval
		return np.nan, np.nan, np.nan, len(v)
	return np.percentile(v, 2.5), np.percentile(v, 97.5), np.std(v, ddof=1), len(v)


# ---------------------------------------------------------------- representative outcome + sensitivity
ROWS = [("main", "Primary: IRS, all 35 diseases"), ("pass18", "Crosswalk-validated 18 diseases"), ("same_model", "Same-model comparison only"),
        ("bands3", "3 risk bands"), ("bands10", "10 risk bands"), ("shift10", "Band boundaries shifted by 10 ranks"),
        ("incl_lowest", "Lowest band kept in the denominator"), ("base28", "Baseline within 28 days of registration"),
        ("pooled", "Disease-count-weighted proportion (pooled over diseases)"), ("life_ch", "Users with changed lifestyle input"),
        ("no_life_ch", "Users with unchanged lifestyle input"), ("no_trunc", "Weights not truncated"), ("unadjusted", "Unweighted, unadjusted"),
        ("susp1", "Suspect login days removed (rule 1)"), ("susp2", "Suspect login days removed (rule 2)"),
        ("gap_common", "Follow-up interval within the common range (exploratory)"), ("gap_adj", "Adjusted for log follow-up interval (exploratory)"),
        ("mrs_rep", "Medical rank (MRS)"), ("lrs_rep", "Lifestyle rank (LRS), changed input only")]
rep = []
for k, lab in ROWS:
	e = E[k]
	Bk = [b for b in B if b[k].get("conv", False)]  # replicate accepted only if the PS and outcome models converged
	lo, hi, se, nb = ci([b[k]["diff"] for b in Bk], e["diff"])
	rlo, rhi, _, _ = ci([b[k]["ratio"] for b in Bk], e["ratio"])
	if nb < 900 or not e.get("conv", False):  # too few converged replicates, or the original-data fit did not converge: point estimate only
		lo = hi = se = rlo = rhi = np.nan
	p = S.wald_p(e["diff"], se)
	ev = S.evalue_rr(e["ratio"], rlo, rhi)
	rep.append(dict(key=k, analysis=lab, n=e["n"], n_high=e.get("n_hi"), m_high=e["m1"], m_low=e["m0"], diff_pp=100 * e["diff"],
	                diff_lo=100 * lo, diff_hi=100 * hi, ratio=e["ratio"], ratio_lo=rlo, ratio_hi=rhi, p=p, boot_valid=nb,
	                evalue=ev[0], evalue_ci=ev[1]))
REP = pd.DataFrame(rep)

# crude (observed) per-user proportions by group for the primary definition
out0 = A3.rebuild(None)
n0, k0, mb0, mp0 = A3.user_outcome(*out0["irs"], np.ones(len(A3.LB), bool))
prop = np.where(n0 > 0, k0 / np.where(n0 > 0, n0, 1), np.nan)
crude = dict(high=float(np.nanmean(prop[A3.A == 1])), low=float(np.nanmean(prop[A3.A == 0])), zero_denominator=int((n0 == 0).sum()))

# dose-response
d0 = E["dose"]; BD = [b for b in B if b["dose"].get("conv", False)]
lo, hi, se, nb = ci([b["dose"]["diff"] for b in BD], d0["diff"])
_, _, se_nl, _ = ci([b["dose"]["nonlin"] for b in BD], d0["nonlin"])
if not d0.get("conv", False):
	lo = hi = se = se_nl = np.nan
DOSE = dict(diff_pp=100 * d0["diff"], lo=100 * lo, hi=100 * hi, p_nonlin=S.wald_p(d0["nonlin"], se_nl), q25=float(A3.Q25), q75=float(A3.Q75),
            knots=[float(x) for x in A3.KNOTS])
curve_bs = np.array([b["dose"]["curve"] for b in BD])
DOSE["boot_valid"] = len(BD)

# ---------------------------------------------------------------- per-disease
def dis_table(key):
	rows = []
	for d in A3.DIS:
		r = E[key][d]
		row = dict(disease=d, name_ko=KO.get(d, d), name_en=EN.get(d, d), n=r["n"], n_high=r["n1"], n_low=r["n0"], ev_high=r["e1"], ev_low=r["e0"],
		           crude_high=r["crude1"], crude_low=r["crude0"], tested=r["tested"], reason=r.get("reason"), rr=r.get("rr", np.nan), rd=r.get("rd", np.nan),
		           rr_firth=r.get("rr_firth", np.nan), rr_cov=r.get("rr_cov", np.nan))
		if r["tested"] and not r.get("conv", True):  # original-data propensity score did not converge
			row.update(tested=False, reason="ps_nonconv")
		if row["tested"]:
			okb = [b for b in B if b[key][d].get("tested") and b[key][d].get("conv", True) and np.isfinite(b[key][d].get("rr", np.nan)) and b[key][d]["rr"] > 0]
			lrr = [np.log(b[key][d]["rr"]) for b in okb]
			rds = [b[key][d]["rd"] for b in okb]
			if len(lrr) >= 900:
				row.update(rr_lo=float(np.exp(np.percentile(lrr, 2.5))), rr_hi=float(np.exp(np.percentile(lrr, 97.5))),
				           rd_lo=float(np.percentile(rds, 2.5)), rd_hi=float(np.percentile(rds, 97.5)),
				           p=S.wald_p(np.log(r["rr"]), np.std(lrr, ddof=1)), boot_valid=len(lrr))
			else:
				row.update(tested=False, boot_valid=len(lrr), reason="boot_unstable")
		rows.append(row)
	t = pd.DataFrame(rows)
	for c in ["rr_lo", "rr_hi", "rd_lo", "rd_hi", "p", "boot_valid"]:
		if c not in t:
			t[c] = np.nan
	t["q"] = np.nan
	m = t.tested & t.p.notna()
	t.loc[m, "q"] = S.bh(t.loc[m, "p"].values)
	t["q_keep_all"] = S.bh(np.where(m, t.p, 1.0))  # untested hypotheses kept in the family with P = 1
	t["selected"] = t.q < 0.05
	return t


DT = {k: dis_table("dis_" + k) for k in ["irs", "mrs", "lrs"]}
for k in ["irs", "mrs"]:
	DT[k]["crosswalk_pass"] = DT[k].disease.isin(A3.PASS[k])

# ---------------------------------------------------------------- Table 1 and balance
Dr = A3.Dr.copy()
w_main, ps_main, _ = A3.ps_fit(A3.CNT1, np.ones(len(Dr), bool))
Dr["w"] = w_main; Dr["ps"] = ps_main; Dr["high"] = A3.A
L0 = A3.LB.copy(); rc, rf = out0["irs"]
L0["bc"] = A3.bands(rc)
Dr["n_eval"] = L0[np.isfinite(rc)].groupby("ui").size().reindex(range(len(Dr))).fillna(0).values
Dr["n_elig"] = n0
Dr["n_top"] = L0[np.isfinite(rc) & (L0.bc == 4)].groupby("ui").size().reindex(range(len(Dr))).fillna(0).values
Dr["n_prs_top"] = L0[L0.prs_r_b >= 81].groupby("ui").size().reindex(range(len(Dr))).fillna(0).values
Dr["mean_band"] = mb0 + 1; Dr["same_model"] = (Dr.model_f == "P0").astype(float); Dr["lch"] = A3.LCH.astype(float)
T1V = [("age", "Age, years", "mean"), ("female", "Female", "pct"), ("k_b", "Days from registration to baseline IRS", "med"),
       ("act_pre", "Login days before baseline", "med"), ("base_day", "Baseline calculation, days after the first baseline", "med"),
       ("wear_pre", "Wearable linked before baseline", "pct"), ("act28", "Login days in the 28-day exposure window", "med"),
       ("gap", "Days between baseline and follow-up IRS", "med"), ("same_model", "Same-model comparison", "pct"),
       ("lch", "Lifestyle input changed", "pct"), ("n_eval", "Diseases evaluated", "med"), ("n_elig", "Diseases above the lowest band", "med"),
       ("n_top", "Diseases in the highest band (81-100)", "med"), ("n_prs_top", "Diseases with genetic rank 81-100", "med"),
       ("mean_band", "Mean baseline band of eligible diseases (1 = ranks 1-20 ... 5 = ranks 81-100)", "mean")]
SECTION = {"act28": "Exposure", "gap": "After baseline", "same_model": "After baseline", "lch": "After baseline"}
NO_SMD = {"act28", "gap", "same_model", "lch"}
hi = Dr.high == 1
t1 = []
for v, lab, kind in T1V:
	x = Dr[v].astype(float)
	def fmt(s):
		if kind == "mean":
			return f"{s.mean():.1f} ({s.std(ddof=1):.1f})"
		if kind == "pct":
			return f"{int(s.sum())} ({100 * s.mean():.1f})"
		return f"{s.median():.0f} ({s.quantile(.25):.0f}-{s.quantile(.75):.0f})"
	ok = x.notna()
	row = dict(section=SECTION.get(v, "Baseline"), variable=lab, overall=fmt(x[ok]), high=fmt(x[ok & hi]), low=fmt(x[ok & ~hi]))
	if v not in NO_SMD:
		row["smd_before"] = S.smd(x[ok].values, hi[ok].values)
		row["smd_after"] = S.smd(x[ok].values, hi[ok].values, Dr.w[ok].values)
	t1.append(row)
T1 = pd.DataFrame(t1)
BAL = dict(ess_high=S.ess(Dr.w[hi]), ess_low=S.ess(Dr.w[~hi]), w_min=float(Dr.w.min()), w_max=float(Dr.w.max()),
           max_abs_smd_after=float(np.nanmax(np.abs(T1.smd_after))), max_abs_smd_before=float(np.nanmax(np.abs(T1.smd_before))))

# ---------------------------------------------------------------- figures
def fig_flow():
	fl = json.load(open(FZ / "x7b_flow.json"))
	fig = plt.figure(figsize=(8, 8))
	axa = fig.add_axes([0.03, 0.80, 0.94, 0.18]); axb = fig.add_axes([0.03, 0.02, 0.94, 0.76])
	axa.set_xlim(0, 100); axa.set_ylim(0, 10); axa.axis("off")
	axa.text(0, 9.3, "A", fontsize=13, fontweight="bold")
	segs = [(2, 30, "Baseline IRS\n0-56 days after registration\n(before the model update)", "#E8E8E8"),
	        (34, 62, "Exposure\nlogin days in the\n28 days after baseline", "#CFE3F2"),
	        (68, 98, "Follow-up IRS\n>=90 days after baseline,\nchanged medical input", "#E8E8E8")]
	for a_, b_, t_, c_ in segs:
		axa.add_patch(FancyBboxPatch((a_, 3.2), b_ - a_, 5.0, boxstyle="round,pad=0.3", fc=c_, ec="#555555"))
		axa.text((a_ + b_) / 2, 5.7, t_, ha="center", va="center", fontsize=8)
	axa.annotate("", xy=(99, 1.6), xytext=(1, 1.6), arrowprops=dict(arrowstyle="->", color="#333333"))
	axa.text(1, 0.0, "Registration (first login)", fontsize=7.5); axa.text(99, 0.0, "Time", fontsize=7.5, ha="right")
	axb.set_xlim(0, 100); axb.set_ylim(0, 100); axb.axis("off")
	axb.text(0, 97, "B", fontsize=13, fontweight="bold")
	main = [f"Users linked to the service (n={fl['site_users']})",
	        f"Common cohort (n={fl['common_cohort']})",
	        f"At least one complete IRS (n={fl['with_complete_irs']})",
	        f"Complete IRS within 56 days, before the model update (n={fl['baseline_model_ok']})",
	        f"Analysed (n={fl['final']})"]
	exc = [f"Operator or test accounts, {fl['excl_operator_test']}\nNo login, {fl['no_login']}\nRegistered too recently or withdrew early, {fl['not_common']}",
	       f"No IRS, {fl['excl_no_irs']}\nNo complete IRS, {fl['excl_no_complete']}",
	       f"First complete IRS after day 56, {fl['excl_after_window']}\nBaseline IRS from the updated model, {fl['excl_post_july_baseline']}",
	       f"No complete IRS >=90 days later, {fl['no_complete_90d']}\nNo changed medical input, {fl['no_new_checkup']}\nChanged input only after the next update, {fl['new_checkup_only_later']}"]
	ys = [90, 70, 50, 30, 10]
	for i, (txt, y) in enumerate(zip(main, ys)):
		axb.add_patch(FancyBboxPatch((2, y - 4), 50, 8, boxstyle="round,pad=0.6", fc="white", ec="#333333"))
		axb.text(27, y, txt, ha="center", va="center", fontsize=8)
		if i < len(ys) - 1:
			axb.annotate("", xy=(27, ys[i + 1] + 4.8), xytext=(27, y - 4.8), arrowprops=dict(arrowstyle="->", color="#333333"))
			ym = (y + ys[i + 1]) / 2
			axb.add_patch(FancyBboxPatch((58, ym - 6), 40, 12, boxstyle="round,pad=0.6", fc="#F5F5F5", ec="#888888"))
			axb.text(78, ym, exc[i], ha="center", va="center", fontsize=7)
			axb.annotate("", xy=(57.4, ym), xytext=(27, ym), arrowprops=dict(arrowstyle="->", color="#888888"))
	axb.text(2, 1.5, f"Crosswalk comparison {int((Dr.model_f == 'P1').sum())}, same model {int((Dr.model_f == 'P0').sum())}; "
	                  f"high engagement (>= median {A3.MED:.0f} days) {int(A3.A.sum())}, low {int((1 - A3.A).sum())}", ha="left", fontsize=7.5)
	savefig(fig, "fig2_timeline_flow.png")


def fig_transitions():
	rc, rf = out0["irs"]; bc, bf = A3.bands(rc), A3.bands(rf)
	ok = np.isfinite(rc) & np.isfinite(rf) & (bc > 0)
	t = pd.DataFrame({"d": A3.LB.disease.values[ok], "down": (bf < bc)[ok], "same": (bf == bc)[ok], "up": (bf > bc)[ok]})
	g = t.groupby("d").agg(n=("down", "size"), down=("down", "mean"), same=("same", "mean"), up=("up", "mean")).reindex(A3.DIS)
	fig, ax = plt.subplots(figsize=(8, 8))
	yy = np.arange(len(g))[::-1]
	ax.barh(yy, g.down, color="#0072B2", label="Lower band", hatch="///", edgecolor="white")
	ax.barh(yy, g.same, left=g.down, color="#BBBBBB", label="Same band")
	ax.barh(yy, g.up, left=g.down + g.same, color="#D55E00", label="Higher band", hatch="...", edgecolor="white")
	lab = [EN[d] + (" *" if d in A3.PASS["irs"] else "") for d in g.index]
	ax.set_yticks(yy); ax.set_yticklabels(lab, fontsize=7)
	for yv, n in zip(yy, g.n):
		ax.text(1.01, yv, f"{int(n)}", va="center", fontsize=6.5)
	ax.text(1.01, len(g) + 0.2, "n", fontsize=7)
	ax.set_xlim(0, 1.08); ax.set_xlabel("Share of users above the lowest band at baseline")
	ax.legend(loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=3, frameon=False, fontsize=8)
	fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.text(0.01, 0.01, "* crosswalk agreement >= 95% in each sex", fontsize=7)
	savefig(fig, "fig3_band_transitions.png")


def fig_forest():
	fig, axes = plt.subplots(1, 2, figsize=(8, 8), sharey=True)
	for ax, key, title in zip(axes, ["irs", "mrs"], ["A  Integrated risk rank (IRS)", "B  Medical risk rank (MRS)"]):
		t = DT[key].set_index("disease").reindex(A3.DIS); yy = np.arange(len(t))[::-1]
		ax.axvline(1, color="#888888", lw=0.8)
		for yv, (d, r) in zip(yy, t.iterrows()):
			if not r.tested:
				ax.text(1, yv, "descriptive only", fontsize=6, va="center", ha="center", color="#777777")
				continue
			mk = "o" if r.get("crosswalk_pass", False) else "^"
			fill = C_HI if r.q < 0.05 else "white"
			draw_ci(ax, r.rr_lo, r.rr_hi, yv)
			ax.plot(r.rr, yv, marker=mk, ms=5, mfc=fill, mec="#333333")
		ax.set_xscale("log"); ax.set_xlim(0.1, 10); ax.set_title(title, fontsize=9, loc="left"); logticks(ax)
		ax.set_xlabel("Risk ratio, high vs low engagement")
		ax.set_yticks(yy); ax.set_yticklabels([EN[d] for d in A3.DIS], fontsize=7)
	fig.tight_layout(rect=(0, 0.04, 1, 1))
	fig.text(0.01, 0.012, "Circle: crosswalk agreement >= 95% in each sex; triangle: below. Filled marker: q < .05 (Benjamini-Hochberg within each score).", fontsize=6.5)
	savefig(fig, "fig4_forest_irs_mrs.png")


def fig_supp():
	# S1 exposure distribution
	fig, ax = plt.subplots(figsize=(6, 3.5))
	ax.hist(Dr.act28, bins=np.arange(-0.5, 29.5, 1), color="#888888", edgecolor="white")
	ax.axvline(A3.MED - 0.5, color="#333333", ls="--"); ax.text(A3.MED - 0.3, ax.get_ylim()[1] * 0.92, f"median {A3.MED:.0f}", fontsize=8)
	ax.set_xlabel("Login days in the 28-day exposure window"); ax.set_ylabel("Users")
	fig.tight_layout(); savefig(fig, "figS1_exposure.png")
	# S2 propensity overlap and love plot
	fig, (a1, a2) = plt.subplots(1, 2, figsize=(8, 3.8), gridspec_kw={"width_ratios": [1, 1.3]})
	bins = np.linspace(0, 1, 21)
	a1.hist(Dr.ps[hi], bins=bins, alpha=0.6, color=C_HI, label="High", histtype="stepfilled")
	a1.hist(Dr.ps[~hi], bins=bins, color=C_LO, label="Low", histtype="step", lw=1.5, ls="--")
	a1.set_xlabel("Propensity score"); a1.set_ylabel("Users"); a1.legend(frameon=False); a1.set_title("A", loc="left")
	tb = T1.dropna(subset=["smd_before"])
	yy = np.arange(len(tb))[::-1]
	a2.scatter(tb.smd_before.abs(), yy, marker="o", facecolors="white", edgecolors="#333333", label="Before weighting")
	a2.scatter(tb.smd_after.abs(), yy, marker="s", color=C_HI, label="After weighting")
	a2.axvline(0.1, color="#888888", ls="--", lw=0.8)
	SHORTV = {"Mean baseline band of eligible diseases (1 = ranks 1-20 ... 5 = ranks 81-100)": "Mean baseline band (1-5)",
	          "Baseline calculation, days after the first baseline": "Baseline calculation date",
	          "Days from registration to baseline IRS": "Registration to baseline, days",
	          "Diseases with genetic rank 81-100": "Diseases with genetic rank 81-100", "Diseases in the highest band (81-100)": "Diseases in the top band"}
	a2.set_yticks(yy); a2.set_yticklabels([SHORTV.get(v, v) for v in tb.variable], fontsize=6.5); a2.set_xlabel("Absolute standardized mean difference")
	a2.legend(frameon=False, fontsize=7); a2.set_title("B", loc="left")
	fig.tight_layout(); savefig(fig, "figS2_ps_balance.png")
	# S3 dose-response
	fig, ax = plt.subplots(figsize=(6, 3.8))
	g = np.arange(29); cv = np.array(d0["curve"])
	if len(curve_bs) >= 900 and d0.get("conv", False):
		lo_, hi_ = np.percentile(curve_bs, 2.5, axis=0), np.percentile(curve_bs, 97.5, axis=0)
		ax.fill_between(g, 100 * lo_, 100 * hi_, color="#CCCCCC", label="95% CI")
	ax.plot(g, 100 * cv, color="#333333", label="Standardized mean")
	ax.set_xlabel("Login days in the 28-day exposure window"); ax.set_ylabel("Diseases moving to a lower band, %")
	ax.legend(frameon=False, fontsize=8, title="Pointwise 95% CI from the bootstrap", title_fontsize=7); fig.tight_layout(); savefig(fig, "figS3_dose_response.png")
	# S4 LRS forest
	t = DT["lrs"].set_index("disease").reindex(A3.DIS); yy = np.arange(len(t))[::-1]
	fig, ax = plt.subplots(figsize=(5, 8)); ax.axvline(1, color="#888888", lw=0.8)
	for yv, (d, r) in zip(yy, t.iterrows()):
		if not r.tested:
			ax.text(1, yv, "descriptive only", fontsize=6, va="center", ha="center", color="#777777"); continue
		draw_ci(ax, r.rr_lo, r.rr_hi, yv)
		ax.plot(r.rr, yv, "o", ms=5, mfc=C_HI if r.q < 0.05 else "white", mec="#333333")
	ax.set_xscale("log"); ax.set_xlim(0.1, 10); logticks(ax); ax.set_yticks(yy); ax.set_yticklabels([EN[d] for d in A3.DIS], fontsize=7)
	ax.set_xlabel("Risk ratio, high vs low engagement"); ax.set_title("Lifestyle risk rank (LRS), changed input only", fontsize=9, loc="left")
	fig.tight_layout(); savefig(fig, "figS4_forest_lrs.png")
	# S5 sensitivity forest
	t = REP.copy(); yy = np.arange(len(t))[::-1]
	fig, ax = plt.subplots(figsize=(8, 6)); ax.axvline(0, color="#888888", lw=0.8)
	for yv, (_, r) in zip(yy, t.iterrows()):
		ax.plot([r.diff_lo, r.diff_hi], [yv, yv], color="#333333", lw=0.9)
		ax.plot(r.diff_pp, yv, "s" if r.key == "main" else "o", ms=5, color=C_HI if r.key == "main" else "#333333")
		if not np.isfinite(r.diff_lo):
			ax.text(r.diff_pp + 0.6, yv, f"{int(r.boot_valid)} valid resamples", fontsize=6.5, va="center", color="#777777")
	ax.set_yticks(yy); ax.set_yticklabels(t.analysis, fontsize=7)
	ax.set_xlabel("Difference in mean share of diseases moving to a lower band,\npercentage points (high minus low engagement)")
	fig.text(0.01, 0.01, "Square: primary analysis. A marker without a line: CI not reported (<900 valid resamples). Rules 1 and 2 removed the same days.",
	         fontsize=6.5)
	fig.tight_layout(rect=(0, 0.03, 1, 1)); savefig(fig, "figS5_sensitivity.png")


fig_flow(); fig_transitions(); fig_forest(); fig_supp()

# ---------------------------------------------------------------- added after the first Codex review
# four groups: engagement x lifestyle-input change (descriptive only)
FOUR = []
for key, lab in [("1_1", "High engagement, lifestyle input changed"), ("1_0", "High engagement, unchanged"),
                 ("0_1", "Low engagement, lifestyle input changed"), ("0_0", "Low engagement, unchanged")]:
	e = E["four_group"][key]; v = [b["four_group"][key]["mean"] for b in B]
	f_lo, f_hi, _, _ = ci(v, e["mean"])
	FOUR.append(dict(group=lab, n=e["n"], mean_pct=100 * e["mean"], lo=100 * f_lo, hi=100 * f_hi))
FOUR = pd.DataFrame(FOUR)
GAP = dict(lo=A3.GAP_LO, hi=A3.GAP_HI, n_in=int(((Dr.gap >= A3.GAP_LO) & (Dr.gap <= A3.GAP_HI)).sum()),
           high=Dr.gap[hi].describe().round(1).to_dict(), low=Dr.gap[~hi].describe().round(1).to_dict())


def selection_compare():
	"""Analysed users vs the other baseline candidates (complete IRS within 56 days, before the model update)."""
	import os
	cwd = os.getcwd(); os.chdir(FZ)
	try:
		I = pd.read_pickle("I_final.pkl"); I["mode"] = I["mode"].astype(str); I = I.sort_values(["t", "seq"]).reset_index(drop=True)
		I["d"] = I.t.dt.normalize(); I["model"] = np.where(I.t < pd.Timestamp("2026-07-01 10:00"), "P0", "P1+")
		I["complete"] = I["mode"].isin(["1", "4"]) & I.meas.astype(bool) & I.life_h.notna()
		Lg = pd.read_csv("login.csv", parse_dates=["d"])[["user_id", "d"]].drop_duplicates()
	finally:
		os.chdir(cwd)
	from common_cohort import load_common_cohort
	C = load_common_cohort()
	comp = I[I.complete & I.user_id.isin(C.index)].copy(); comp["k"] = (comp.d - comp.user_id.map(C.d0)).dt.days
	base = comp[(comp.k >= 0) & (comp.k <= 56)].drop_duplicates("user_id", keep="first")
	base = base[base.model == "P0"].set_index("user_id")
	base["analysed"] = base.index.isin(A3.Dr.user_id)
	ld = Lg[Lg.user_id.isin(base.index)].merge(base[["d"]].rename(columns={"d": "db"}), left_on="user_id", right_index=True)
	base["exp28"] = ld[(ld.d > ld.db) & (ld.d <= ld.db + pd.Timedelta(days=28))].groupby("user_id").size().reindex(base.index).fillna(0)
	base["pre"] = ld[ld.d < ld.db].groupby("user_id").size().reindex(base.index).fillna(0)
	base["age_n"] = pd.to_numeric(base.age, errors="coerce"); base["female"] = (base.sex == "F").astype(float)
	out = []
	for lab, v, kind in [("Age, years", "age_n", "mean"), ("Female", "female", "pct"),
	                     ("Days from registration to baseline", "k", "med"), ("Login days before baseline", "pre", "med"),
	                     ("Login days in the 28 days after baseline", "exp28", "med")]:
		row = dict(variable=lab)
		for g, m in [("analysed", base.analysed), ("not analysed", ~base.analysed)]:
			x = base.loc[m, v].astype(float).dropna()
			row[g] = (f"{x.mean():.1f} ({x.std(ddof=1):.1f})" if kind == "mean" else f"{int(x.sum())} ({100 * x.mean():.1f})" if kind == "pct"
			          else f"{x.median():.0f} ({x.quantile(.25):.0f}-{x.quantile(.75):.0f})")
		out.append(row)
	return pd.DataFrame(out), int(base.analysed.sum()), int((~base.analysed).sum())


SEL, N_SEL_IN, N_SEL_OUT = selection_compare()

# balance inside each disease's eligible subset, with the weights used by the per-disease models (IRS and MRS: all users; LRS: changed input)
dbal = []
_nU = len(A3.users)
_w_all = np.zeros(_nU); _sub = np.ones(_nU, bool); _w, _, _ = A3.ps_fit(A3.CNT1.astype(float), _sub); _w_all[_sub] = _w
_w_l = np.zeros(_nU); _sl = A3.LCH.copy(); _wl, _, _ = A3.ps_fit(A3.CNT1.astype(float), _sl); _w_l[_sl] = _wl
for score, wv, um in [("irs", _w_all, np.ones(_nU, bool)), ("mrs", _w_all, np.ones(_nU, bool)), ("lrs", _w_l, A3.LCH)]:
	rc_, rf_ = out0[score]; bc_ = A3.bands(rc_)
	for d in A3.DIS:
		ix = np.where((A3.LB.disease.values == d) & np.isfinite(rc_) & np.isfinite(rf_) & (bc_ > 0))[0]
		ui = A3.LB.ui.values[ix]; ui = ui[um[ui]]
		if len(ui) < 30:
			continue
		aa = A3.A[ui]; ww = wv[ui]
		sm = [abs(S.smd(Dr[v].values[ui], aa, ww)) for v in A3.PSV]
		dbal.append(dict(score=score, disease=d, n=len(ui), max_abs_smd=max(sm), ess_high=S.ess(ww[aa == 1]), ess_low=S.ess(ww[aa == 0])))
DBAL = pd.DataFrame(dbal)

TAB2 = REP[REP.key.isin(["main", "mrs_rep", "lrs_rep"])].copy()
SENS = REP[~REP.key.isin(["main", "mrs_rep", "lrs_rep"])].copy()
IPW_ONLY = None


# ---------------------------------------------------------------- write tables and summary
NOTES3 = [
	"Representative outcome: per user, the share of evaluated diseases (baseline band not the lowest, ranks 1-20) that moved to a lower 20-rank band at follow-up. Estimates: standardized mean share (high, low), difference in percentage points and ratio, from a fractional logistic model with stabilized IPTW, adjusted for the propensity-score covariates (age, sex, days from registration to baseline, login days before baseline, baseline calculation date, wearable linked before baseline), the mean baseline band and the mean within-band position.",
	"95% CI: percentile interval from 1,000 bootstrap resamples that jointly resample the bridge pairs, the rank-table users and the analysed users and rebuild the crosswalk, rank table, bands, propensity score and models each time. P: Wald test with the bootstrap SE (difference scale; risk ratios on the log scale). P and the percentile CI can disagree when the bootstrap distribution is skewed.",
	"Only resamples in which the propensity-score and outcome models converged are used, and the original-data fit must converge; with fewer than 900 valid resamples no CI or P is reported.",
	"Per-disease tables: risk ratio and risk difference of moving down among eligible users, from a weighted logistic model adjusted for baseline band and within-band position. q: Benjamini-Hochberg within each score over the diseases tested (" + ", ".join(f"{k.upper()} {int(DT[k].tested.sum())}" for k in ["irs", "mrs", "lrs"]) + "); q_keep_all keeps untested diseases in the family with P = 1. reason: min_n (< 30 users or < 10 per group), no_variation, nonconv, large_coef (|coefficient| > 15), boot_unstable (< 900 valid resamples).",
	"E-value: for the ratio and for the CI limit nearer the null (1 when the CI includes 1).",
	"Per-disease columns: rr = risk ratio (main per-disease model); rd = risk difference on the probability scale (multiply by 100 for percentage points); rr_firth = risk ratio from a Firth-penalized model (sparse-data sensitivity; blank if that fit failed); rr_cov = risk ratio with the propensity covariates added to the outcome model (blank if that fit failed or a coefficient exceeded 15).",
	"Sheet-specific methods: 'Unweighted, unadjusted' = no propensity weighting and no covariates; 'Weights not truncated' = no 1/99 percentile truncation; dose-response = unweighted fractional logit with a restricted cubic spline of login days and the same covariates; four groups = descriptive means; follow-up interval rows are exploratory.",
	"Representative analyses follow the common minimum-n rule (>= 30 users and >= 10 per group, counted with resampling frequencies); resamples failing it are not valid.",
]
with pd.ExcelWriter(OUT / "tables_03.xlsx") as xw:
	pd.DataFrame({"note": NOTES3}).to_excel(xw, sheet_name="Notes", index=False)
	T1.to_excel(xw, sheet_name="Table1", index=False)
	TAB2.to_excel(xw, sheet_name="Table2", index=False)
	SENS.to_excel(xw, sheet_name="S_sensitivity", index=False)
	FOUR.to_excel(xw, sheet_name="S_four_groups", index=False)
	SEL.to_excel(xw, sheet_name="S_selection", index=False)
	DBAL.to_excel(xw, sheet_name="S_disease_balance", index=False)
	for k in ["irs", "mrs", "lrs"]:
		DT[k].to_excel(xw, sheet_name=f"S_disease_{k}", index=False)
SUM = dict(gap=GAP, selection=dict(analysed=N_SEL_IN, not_analysed=N_SEL_OUT),
           disease_balance={sc: dict(median_max_smd=float(g.max_abs_smd.median()), max_max_smd=float(g.max_abs_smd.max()),
                                     n_over_02=int((g.max_abs_smd > 0.2).sum()), n=len(g)) for sc, g in DBAL.groupby("score")},
           reasons={k: DT[k].reason.value_counts().to_dict() for k in DT}, median_exposure=A3.MED, n_high=int(A3.A.sum()), n_low=int((1 - A3.A).sum()), crude=crude, dose=DOSE, balance=BAL,
           boot_valid=len(B), selected={k: DT[k].loc[DT[k].selected, "disease"].tolist() for k in DT},
           tested={k: int(DT[k].tested.sum()) for k in DT}, figures=FIG)
json.dump(SUM, open(OUT / "summary_03.json", "w"), indent=1, default=float)
pd.set_option("display.width", 200)
print(REP[["analysis", "n", "m_high", "m_low", "diff_pp", "diff_lo", "diff_hi", "ratio", "ratio_lo", "ratio_hi", "p", "evalue", "evalue_ci", "boot_valid"]].round(3).to_string(index=False))
print(json.dumps({k: v for k, v in SUM.items() if k != "figures"}, indent=1, default=float))
for k in DT:
	t = DT[k]
	print(k, "tested", int(t.tested.sum()), "min q", round(float(t.q.min()), 3) if t.q.notna().any() else None)
print(T1.round(3).to_string(index=False))
print(FOUR.round(2).to_string(index=False)); print(SEL.to_string(index=False)); print(DBAL.round(3).describe().to_string())
for k in DT:
	print(k, DT[k][["disease", "tested", "reason", "rr", "rr_lo", "rr_hi", "rr_firth", "rr_cov", "p", "q", "q_keep_all"]].round(3).to_string(index=False))
