# -*- coding: utf-8 -*-
"""Main-text figures for study 02 that show what is specific to this study: the shape of the engagement outcome and why it needs
an overdispersed model, engagement by checkup-linkage status (selection into the analysis), and the screen of all checkup items
as effect size against evidence. Reads the analysis data through ana2 and the result workbook written by report2.
Run from retrospective_study/."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import special, stats

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "02_checkup_metrics/src"))
sys.path.insert(0, str(ROOT / "00_common/src"))
import ana2 as A2  # noqa: E402
import figstyle as FS  # noqa: E402
import statlib as S  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402

FS.use()
OUT = A2.OUT
TB = pd.ExcelFile(OUT / "tables_02.xlsx")
U = A2.U
LAB = {"height": "Height", "weight": "Weight", "bmi": "BMI ≥25", "waist": "Waist", "sbp": "SBP ≥130", "dbp": "DBP ≥85", "fbg": "Glucose ≥100",
       "tc": "TC ≥200", "hdl": "Low HDL", "ldl": "LDL ≥130", "tg": "TG ≥150", "hb": "Low Hb", "ast": "AST >40", "alt": "ALT >35", "ggt": "High GGT",
       "cr": "Creatinine", "gfr": "eGFR <60", "uprot": "Urine protein", "sight": "Visual acuity", "hearing": "Hearing", "chest": "Chest radiograph",
       "judge": "Overall judgment"}
DOMAIN = {"height": "Body", "weight": "Body", "bmi": "Body", "waist": "Body", "sbp": "Cardiometabolic", "dbp": "Cardiometabolic", "fbg": "Cardiometabolic",
          "tc": "Cardiometabolic", "hdl": "Cardiometabolic", "ldl": "Cardiometabolic", "tg": "Cardiometabolic", "hb": "Organ function", "ast": "Organ function",
          "alt": "Organ function", "ggt": "Organ function", "gfr": "Organ function", "sight": "Other", "hearing": "Other", "chest": "Other", "judge": "Other"}
MARK = {"Body": "s", "Cardiometabolic": "o", "Organ function": "^", "Other": "D"}


def save(fig, name):
	fig.savefig(OUT / name, facecolor="white"); plt.close(fig); print("wrote", name)


def linkage_groups():
	"""Common-cohort users by checkup linkage: baseline checkup in the 24-month window, checkups only outside it, none."""
	C = A2.C
	valid = set(A2._L[A2._L.used & A2._L.ok].user_id)
	base = set(A2.BSEL.user_id.unique())
	g = pd.Series("No valid checkup", index=C.index)
	g[C.index.isin(list(valid))] = "Checkup outside the window"
	g[C.index.isin(list(base))] = "Baseline checkup"
	return g


# ------------------------------------------------------------------ Figure 3: the engagement outcome
def fig_engagement():
	y = U.y.values.astype(float)
	X = S.add_const(U[A2.BASECOV].values.astype(float))
	X = X[:, S.independent_columns(X, protect=1)]
	b, lt, conv = S.betabinom_fit(X, y, 28.0)
	mu = S.expit(X @ b); th = np.exp(lt)
	k = np.arange(29)
	bb = np.array([np.sum(np.exp(special.gammaln(29) - special.gammaln(kk + 1) - special.gammaln(29 - kk) + special.betaln(kk + mu * th, 28 - kk + (1 - mu) * th)
	                             - special.betaln(mu * th, (1 - mu) * th))) for kk in k])
	bq, _ = S.glm_logit(X, y / 28); mq = S.expit(X @ bq)
	bi = np.array([np.sum(stats.binom.pmf(kk, 28, mq)) for kk in k])
	obs = np.bincount(y.astype(int), minlength=29)

	g = linkage_groups()
	lgc = pd.read_csv(A2.EX / "login_hours_days.csv", parse_dates=["d"]).merge(A2.C[["d0"]], left_on="user_id", right_index=True)
	lgc["day"] = (lgc.d - lgc.d0).dt.days
	lgc = lgc[(lgc.day >= 1) & (lgc.day <= 28)]
	fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.9), gridspec_kw={"width_ratios": [1.15, 1], "wspace": 0.28})
	FS.hgrid(a1)
	a1.bar(k, obs, width=0.78, color=FS.NEUTRAL, label="Observed users")
	a1.plot(k, bi, color=FS.INK2, lw=1.4, ls=(0, (4, 2)), label="Binomial expected")
	a1.plot(k, bb, color=FS.S02_ITEM, lw=1.9, label="Beta-binomial expected")
	a1.set_xlim(-0.8, 28.8); a1.set_xticks([0, 7, 14, 21, 28])
	a1.set_xlabel("Login days on days 1-28"); a1.set_ylabel("Users")
	a1.annotate(f"28 days: {obs[28]} observed,\n{bb[28]:.0f} expected", (28, obs[28]), xytext=(-8, 4), textcoords="offset points", ha="right", fontsize=7, color=FS.INK2)
	a1.legend(loc="upper left", fontsize=7.2, bbox_to_anchor=(0.0, 1.0))
	FS.panel(a1, "A", f"Analyzed users (n={len(y)})")
	FS.hgrid(a2)
	res = {}
	for lab, col, ls, dy in [("Baseline checkup", FS.S02["valid"], "-", 9), ("Checkup outside the window", FS.S02["outside"], (0, (5, 2)), -7),
	                         ("No valid checkup", FS.S02["none"], (0, (1.5, 1.5)), 0)]:
		users = g.index[g == lab]
		sh = lgc[lgc.user_id.isin(users)].groupby("day").user_id.nunique().reindex(range(1, 29)).fillna(0) / len(users)
		a2.plot(sh.index, 100 * sh.values, color=col, ls=ls, lw=1.9)
		yd = lgc[lgc.user_id.isin(users)].groupby("user_id").size().reindex(users).fillna(0)
		res[lab] = dict(n=len(users), median=float(yd.median()), q1=float(yd.quantile(.25)), q3=float(yd.quantile(.75)))
		a2.text(28.6, 100 * sh.values[-1] + dy, f"{lab}\n(n={len(users)}; median {yd.median():.0f} days)", fontsize=7, va="center", color=FS.INK)
	a2.set_xlim(1, 28); a2.set_ylim(0, 100); a2.set_xticks([1, 7, 14, 21, 28])
	a2.set_xlabel("Day after registration"); a2.set_ylabel("Users logging in, %")
	FS.panel(a2, "B", "Common cohort by checkup linkage")
	save(fig, "fig3_engagement_profile.png")
	return dict(theta=float(th), rho=float(1 / (1 + th)), obs0=int(obs[0]), bb0=float(bb[0]), bi0=float(bi[0]), obs28=int(obs[28]), bb28=float(bb[28]),
	            bi28=float(bi[28]), groups=res)


# ------------------------------------------------------------------ Figure 4: all items, effect against evidence
def fig_screen():
	t = TB.parse("Table2"); t = t[t.tested].copy()
	t["lp"] = -np.log10(t.p)
	t["dom"] = t["item"].map(DOMAIN)
	fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4.4), gridspec_kw={"width_ratios": [1.45, 1], "wspace": 0.3})
	FS.hgrid(a1)
	a1.axvline(0, color=FS.AXIS, lw=0.9)
	p_bh1 = 0.05 / len(t)  # first Benjamini-Hochberg critical value (.05 / m)
	a1.axhline(-np.log10(0.05), color=FS.MUTED, lw=0.8, ls=(0, (3, 2)))
	a1.axhline(-np.log10(p_bh1), color=FS.INK2, lw=0.9)
	a1.text(-6.9, -np.log10(0.05) + 0.04, "P = .05", fontsize=7, color=FS.MUTED, va="bottom")
	a1.text(6.9, -np.log10(p_bh1) + 0.04, f"First Benjamini-Hochberg critical value, .05/{len(t)} = {p_bh1:.4f}".replace("0.", ".", 1).replace("= 0.", "= ."), fontsize=7, color=FS.INK2, va="bottom", ha="right")
	for dom, mk in MARK.items():
		s = t[t.dom == dom]
		size = np.where(s["item"].isin(["height", "weight"]), 40, 18 + 1.4 * s.n_abn.fillna(0))
		a1.scatter(s.est, s.lp, s=size, marker=mk, facecolor=FS.S02_ITEM, alpha=0.85, edgecolor="white", lw=0.8, label=dom, zorder=3)
	for _, r in t.iterrows():
		if r.p < 0.2:
			a1.annotate(LAB[r["item"]], (r.est, r.lp), xytext=(5, 2), textcoords="offset points", fontsize=7, color=FS.INK)
	a1.set_xlim(-7, 7); a1.set_ylim(0, max(2.9, -np.log10(p_bh1) + 0.3))
	a1.set_xlabel("Adjusted difference in login days, out of range minus within range")
	a1.set_ylabel("-log10 P")
	from matplotlib.lines import Line2D
	hd = [Line2D([], [], marker=mk, ls="", ms=6, mfc=FS.S02_ITEM, mec="white", label=dom) for dom, mk in MARK.items()]
	a1.legend(handles=hd, loc="upper left", fontsize=7, title="Domain (marker area grows with users out of range;\nheight and weight per SD, fixed size)", title_fontsize=7, bbox_to_anchor=(0, 0.9))
	FS.panel(a1, "A", f"{len(t)} tested checkup items")
	# B: count of out-of-range components
	E = pd.read_pickle(OUT / "est_point.pkl")
	Bt = [b for b in pd.read_pickle(OUT / "est_boot.pkl") if "error" not in b]
	curve_bs = np.array([b["summary"]["curve"] for b in Bt if b["summary"].get("conv", False)])
	g = np.arange(8); cv = np.array(E["summary"]["curve"])
	FS.hgrid(a2)
	if len(curve_bs) >= 900:
		a2.fill_between(g, np.percentile(curve_bs, 2.5, axis=0), np.percentile(curve_bs, 97.5, axis=0), color=FS.S02_ITEM, alpha=0.15, lw=0, label="95% CI (pointwise)")
	a2.plot(g, cv, color=FS.S02_ITEM, lw=1.9, label="Standardized mean")
	ok = A2.N_MEAS == 11
	o = pd.DataFrame({"k": np.minimum(A2.N_OUT[ok], 7), "y": U.y.values[ok]}).groupby("k").y.agg(["mean", "size"])
	a2.scatter(o.index, o["mean"], s=np.clip(o["size"] * 0.9, 8, 90), facecolor="white", edgecolor=FS.INK2, lw=1, zorder=3, label="Observed mean (size: users)")
	for kk, r in o.iterrows():
		a2.text(kk, r["mean"] - 1.25, f"{int(r['size'])}", ha="center", fontsize=6.5, color=FS.MUTED)
	a2.set_xticks(g); a2.set_xticklabels([str(i) for i in g[:-1]] + ["7+"]); a2.set_ylim(8, 22)
	a2.set_xlabel("Out-of-range components among 11 panel items"); a2.set_ylabel("Login days on days 1-28")
	a2.legend(loc="upper right", fontsize=7)
	FS.panel(a2, "B", f"Out-of-range count (n={int(ok.sum())})")
	save(fig, "fig4_item_screen.png")
	return dict(m=len(t), p_bh1=p_bh1)


# ------------------------------------------------------------------ Figure 2: flow with what the excluded users look like, and checkup timing
def fig_design():
	from matplotlib.patches import FancyBboxPatch
	g = linkage_groups()
	lgc = pd.read_csv(A2.EX / "login_hours_days.csv", parse_dates=["d"]).merge(A2.C[["d0"]], left_on="user_id", right_index=True)
	lgc = lgc[(lgc.d > lgc.d0) & (lgc.d <= lgc.d0 + pd.Timedelta(days=28))]
	yd = lgc.groupby("user_id").size().reindex(A2.C.index).fillna(0)
	def med(m):
		v = yd[m]; q1, q3 = v.quantile(.25), v.quantile(.75)
		f = lambda x: f"{x:.0f}" if float(x).is_integer() else f"{x:.1f}"
		return f"median {f(v.median())} login days (IQR {f(q1)}-{f(q3)})"
	n_c = len(A2.C); n_valid = int((g != "No valid checkup").sum()); n_base = int((g == "Baseline checkup").sum()); n_an = len(U)
	miss = [u for u in g.index[g == "Baseline checkup"] if u not in U.index]
	fig = plt.figure(figsize=(10.2, 6.4))
	a1 = fig.add_axes([0.0, 0.03, 0.55, 0.94]); a4 = fig.add_axes([0.63, 0.6, 0.25, 0.34]); a2 = fig.add_axes([0.63, 0.09, 0.25, 0.34])
	a1.set_xlim(0, 100); a1.set_ylim(0, 100); a1.axis("off")
	a1.text(0, 99, "A", fontsize=11, fontweight="bold", va="top")
	main = [(f"Common cohort\nn={n_c}", 88), (f"Any valid health checkup\nn={n_valid}", 63), (f"Baseline checkup within 24 months\nbefore registration, n={n_base}", 38),
	        (f"Analyzed\nn={n_an}; {med(g.index.isin(U.index))}", 13)]
	side = [(f"No valid checkup, n={int((g == 'No valid checkup').sum())}\n{med(g == 'No valid checkup')}", FS.S02["none"]),
	        (f"Checkups only outside the window, n={int((g == 'Checkup outside the window').sum())}\n{med(g == 'Checkup outside the window')}", FS.S02["outside"]),
	        (f"Age or sex missing, n={len(miss)}", FS.MUTED)]
	for i, (t, y) in enumerate(main):
		last = i == len(main) - 1
		a1.add_patch(FancyBboxPatch((3, y - 6.5), 44, 13, boxstyle="round,pad=0.4", fc="#e2f5ee" if last else "white", ec=FS.S02["valid"] if last else FS.INK2, lw=1.2 if last else 0.8))
		a1.text(25, y, t, ha="center", va="center", fontsize=7.8, color=FS.INK, fontweight="bold" if last else None)
		if not last:
			yn = main[i + 1][1]
			a1.annotate("", xy=(25, yn + 7.2), xytext=(25, y - 7.2), arrowprops=dict(arrowstyle="-|>", color=FS.INK2, lw=0.9))
			ym = (y + yn) / 2
			t2, col = side[i]
			a1.add_patch(FancyBboxPatch((55, ym - 5.5), 44, 11, boxstyle="round,pad=0.4", fc="white", ec=col, lw=1.4))
			a1.text(77, ym, t2, ha="center", va="center", fontsize=7.2, color=FS.INK)
			a1.annotate("", xy=(54.3, ym), xytext=(25, ym), arrowprops=dict(arrowstyle="-|>", color=FS.MUTED, lw=0.8))
	# B: timing of the baseline checkup (BMI item, latest valid result) and its entry into the service
	k = A2.ITEMF["bmi"].k.dropna().values
	lag = A2.ITEMF["bmi"].entry_lag.dropna().values
	FS.hgrid(a2)
	a2.hist(k / 30.44, bins=np.arange(0, 24.5, 1), color=FS.S02["valid"], edgecolor="white", lw=0.6)
	a2.set_xlim(0, 24); a2.set_xticks([0, 6, 12, 18, 24])
	a2.set_xlabel("Months from the baseline checkup to registration"); a2.set_ylabel("Users")
	FS.panel(a2, "C", "Timing of the baseline checkup")
	a2.text(0.98, 0.97, f"Same day as registration: {int((k == 0).sum())}\nEntered into the service by\nthe registration day: {int((lag <= 0).sum())} of {len(lag)}",
	        transform=a2.transAxes, ha="right", va="top", fontsize=7, color=FS.INK2)
	# B: daily logins in the common cohort by checkup linkage
	lgd = pd.read_csv(A2.EX / "login_hours_days.csv", parse_dates=["d"]).merge(A2.C[["d0"]], left_on="user_id", right_index=True)
	lgd["day"] = (lgd.d - lgd.d0).dt.days; lgd = lgd[(lgd.day >= 1) & (lgd.day <= 28)]
	FS.hgrid(a4)
	for lab, col, ls, dy, short in [("Baseline checkup", FS.S02["valid"], "-", 7, "Baseline checkup"), ("Checkup outside the window", FS.S02["outside"], (0, (5, 2)), -7, "Outside window"),
	                                ("No valid checkup", FS.S02["none"], (0, (1.5, 1.5)), 0, "No valid checkup")]:
		users = g.index[g == lab]
		sh = lgd[lgd.user_id.isin(users)].groupby("day").user_id.nunique().reindex(range(1, 29)).fillna(0) / len(users)
		a4.plot(sh.index, 100 * sh.values, color=col, ls=ls, lw=1.8)
		a4.text(28.8, 100 * sh.values[-1] + dy, f"{short}\n(n={len(users)})", fontsize=6.8, va="center", color=FS.INK)
	a4.set_xlim(1, 28); a4.set_ylim(0, 100); a4.set_xticks([1, 7, 14, 21, 28]); a4.set_xlabel("Day after registration"); a4.set_ylabel("Users logging in, %")
	FS.panel(a4, "B", "Common cohort by checkup linkage")
	save(fig, "fig2_design_flow.png")


# ------------------------------------------------------------------ Figure 3: user-by-day login raster ordered by checkup burden
def fig_raster():
	lg = A2.lg.copy(); lg["day"] = (lg.d - lg.d0).dt.days
	ok11 = A2.N_MEAS == 11
	grp = np.where(ok11, np.minimum(A2.N_OUT, 4), -1).astype(int)
	labs = {0: "0 components", 1: "1", 2: "2", 3: "3", 4: "4 or more", -1: "Fewer than 11 measured"}
	M = np.zeros((len(U), 28))
	ui = {u: i for i, u in enumerate(U.index)}
	for u, d in zip(lg.user_id, lg.day):
		if 1 <= d <= 28:
			M[ui[u], d - 1] = 1
	tot = M.sum(axis=1)
	order, ticks, seps = [], [], []
	for gk in [0, 1, 2, 3, 4, -1]:
		idx = np.where(grp == gk)[0]
		idx = idx[np.lexsort((-M[idx][:, :7].sum(axis=1), -tot[idx]))]
		if len(order):
			seps.append(len(order))
		ticks.append((len(order) + len(idx) / 2, f"{labs[gk]} (n={len(idx)})", float(np.median(tot[idx]))))
		order.extend(idx.tolist())
	from matplotlib.colors import ListedColormap
	fig = plt.figure(figsize=(10.2, 6.6))
	a1 = fig.add_axes([0.17, 0.08, 0.47, 0.86]); a2 = fig.add_axes([0.66, 0.08, 0.08, 0.86]); a3 = fig.add_axes([0.85, 0.55, 0.14, 0.39])
	a1.imshow(M[order], aspect="auto", interpolation="nearest", cmap=ListedColormap(["#f4f4f1", FS.S02["valid"]]), extent=(0.5, 28.5, len(order), 0))
	for sp in seps:
		a1.axhline(sp, color="white", lw=2.2); a1.axhline(sp, color=FS.INK2, lw=0.6)
	a1.set_yticks([t[0] for t in ticks]); a1.set_yticklabels([t[1] for t in ticks], fontsize=7.4)
	a1.set_xticks([1, 7, 14, 21, 28]); a1.set_xlabel("Day after registration")
	a1.tick_params(axis="y", length=0)
	for sp_ in a1.spines.values():
		sp_.set_visible(False)
	FS.panel(a1, "A", "Login (filled) by user and day, grouped by out-of-range panel components")
	a1.text(-0.25, 1.0, "", transform=a1.transAxes)
	a2.barh(np.arange(len(order)) + 0.5, tot[order], height=1.0, color=FS.S02_ITEM, lw=0)
	a2.set_ylim(len(order), 0); a2.set_yticks([]); a2.set_xlim(0, 28); a2.set_xticks([0, 14, 28]); a2.set_xlabel("Login days")
	for sp in seps:
		a2.axhline(sp, color=FS.INK2, lw=0.6)
	a2.spines["left"].set_visible(False)
	# C: median login days by group
	FS.vgrid(a3)
	gy = np.arange(len(ticks))[::-1]
	for yy, (gk, t) in zip(gy, zip([0, 1, 2, 3, 4, -1], ticks)):
		idx = np.where(grp == gk)[0]
		q1, q2, q3 = np.percentile(tot[idx], [25, 50, 75])
		a3.hlines(yy, q1, q3, color=FS.S02_ITEM, lw=2.4, alpha=0.45); a3.scatter(q2, yy, color=FS.S02_ITEM, s=26, zorder=3)
	a3.set_yticks(gy); a3.set_yticklabels(["0", "1", "2", "3", "≥4", "<11 measured"], fontsize=7)
	a3.set_xlim(0, 28); a3.set_xticks([0, 7, 14, 21, 28]); a3.set_xlabel("Login days, median (IQR)")
	FS.panel(a3, "B", "By group")
	save(fig, "fig3_login_raster.png")
	return {t[1]: t[2] for t in ticks}


# ------------------------------------------------------------------ Figure 5: how well the outcome model fits
def fig_fit():
	f = A2.ITEMF["bmi"]
	X = np.column_stack([f.x.values, U[A2.BASECOV].values, f.k.values, f.src104.values]); y = U.y.values.astype(float)
	X = X[:, S.independent_columns(X, protect=1)]; Xc = S.add_const(X)
	b, lt, conv = S.betabinom_fit(Xc, y, 28.0)
	mu = S.expit(Xc @ b); th = np.exp(lt)
	k = np.arange(29)
	bb = np.array([np.sum(np.exp(special.gammaln(29) - special.gammaln(kk + 1) - special.gammaln(29 - kk) + special.betaln(kk + mu * th, 28 - kk + (1 - mu) * th)
	                             - special.betaln(mu * th, (1 - mu) * th))) for kk in k])
	bq, _ = S.glm_logit(Xc, y / 28); mq = S.expit(Xc @ bq)
	bi = np.array([np.sum(stats.binom.pmf(kk, 28, mq)) for kk in k])
	obs = np.bincount(y.astype(int), minlength=29)
	cal = TB.parse("S_fit_calibration")
	fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.9), gridspec_kw={"width_ratios": [1.5, 1], "wspace": 0.32})
	FS.hgrid(a1)
	a1.bar(k, obs, width=0.78, color=FS.NEUTRAL, label="Observed users")
	a1.plot(k, bi, color=FS.INK2, lw=1.4, ls=(0, (4, 2)), label="Binomial expected")
	a1.plot(k, bb, color=FS.S02_ITEM, lw=1.9, label="Beta-binomial expected")
	a1.set_xlim(-0.8, 28.8); a1.set_xticks([0, 7, 14, 21, 28]); a1.set_xlabel("Login days on days 1-28"); a1.set_ylabel("Users")
	a1.annotate(f"0 days: {obs[0]} observed, {bb[0]:.0f} expected", (0, bb[0]), xytext=(6, 10), textcoords="offset points", fontsize=7, color=FS.INK2,
	            arrowprops=dict(arrowstyle="-", color=FS.MUTED, lw=0.6))
	a1.annotate(f"28 days: {obs[28]} observed,\n{bb[28]:.0f} expected", (28, obs[28]), xytext=(-8, -4), textcoords="offset points", ha="right", va="top", fontsize=7, color=FS.INK2)
	a1.legend(loc="upper left", fontsize=7.2)
	FS.panel(a1, "A", f"Distribution (intraclass correlation {1 / (1 + th):.2f})")
	FS.vgrid(a2)
	yy = np.arange(len(cal))[::-1]
	a2.hlines(yy, cal.observed, cal.predicted, color=FS.NEUTRAL, lw=2)
	a2.scatter(cal.observed, yy, s=30, facecolor="white", edgecolor=FS.INK2, lw=1, zorder=3, label="Observed mean")
	a2.scatter(cal.predicted, yy, s=30, color=FS.S02_ITEM, zorder=3, label="Predicted mean")
	nm = {"quarter": "Quarter", "BMI >=25": "BMI ≥25"}
	a2.set_yticks(yy); a2.set_yticklabels([f"{nm.get(g, g)} {l} (n={n})" for g, l, n in zip(cal.grouping, cal.level, cal.n)], fontsize=7.2)
	a2.set_xlabel("Mean login days"); a2.legend(loc="lower right", fontsize=7)
	FS.panel(a2, "B", "Calibration in subgroups")
	save(fig, "fig5_model_fit.png")
	return dict(obs0=int(obs[0]), bb0=float(bb[0]), obs28=int(obs[28]), bb28=float(bb[28]), icc=float(1 / (1 + th)))


if __name__ == "__main__":
	fig_design(); print(fig_raster()); print(fig_screen()); print(fig_fit())
