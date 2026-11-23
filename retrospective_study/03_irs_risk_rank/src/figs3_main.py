# -*- coding: utf-8 -*-
"""Main-text figures for study 03 that show what is specific to this study: the crosswalk between IRS model versions,
band-to-band transitions by engagement group, and the robustness of the primary estimate to the outcome definition.
Reads the frozen analysis data through ana3 and the result workbook written by report3. Run from retrospective_study/."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "03_irs_risk_rank/src"))
sys.path.insert(0, str(ROOT / "00_common/src"))
import ana3 as A3  # noqa: E402
import figstyle as FS  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

FS.use()
OUT = A3.OUT
TB = pd.ExcelFile(OUT / "tables_03.xlsx")
HI, LO = FS.S03["high"], FS.S03["low"]
EN = {d: d.replace("_", " ").capitalize() for d in A3.DIS}
EN.update({"type_2_diabetes": "Type 2 diabetes", "chronic_obstructive_pulmonary_disease": "COPD", "alzheimers_disease": "Alzheimer disease",
           "non-alcoholic_fatty_liver_disease": "NAFLD", "benign_prostatic_hyperplasia": "Benign prostatic hyperplasia"})
BANDS = ["1-20", "21-40", "41-60", "61-80", "81-100"]


def save(fig, name):
	fig.savefig(OUT / name, facecolor="white"); plt.close(fig); print("wrote", name)


def false_movement(B=1000, seed=303):
	"""Bridge pairs carry the same inputs under both model versions, so any band change between the pre-update representation
	(service rank before the crosswalk, cross-validated converted rank after it) and the updated-model rank is artificial.
	False down: updated band lower than the baseline band, among pairs whose baseline band is above the lowest (the outcome's
	eligible pairs); false up: updated band higher. 95% CI: users resampled with replacement."""
	V = pd.read_pickle(A3.FZ / "VR.pkl")
	band = lambda r: np.floor((np.asarray(r, float) - 1) / 20)
	rows = []
	rng = np.random.default_rng(seed)
	for sc in ["irs", "mrs"]:
		v = V[(V.score == sc) & V.truth.notna() & V.pred.notna() & V.raw.notna()]
		g = v.g.values; ug = np.unique(g); gi = np.searchsorted(ug, g)
		bt = band(v.truth.values)
		for when, base in [("before", band(v.raw.values)), ("after", band(v.pred.values))]:
			el = base > 0
			dn = ((bt < base) & el).astype(float); up = (bt > base).astype(float)
			def rates(w):
				return 100 * np.sum(w * dn) / np.sum(w * el), 100 * np.sum(w * up) / np.sum(w)
			est = rates(np.ones(len(v)))
			bs = []
			for _ in range(B):
				c = np.bincount(rng.integers(0, len(ug), len(ug)), minlength=len(ug))[gi].astype(float)
				bs.append(rates(c))
			bs = np.array(bs)
			for j, kind in enumerate(["down", "up"]):
				rows.append(dict(score=sc, when=when, kind=kind, rate=est[j], lo=np.percentile(bs[:, j], 2.5), hi=np.percentile(bs[:, j], 97.5),
				                 pairs=int(el.sum()) if kind == "down" else len(v), users=len(ug)))
	return pd.DataFrame(rows)


# ------------------------------------------------------------------ Figure 3: linking model versions
def fig_crosswalk():
	m = A3.MET[(A3.MET.sex == "all")]
	fig, axes = plt.subplots(1, 3, figsize=(10.6, 6.6), gridspec_kw={"width_ratios": [1.15, 1.15, 0.85], "wspace": 0.1})
	order = m[m.score == "irs"].sort_values("rate").disease.tolist()
	y = np.arange(len(order))
	for ax, sc, title in [(axes[0], "irs", "IRS"), (axes[1], "mrs", "MRS")]:
		t = m[m.score == sc].set_index("disease").reindex(order)
		FS.vgrid(ax)
		ax.axvline(95, color=FS.MUTED, lw=0.8, ls=(0, (3, 2)))
		ax.hlines(y, 100 * t.raw_rate, 100 * t.rate, color=FS.NEUTRAL, lw=2.2, zorder=1)
		ax.scatter(100 * t.raw_rate, y, s=26, facecolor="white", edgecolor=FS.INK2, lw=1, zorder=2, label="Before crosswalk")
		ax.scatter(100 * t.rate, y, s=30, color=HI, zorder=3, label="After crosswalk (cross-validated)")
		xlo = 5 * np.floor(100 * min(m[m.score.isin(["irs", "mrs"])].raw_rate.min(), m[m.score.isin(["irs", "mrs"])].rate.min()) / 5) - 1
		ax.set_xlim(xlo, 101); ax.set_ylim(-0.8, len(order) - 0.2)
		ax.set_xlabel("Bridge pairs in the same 20-rank band, %")
		FS.panel(ax, "A" if sc == "irs" else "B", f"{title}: band agreement")
		ax.set_yticks(y); ax.set_yticklabels([EN[d] for d in order] if sc == "irs" else [], fontsize=7)
		if sc == "irs":
			ax.text(95.3, len(order) - 0.6, "95%", fontsize=7, color=FS.MUTED)
	# C: false band movement on bridge pairs (same inputs under both versions), before and after the crosswalk, user-bootstrap 95% CI
	ax = axes[2]
	fm = false_movement()
	FS.vgrid(ax)
	ylab, yy = [], 0
	ypos = []
	for sc in ["irs", "mrs"]:
		for kind in ["down", "up"]:
			for when, col, hat in [("before", FS.NEUTRAL, None), ("after", HI if kind == "down" else LO, None)]:
				r = fm[(fm.score == sc) & (fm.kind == kind) & (fm.when == when)].iloc[0]
				ax.barh(yy, r.rate, height=0.72, color=col, edgecolor="white", hatch="////" if (kind == "up" and when == "after") else None)
				ax.hlines(yy, r.lo, r.hi, color=FS.INK, lw=0.9)
				ax.text(r.hi + 0.25, yy, f"{r.rate:.1f}", va="center", fontsize=6.8, color=FS.INK)
				ypos.append(yy); ylab.append(f"{sc.upper()} {'false down' if kind == 'down' else 'false up'}, {when}")
				yy -= 1
			yy -= 0.4
		yy -= 0.6
	ax.set_yticks(ypos); ax.set_yticklabels(ylab, fontsize=6.8); ax.yaxis.tick_right(); ax.tick_params(axis="y", length=0)
	ax.set_xlim(0, 8); ax.set_xlabel("Bridge pairs, %")
	FS.panel(ax, "C", "False band movement")
	h, l = axes[0].get_legend_handles_labels()
	fig.legend(h, l, loc="lower left", bbox_to_anchor=(0.12, -0.035), ncol=2, fontsize=7.5)
	save(fig, "fig3_crosswalk.png")
	return dict(med_before=float(100 * m[m.score == "irs"].raw_rate.median()), med_after=float(100 * m[m.score == "irs"].rate.median()),
	            false_movement=fm.round(2).to_dict("records"))


# ------------------------------------------------------------------ Figure 4: transitions between bands by engagement group
def fig_transitions():
	out0 = A3.rebuild(None)
	rc, rf = out0["irs"]; bc, bf = A3.bands(rc), A3.bands(rf)
	ok = np.isfinite(rc) & np.isfinite(rf)
	grp = A3.A[A3.LB.ui.values]
	cmap = LinearSegmentedColormap.from_list("g", FS.SEQ_GREEN)
	fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.4), gridspec_kw={"wspace": 0.25})
	res = {}
	for ax, g, lab in [(axes[0], 1, "High engagement"), (axes[1], 0, "Low engagement")]:
		s = ok & (grp == g)
		M = np.zeros((5, 5))
		for i in range(5):
			for j in range(5):
				M[i, j] = np.sum(s & (bc == i) & (bf == j))
		R = M / M.sum(axis=1, keepdims=True)
		ax.imshow(R[::-1], cmap=cmap, vmin=0, vmax=1, aspect="equal")
		for i in range(5):
			for j in range(5):
				v = R[::-1][i, j]
				ax.text(j, i, f"{100 * v:.0f}", ha="center", va="center", fontsize=8, color="white" if v > 0.55 else FS.INK)
		# outline the cells that count as moving to a lower band (below the diagonal, baseline band above the lowest)
		for i in range(1, 5):
			for j in range(0, i):
				ax.add_patch(plt.Rectangle((j - 0.5, 4 - i - 0.5), 1, 1, fill=False, ec=FS.INK, lw=1.1))
		ax.set_xticks(range(5)); ax.set_xticklabels(BANDS, fontsize=7.5); ax.set_yticks(range(5)); ax.set_yticklabels(BANDS[::-1], fontsize=7.5)
		ax.set_xlabel("Follow-up IRS band (ranks)"); ax.set_ylabel("Baseline IRS band (ranks)" if g == 1 else "")
		el = s & (bc > 0); down = np.sum(el & (bf < bc)) / np.sum(el)
		n_u = int(np.sum(A3.A == g))
		FS.panel(ax, "A" if g == 1 else "B", f"{lab} ({n_u} users)")
		ax.text(0, -0.2, f"{int(s.sum())} user-disease pairs; moved to a lower band\n(outlined cells, baseline above ranks 1-20): {100 * down:.1f}%", transform=ax.transAxes, fontsize=7.5, color=FS.INK2, va="top")
		for sp in ax.spines.values():
			sp.set_visible(False)
		ax.tick_params(length=0)
		res[lab] = dict(pairs=int(s.sum()), down=float(100 * down))
	sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, 100))
	cb = fig.colorbar(sm, ax=axes, fraction=0.025, pad=0.02); cb.set_label("Row percentage", fontsize=7.5); cb.outline.set_visible(False)
	save(fig, "fig4_transition_matrix.png")
	return res


# ------------------------------------------------------------------ Figure 5: specification curve for the primary contrast
SPEC = [  # key, disease set, band scheme, denominator, baseline window, aggregation, weighting, exposure
	("main", "All", "5 bands of 20 ranks", "Above lowest", "56 d", "User share", "Truncated IPTW", "All login days"),
	("pass18", "Validated 18", "5 bands of 20 ranks", "Above lowest", "56 d", "User share", "Truncated IPTW", "All login days"),
	("bands3", "All", "3 bands (1-34, 35-67, 68-100)", "Above lowest", "56 d", "User share", "Truncated IPTW", "All login days"),
	("bands10", "All", "10 bands of 10 ranks", "Above lowest", "56 d", "User share", "Truncated IPTW", "All login days"),
	("shift10", "All", "20-rank bands shifted by 10 (6 bands)", "Above lowest", "56 d", "User share", "Truncated IPTW", "All login days"),
	("incl_lowest", "All", "5 bands of 20 ranks", "All bands", "56 d", "User share", "Truncated IPTW", "All login days"),
	("base28", "All", "5 bands of 20 ranks", "Above lowest", "28 d", "User share", "Truncated IPTW", "All login days"),
	("pooled", "All", "5 bands of 20 ranks", "Above lowest", "56 d", "Pooled pairs", "Truncated IPTW", "All login days"),
	("no_trunc", "All", "5 bands of 20 ranks", "Above lowest", "56 d", "User share", "Untruncated IPTW", "All login days"),
	("unadjusted", "All", "5 bands of 20 ranks", "Above lowest", "56 d", "User share", "None (unadjusted)", "All login days"),
	("susp1", "All", "5 bands of 20 ranks", "Above lowest", "56 d", "User share", "Truncated IPTW", "Token-only days removed"),
]
DIMS = ["Diseases", "Band scheme", "Denominator", "Baseline window", "Aggregation", "Weighting", "Exposure"]


def fig_spec():
	t2 = TB.parse("Table2").set_index("key"); ss = TB.parse("S_sensitivity").set_index("key")
	rows = []
	for spec in SPEC:
		r = t2.loc["main"] if spec[0] == "main" else ss.loc[spec[0]]
		rows.append(dict(key=spec[0], est=r.diff_pp, lo=r.diff_lo, hi=r.diff_hi, choices=spec[1:]))
	D = pd.DataFrame(rows).sort_values("est").reset_index(drop=True)
	opts = {k: [] for k in DIMS}
	for spec in SPEC:
		for k, v in zip(DIMS, spec[1:]):
			if v not in opts[k]:
				opts[k].append(v)
	nrow = sum(len(v) for v in opts.values())
	fig, (a0, a1) = plt.subplots(2, 1, figsize=(7.6, 8.4), sharex=True, gridspec_kw={"height_ratios": [1, 1.9], "hspace": 0.06})
	x = np.arange(len(D))
	FS.hgrid(a0)
	a0.axhline(0, color=FS.AXIS, lw=0.9)
	for i, r in D.iterrows():
		main = r.key == "main"
		a0.vlines(i, r.lo, r.hi, color=HI if main else FS.INK2, lw=1.6 if main else 1.1)
		a0.scatter(i, r.est, s=46 if main else 30, color=HI if main else "white", edgecolor=HI if main else FS.INK2, lw=1.2, zorder=3,
		           marker="D" if main else "o")
	a0.set_ylabel("Difference in share moving to a\nlower band, percentage points")
	FS.panel(a0, "A", "Estimate and 95% CI under each outcome definition")
	im = int(D.index[D.key == "main"][0])
	a0.annotate("Primary", (im, D.loc[im, "hi"]), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=7.5, color=HI, fontweight="bold")
	# choice matrix
	yl, yt, ypos, hdr, y0 = [], [], {}, [], 0
	for k in DIMS:
		hdr.append((k, y0)); y0 += 0.9
		for v in opts[k]:
			yl.append(v); yt.append(y0); ypos[(k, v)] = y0; y0 += 1
		y0 += 0.25
	for i, r in D.iterrows():
		for k, v in zip(DIMS, r.choices):
			for vv in opts[k]:
				a1.scatter(i, ypos[(k, vv)], s=20, color=FS.NEUTRAL if vv != v else (HI if r.key == "main" else FS.INK), zorder=2)
	a1.set_yticks(yt); a1.set_yticklabels(yl, fontsize=7); a1.invert_yaxis()
	for k, yh in hdr:
		a1.text(-0.75, yh + 0.25, k, fontsize=7.2, fontweight="bold", ha="right", va="center", color=FS.INK, clip_on=False)
	a1.set_xticks([]); a1.spines["bottom"].set_visible(False); a1.spines["left"].set_visible(False); a1.tick_params(axis="y", length=0)
	a1.set_xlim(-0.7, len(D) - 0.3)
	FS.panel(a1, "B", "Analytic choices (dark dot = choice used)")
	save(fig, "fig5_specification_curve.png")
	return dict(range=(float(D.est.min()), float(D.est.max())), n=len(D))


def _band_poly(ax, x0, x1, y0a, y0b, y1a, y1b, color, alpha=0.75, z=1):
	"""Filled ribbon from [y0a, y0b] at x0 to [y1a, y1b] at x1 with smooth (cubic) edges."""
	t = np.linspace(0, 1, 40); sm = 3 * t ** 2 - 2 * t ** 3
	xs = x0 + (x1 - x0) * t
	top = y0b + (y1b - y0b) * sm; bot = y0a + (y1a - y0a) * sm
	ax.fill_between(xs, bot, top, color=color, alpha=alpha, lw=0, zorder=z)


# ------------------------------------------------------------------ Figure 4: alluvial of band transitions by engagement group
DIRC = {"down": "#008300", "same": "#cfcec8", "up": "#e87ba4"}


def fig_alluvial():
	out0 = A3.rebuild(None)
	rc, rf = out0["irs"]; bc, bf = A3.bands(rc), A3.bands(rf)
	ok = np.isfinite(rc) & np.isfinite(rf)
	grp = A3.A[A3.LB.ui.values]
	fig, axes = plt.subplots(1, 2, figsize=(10, 5.6), gridspec_kw={"wspace": 0.42})
	res = {}
	gap = 0.012
	for ax, g, lab in [(axes[0], 1, "High engagement"), (axes[1], 0, "Low engagement")]:
		s_ = ok & (grp == g)
		M = np.array([[np.sum(s_ & (bc == i) & (bf == j)) for j in range(5)] for i in range(5)], float)
		P = M / M.sum()
		left = P.sum(axis=1); right = P.sum(axis=0)
		# stacked positions, band 5 (highest risk) on top
		def stack(v):
			pos, y = {}, 0.0
			for i in range(5):
				pos[i] = (y, y + v[i]); y += v[i] + gap
			return pos
		L, R = stack(left), stack(right)
		lo_off = {i: L[i][0] for i in range(5)}; ro_off = {j: R[j][0] for j in range(5)}
		# draw same first, then up, then down on top
		flows = [(i, j) for i in range(5) for j in range(5) if P[i, j] > 0]
		flows.sort(key=lambda ij: {"same": 0, "up": 1, "down": 2}["same" if ij[0] == ij[1] else ("up" if ij[1] > ij[0] else "down")])
		# offsets must follow a fixed order within each node, independent of drawing order
		lpos, rpos = {}, {}
		for i in range(5):
			y = L[i][0]
			for j in range(5):
				lpos[(i, j)] = (y, y + P[i, j]); y += P[i, j]
		for j in range(5):
			y = R[j][0]
			for i in range(5):
				rpos[(i, j)] = (y, y + P[i, j]); y += P[i, j]
		for (i, j) in flows:
			kind = "same" if i == j else ("up" if j > i else "down")
			(a0, b0), (a1, b1) = lpos[(i, j)], rpos[(i, j)]
			_band_poly(ax, 0.06, 0.94, a0, b0, a1, b1, DIRC[kind], alpha=0.85 if kind != "same" else 0.7, z={"same": 1, "up": 2, "down": 3}[kind])
		for i in range(5):
			ax.add_patch(plt.Rectangle((0, L[i][0]), 0.06, left[i], color=FS.INK2, lw=0))
			ax.add_patch(plt.Rectangle((0.94, R[i][0]), 0.06, right[i], color=FS.INK2, lw=0))
			ax.text(-0.02, (L[i][0] + L[i][1]) / 2, f"{BANDS[i]}  {100 * left[i]:.0f}%", ha="right", va="center", fontsize=7.4)
			ax.text(1.02, (R[i][0] + R[i][1]) / 2, f"{100 * right[i]:.0f}%  {BANDS[i]}", ha="left", va="center", fontsize=7.4)
		ax.set_xlim(-0.02, 1.02); ax.set_ylim(-0.01, 1 + 4 * gap + 0.01); ax.axis("off")
		ax.text(0.03, 1.07, "Baseline band", ha="center", fontsize=7.6, color=FS.INK2, transform=ax.transData)
		ax.text(0.97, 1.07, "Follow-up band", ha="center", fontsize=7.6, color=FS.INK2, transform=ax.transData)
		el = s_ & (bc > 0)
		dn, up_, sm_ = np.sum(el & (bf < bc)) / el.sum(), np.sum(s_ & (bf > bc)) / s_.sum(), np.sum(s_ & (bf == bc)) / s_.sum()
		ax.set_title(f"{'A' if g == 1 else 'B'}  {lab} ({int(np.sum(A3.A == g))} users, {int(s_.sum())} user-disease pairs)", loc="left", pad=22, fontsize=9.5, fontweight="bold")
		ax.text(0.5, -0.06, f"Lower band {100 * dn:.1f}% of eligible pairs · same {100 * sm_:.1f}% · higher {100 * up_:.1f}% of all pairs",
		        ha="center", fontsize=7.4, color=FS.INK2, transform=ax.transData)
		res[lab] = dict(pairs=int(s_.sum()), down_eligible=float(100 * dn), same=float(100 * sm_), up=float(100 * up_))
	from matplotlib.patches import Patch
	fig.legend(handles=[Patch(color=DIRC["down"], label="Moved to a lower band"), Patch(color=DIRC["same"], label="Same band"), Patch(color=DIRC["up"], label="Moved to a higher band")],
	           loc="lower center", ncol=3, fontsize=7.6, bbox_to_anchor=(0.5, -0.02))
	save(fig, "fig4_alluvial.png")
	return res


# ------------------------------------------------------------------ Figure 2: timeline and Sankey-style participant flow
def fig_design():
	import json
	from matplotlib.patches import FancyBboxPatch
	fl = json.load(open(A3.FZ / "x7b_flow.json"))
	n_conv, n_same = int((A3.Dr.model_f == "P1").sum()), int((A3.Dr.model_f == "P0").sum())
	fig = plt.figure(figsize=(10.4, 6.6))
	a0 = fig.add_axes([0.03, 0.80, 0.94, 0.17]); a1 = fig.add_axes([0.03, 0.02, 0.94, 0.74])
	# A: one user's timeline with the model update
	a0.set_xlim(-5, 210); a0.set_ylim(0, 3); a0.axis("off")
	a0.add_patch(FancyBboxPatch((0, 1.0), 56, 1.6, boxstyle="round,pad=0.02,rounding_size=1.2", fc="#f1f0ec", ec="none"))
	a0.text(28, 2.25, "Eligible baseline period: 0-56 days after registration", ha="center", va="center", fontsize=7.0, color=FS.INK2)
	xb = 20
	a0.plot([xb], [1.55], marker="o", ms=7, color=FS.INK, zorder=4); a0.text(xb, 1.15, "Baseline IRS", ha="center", va="top", fontsize=7.2)
	a0.add_patch(FancyBboxPatch((xb + 1, 1.35), 28, 0.4, boxstyle="round,pad=0.02,rounding_size=0.2", fc="#bfe0b8", ec="none", zorder=3))
	a0.text(xb + 15, 1.95, "Exposure: login days in the 28 days after baseline", ha="left", va="center", fontsize=7.0)
	a0.plot([xb + 120], [1.55], marker="o", ms=7, color=FS.INK, zorder=4)
	a0.text(xb + 120, 1.15, "Follow-up IRS (≥90 days after baseline,\nchanged medical input)", ha="center", va="top", fontsize=7.0)
	a0.annotate("", xy=(xb + 118, 1.55), xytext=(xb + 30, 1.55), arrowprops=dict(arrowstyle="-", color=FS.MUTED, lw=0.8, ls=(0, (2, 2))))
	a0.annotate("", xy=(208, 0.6), xytext=(-4, 0.6), arrowprops=dict(arrowstyle="-|>", color=FS.INK2, lw=0.9))
	a0.plot([0, 0], [0.45, 0.75], color=FS.INK, lw=1.2); a0.text(0, 0.05, "Registration (first login)", fontsize=7, color=FS.INK2)
	a0.plot([95, 95], [0.3, 2.7], color=LO, lw=1.4, ls=(0, (3, 2)))
	a0.text(96.5, 2.55, "IRS model update\n(pre-update baseline\nconverted with the crosswalk)", fontsize=6.8, color=FS.INK, va="top")
	a0.text(-5, 2.95, "A", fontsize=11, fontweight="bold", va="top")
	# B: Sankey-style flow; ribbon width proportional to users
	a1.set_xlim(0, 100); a1.set_ylim(0, 100); a1.axis("off")
	a1.text(0, 99, "B", fontsize=11, fontweight="bold", va="top")
	stages = [("Users linked\nto the service", fl["site_users"]), ("Common\ncohort", fl["common_cohort"]), ("≥1 complete\nIRS", fl["with_complete_irs"]),
	          ("Baseline IRS ≤56 days,\npre-update model", fl["baseline_model_ok"]), ("Analyzed", fl["final"])]
	excl = [[("Operator or test accounts", fl["excl_operator_test"]), ("No login", fl["no_login"]), ("Registered too recently or withdrew early", fl["not_common"])],
	        [("No IRS", fl["excl_no_irs"]), ("No complete IRS", fl["excl_no_complete"])],
	        [("First complete IRS after day 56", fl["excl_after_window"]), ("Baseline IRS from the updated model", fl["excl_post_july_baseline"])],
	        [("No complete IRS ≥90 days later", fl["no_complete_90d"]), ("No changed medical input", fl["no_new_checkup"]), ("Changed input only after the next update", fl["new_checkup_only_later"])]]
	scale = 52.0 / fl["site_users"]; top = 92; xs = [3, 23, 43, 63, 83]; bw = 3.0
	for k, ((lab, n), x) in enumerate(zip(stages, xs)):
		h = n * scale
		a1.add_patch(plt.Rectangle((x, top - h), bw, h, color=HI if k == len(stages) - 1 else FS.INK2, lw=0))
		a1.text(x + bw / 2, top + 1.5, f"{lab}\nn={n}", ha="center", va="bottom", fontsize=7.3, color=FS.INK, fontweight="bold" if k == len(stages) - 1 else None)
		if k < len(stages) - 1:
			n2 = stages[k + 1][1]; h2 = n2 * scale
			_band_poly(a1, x + bw, xs[k + 1], top - h2, top, top - h2, top, "#d6d5cf", alpha=1)
			# exclusions leave from the bottom of the bar and fall to labels
			y = top - h2
			ly = 34 - 0
			for m, (el, ne) in enumerate(excl[k]):
				he = ne * scale
				if he <= 0:
					continue
				yb = y - he
				tx = x + bw + 5.5; ty = 30 - 8.5 * m
				_band_poly(a1, x + bw, tx, yb, y, ty - he / 2, ty + he / 2, "#efc9b9", alpha=0.9)
				a1.text(tx + 0.6, ty, f"{el}: {ne}", va="center", fontsize=6.7, color=FS.INK2)
				y = yb
	# final split
	xf = xs[-1] + bw; h = fl["final"] * scale
	hc = n_conv * scale
	_band_poly(a1, xf, xf + 7, top - hc, top, top - hc - 1, top - 1, "#d6ecd2", alpha=1)
	_band_poly(a1, xf, xf + 7, top - h, top - hc, top - h - 4, top - hc - 4, "#ece9f8", alpha=1)
	a1.text(xf + 7.4, top - hc / 2 - 1, f"Follow-up from the\nupdated model: {n_conv}\n(baseline converted)", fontsize=6.8, va="center")
	a1.text(xf + 7.4, top - hc - (h - hc) / 2 - 4, f"Same model version: {n_same}", fontsize=6.8, va="center")
	a1.text(xs[-1] + bw / 2, top - h - 3, f"High engagement {int(A3.A.sum())}\nlow {int((1 - A3.A).sum())}\n(median {A3.MED:.0f} login days)", ha="center", va="top", fontsize=6.8, color=FS.INK2)
	save(fig, "fig2_design_flow.png")


# ------------------------------------------------------------------ crosswalk checks written to a workbook (post hoc)
def crosswalk_checks():
	"""Out-of-range baseline values, shift versus clip for the primary point estimate, crosswalk kinds per score, and false band
	movement on bridge pairs. The validation predictions in VR.pkl were made by x8b.py with the same CW class and its default
	extrapolation ('shift'), so validation and analysis use the same rule."""
	import xwlib as X
	from collections import Counter
	rows = []
	tot = out_ = 0
	kinds = {c: Counter() for c in ["irs", "mrs", "lrs"]}
	for c in kinds:
		for d in A3.DIS:
			for sx in X.SEXES:
				xo, xn, r = A3.BRG[(d, c, sx)]
				ix = np.where(A3.P1 & (A3.LB.disease.values == d) & (A3.LB.sex.values == sx))[0]
				if not len(ix):
					continue
				cw = X.CW(xo[r], xn[r], X.SCALE[c], "shift"); kinds[c][cw.kind] += 1
				if c == "irs":
					pb = A3.LB["irs_p_b"].values[ix]; ok = np.isfinite(pb)
					tot += int(ok.sum()); out_ += int(cw.outside(pb[ok]).sum())
	for c, k in kinds.items():
		for kind, n in k.items():
			rows.append(dict(check="crosswalk kind (disease x sex with converted rows)", score=c, item=kind, value=n))
	rows.append(dict(check="converted IRS baseline values", score="irs", item="total", value=tot))
	rows.append(dict(check="converted IRS baseline values", score="irs", item="outside the bridge range", value=out_))
	cnt = np.ones(len(A3.users))
	e_shift = A3.representative(A3.rebuild(None), cnt)
	orig = X.CW

	class CWclip(orig):
		def __init__(self, xo, xn, scale="logit", extrap="shift"):
			super().__init__(xo, xn, scale, "clip")
	X.CW = CWclip; A3.X.CW = CWclip
	try:
		e_clip = A3.representative(A3.rebuild(None), cnt)
	finally:
		X.CW = orig; A3.X.CW = orig
	rows.append(dict(check="primary difference, percentage points", score="irs", item="beyond-range shift (primary)", value=100 * e_shift["diff"]))
	rows.append(dict(check="primary difference, percentage points", score="irs", item="beyond-range clip", value=100 * e_clip["diff"]))
	fm = false_movement()
	with pd.ExcelWriter(OUT / "crosswalk_checks_03.xlsx") as xw:
		pd.DataFrame(rows).to_excel(xw, sheet_name="checks", index=False)
		fm.to_excel(xw, sheet_name="false_movement", index=False)
		pd.DataFrame({"note": [crosswalk_checks.__doc__.strip(), false_movement.__doc__.strip()]}).to_excel(xw, sheet_name="Notes", index=False)
	print("wrote crosswalk_checks_03.xlsx")
	return pd.DataFrame(rows)


if __name__ == "__main__":
	fig_design(); print(fig_crosswalk()); print(fig_alluvial()); print(fig_spec()); print(crosswalk_checks())
