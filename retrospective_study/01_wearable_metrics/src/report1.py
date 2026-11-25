# -*- coding: utf-8 -*-
"""Study 01 report: tables (xlsx), figures (PNG <= 1200 px, English labels) and a JSON summary from ana1.py outputs.

Run from retrospective_study/ after ana1.py:  python3 01_wearable_metrics/src/report1.py
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
sys.path.insert(0, str(ROOT / "01_wearable_metrics/src")); sys.path.insert(0, str(ROOT / "00_common/src"))
import ana1 as A1  # noqa: E402
import statlib as S  # noqa: E402

OUT = A1.OUT
E = pd.read_pickle(OUT / "est_point.pkl")
B = [b for b in pd.read_pickle(OUT / "est_boot.pkl") if "error" not in b]
U = A1.U
C_HI, C_LO = "#0072B2", "#D55E00"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
EN = {"steps": "Steps per day", "active_min": "Exercise minutes per wear day", "weight": "Weight, kg", "fat_pct": "Body fat, %",
      "muscle": "Skeletal muscle mass, kg", "sbp": "Systolic BP, mmHg", "dbp": "Diastolic BP, mmHg", "sleep_min": "Sleep, minutes per night",
      "spo2": "SpO2, %", "grip": "Grip strength, kg"}
KO = {"steps": "걸음(보/일)", "active_min": "운동(분/착용일)", "weight": "체중(kg)", "fat_pct": "체지방률(%)", "muscle": "골격근량(kg)",
      "sbp": "수축기 혈압(mmHg)", "dbp": "이완기 혈압(mmHg)", "sleep_min": "수면(분/일)", "spo2": "산소포화도(%)", "grip": "악력(kg)"}
FIG = {}
SHORT = {"steps": "Steps/day", "active_min": "Exercise min/wear day", "weight": "Weight, kg", "fat_pct": "Body fat, %", "muscle": "Muscle mass, kg",
         "sbp": "Systolic BP, mmHg", "dbp": "Diastolic BP, mmHg", "sleep_min": "Sleep, min/night", "spo2": "SpO2, %", "grip": "Grip, kg"}
DIR = {"steps": "\u2191", "active_min": "\u2191", "weight": "\u00b1", "fat_pct": "\u00b1", "muscle": "\u2191", "sbp": "\u00b1", "dbp": "\u00b1",
       "sleep_min": "\u00b1", "spo2": "\u2191", "grip": "\u2191"}


def savefig(fig, name):
	fig.savefig(OUT / name, dpi=150); plt.close(fig); FIG[name] = str(OUT / name)


def bstat(block, k, field="diff"):
	v = np.array([b[block][k].get(field, np.nan) for b in B if k in b.get(block, {}) and b[block][k].get("tested") and b[block][k].get("conv", False)], float)
	v = v[np.isfinite(v)]
	if len(v) < 900:
		return np.nan, np.nan, np.nan, len(v)
	return np.percentile(v, 2.5), np.percentile(v, 97.5), np.std(v, ddof=1), len(v)


def outcome_sd(k):
	if k in A1.DAILY:
		keep, _, rows = A1.daily_data(A1.X, A1.USERS, k)
		return rows.groupby("user_id").y.mean().std(ddof=1)
	p, pfx, col = A1.point_data(A1.P, A1.USERS, k)
	return p[pfx + col].astype(float).std(ddof=1)


def table(block, keys):
	rows = []
	for k in keys:
		r = E[block].get(k, {})
		row = dict(indicator=k, label_ko=KO[k], label_en=EN[k], n=r.get("n"), n_high=r.get("n1"), n_low=r.get("n0"), tested=bool(r.get("tested") and r.get("conv", False)),
		           base_high=r.get("base1"), base_low=r.get("base0"), out_high=r.get("out1"), out_low=r.get("out0"), diff=r.get("diff", np.nan), std=r.get("std", np.nan))
		if row["tested"]:
			lo, hi, se, nb = bstat(block, k); slo, shi, _, _ = bstat(block, k, "std")
			row.update(lo=lo, hi=hi, std_lo=slo, std_hi=shi, p=S.wald_p(row["diff"], se), boot_valid=nb)
			if nb < 900:
				row["not_reported"] = "fewer than 900 valid resamples"
		else:
			row["not_reported"] = "minimum n not met" if not r.get("tested") else "original-data fit did not converge"
		rows.append(row)
	t = pd.DataFrame(rows)
	for c in ["lo", "hi", "std_lo", "std_hi", "p", "boot_valid"]:
		if c not in t:
			t[c] = np.nan
	m = t.tested & t.p.notna(); t["q"] = np.nan; t.loc[m, "q"] = S.bh(t.loc[m, "p"].values)
	t["q_keep_all"] = S.bh(np.where(m, t.p, 1.0))  # conservative: indicators without a valid P kept in the family with P = 1
	t["n_bh"] = int(m.sum())
	return t


MAIN = table("main", A1.ORDER)
for i, r in MAIN.iterrows():
	if r.tested:
		sd = outcome_sd(r.indicator); d = r["diff"] / sd
		rr = np.exp(0.91 * abs(d)); MAIN.loc[i, "evalue"] = S.evalue_rr(rr)[0]
		if not np.isfinite(r.lo):  # no CI -> no CI-based E-value
			MAIN.loc[i, "evalue_ci"] = np.nan; continue
		lo_d = min(abs(r.lo), abs(r.hi)) / sd if np.sign(r.lo) == np.sign(r.hi) else 0
		MAIN.loc[i, "evalue_ci"] = S.evalue_rr(np.exp(0.91 * lo_d))[0] if lo_d > 0 else 1.0
SENS = {"equal_users": table("equal_users", list(A1.DAILY)), "no_trunc": table("no_trunc", A1.ORDER), "unadjusted": table("unadjusted", A1.ORDER),
        "susp1": table("susp1", A1.ORDER), "susp2": table("susp2", A1.ORDER), "week12": table("week12", list(A1.DAILY)),
        "base2_13": table("base2_13", list(A1.DAILY)), "zero_steps": table("zero_steps", ["steps"]), "extended": table("extended", list(A1.POINT)),
        "t0_le56": table("t0_le56", A1.ORDER), "act_gap_zero": table("act_gap_zero", ["active_min"]), "no_plat1102": table("no_plat1102", A1.ORDER),
        "act_calendar": table("act_calendar", ["active_min"]), "plausible": table("plausible", list(A1.DAILY))}
DOSE = []
for k in A1.ORDER:
	r = E["dose"].get(k, {})
	row = dict(indicator=k, n=r.get("n"), tested=bool(r.get("tested") and r.get("conv", False)), diff=r.get("diff", np.nan))
	if row["tested"]:
		okb = [b for b in B if b["dose"][k].get("tested") and b["dose"][k].get("conv", False)]
		d = np.array([b["dose"][k]["diff"] for b in okb]); nl = np.array([b["dose"][k]["nonlin"] for b in okb])
		if len(d) >= 900:
			row.update(lo=np.percentile(d, 2.5), hi=np.percentile(d, 97.5), p=S.wald_p(row["diff"], np.std(d, ddof=1)),
			           p_nonlin=S.wald_p(r["nonlin"], np.std(nl, ddof=1)), boot_valid=len(d))
	DOSE.append(row)
DOSE = pd.DataFrame(DOSE)
STRATA = []
for key, r in E["strata"].items():
	k, lab = key.split("|")
	row = dict(indicator=k, stratum=lab, n=r.get("n"), n_high=r.get("n1"), n_low=r.get("n0"), tested=bool(r.get("tested") and r.get("conv", False)), diff=r.get("diff", np.nan))
	if row["tested"]:
		v = np.array([b["strata"][key].get("diff", np.nan) for b in B if b["strata"][key].get("tested") and b["strata"][key].get("conv", False)]); v = v[np.isfinite(v)]
		row["boot_valid"] = len(v)
		if len(v) >= 900:
			row.update(lo=np.percentile(v, 2.5), hi=np.percentile(v, 97.5))
		else:
			row["not_reported"] = "fewer than 900 valid resamples"
	else:
		row["not_reported"] = "minimum n not met" if not r.get("tested") else "original-data fit did not converge"
	STRATA.append(row)
STRATA = pd.DataFrame(STRATA)
WEAR = pd.DataFrame([dict(cohort_baseline_watch_wear_days=md, indicator=k, n=E["wear"][md][k].get("n"), diff=E["wear"][md][k].get("diff", np.nan), tested=E["wear"][md][k].get("tested"),
                          note="cohort selection threshold changed; per-indicator valid-day rule (>=4 days in each window) unchanged; point estimate only")
                     for md in E["wear"] for k in A1.ORDER])

# ---------------------------------------------------------------- Table 1 and balance
w, _ps_ok = A1.ps_fit(U, A1.A, np.ones(len(U)))
hi = A1.A == 1
T1V = [("Age, years", "age", "mean"), ("Female", "female", "pct"), ("Registered outside the most common quarter", "q_other", "pct"),
       ("Days from registration to time 0", "t0_days", "med"), ("Login days before time 0", "pre_login", "med"),
       ("Platform 20301105 (watch)", "plat1105", "pct"), ("Platform 20301102", "plat1102", "pct"), ("Baseline wear days (of 14)", "base_wear", "med"),
       ("Login days in the 28-day exposure window", "exp", "med")]
t1 = []
for lab, v, kind in T1V:
	x = U[v].astype(float)
	def fmt(s):
		if kind == "mean":
			return f"{s.mean():.1f} ({s.std(ddof=1):.1f})"
		if kind == "pct":
			return f"{int(s.sum())} ({100 * s.mean():.1f})"
		return f"{s.median():.0f} ({s.quantile(.25):.0f}-{s.quantile(.75):.0f})"
	row = dict(variable=lab, overall=fmt(x), high=fmt(x[hi]), low=fmt(x[~hi]))
	if v != "exp":
		row["smd_before"] = S.smd(x.values, hi); row["smd_after"] = S.smd(x.values, hi, w)
	t1.append(row)
T1 = pd.DataFrame(t1)
BAL = dict(ess_high=S.ess(w[hi]), ess_low=S.ess(w[~hi]), w_min=float(w.min()), w_max=float(w.max()),
           max_abs_smd_after=float(np.nanmax(np.abs(T1.smd_after))))

# balance in each indicator's analysis set (weights re-estimated there, as in the analysis)
IBAL = []
for k in A1.ORDER:
	if k in A1.DAILY:
		keep, _, _ = A1.daily_data(A1.X, A1.USERS, k)
	else:
		pp, _, _ = A1.point_data(A1.P, A1.USERS, k); keep = [u for u in A1.USERS if u in pp.index]
	ix = np.array([A1.USERS.index(u) for u in keep]); aa = A1.A[ix]; ww, ok_ = A1.ps_fit(U.iloc[ix], aa, np.ones(len(ix)))
	sm = {v: S.smd(U.iloc[ix][v].values.astype(float), aa == 1, ww) for v in A1.PSV}
	worst = max(sm, key=lambda v: abs(sm[v]))
	IBAL.append(dict(indicator=k, n=len(ix), n_high=int(aa.sum()), max_abs_smd=abs(sm[worst]), worst_variable=worst, ess_high=S.ess(ww[aa == 1]),
	                 ess_low=S.ess(ww[aa == 0]), w_min=float(ww.min()), w_max=float(ww.max()), plat1102_high=int(((U.iloc[ix].plat1102 == 1) & (aa == 1)).sum()),
	                 plat1102_low=int(((U.iloc[ix].plat1102 == 1) & (aa == 0)).sum()), ps_converged=ok_))
IBAL = pd.DataFrame(IBAL)

# activity-session collection gap: daily table and excluded wear days per group
GAP_T = A1.source_gap_table("activity.csv")
_g0 = min(A1.ACT_GAP); GAP_LEN = len(A1.ACT_GAP)
_cand = GAP_T.flag.values
GAP_OUT = pd.DataFrame({"day_rel": (GAP_T.index - _g0).days, "users_with_session_record": GAP_T.num.values, "users_with_step_record": GAP_T.den.values,
                        "ratio": GAP_T.ratio.values, "threshold": GAP_T.threshold.values, "below_threshold": _cand, "in_gap": GAP_T.index.isin(A1.ACT_GAP)})  # no calendar dates
_Xg = A1.X[A1.X.user_id.isin(A1.USERS)].copy(); _Xg = _Xg[_Xg["착용일"].astype(str).isin(["예", "True"])]
_Xg["gap"] = pd.to_datetime(_Xg["날짜"]).isin(A1.ACT_GAP); _Xg["grp"] = _Xg.user_id.map(dict(zip(A1.USERS, A1.A)))
GAP_N = _Xg[_Xg["구간"].isin(["기준선", "결과"])].groupby(["구간", "grp"]).agg(wear_days=("gap", "size"), gap_days=("gap", "sum"),
                                                                         users_with_gap=("user_id", lambda u: _Xg.loc[u.index][_Xg.loc[u.index].gap].user_id.nunique())).reset_index()
GAP_N["구간"] = GAP_N["구간"].map({"기준선": "baseline", "결과": "outcome"}); GAP_N["grp"] = GAP_N.grp.map({1.0: "high", 0.0: "low"})
# share of wear days with a session record among the analysed users, 8 weeks before and after the gap (pooled)
_Xg["sess"] = _Xg["활동_세션수"].notna(); _dd = pd.to_datetime(_Xg["날짜"]); _g1 = max(A1.ACT_GAP)
SESS = []
for lab, a_, b_ in [("8 weeks before the gap (days -56 to -1)", _g0 - pd.Timedelta(days=56), _g0 - pd.Timedelta(days=1)),
                    (f"8 weeks after the gap (days {GAP_LEN} to {GAP_LEN + 55})", _g1 + pd.Timedelta(days=1), _g1 + pd.Timedelta(days=56))]:
	m = (_dd >= a_) & (_dd <= b_)
	SESS.append(dict(period=lab, users=int(_Xg[m].user_id.nunique()), wear_days=int(m.sum()), wear_days_with_session=int(_Xg[m].sess.sum()), share=float(_Xg[m].sess.mean())))
SESS = pd.DataFrame(SESS)

# ---------------------------------------------------------------- figures
# flow counts from the full candidate list (same builder as the analysis set), not typed in
_days = A1.BA.B.load(A1._A, A1.C, A1.END)
_ST = A1.BA.B.build(A1.C, _days, A1.END, A1._A.min_days)["대상자_상태"].value_counts()
FLOW = {"common": len(A1.C), "no_t0": int(_ST.get("시간 0 없음", 0)), "collecting": int(_ST.get("기준선 수집 중", 0)), "low_wear": int(_ST.get("기준선 착용 부족", 0)),
        "pending": int(_ST.get("대상자, 추적 대기", 0)), "analysed": len(U)}
if FLOW["common"] - FLOW["no_t0"] - FLOW["collecting"] - FLOW["low_wear"] - FLOW["pending"] != FLOW["analysed"]:
	raise SystemExit(f"flow counts do not add up: {FLOW}")


def fig_flow():
	fig = plt.figure(figsize=(8, 8))
	axa = fig.add_axes([0.03, 0.78, 0.94, 0.2]); axb = fig.add_axes([0.03, 0.02, 0.94, 0.74])
	axa.set_xlim(0, 100); axa.set_ylim(0, 10); axa.axis("off"); axa.text(0, 9.3, "A", fontsize=13, fontweight="bold")
	for a_, b_, t_, c_ in [(2, 24, "Baseline\nfirst 14 days of\nwearable records", "#E8E8E8"), (28, 58, "Exposure\nlogin days in 28 days\n(from the later of baseline\nend or registration)", "#CFE3F2"),
	                       (62, 98, "Outcome\nnext 28 days: daily indicators;\nfirst measurement in the window", "#E8E8E8")]:
		axa.add_patch(FancyBboxPatch((a_, 3.0), b_ - a_, 5.4, boxstyle="round,pad=0.3", fc=c_, ec="#555555"))
		axa.text((a_ + b_) / 2, 5.7, t_, ha="center", va="center", fontsize=7.5)
	axa.annotate("", xy=(99, 1.6), xytext=(1, 1.6), arrowprops=dict(arrowstyle="->", color="#333333"))
	axa.text(1, 0.0, "Time 0: first step record", fontsize=7.5)
	axb.set_xlim(0, 100); axb.set_ylim(0, 100); axb.axis("off"); axb.text(0, 97, "B", fontsize=13, fontweight="bold")
	main = [f"Common cohort (n={FLOW['common']})", f"Time 0 within range (n={FLOW['common'] - FLOW['no_t0']})",
	        f"Eligible: >=4 watch-wear days at baseline (n={FLOW['common'] - FLOW['no_t0'] - FLOW['collecting'] - FLOW['low_wear']})",
	        f"Analysed: outcome window closed (n={FLOW['analysed']})"]
	exc = [f"No step record from 30 days before registration, {FLOW['no_t0']}",
	       f"Baseline still being collected, {FLOW['collecting']}\nFewer than 4 watch-wear days at baseline, {FLOW['low_wear']}",
	       f"Outcome window not yet closed, {FLOW['pending']}\n(kept for independent confirmation)"]
	ys = [88, 64, 40, 16]
	for i, (txt, y) in enumerate(zip(main, ys)):
		axb.add_patch(FancyBboxPatch((2, y - 4.5), 50, 9, boxstyle="round,pad=0.6", fc="white", ec="#333333")); axb.text(27, y, txt, ha="center", va="center", fontsize=8)
		if i < len(ys) - 1:
			axb.annotate("", xy=(27, ys[i + 1] + 5.2), xytext=(27, y - 5.2), arrowprops=dict(arrowstyle="->", color="#333333"))
			ym = (y + ys[i + 1]) / 2
			axb.add_patch(FancyBboxPatch((58, ym - 5.5), 40, 11, boxstyle="round,pad=0.6", fc="#F5F5F5", ec="#888888")); axb.text(78, ym, exc[i], ha="center", va="center", fontsize=7)
			axb.annotate("", xy=(57.4, ym), xytext=(27, ym), arrowprops=dict(arrowstyle="->", color="#888888"))
	n = MAIN.set_index("indicator").n
	FL = {"steps": "steps", "active_min": "exercise minutes", "weight": "weight", "fat_pct": "body fat", "muscle": "skeletal muscle mass",
	      "sbp": "systolic BP", "dbp": "diastolic BP", "sleep_min": "sleep", "spo2": "SpO2", "grip": "grip strength"}
	lab = [f"{FL[k]} {int(n[k])}" for k in A1.ORDER]
	axb.text(2, 5, "Analysable: " + ", ".join(lab[:5]) + ",", fontsize=7)
	axb.text(2, 2, "  " + ", ".join(lab[5:]), fontsize=7)
	axb.text(2, -1.5, f"High engagement (>= median {A1.MED:.0f} login days) {int(A1.A.sum())}, low {int((1 - A1.A).sum())}", fontsize=7)
	savefig(fig, "fig2_timeline_flow.png")


def fig_weekly():
	X = A1.X[A1.X.user_id.isin(A1.USERS)].copy()
	X["grp"] = X.user_id.map(dict(zip(A1.USERS, A1.A)))
	off = {"기준선": 0, "노출": 2, "결과": 6}
	fig, axes = plt.subplots(2, 2, figsize=(8, 6)); axes = axes.ravel()
	for ax, k in zip(axes, A1.DAILY):
		v = A1.valid_rows(X, k).copy(); col = A1.DAILY[k][0]
		v = v[v["구간"].isin(off)]
		start = {"기준선": 0, "노출": "노출시작후일", "결과": "노출시작후일"}
		v["wk"] = np.where(v["구간"] == "기준선", v["시간0후일"] // 7, np.where(v["구간"] == "노출", v["노출시작후일"] // 7 + 2, (v["노출시작후일"] - 28) // 7 + 6))
		um = v.groupby(["user_id", "wk", "grp"])[col].mean().reset_index()
		for g, c_, ls, mk, lab in [(1, C_HI, "-", "o", "High"), (0, C_LO, "--", "s", "Low")]:
			s = um[um.grp == g].groupby("wk")[col].agg(["mean", "std", "size"])
			se = s["std"] / np.sqrt(s["size"])
			for seg in [(0, 1), (2, 5), (6, 9)]:
				ss = s.loc[(s.index >= seg[0]) & (s.index <= seg[1])]; e = se.loc[ss.index]
				ax.errorbar(ss.index, ss["mean"], yerr=1.96 * e, color=c_, ls=ls, marker=mk, ms=3, capsize=2, lw=1, label=lab if seg[0] == 0 else None)
		for xb in [1.5, 5.5]:
			ax.axvline(xb, color="#BBBBBB", lw=0.8, ls=":")
		nwk = um.groupby("wk").user_id.nunique()
		for wk_, nn in nwk.items():
			ax.text(wk_, 0.015, str(nn), transform=ax.get_xaxis_transform(), fontsize=5.8, ha="center", color="#666666")
		ax.set_xticks(range(10)); ax.set_xticklabels(["B1", "B2", "E1", "E2", "E3", "E4", "O1", "O2", "O3", "O4"], fontsize=7)
		ax.set_title(EN[k], fontsize=8.5, loc="left")
	axes[0].legend(frameon=False, fontsize=7)
	fig.text(0.01, 0.028, "B: baseline week, E: exposure week, O: outcome week. Unadjusted user-level weekly means with 95% CI; grey numbers: users per week. Lines are broken",
	         fontsize=6.8)
	fig.text(0.01, 0.006, "between windows because the gap between baseline and exposure varies. Exercise minutes: days in a cohort-wide collection gap are left out.",
	         fontsize=6.8)
	fig.tight_layout(rect=(0, 0.05, 1, 1)); savefig(fig, "fig3_weekly.png")


def fig_forest():
	t = MAIN.set_index("indicator").reindex(A1.ORDER); yy = np.arange(len(t))[::-1]
	fig, ax = plt.subplots(figsize=(8, 5)); ax.axvline(0, color="#888888", lw=0.8)
	for yv, (k, r) in zip(yy, t.iterrows()):
		if not r.tested:
			ax.text(0, yv, "descriptive only", fontsize=7, ha="center", va="center", color="#777777"); continue
		if np.isfinite(r.std_lo):
			ax.plot([r.std_lo, r.std_hi], [yv, yv], color="#333333", lw=0.9)
		else:
			ax.text(r["std"] + 0.03, yv + 0.25, "CI not reported (<900 valid resamples)", fontsize=6.5, color="#777777")
		ax.plot(r["std"], yv, "o", ms=5, mfc=C_HI if r.q < 0.05 else "white", mec="#333333")
		ax.text(1.02, yv, f"{int(r.n_high)}/{int(r.n_low)}", transform=ax.get_yaxis_transform(), fontsize=7, va="center")
	ax.text(1.02, len(t) - 0.4, "n high/low", transform=ax.get_yaxis_transform(), fontsize=7)
	ax.set_yticks(yy); ax.set_yticklabels([f"{EN[k]} [{DIR[k]}]" for k in t.index], fontsize=7.5)
	ax.set_xlabel("Baseline-adjusted standardized difference (high minus low engagement)")
	fig.text(0.01, 0.028, "[\u2191] higher is desirable; [\u00b1] the desirable direction depends on the baseline level (results by baseline stratum in Table S2).",
	         fontsize=6.5)
	fig.text(0.01, 0.008, f"Heart rate not shown: daily values not extracted. Filled marker: q < .05 (Benjamini-Hochberg over the {int(MAIN.n_bh.iloc[0])} indicators with a valid P).", fontsize=6.5)
	fig.tight_layout(rect=(0.0, 0.06, 0.93, 1)); savefig(fig, "fig4_forest.png")


def fig_exposure():
	fig, ax = plt.subplots(figsize=(6, 3.4))
	e = U.exp.values.astype(int); cnt = np.bincount(e, minlength=29)
	ax.step(np.arange(29), np.cumsum(cnt) / cnt.sum(), where="post", color="#333333")
	ax.axvline(A1.MED, color=C_HI, ls="--", lw=1); ax.text(A1.MED - 0.3, 0.55, f"median {A1.MED:.0f} days\n(high engagement: >= median)", ha="right", fontsize=7, color=C_HI)
	ax.set_xlabel("Login days in the 28-day exposure window"); ax.set_ylabel("Cumulative proportion of users"); ax.set_xlim(0, 28.5)
	ax.text(0.3, 0.92, f"n={len(e)}; {int((e == 28).sum())} users logged in on all 28 days", fontsize=7)
	fig.tight_layout(); savefig(fig, "figS1_exposure.png")


def fig_ps():
	Xp = U[A1.PSV].values; keep = S.independent_columns(Xp); Xc = S.add_const(Xp[:, keep])
	b, ok = S.glm_logit(Xc, A1.A)
	if not ok or np.max(np.abs(b)) > 15:
		b, ok = S.firth_logit(Xc, A1.A)
	ps = S.expit(Xc @ b)
	fig, (a1, a2) = plt.subplots(1, 2, figsize=(8, 3.6), gridspec_kw={"width_ratios": [1, 1.25]})
	bins = np.linspace(0, 1, 21)
	a1.hist(ps[hi], bins=bins, histtype="step", color=C_HI, lw=1.2, label="High"); a1.hist(ps[~hi], bins=bins, histtype="step", color=C_LO, lw=1.2, ls="--", label="Low")
	a1.set_xlabel("Propensity score"); a1.set_ylabel("Users"); a1.legend(frameon=False, fontsize=7.5); a1.set_title("A", loc="left")
	t = T1.dropna(subset=["smd_before"]); yy = np.arange(len(t))[::-1]
	a2.axvline(0, color="#888888", lw=0.7); a2.axvline(0.1, color="#BBBBBB", lw=0.7, ls=":"); a2.axvline(-0.1, color="#BBBBBB", lw=0.7, ls=":")
	a2.plot(t.smd_before, yy, "o", mfc="white", mec="#333333", ms=4, label="Before weighting"); a2.plot(t.smd_after, yy, "o", color="#333333", ms=4, label="After weighting")
	a2.set_yticks(yy); a2.set_yticklabels([v.replace("Registered outside the most common quarter", "Outside the most common quarter") for v in t.variable], fontsize=6.5)
	a2.set_xlabel("Standardized mean difference"); a2.legend(frameon=False, fontsize=6.5, loc="lower right"); a2.set_title("B", loc="left")
	fig.tight_layout(); savefig(fig, "figS2_ps_balance.png")


def fig_dose():
	fig, axes = plt.subplots(2, 5, figsize=(8, 4)); axes = axes.ravel()
	g = A1.GRID; lo_x = np.percentile(U.exp, 5)
	for ax, k in zip(axes, A1.ORDER):
		r = E["dose"][k]
		if not (r.get("tested") and r.get("conv", False)):
			ax.axis("off"); continue
		cv = np.array([b["dose"][k]["curve"] for b in B if b["dose"][k].get("tested") and b["dose"][k].get("conv", False)])
		m = g >= lo_x
		if len(cv) >= 900:  # band only with >= 900 valid replicates
			ax.fill_between(g[m], np.percentile(cv, 2.5, axis=0)[m], np.percentile(cv, 97.5, axis=0)[m], color="#DDDDDD")
		ax.plot(g[m], np.array(r["curve"])[m], color="#333333", lw=1)
		ax.set_title(SHORT[k], fontsize=7, loc="left"); ax.tick_params(labelsize=6)
		en = np.array(r["exp_n"]); xs = np.repeat(np.arange(29), en.astype(int))  # exposure of this indicator's analysis set
		ax.plot(xs, np.full(len(xs), ax.get_ylim()[0]), "|", color="#999999", ms=4)
	fig.text(0.01, 0.028, "x axis: login days in the exposure window (curve from the 5th percentile to 28). Unweighted outcome regression adjusted for baseline and the",
	         fontsize=6.3)
	fig.text(0.01, 0.008, "propensity-score covariates; band: pointwise 95% CI; ticks: exposure of each indicator's analysis set. Knots: 10th/50th/90th percentiles.", fontsize=6.3)
	fig.tight_layout(rect=(0, 0.05, 1, 1)); savefig(fig, "figS3_dose_response.png")


def fig_sens():
	rows = [("main", "Main"), ("equal_users", "Users weighted equally"), ("no_trunc", "Weights not truncated"), ("unadjusted", "Baseline only, no weighting"),
	        ("susp1", "Token-only login days removed"), ("week12", "Later outcome window (days 70-97)"), ("base2_13", "Baseline days 2-13"), ("t0_le56", "Time 0 within 56 days"),
	        ("no_plat1102", "Without platform type C"), ("zero_steps", "Wear days without steps as 0"), ("act_gap_zero", "Collection-gap days as 0"), ("act_calendar", "Adjusted for calendar time"),
	        ("extended", "Extended measurement window")]
	tabs = {"main": MAIN.set_index("indicator")}; tabs.update({k: SENS[k].set_index("indicator") for k, _ in rows[1:]})
	fig, axes = plt.subplots(2, 5, figsize=(8, 6.4), sharey=True); axes = axes.ravel()
	yy = np.arange(len(rows))[::-1]
	for ax, k in zip(axes, A1.ORDER):
		ax.axvline(0, color="#888888", lw=0.7)
		for yv, (key, _) in zip(yy, rows):
			t = tabs[key]
			if k not in t.index or not t.loc[k, "tested"]:
				continue
			r = t.loc[k]
			if np.isfinite(r.lo):
				ax.plot([r.lo, r.hi], [yv, yv], color="#333333", lw=0.7)
			ax.plot(r["diff"], yv, "o", ms=3, mfc="#333333" if key == "main" else "white", mec="#333333")
		ax.set_title(SHORT[k], fontsize=6.5, loc="left"); ax.tick_params(axis="x", labelsize=6)
	for ax in axes[::5]:
		ax.set_yticks(yy); ax.set_yticklabels([l for _, l in rows], fontsize=6)
	fig.text(0.01, 0.024, "Adjusted difference in original units (high minus low); filled marker: main analysis. A marker without a line: CI not reported", fontsize=6.3)
	fig.text(0.01, 0.006, "(<900 valid resamples). Rule 2 for suspected token-only login days gave the same exposure groups as rule 1.", fontsize=6.3)
	fig.tight_layout(rect=(0, 0.04, 1, 1)); savefig(fig, "figS4_sensitivity.png")


def fig_gap():
	t = GAP_OUT[(GAP_OUT.day_rel >= -90) & (GAP_OUT.day_rel <= 150)]
	fig, (a0, a1) = plt.subplots(2, 1, figsize=(8, 4.6), sharex=True, gridspec_kw={"height_ratios": [1, 1.2]})
	a0.plot(t.day_rel, t.users_with_step_record, color="#888888", lw=0.8, label="Users with a step record (denominator)")
	a0.plot(t.day_rel, t.users_with_session_record, color="#333333", lw=0.8, label="Users with a session record (numerator)")
	a0.set_ylabel("Users"); a0.legend(frameon=False, fontsize=7, loc="upper left"); a0.set_title("A", loc="left")
	a1.plot(t.day_rel, t.ratio, color="#333333", lw=0.8, label="Daily ratio")
	a1.plot(t.day_rel, t.threshold, color=C_LO, lw=0.8, ls="--", label="Threshold: 0.5 x median of the previous 28 days")
	for ax in (a0, a1):
		ax.axvspan(0, GAP_LEN, color="#DDDDDD", zorder=0)
	a1.text(GAP_LEN + 2, a1.get_ylim()[1] * 0.92, f"collection gap ({GAP_LEN} days)", fontsize=7)
	a1.set_ylabel("Ratio"); a1.set_xlabel("Days relative to the first gap day"); a1.legend(frameon=False, fontsize=7, loc="lower right", ncol=2); a1.set_title("B", loc="left")
	fig.tight_layout(); savefig(fig, "figS5_collection_gap.png")


fig_flow(); fig_weekly(); fig_forest(); fig_exposure(); fig_ps(); fig_dose(); fig_sens(); fig_gap()

NOTES1 = [
	"Estimates: high minus low engagement. Daily indicators: WLS on user means weighted by 1/(tau2 + sigma2/n) x IPTW (equivalent to a random-intercept model); point indicators: weighted linear regression on the first measurement in the outcome window. Adjusted for the baseline value and the propensity-score covariates (age, sex, registration outside the most common quarter, days from registration to time 0, login days before time 0, platform, baseline wear days); point indicators also for the record source.",
	"95% CI: percentile interval from 1,000 user-level bootstrap resamples (propensity score re-estimated each time). P: Wald test using the bootstrap SE; it can disagree with the percentile CI when the bootstrap distribution is skewed.",
	"Only resamples in which every fit converged (propensity score, REML, outcome model) are used; with fewer than 900 valid resamples no CI, P or q is reported (e.g. grip strength).",
	"q: Benjamini-Hochberg over the indicators with a valid P (n_bh). q_keep_all: indicators without a valid P kept in the family with P = 1.",
	"Blank cells: not tested (fewer than 30 users or fewer than 10 per group), or no CI (fewer than 900 valid resamples).",
	"Standardized difference: adjusted difference divided by the pooled baseline SD of the two groups (frequency-weighted in each resample).",
	"E-value: from exp(0.91 x d), d = adjusted difference / outcome SD; CI E-value is 1 when the CI includes 0 and blank when there is no CI.",
	"S_collection_gap: days are relative to the first gap day; no calendar dates are shown.",
	"Sheet-specific methods: S_equal_users = same model but users weighted equally (no 1/(tau2 + sigma2/n) factor); S_unadjusted = no propensity weighting and no propensity covariates (baseline value only); S_no_trunc = weights not truncated; S_dose = unweighted outcome regression with a restricted cubic spline of login days, adjusted for the baseline value and the propensity covariates; S_wear_days = cohort rebuilt with another baseline watch-wear threshold, point estimates only; S_act_calendar = main model plus the outcome-window start (days) as a covariate; S_plausible (post hoc) = daily values above 60,000 steps, 1,440 exercise or sleep minutes, or 100% SpO2 removed before the usual daily rules; S_week12 = later outcome window (days 70-97), users whose window had closed by the cutoff; S_strata = main model within baseline strata (exploratory, no multiplicity adjustment).",
]
with pd.ExcelWriter(OUT / "tables_01.xlsx") as xw:
	T1.to_excel(xw, sheet_name="Table1", index=False); MAIN.to_excel(xw, sheet_name="Table2", index=False)
	for k, t in SENS.items():
		t.to_excel(xw, sheet_name=f"S_{k}", index=False)
	STRATA.to_excel(xw, sheet_name="S_strata", index=False); WEAR.to_excel(xw, sheet_name="S_wear_days", index=False)
	DOSE.to_excel(xw, sheet_name="S_dose", index=False); IBAL.to_excel(xw, sheet_name="S_balance_by_indicator", index=False)
	GAP_N.to_excel(xw, sheet_name="S_gap_days", index=False)
	GAP_OUT.to_excel(xw, sheet_name="S_collection_gap", index=False); SESS.to_excel(xw, sheet_name="S_session_share", index=False)
	pd.DataFrame({"note": NOTES1}).to_excel(xw, sheet_name="Notes", index=False)
SUM = dict(median_exposure=A1.MED, n_high=int(A1.A.sum()), n_low=int((1 - A1.A).sum()), balance=BAL, boot_valid=len(B),
           selected=MAIN.loc[MAIN.q < 0.05, "indicator"].tolist(), figures=FIG)
json.dump(SUM, open(OUT / "summary_01.json", "w"), indent=1, default=float)
pd.set_option("display.width", 230)
print(MAIN[["indicator", "n", "n_high", "n_low", "base_high", "base_low", "out_high", "out_low", "diff", "lo", "hi", "std", "p", "q", "evalue", "evalue_ci", "boot_valid"]].round(3).to_string(index=False))
print(json.dumps({k: v for k, v in SUM.items() if k != "figures"}, indent=1, default=float))
for k, t in SENS.items():
	print(k, t[["indicator", "n", "tested", "diff", "lo", "hi", "p"]].round(2).to_string(index=False).replace("\n", " | ")[:1300])
print(STRATA.round(2).to_string(index=False)); print(WEAR.round(2).to_string(index=False)); print(T1.round(3).to_string(index=False))
print(DOSE.round(3).to_string(index=False)); print(IBAL.round(3).to_string(index=False)); print(GAP_N.to_string(index=False)); print(SESS.to_string(index=False))
