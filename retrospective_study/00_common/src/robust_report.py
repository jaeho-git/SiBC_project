# -*- coding: utf-8 -*-
"""Tables, figures and a JSON summary of the post hoc robustness analyses (robust1.py, robust2.py, robust3.py).

Run from retrospective_study/:  python3 00_common/src/robust_report.py 01|02|03
Writes robust_0X.xlsx, robust_0X_summary.json and figS_multiverse.png to the study's 01_Results/analysis/ (git-ignored).
Every specification is reported; nothing is selected by its result.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "00_common/src"))
import figstyle as FS  # noqa: E402
import multiverse as MV  # noqa: E402
import statlib as S  # noqa: E402

FS.use()
import matplotlib.pyplot as plt  # noqa: E402

STUDY = sys.argv[1]
DIRS = {"01": "01_wearable_metrics", "02": "02_checkup_metrics", "03": "03_irs_risk_rank"}
OUT = ROOT / DIRS[STUDY] / "01_Results/analysis"
R = pd.read_pickle(OUT / f"robust_{STUDY}.pkl")


def part(key):
	return [b[key] if isinstance(b, dict) and key in b else {"error": 1} for b in R["boot"]]


def ci_dict(point, boots):
	"""Percentile CI for every key of a point dictionary (900 valid replicates required)."""
	rows = {}
	good = [b for b in boots if "error" not in b]
	for k, v in point.items():
		x = np.array([b.get(k, np.nan) for b in good], float); x = x[np.isfinite(x)]
		ok = bool(np.isfinite(v) and len(x) >= MV.MIN_VALID)
		rows[k] = dict(est=v, lo=np.percentile(x, 2.5) if ok else np.nan, hi=np.percentile(x, 97.5) if ok else np.nan,
		               se=np.std(x, ddof=1) if ok else np.nan, valid=len(x))
	return rows


def r(x, d=3):
	return None if x is None or not np.isfinite(x) else round(float(x), d)


def save(fig, name):
	fig.savefig(OUT / name, facecolor="white"); plt.close(fig); print("wrote", name)


SUMMARY = {}

# ======================================================================= study 01
if STUDY == "01":
	sys.path.insert(0, str(ROOT / "01_wearable_metrics/src"))
	ORDER = ["steps", "active_min", "weight", "fat_pct", "muscle", "sbp", "dbp", "sleep_min", "spo2", "grip"]
	INFER = ORDER[:-1]
	LAB = {"steps": "Steps/day", "active_min": "Exercise min/wear day", "weight": "Weight, kg", "fat_pct": "Body fat, %", "muscle": "Skeletal muscle, kg",
	       "sbp": "Systolic BP, mm Hg", "dbp": "Diastolic BP, mm Hg", "sleep_min": "Sleep min/day", "spo2": "SpO2, %", "grip": "Grip, kg"}
	tab = MV.ci_table(R["point"], part("mv"), R["factors"])
	tab["P"] = [S.wald_p(e, s) for e, s in zip(tab.est, tab.se)]
	perms = R["perm"]
	# reproduction of the main bootstrap intervals by the primary specification
	EB = pd.read_pickle(OUT / "est_boot.pkl"); chk = []
	for k in ORDER:
		v = np.array([b["main"][k]["diff"] for b in EB if "error" not in b and b["main"][k].get("tested") and b["main"][k].get("conv")], float)
		t = tab[(tab.indicator == k) & (tab.exposure == "login") & (tab.contrast == "median") & (tab.estimator == "dr") & (tab["sample"] == "all")].iloc[0]
		lo, hi = (np.percentile(v, 2.5), np.percentile(v, 97.5)) if len(v) >= 900 else (np.nan, np.nan)
		chk.append(dict(indicator=k, main_lo=lo, main_hi=hi, spec_lo=t.lo, spec_hi=t.hi, same=bool((np.isnan(lo) and np.isnan(t.lo)) or (abs(lo - t.lo) < 1e-9 and abs(hi - t.hi) < 1e-9))))
	CHK = pd.DataFrame(chk)
	if not CHK.same.all():
		raise SystemExit("primary specification intervals differ from the main analysis:\n" + CHK.to_string())
	curves = []
	for k in ORDER:
		sp = [s for s in R["specs"] if s[0] == k]
		c = MV.curve_summary(tab, part("mv"), sp); c.update({f"perm_{x}": y for x, y in MV.perm_test(tab, perms, sp).items()}); c["indicator"] = k
		curves.append(c)
		for e in ["login", "login_s1", "action"]:
			sp2 = [s for s in sp if s[1] == e]
			c2 = MV.curve_summary(tab, part("mv"), sp2); c2.update(indicator=k, exposure=e); curves.append(c2)
	sp_all = [s for s in R["specs"] if s[0] in INFER]
	overall = MV.perm_test(tab, perms, sp_all)
	CUR = pd.DataFrame(curves)
	rep = tab[tab.reported & tab.indicator.isin(INFER)]
	FAC = []
	for f in ["exposure", "contrast", "estimator", "sample"]:
		for lev, g in rep.groupby(f):
			FAC.append(dict(factor=f, level=lev, specs=len(g), ci_above_0=int((g.lo > 0).sum()), ci_below_0=int((g.hi < 0).sum())))
	FAC = pd.DataFrame(FAC)
	# observability
	O = ci_dict(R["obs"], part("obs"))
	ob = []
	for k in ORDER:
		for e in ["login", "login_s1", "action"]:
			for ct in ["median", "continuous"]:
				g = lambda s: O[(k, e, ct, s)]
				ob.append(dict(indicator=k, exposure=e, contrast=ct, p_high=g("p1")["est"], p_low=g("p0")["est"], rd=g("rd")["est"], rd_lo=g("rd")["lo"], rd_hi=g("rd")["hi"],
				               rr=g("rr")["est"], rr_lo=g("rr")["lo"], rr_hi=g("rr")["hi"], P=S.wald_p(g("rd")["est"], g("rd")["se"])))
	OB = pd.DataFrame(ob)
	OB["q"] = np.nan
	for (e, ct), g in OB.groupby(["exposure", "contrast"]):
		OB.loc[g.index, "q"] = S.bh(g.P.values)
	# added after the adjusted results were seen (change log): unadjusted shares with bootstrap CIs, because the selection
	# argument of the manuscript rests on the unadjusted contrast between the analysed groups; same resamples as ana1.py
	_argv = sys.argv; sys.argv = [sys.argv[0]]
	import robust1 as R1  # noqa: E402
	sys.argv = _argv
	def crude(cnt):
		o = {}
		for k in ORDER:
			for e in R1.EXPOS:
				a_, _ = R1.group(R1.EXPO0[:, R1.EXPOS.index(e)], e, "median"); y = R1.HAS[k]
				p1 = np.sum(cnt * y * (a_ == 1)) / np.sum(cnt * (a_ == 1)); p0 = np.sum(cnt * y * (a_ == 0)) / np.sum(cnt * (a_ == 0))
				o[(k, e, "p1")], o[(k, e, "p0")], o[(k, e, "rd")] = p1, p0, p1 - p0
				o[(k, e, "rr")] = p1 / p0 if p0 > 0 else np.nan
		return o
	CR0 = crude(np.ones(R1.NU))
	CRB = [crude(np.bincount(np.random.default_rng(71000 + i).integers(0, R1.NU, R1.NU), minlength=R1.NU).astype(float)) for i in range(len(R["boot"]))]
	CRC = ci_dict(CR0, CRB)
	OBC = pd.DataFrame([dict(indicator=k, exposure=e, p_high=CRC[(k, e, "p1")]["est"], p_low=CRC[(k, e, "p0")]["est"], rd=CRC[(k, e, "rd")]["est"],
	                         rd_lo=CRC[(k, e, "rd")]["lo"], rd_hi=CRC[(k, e, "rd")]["hi"], rr=CRC[(k, e, "rr")]["est"], rr_lo=CRC[(k, e, "rr")]["lo"], rr_hi=CRC[(k, e, "rr")]["hi"],
	                         P=S.wald_p(CRC[(k, e, "rd")]["est"], CRC[(k, e, "rd")]["se"])) for k in ORDER for e in R1.EXPOS])
	OBC["q"] = np.nan
	for e, g in OBC.groupby("exposure"):
		OBC.loc[g.index, "q"] = S.bh(g.P.values)
	# gap rule
	GT = R["gaptab"]
	G = ci_dict(R["gap"], part("gap"))
	GE = pd.DataFrame([dict(gap_set=k, gap_days=R["gapsets"][k][0], settings=len(R["gapsets"][k][1]), settings_list="; ".join(f"{a}/{b}/{c}" for a, b, c in R["gapsets"][k][1]),
	                        est=v["est"], lo=v["lo"], hi=v["hi"], valid=v["valid"]) for k, v in G.items()]).sort_values("gap_days")
	with pd.ExcelWriter(OUT / "robust_01.xlsx") as xw:
		tab.drop(columns="spec").to_excel(xw, sheet_name="R_specs", index=False)
		CUR.to_excel(xw, sheet_name="R_curves", index=False)
		pd.DataFrame([overall]).to_excel(xw, sheet_name="R_joint_test", index=False)
		FAC.to_excel(xw, sheet_name="R_by_factor", index=False)
		OB.to_excel(xw, sheet_name="R_observability", index=False)
		OBC.to_excel(xw, sheet_name="R_observability_crude", index=False)
		GT.to_excel(xw, sheet_name="R_gap_grid", index=False)
		GE.to_excel(xw, sheet_name="R_gap_effects", index=False)
		CHK.to_excel(xw, sheet_name="R_check", index=False)
	print("wrote robust_01.xlsx")
	main_cur = CUR[CUR.exposure.isna()].set_index("indicator")
	SUMMARY.update(n_specs=len(R["specs"]), n_specs_infer=len(sp_all), reported_infer=int(len(rep)), ci_above=int((rep.lo > 0).sum()), ci_below=int((rep.hi < 0).sum()),
	               joint=overall, by_indicator={k: {x: r(main_cur.loc[k, x]) if isinstance(main_cur.loc[k, x], (float, np.floating)) else main_cur.loc[k, x] for x in
	                                                ["median", "median_lo", "median_hi", "min", "max", "n_reported", "n_pos", "n_neg", "perm_p_count", "perm_p_median"]} for k in ORDER},
	               observability=OB[(OB.exposure == "login") & (OB.contrast == "median")][["indicator", "p_high", "p_low", "rd", "rd_lo", "rd_hi", "rr", "rr_lo", "rr_hi", "q"]].round(4).to_dict("records"),
	               observability_crude=OBC[OBC.exposure == "login"][["indicator", "p_high", "p_low", "rd", "rd_lo", "rd_hi", "rr", "rr_lo", "rr_hi", "q"]].round(4).to_dict("records"),
	               gap=dict(main_gap_days=int(GT[(GT.source == "activity") & (GT.frac == 0.5) & (GT.window == 28) & (GT.min_run == 3)].gap_days.iloc[0]),
	                        activity_settings=int((GT.source == "activity").sum()),
	                        activity_settings_all_main_days=int(((GT.source == "activity") & (GT.main_missed == 0)).sum()),
	                        activity_settings_exact=int(((GT.source == "activity") & (GT.main_missed == 0) & (GT.only_this == 0)).sum()),
	                        other_sources_max_gap_days={s: int(GT[GT.source == s].gap_days.max()) for s in GT.source.unique() if s != "activity"},
	                        exercise_est_range=[r(GE.est.min()), r(GE.est.max())], exercise_ci_include_0=bool(((GE.lo <= 0) & (GE.hi >= 0)).all())))
	# figure: specification curves per indicator
	fig, axes = plt.subplots(3, 3, figsize=(10.2, 8.4))
	col = {"login": FS.INK2, "login_s1": FS.MUTED, "action": FS.S01["high"]}
	for ax, k in zip(axes.flat, INFER):
		t = tab[(tab.indicator == k) & tab.reported].sort_values("est").reset_index(drop=True)
		x = np.arange(len(t))
		FS.hgrid(ax); ax.axhline(0, color=FS.INK2, lw=0.8)
		for e in col:
			m = (t.exposure == e).values
			ax.vlines(x[m], t.lo[m], t.hi[m], color=col[e], lw=0.6, alpha=0.6)
			ax.scatter(x[m], t.est[m], s=9, color=col[e], zorder=3, label={"login": "Login days", "login_s1": "Login days without suspect days", "action": "Feature-use days"}[e])
		pm = ((t.exposure == "login") & (t.contrast == "median") & (t.estimator == "dr") & (t["sample"] == "all")).values
		ax.scatter(x[pm], t.est[pm], s=46, marker="D", facecolor="white", edgecolor=FS.INK, lw=1.1, zorder=4, label="Primary analysis")
		ax.set_title(LAB[k], loc="left", fontsize=8.5); ax.set_xticks([])
		c = main_cur.loc[k]
		ax.text(0.02, 0.97, f"{int(c.n_reported)} specs; CI>0: {int(c.n_pos)}, CI<0: {int(c.n_neg)}\nexploratory permutation summary P={c.perm_p_count:.2f}", transform=ax.transAxes, va="top", fontsize=6.8, color=FS.INK2)
	axes.flat[0].legend(loc="lower right", fontsize=6.2, handletextpad=0.2)
	fig.supxlabel("Specifications ordered by estimate", fontsize=8.5); fig.supylabel("Adjusted difference (high minus low; 75th minus 25th percentile)", fontsize=8.5)
	fig.tight_layout(); save(fig, "figS6_multiverse.png")

# ======================================================================= study 02
if STUDY == "02":
	ITEMS = R["items"]
	tab = MV.ci_table(R["point"], part("mv"), R["factors"])
	tab["P"] = [S.wald_p(e, s) for e, s in zip(tab.est, tab.se)]
	sys.path.insert(0, str(ROOT / "02_checkup_metrics/src"))
	ALT = {"bmi", "sbp", "dbp", "fbg", "tc", "ldl", "tg", "uprot"}
	NUMC = {"bmi", "waist", "sbp", "dbp", "fbg", "tc", "hdl", "ldl", "tg", "hb", "ast", "alt", "ggt", "cr", "gfr"}
	eff = lambda it, c: "alt" if (c == "alt" and it in ALT) else ("cont" if (c == "cont" and it in NUMC) else "cut")
	T = tab.set_index("spec")
	# reproduction of the main intervals by the primary path
	EB = pd.read_pickle(OUT / "est_boot.pkl"); chk = []
	for it in ITEMS:
		v = np.array([b["main"][it]["diff"] for b in EB if "error" not in b and b["main"][it].get("tested") and b["main"][it].get("conv")], float)
		t = T.loc[[(it, "y", eff(it, "cut"), "bb", "full", "all")]].iloc[0]
		lo, hi = (np.percentile(v, 2.5), np.percentile(v, 97.5)) if len(v) >= 900 else (np.nan, np.nan)
		chk.append(dict(item=it, main_lo=lo, main_hi=hi, spec_lo=t.lo, spec_hi=t.hi, same=bool((np.isnan(lo) and np.isnan(t.lo)) or (abs(lo - t.lo) < 1e-9 and abs(hi - t.hi) < 1e-9))))
	CHK = pd.DataFrame(chk)
	if not CHK.same.all():
		raise SystemExit("primary path intervals differ from the main analysis:\n" + CHK.to_string())
	SE = T.se
	pth = []
	PATHSPECS = {p: [(it, p[0], eff(it, p[1])) + p[2:] for it in ITEMS] for p in R["paths"]}
	for p, sp in PATHSPECS.items():
		t = T.loc[sp]; t = t[t.reported]
		q = S.bh(t.P.values)
		pth.append(dict(outcome=p[0], coding=p[1], model=p[2], adjustment=p[3], sample=p[4], tested=len(t), nominal_p05=int((t.P < .05).sum()),
		                min_q=float(np.nanmin(q)) if len(q) else np.nan, n_q05=int(np.sum(q < .05)), min_q_item=t.index[np.nanargmin(q)][0] if len(q) else ""))
	PTH = pd.DataFrame(pth)
	obs_paths_q05 = int((PTH.min_q < .05).sum()); obs_nominal = int((tab.reported & (tab.P < .05)).sum())
	pc, nc = [], []
	for pm in R["perm"]:
		if "error" in pm:
			continue
		cnt = 0
		for p, sp in PATHSPECS.items():
			z = np.array([pm.get(s, np.nan) / SE.get(s, np.nan) if T.loc[[s]].reported.iloc[0] else np.nan for s in sp], float)
			z = z[np.isfinite(z)]
			if len(z) and np.nanmin(S.bh(2 * stats.norm.sf(np.abs(z)))) < .05:
				cnt += 1
		pc.append(cnt)
		zz = np.array([pm.get(s, np.nan) / SE[s] for s in tab.spec[tab.reported]], float)
		nc.append(int(np.sum(np.abs(zz[np.isfinite(zz)]) > 1.96)))
	pc, nc = np.array(pc), np.array(nc)
	JOINT = dict(paths=len(PTH), paths_any_q05=obs_paths_q05, p_paths=(1 + np.sum(pc >= obs_paths_q05)) / (1 + len(pc)), paths_any_q05_perm_mean=float(pc.mean()),
	             specs_reported=int(tab.reported.sum()), specs_nominal_p05=obs_nominal, specs_nominal_perm_mean=float(nc.mean()), specs_nominal_perm_95=float(np.percentile(nc, 95)),
	             p_specs=(1 + np.sum(nc >= obs_nominal)) / (1 + len(nc)), n_perm=len(pc))
	itm = []
	for it in ITEMS:
		t = tab[(tab["item"] == it) & tab.reported]
		row = dict(item=it, specs=len(t), nominal_pos=int(((t.P < .05) & (t.est > 0)).sum()), nominal_neg=int(((t.P < .05) & (t.est < 0)).sum()),
		           min_P=float(t.P.min()) if len(t) else np.nan)
		for c in ["cut", "alt", "cont"]:
			g = t[t.coding == c]
			row[f"median_{c}"] = float(g.est.median()) if len(g) else np.nan
		itm.append(row)
	ITM = pd.DataFrame(itm)
	L = ci_dict(R["link"], part("link"))
	LK = pd.DataFrame([dict(outcome=k[0], model=k[1], kind=k[2], group=k[3], **v) for k, v in L.items()])
	with pd.ExcelWriter(OUT / "robust_02.xlsx") as xw:
		tab.drop(columns="spec").to_excel(xw, sheet_name="R_specs", index=False)
		PTH.to_excel(xw, sheet_name="R_paths", index=False)
		pd.DataFrame([JOINT]).to_excel(xw, sheet_name="R_joint_test", index=False)
		ITM.to_excel(xw, sheet_name="R_items", index=False)
		LK.to_excel(xw, sheet_name="R_linkage", index=False)
		CHK.to_excel(xw, sheet_name="R_check", index=False)
	print("wrote robust_02.xlsx")
	ld = LK[(LK.kind == "diff")]
	SUMMARY.update(joint=JOINT, paths_min_q_range=[r(PTH.min_q.min()), r(PTH.min_q.max())], link_n=R["link_n"],
	               linkage=ld.round(3).to_dict("records"), items=ITM.round(4).to_dict("records"))
	# figure: z of every specification by item
	order = ITM.assign(mz=[np.nanmedian((tab[(tab["item"] == it) & tab.reported].est / tab[(tab["item"] == it) & tab.reported].se).values) if ((tab["item"] == it) & tab.reported).any() else np.nan for it in ITEMS]).dropna(subset=["mz"]).sort_values("mz")
	LABI = {"height": "Height (per SD)", "weight": "Weight (per SD)", "bmi": "BMI", "waist": "Waist", "sbp": "Systolic BP", "dbp": "Diastolic BP", "fbg": "Fasting glucose",
	        "tc": "Total cholesterol", "hdl": "HDL cholesterol", "ldl": "LDL cholesterol", "tg": "Triglycerides", "hb": "Hemoglobin", "ast": "AST", "alt": "ALT", "ggt": "GGT",
	        "cr": "Creatinine", "gfr": "eGFR", "uprot": "Urine protein", "sight": "Visual acuity", "hearing": "Hearing", "chest": "Chest radiograph", "judge": "Overall judgment"}
	fig, ax = plt.subplots(figsize=(7.4, 6.6))
	FS.vgrid(ax)
	rng = np.random.default_rng(2)
	for i, it in enumerate(order["item"]):
		t = tab[(tab["item"] == it) & tab.reported]
		z = (t.est / t.se).values
		ax.scatter(z, i + rng.uniform(-0.28, 0.28, len(z)), s=5, color=FS.S02_ITEM, alpha=0.35, lw=0)
		pr = t[(t.outcome == "y") & (t.coding == eff(it, "cut")) & (t.model == "bb") & (t.adjustment == "full") & (t["sample"] == "all")]
		if len(pr):
			ax.scatter((pr.est / pr.se).values, [i], s=34, marker="D", facecolor="white", edgecolor=FS.INK, lw=1.0, zorder=4)
	for v in (-1.96, 1.96):
		ax.axvline(v, color=FS.MUTED, lw=0.8, ls=(0, (3, 2)))
	ax.axvline(0, color=FS.INK2, lw=0.8)
	ax.set_yticks(range(len(order))); ax.set_yticklabels([LABI.get(x, x) for x in order["item"]])
	ax.set_xlabel("z of the adjusted difference in login days (estimate / bootstrap SE)")
	ax.text(0.01, 0.995, f"{JOINT['specs_reported']} specifications; |z|>1.96: {JOINT['specs_nominal_p05']} (permutation mean {JOINT['specs_nominal_perm_mean']:.0f}, P={JOINT['p_specs']:.2f})\n"
	        f"paths with any q<.05: {JOINT['paths_any_q05']} of {JOINT['paths']} (P={JOINT['p_paths']:.2f}); P: exploratory permutation summary. Diamond: primary analysis",
	        transform=ax.transAxes, ha="left", va="top", fontsize=6.8, color=FS.INK2)
	save(fig, "figS6_multiverse.png")

# ======================================================================= study 03
if STUDY == "03":
	tab = MV.ci_table(R["point"], part("mv"), R["factors"])
	tab["P"] = [S.wald_p(e, s) for e, s in zip(tab.est, tab.se)]
	EB = pd.read_pickle(OUT / "est_boot.pkl")
	v = np.array([b["main"]["diff"] for b in EB if "error" not in b and b["main"].get("conv") and np.isfinite(b["main"]["diff"])], float)
	t0 = tab[tab.spec.apply(lambda s: s == ("login", "median", "dr", "bands5", "all", "iso_shift"))].iloc[0]
	lo, hi = np.percentile(v, 2.5), np.percentile(v, 97.5)
	if not (abs(lo - t0.lo) < 1e-9 and abs(hi - t0.hi) < 1e-9):
		raise SystemExit(f"primary interval differs from the main analysis: {t0.lo},{t0.hi} vs {lo},{hi}")
	CHK = pd.DataFrame([dict(main_lo=lo, main_hi=hi, spec_lo=t0.lo, spec_hi=t0.hi)])
	sp = R["specs"]
	cur = [dict(group="all", **MV.curve_summary(tab, part("mv"), sp), **{f"perm_{x}": y for x, y in MV.perm_test(tab, R["perm"], sp).items()})]
	for f_i, f in enumerate(R["factors"]):
		for lev in sorted({s[f_i] for s in sp}):
			s2 = [s for s in sp if s[f_i] == lev]
			cur.append(dict(group=f"{f}={lev}", **MV.curve_summary(tab, part("mv"), s2)))
	CUR = pd.DataFrame(cur)
	F = ci_dict(R["fr"], part("fr"))
	FR = pd.DataFrame([dict(method=k[0], score=k[1], when=k[2], kind=k[3], **v) for k, v in F.items()])
	Q = ci_dict(R["qba"], part("qba"))
	QB = pd.DataFrame([dict(quantity=k, **v) for k, v in Q.items()])
	# post hoc addition (change log): upward movement as a further outcome, and net movement on a common denominator
	RU = pd.read_pickle(OUT / "robust_03_up.pkl")
	def kind_parts(kind):
		return [b[kind] if isinstance(b, dict) and kind in b else {"error": 1} for b in RU["boot"]], [p[kind] if isinstance(p, dict) and kind in p else {"error": 1} for p in RU["perm"]]
	TABS, CURS = {}, {}
	for kind in ["up", "net"]:
		bk, pk = kind_parts(kind)
		t_ = MV.ci_table(RU["point"][kind], bk, RU["factors"])
		c_ = [dict(group="all", **MV.curve_summary(t_, bk, sp), **{f"perm_{x}": y for x, y in MV.perm_test(t_, pk, sp).items()})]
		for f_i, f in enumerate(RU["factors"]):
			for lev in sorted({s_[f_i] for s_ in sp}):
				c_.append(dict(group=f"{f}={lev}", **MV.curve_summary(t_, bk, [s_ for s_ in sp if s_[f_i] == lev])))
		TABS[kind], CURS[kind] = t_, pd.DataFrame(c_)
	tab_up, tab_net, CUP, CNET = TABS["up"], TABS["net"], CURS["up"], CURS["net"]
	prim = ("login", "median", "dr", "bands5", "all", "iso_shift")
	PRIM = pd.DataFrame([dict(outcome=o, **t[t.spec.apply(lambda s_: s_ == prim)].iloc[0][["est", "lo", "hi", "se"]].to_dict())
	                     for o, t in [("down", tab), ("up", tab_up), ("net", tab_net)]])
	PRIM["P"] = [S.wald_p(e, s_) for e, s_ in zip(PRIM.est, PRIM.se)]
	# scenario-based correction: primary difference minus the expected false-down difference, paired within replicates
	_mv, _qb = part("mv"), part("qba")
	corr0 = R["point"][prim] - R["qba"]["exp_diff"]
	corr_b = np.array([a_[prim] - b_["exp_diff"] for a_, b_ in zip(_mv, _qb) if "error" not in a_ and "error" not in b_], float)
	corr_b = corr_b[np.isfinite(corr_b)]
	QB = pd.concat([QB, pd.DataFrame([dict(quantity="corrected_diff_subtraction", est=corr0, lo=np.percentile(corr_b, 2.5), hi=np.percentile(corr_b, 97.5),
	                                       se=np.std(corr_b, ddof=1), valid=len(corr_b))])], ignore_index=True)
	with pd.ExcelWriter(OUT / "robust_03.xlsx") as xw:
		tab.drop(columns="spec").to_excel(xw, sheet_name="R_specs", index=False)
		CUR.to_excel(xw, sheet_name="R_curves", index=False)
		FR.to_excel(xw, sheet_name="R_false_movement", index=False)
		QB.to_excel(xw, sheet_name="R_bias_analysis", index=False)
		tab_up.drop(columns="spec").to_excel(xw, sheet_name="R_up_specs", index=False)
		CUP.to_excel(xw, sheet_name="R_up_curves", index=False)
		tab_net.drop(columns="spec").to_excel(xw, sheet_name="R_net_specs", index=False)
		CNET.to_excel(xw, sheet_name="R_net_curves", index=False)
		PRIM.to_excel(xw, sheet_name="R_primary_down_up_net", index=False)
		CHK.to_excel(xw, sheet_name="R_check", index=False)
	print("wrote robust_03.xlsx")
	SUMMARY.update(up_curve=CUP.iloc[0].to_dict(), net_curve=CNET.iloc[0].to_dict(), primary_down_up_net=PRIM.round(4).to_dict("records"),
	               up_by_factor=CUP.iloc[1:][["group", "median", "median_lo", "median_hi", "n_pos", "n_neg"]].round(4).to_dict("records"),
	               net_by_factor=CNET.iloc[1:][["group", "median", "median_lo", "median_hi", "n_pos", "n_neg"]].round(4).to_dict("records"))
	# figure S7: downward against upward difference for every specification
	m = pd.DataFrame({"down": tab.set_index("spec").est, "up": tab_up.set_index("spec").est}).dropna()
	fig, ax = plt.subplots(figsize=(5.6, 5.0))
	FS.hgrid(ax); FS.vgrid(ax)
	lim = [min(m.min().min(), 0) * 100 - 1, m.max().max() * 100 + 1]
	ax.plot(lim, lim, color=FS.MUTED, lw=0.8, ls=(0, (3, 2)))
	ax.axhline(0, color=FS.INK2, lw=0.8); ax.axvline(0, color=FS.INK2, lw=0.8)
	ax.scatter(100 * m.down, 100 * m.up, s=6, color=FS.S03["high"], alpha=0.45, lw=0)
	pm_ = m.loc[[prim]]
	ax.scatter(100 * pm_.down, 100 * pm_.up, s=50, marker="D", facecolor="white", edgecolor=FS.INK, lw=1.1, zorder=4, label="Primary analysis")
	ax.set_xlim(lim); ax.set_ylim(lim)
	ax.set_xlabel("Difference in the proportion moving down, percentage points"); ax.set_ylabel("Difference in the proportion moving up, percentage points")
	cn = CNET.iloc[0]
	ax.text(0.02, 0.98, f"{len(m)} specifications; dashed line: equal differences\nnet movement (all evaluated diseases): median {100 * cn['median']:.1f} pp (95% CI {100 * cn['median_lo']:.1f} to {100 * cn['median_hi']:.1f})",
	        transform=ax.transAxes, va="top", fontsize=6.8, color=FS.INK2)
	ax.legend(loc="lower right", fontsize=7)
	save(fig, "figS7_down_vs_up.png")
	c0 = CUR.iloc[0]
	SUMMARY.update(curve={k: r(c0[k], 4) if isinstance(c0[k], (float, np.floating)) else (int(c0[k]) if isinstance(c0[k], (int, np.integer)) else c0[k]) for k in c0.index if k != "group"},
	               by_factor=CUR.iloc[1:][["group", "n_reported", "median", "median_lo", "median_hi", "n_pos", "n_neg"]].round(4).to_dict("records"),
	               false_movement=FR.round(3).to_dict("records"), qba=QB.round(4).to_dict("records"))
	# figure: specification curve with the factor matrix
	t = tab[tab.reported].sort_values("est").reset_index(drop=True)
	x = np.arange(len(t))
	fig, (ax, axm) = plt.subplots(2, 1, figsize=(10.4, 7.2), gridspec_kw={"height_ratios": [1.5, 1.6], "hspace": 0.06}, sharex=True)
	FS.hgrid(ax); ax.axhline(0, color=FS.INK2, lw=0.8)
	sig = (t.lo > 0) | (t.hi < 0)
	sig = sig.values
	ax.vlines(x, 100 * t.lo.values, 100 * t.hi.values, color=FS.NEUTRAL, lw=0.3, alpha=0.6, zorder=1)
	ax.scatter(x[~sig], 100 * t.est.values[~sig], s=7, color=FS.S03["high"], lw=0, zorder=3, label="95% CI includes 0")
	ax.scatter(x[sig], 100 * t.est.values[sig], s=7, color=FS.S03["low"], lw=0, zorder=3, label="95% CI excludes 0")
	pm = t.spec.apply(lambda s: s == ("login", "median", "dr", "bands5", "all", "iso_shift")).values
	ax.scatter(x[pm], 100 * t.est[pm], s=50, marker="D", facecolor="white", edgecolor=FS.INK, lw=1.1, zorder=4, label="Primary analysis")
	ax.set_ylabel("Difference in proportion moving down, pp"); ax.legend(loc="upper left", fontsize=7)
	ax.text(0.99, 0.03, f"{len(t)} specifications; CI excludes 0: {int(sig.sum())}; exploratory permutation summary P={c0.perm_p_count:.2f} (count), {c0.perm_p_median:.2f} (median)", transform=ax.transAxes, ha="right", fontsize=7, color=FS.INK2)
	rows, labels = [], []
	LEV = {"exposure": ["login", "login_s1", "action"], "contrast": ["median", "tertile", "continuous"], "estimator": ["dr", "reg", "ipw", "ow"],
	       "outcome": ["bands5", "bands3", "bands10", "shift10", "incl_lowest"], "diseases": ["all", "pass18"], "crosswalk": ["iso_shift", "iso_clip", "linear", "equip"]}
	NAME = {"login": "Login days", "login_s1": "Login, no suspect days", "action": "Feature-use days", "median": "Median split", "tertile": "Top vs bottom third",
	        "continuous": "Continuous", "dr": "IPTW + outcome model", "reg": "Outcome model", "ipw": "IPTW only", "ow": "Overlap weights", "bands5": "5 bands",
	        "bands3": "3 bands", "bands10": "10 bands", "shift10": "Boundaries +10", "incl_lowest": "Lowest band included", "all": "All diseases", "pass18": "18 diseases",
	        "iso_shift": "Isotonic, shift", "iso_clip": "Isotonic, clip", "linear": "Linear", "equip": "Equipercentile"}
	yy = 0
	for f in R["factors"]:
		for lev in LEV[f]:
			m = (t[f] == lev).values
			axm.scatter(x[m], np.full(m.sum(), yy), s=2.5, marker="|", color=FS.INK2, lw=0.6)
			labels.append(NAME[lev]); yy -= 1
		yy -= 0.6
	ypos = []; yy = 0
	for f in R["factors"]:
		for lev in LEV[f]:
			ypos.append(yy); yy -= 1
		yy -= 0.6
	axm.set_yticks(ypos); axm.set_yticklabels(labels, fontsize=6.5); axm.set_xticks([]); axm.spines["bottom"].set_visible(False)
	axm.set_xlabel("Specifications ordered by estimate")
	save(fig, "figS6_multiverse.png")

json.dump(SUMMARY, open(OUT / f"robust_{STUDY}_summary.json", "w"), ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
print("wrote", f"robust_{STUDY}_summary.json")
