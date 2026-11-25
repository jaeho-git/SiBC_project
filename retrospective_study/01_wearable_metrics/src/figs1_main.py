# -*- coding: utf-8 -*-
"""Main-text figures for study 01 that show what is specific to this study: day-level wearable trajectories around the
exposure window, the platform-wide collection gap found by the data-quality rule and what it does to the outcome, and how the
engagement contrast changes from baseline-only to full confounding adjustment. Reads the analysis data through ana1 and the
result workbook written by report1. Run from retrospective_study/."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "01_wearable_metrics/src"))
sys.path.insert(0, str(ROOT / "00_common/src"))
sys.argv = [sys.argv[0]]
import ana1 as A1  # noqa: E402
import figstyle as FS  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402

FS.use()
OUT = A1.OUT
TB = pd.ExcelFile(OUT / "tables_01.xlsx")
HI, LO = FS.S01["high"], FS.S01["low"]
GRP = pd.Series(A1.A, index=A1.USERS)


def save(fig, name):
	fig.savefig(OUT / name, facecolor="white"); plt.close(fig); print("wrote", name)


# ------------------------------------------------------------------ Figure 3: day-level trajectories around the exposure window
def fig_trajectories():
	X = A1.X[A1.X.user_id.isin(A1.USERS) & A1.X["구간"].isin(["기준선", "노출", "결과"])].copy()
	X["day"] = pd.to_numeric(X["노출시작후일"])
	X = X[(X.day >= -14) & (X.day <= 55)]
	X["g"] = X.user_id.map(GRP)
	gapd = set(pd.to_datetime(list(A1.ACT_GAP)))
	panels = [("steps", "걸음", "Steps per day", 1.0), ("active_min", "활동_분", "Exercise minutes per wear day", 1.0), ("sleep_min", "수면_분", "Sleep minutes per night", 1.0)]
	fig = plt.figure(figsize=(10.2, 7.2))
	gs = fig.add_gridspec(4, 1, height_ratios=[1, 1, 0.28, 1], hspace=0.32)
	axes = [fig.add_subplot(gs[0]), fig.add_subplot(gs[1]), fig.add_subplot(gs[3])]
	astrip = fig.add_subplot(gs[2], sharex=axes[1])
	letters = ["A", "B", "D"]
	for ax, (k, col, title), L in zip(axes, [(p[0], p[1], p[2]) for p in panels], letters):
		v = A1.valid_rows(X, k, plausible=True)  # impossible daily values are not drawn
		v = v[(v["구간"] != "기준선") | (v.day < 0)]
		FS.hgrid(ax)
		for x0, x1, lab in [(-14, -0.5, "Baseline"), (-0.5, 27.5, "Exposure (login days counted)"), (27.5, 55, "Outcome")]:
			if lab.startswith("Exposure"):
				ax.axvspan(x0, x1, color="#f2f1ec", lw=0, zorder=0)
			if ax is axes[0]:
				ax.text((x0 + x1) / 2, 0.97, lab, transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=7.5, color=FS.INK2)
		for g, c, ls in [(1, HI, "-"), (0, LO, (0, (4, 1.6)))]:
			s = v[v.g == g]
			# user x day matrix; the curve is the 7-day centered mean of the daily group mean, and the band is the 2.5th-97.5th
			# percentile of the same curve over user-level bootstrap resamples (whole trajectories resampled, so within-user
			# correlation across days is kept)
			Mu = s.groupby(["user_id", "day"])[col].mean().unstack().reindex(columns=range(-14, 56))
			def curve(Mx):
				return pd.Series(np.nanmean(Mx, axis=0), index=range(-14, 56)).rolling(7, center=True, min_periods=4).mean()
			with np.errstate(all="ignore"):
				import warnings
				warnings.simplefilter("ignore")
				sm = curve(Mu.values)
				rng = np.random.default_rng(1101 + g)
				bs = np.array([curve(Mu.values[rng.integers(0, len(Mu), len(Mu))]).values for _ in range(500)])
				lo_, hi_ = np.nanpercentile(bs, 2.5, axis=0), np.nanpercentile(bs, 97.5, axis=0)
			lo_, hi_ = pd.Series(lo_, index=range(-14, 56)), pd.Series(hi_, index=range(-14, 56))
			for seg in [(-14, -1), (0, 27), (28, 55)]:
				idx = range(seg[0], seg[1] + 1)
				ax.fill_between(list(idx), lo_.reindex(idx), hi_.reindex(idx), color=c, alpha=0.13, lw=0)
				ax.plot(list(idx), sm.reindex(idx), color=c, ls=ls, lw=1.7)
		ax.set_xlim(-14, 55)
		FS.panel(ax, L, title)
		if ax is not axes[2]:
			plt.setp(ax.get_xticklabels(), visible=False)
	# direct labels on the first panel
	from matplotlib.lines import Line2D
	axes[0].legend(handles=[Line2D([], [], color=HI, lw=1.7, label=f"High engagement (n={int(A1.A.sum())})"),
	                        Line2D([], [], color=LO, lw=1.7, ls=(0, (4, 1.6)), label=f"Low engagement (n={int((1 - A1.A).sum())})")],
	                loc="lower left", ncol=2, fontsize=7.5)
	# C: share of users whose wear day fell in the platform-wide session gap
	w = X[X["착용일"].astype(str).isin(["예", "True"])].copy()
	w["gap"] = pd.to_datetime(w["날짜"]).isin(gapd)
	for g, c in [(1, HI), (0, LO)]:
		sh = w[w.g == g].groupby("day").gap.mean().reindex(range(-14, 56)).fillna(0)
		astrip.bar(sh.index + (0.2 if g == 1 else -0.2), 100 * sh.values, width=0.4, color=c, lw=0)
	astrip.set_ylabel("Wear days\nin gap, %", fontsize=7.5); astrip.set_ylim(0, 100); astrip.set_yticks([0, 50, 100])
	FS.panel(astrip, "C", "Session-record collection gap (days treated as missing in B)")
	plt.setp(astrip.get_xticklabels(), visible=False)
	axes[2].set_xlabel("Days after the start of the exposure window (7-day centered means; bands: user-bootstrap 95% intervals)")
	save(fig, "fig3_trajectories.png")


# ------------------------------------------------------------------ Figure 4: the collection gap and its consequence
def fig_gap():
	G = TB.parse("S_collection_gap"); ss = TB.parse("S_session_share")
	t2 = TB.parse("Table2").set_index("indicator").loc["active_min"]
	gz = TB.parse("S_act_gap_zero").iloc[0]; gc = TB.parse("S_act_calendar").iloc[0]
	fig = plt.figure(figsize=(10.4, 4.3))
	gs = fig.add_gridspec(1, 3, width_ratios=[1.6, 0.62, 1.25], wspace=0.34)
	a1, a2, a3 = fig.add_subplot(gs[0]), fig.add_subplot(gs[1]), fig.add_subplot(gs[2])
	t = G[(G.day_rel >= -90) & (G.day_rel <= 120)]
	gl = int(A1.pd.Series(sorted(A1.ACT_GAP)).size)
	FS.hgrid(a1)
	a1.axvspan(0, gl - 1, color="#f6dccf", lw=0, zorder=0)
	a1.plot(t.day_rel, t.ratio, color=FS.INK, lw=1.1, label="Users with a session record / users with a step record")
	a1.plot(t.day_rel, t.threshold, color=LO, lw=1.2, ls=(0, (4, 2)), label="Flag threshold: 0.5 × median of the previous 28 days")
	a1.text(gl + 1.5, 0.95 * a1.get_ylim()[1], f"Detected gap: {gl} consecutive days", fontsize=7.5, color=FS.INK2, va="top")
	a1.set_xlabel("Calendar days relative to the first flagged day (all users)")
	a1.set_ylabel("Daily ratio")
	a1.legend(loc="lower left", fontsize=7)
	FS.panel(a1, "A", "Source-level collection-gap check")
	# B: session capture before and after the gap
	FS.hgrid(a2)
	lab = ["8 weeks\nbefore", "8 weeks\nafter"]
	a2.bar([0, 1], 100 * ss.share.values, width=0.55, color=[FS.INK2, FS.MUTED])
	for i, v in enumerate(ss.share.values):
		a2.text(i, 100 * v + 1.5, f"{100 * v:.0f}%", ha="center", fontsize=8, color=FS.INK)
	a2.set_xticks([0, 1]); a2.set_xticklabels(lab, fontsize=7.5); a2.set_ylim(0, 70)
	a2.set_ylabel("Wear days with a session record, %")
	FS.panel(a2, "B", "Capture")
	# C: outcome-window means and the adjusted difference under three handlings of the gap
	rows = [("Gap days counted as 0 min", gz), ("Gap days missing (primary)", t2), ("Primary + calendar time", gc)]
	FS.vgrid(a3)
	y = np.arange(len(rows))[::-1]
	for yy, (lab, r) in zip(y, rows):
		a3.hlines(yy, r.out_low, r.out_high, color=FS.NEUTRAL, lw=2)
		a3.scatter(r.out_high, yy, color=HI, s=34, zorder=3); a3.scatter(r.out_low, yy, color=LO, s=34, marker="s", zorder=3)
		a3.text(22.3, yy + 0.22, lab, fontsize=7.5, color=FS.INK, va="bottom")
		a3.text(22.3, yy - 0.22, "adjusted difference " + f"{r['diff']:+.1f} ({r.lo:.1f} to {r.hi:.1f})".replace("-", "−"), va="top", fontsize=7, color=FS.INK2)
	a3.set_yticks([]); a3.spines["left"].set_visible(False); a3.set_ylim(-0.7, len(rows) - 0.3)
	a3.set_xlim(22, 34); a3.set_xlabel("Outcome-window mean, min per wear day")
	from matplotlib.lines import Line2D
	a3.legend(handles=[Line2D([], [], marker="o", ls="", color=HI, label="High engagement"), Line2D([], [], marker="s", ls="", color=LO, label="Low engagement")],
	          loc="upper right", fontsize=7, ncol=1, bbox_to_anchor=(1.0, 1.1))
	FS.panel(a3, "C", "Exercise minutes")
	save(fig, "fig4_collection_gap.png")
	return dict(gap_len=gl, share_before=float(ss.share.values[0]), share_after=float(ss.share.values[1]))


# ------------------------------------------------------------------ Figure 5: from baseline-only to full adjustment
def fig_adjustment():
	t2 = TB.parse("Table2").set_index("indicator"); un = TB.parse("S_unadjusted").set_index("indicator")
	order = [k for k in A1.ORDER if k in t2.index and t2.loc[k, "tested"]]
	lab = t2.loc[order, "label_en"].str.replace("Exercise minutes per wear day", "Exercise, min/wear day").str.replace("Steps per day", "Steps/day")
	fig, ax = plt.subplots(figsize=(6.4, 4.9))
	FS.vgrid(ax)
	ax.axvline(0, color=FS.AXIS, lw=0.9)
	y = np.arange(len(order))[::-1]
	for yy, k in zip(y, order):
		m, u = t2.loc[k], un.loc[k]
		if np.isfinite(m.std_lo):
			ax.hlines(yy, m.std_lo, m.std_hi, color=HI, lw=1.4)
		ax.annotate("", xy=(m["std"], yy), xytext=(u["std"], yy + 0.28), arrowprops=dict(arrowstyle="-|>", color=FS.MUTED, lw=0.8, shrinkA=3, shrinkB=4))
		ax.scatter(u["std"], yy + 0.28, s=26, facecolor="white", edgecolor=FS.INK2, lw=1, zorder=3)
		ax.scatter(m["std"], yy, s=34, color=HI, zorder=4)
		ax.text(0.80, yy, f"{int(m.n_high)}/{int(m.n_low)}", va="center", fontsize=7, color=FS.INK2)
		dg = 0 if abs(m["diff"]) >= 100 else (1 if abs(m["diff"]) >= 1 else 2)
		ci_txt = f" ({m.lo:,.{dg}f} to {m.hi:,.{dg}f})" if np.isfinite(m.lo) else " (CI not reported)"
		ax.text(1.02, yy, (f"{m['diff']:,.{dg}f}" + ci_txt).replace("-", "−"), va="center", fontsize=7, color=FS.INK)
	ax.text(0.80, len(order) - 0.35, "n high/low", fontsize=7, color=FS.INK2)
	ax.text(1.02, len(order) - 0.35, "Adjusted difference, original units", fontsize=7, color=FS.INK2)
	ax.set_yticks(y); ax.set_yticklabels(lab, fontsize=7.8); ax.set_xlim(-0.75, 0.75)
	ax.set_xticks([-0.6, -0.4, -0.2, 0, 0.2, 0.4, 0.6])
	ax.set_xlabel("Standardized difference, high minus low engagement")
	from matplotlib.lines import Line2D
	ax.legend(handles=[Line2D([], [], marker="o", ls="", mfc="white", mec=FS.INK2, label="Baseline value only"),
	                   Line2D([], [], marker="o", ls="-", color=HI, label="IPTW + covariates (primary, 95% CI)")],
	          loc="upper center", fontsize=7.2, bbox_to_anchor=(0.45, -0.12), ncol=2)
	save(fig, "fig5_adjustment.png")


# ------------------------------------------------------------------ Figure 2: design, participant flow and who is measured
def flow_counts():
	days = A1.BA.B.load(A1._A, A1.C, A1.END)
	st = A1.BA.B.build(A1.C, days, A1.END, A1._A.min_days)["대상자_상태"].value_counts()
	f = {"common": len(A1.C), "no_t0": int(st.get("시간 0 없음", 0)), "collecting": int(st.get("기준선 수집 중", 0)), "low_wear": int(st.get("기준선 착용 부족", 0)),
	     "pending": int(st.get("대상자, 추적 대기", 0)), "analysed": len(A1.USERS)}
	if f["common"] - f["no_t0"] - f["collecting"] - f["low_wear"] - f["pending"] != f["analysed"]:
		raise SystemExit(f"flow counts do not add up: {f}")
	return f


def fig_design():
	from matplotlib.patches import FancyBboxPatch
	f = flow_counts()
	fig = plt.figure(figsize=(10.2, 6.4))
	a0 = fig.add_axes([0.04, 0.79, 0.92, 0.18]); a1 = fig.add_axes([0.04, 0.50, 0.92, 0.27]); a2 = fig.add_axes([0.26, 0.06, 0.56, 0.38])
	# A: windows on one user's time line
	a0.set_xlim(-3, 75); a0.set_ylim(0, 3); a0.axis("off")
	for x0, w, lab, fc in [(0, 14, "Baseline\nfirst 14 days of\nwearable records", FS.NEUTRAL), (18, 28, "Exposure window\nlogin days in 28 days", "#cfe0f6"),
	                       (46, 28, "Outcome window\ndays 28-55 after exposure start", FS.NEUTRAL)]:
		a0.add_patch(FancyBboxPatch((x0, 1.05), w, 1.5, boxstyle="round,pad=0.02,rounding_size=0.25", fc=fc, ec="none"))
		a0.text(x0 + w / 2, 1.8, lab, ha="center", va="center", fontsize=7.6, color=FS.INK)
	a0.annotate("", xy=(75, 0.6), xytext=(-2, 0.6), arrowprops=dict(arrowstyle="-|>", color=FS.INK2, lw=0.9))
	a0.plot([0, 0], [0.45, 0.75], color=FS.INK, lw=1.2); a0.text(0, 0.05, "Time 0: first step record", fontsize=7.2, color=FS.INK2)
	a0.text(18, 0.05, "Start: later of the day after baseline ends and the day after registration", fontsize=7.2, color=FS.INK2)
	a0.text(-3, 2.95, "A", fontsize=11, fontweight="bold", va="top")
	# A (cont.): flow, left to right
	a1.set_xlim(0, 100); a1.set_ylim(0, 10); a1.axis("off")
	boxes = [(f"Common cohort\nn={f['common']}", 1), (f"Time 0 within range\nn={f['common'] - f['no_t0']}", 26.5),
	         (f"≥4 watch-wear days\nat baseline\nn={f['common'] - f['no_t0'] - f['collecting'] - f['low_wear']}", 52), (f"Outcome window closed\nanalyzed n={f['analysed']}", 77.5)]
	exc = [f"No step record from\n30 days before registration: {f['no_t0']}", f"Baseline still collecting: {f['collecting']}\nFewer than 4 wear days: {f['low_wear']}",
	       f"Outcome window not\nyet closed: {f['pending']}"]
	for i, (t, x) in enumerate(boxes):
		last = i == len(boxes) - 1
		a1.add_patch(FancyBboxPatch((x, 5.6), 21.5, 3.6, boxstyle="round,pad=0.25", fc="#e3eefb" if last else "white", ec=HI if last else FS.INK2, lw=1.2 if last else 0.8))
		a1.text(x + 10.75, 7.4, t, ha="center", va="center", fontsize=7.8, color=FS.INK, fontweight="bold" if last else None)
		if not last:
			a1.annotate("", xy=(boxes[i + 1][1] - 0.4, 7.4), xytext=(x + 21.9, 7.4), arrowprops=dict(arrowstyle="-|>", color=FS.INK2, lw=0.9))
			xm = x + 23.6
			a1.annotate("", xy=(xm, 3.9), xytext=(xm, 7.3), arrowprops=dict(arrowstyle="-|>", color=FS.MUTED, lw=0.8))
			a1.text(xm, 3.6, exc[i], ha="center", va="top", fontsize=6.9, color=FS.INK2)
	a1.text(77.5 + 10.75, 4.9, f"High engagement {int(A1.A.sum())}, low {int((1 - A1.A).sum())}\n(median split at {A1.MED:.0f} login days)", ha="center", va="top", fontsize=7, color=FS.INK2)
	# B: who is measured - analyzable share of each group by indicator
	t2 = TB.parse("Table2").set_index("indicator")
	nh, nl = int(A1.A.sum()), int((1 - A1.A).sum())
	order = [k for k in A1.ORDER if k in t2.index]
	lab = {"steps": "Steps", "active_min": "Exercise minutes", "weight": "Weight", "fat_pct": "Body fat", "muscle": "Skeletal muscle mass", "sbp": "Systolic BP",
	       "dbp": "Diastolic BP", "sleep_min": "Sleep", "spo2": "SpO2", "grip": "Grip strength"}
	y = np.arange(len(order))[::-1]
	FS.vgrid(a2)
	rows = []
	for yy, k in zip(y, order):
		r = t2.loc[k]; ph, pl = 100 * r.n_high / nh, 100 * r.n_low / nl
		a2.hlines(yy, min(ph, pl), max(ph, pl), color=FS.NEUTRAL, lw=2.2)
		a2.scatter(ph, yy, color=HI, s=34, zorder=3); a2.scatter(pl, yy, color=LO, marker="s", s=32, zorder=3)
		a2.text(103, yy, f"{int(r.n_high)}/{int(r.n_low)}", va="center", fontsize=7, color=FS.INK2)
		rows.append(dict(indicator=k, pct_high=ph, pct_low=pl))
	a2.text(103, len(order) - 0.4, "n high/low", fontsize=7, color=FS.INK2)
	a2.set_yticks(y); a2.set_yticklabels([lab[k] for k in order], fontsize=7.8); a2.set_xlim(0, 101)
	a2.set_xlabel("Users with analyzable baseline and outcome data, % of engagement group")
	FS.panel(a2, "B", "Data availability by indicator")
	from matplotlib.lines import Line2D
	a2.legend(handles=[Line2D([], [], marker="o", ls="", color=HI, label=f"High engagement (of {nh})"), Line2D([], [], marker="s", ls="", color=LO, label=f"Low engagement (of {nl})")],
	          loc="upper left", fontsize=7)
	save(fig, "fig2_design_flow.png")
	return pd.DataFrame(rows)


if __name__ == "__main__":
	print(fig_design()); fig_trajectories(); print(fig_gap()); fig_adjustment()
