# -*- coding: utf-8 -*-
"""Study 01 post hoc robustness analyses (plan: 00_common/docs/local/견고성분석계획, section 3).

Run from retrospective_study/:  python3 01_wearable_metrics/src/robust1.py [--boot 1000] [--perm 500] [--workers 10]
1. Multiverse: per indicator, exposure (login days, login days without suspect rule-1 days, feature-use days) x contrast
   (median split, top vs bottom third, continuous) x estimator (IPTW + outcome model, outcome model only, IPTW + baseline
   only, overlap weights + outcome model; continuous: outcome model only) x sample (all, without platform 20301102).
2. Observability: adjusted risk difference / ratio of having analysable data, per indicator.
3. Collection-gap rule grid (ratio threshold, reference window, minimum run) for four sources, and the exercise estimate
   for every distinct gap set.
The bootstrap uses the seeds of ana1.py, so the primary specification reproduces the main analysis. Writes
robust_01.pkl / robust_01.xlsx to 01_wearable_metrics/01_Results/analysis/ (git-ignored). Prints aggregates only.
"""
import argparse
import itertools
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "00_common/src")); sys.path.insert(0, str(ROOT / "01_wearable_metrics/src"))
_argv = sys.argv; sys.argv = [sys.argv[0]]
import ana1 as A1  # noqa: E402
sys.argv = _argv
import multiverse as MV  # noqa: E402
import statlib as S  # noqa: E402

OUT = A1.OUT
USERS, U = A1.USERS, A1.U
NU = len(USERS)
INFER = [k for k in A1.ORDER if k != "grip"]  # grip had no stable interval in the main analysis; kept in the tables

# ---------------------------------------------------------------- exposures (users x 3, permuted jointly by rows)
_ev = pd.read_csv(A1.EX / "event_days.csv", parse_dates=["d"]); _ev = _ev[(_ev.n_action > 0) & _ev.user_id.isin(USERS)]
_ed = {u: g.d.values for u, g in _ev.groupby("user_id")}
_s0, _s1 = pd.to_datetime(A1.T.loc[USERS, "노출_시작일"]), pd.to_datetime(A1.T.loc[USERS, "노출_종료일"])
ACTION = np.array([float(np.sum((_ed.get(u, np.array([], "datetime64[ns]")) >= np.datetime64(a)) & (_ed.get(u, np.array([], "datetime64[ns]")) <= np.datetime64(b))))
                   for u, a, b in zip(USERS, _s0, _s1)])
EXPOS = ["login", "login_s1", "action"]
EXPO0 = np.column_stack([U.exp.values, U.exp_s1.values, ACTION])
CUTS = {e: dict(med=np.median(EXPO0[:, j]), t1=np.percentile(EXPO0[:, j], 100 / 3), t2=np.percentile(EXPO0[:, j], 200 / 3),
                q25=np.percentile(EXPO0[:, j], 25), q75=np.percentile(EXPO0[:, j], 75)) for j, e in enumerate(EXPOS)}  # fixed from the original data
CONTRASTS = ["median", "tertile", "continuous"]
ESTS = ["dr", "reg", "ipw", "ow"]
SAMPLES = ["all", "no1102"]
SPECS = [(k, e, c, m, s) for k in A1.ORDER for e in EXPOS for c in CONTRASTS for m in (ESTS if c != "continuous" else ["reg"]) for s in SAMPLES]
FACTORS = ["indicator", "exposure", "contrast", "estimator", "sample"]
PRIMARY = lambda k: (k, "login", "median", "dr", "all")

# cached per indicator (independent of the resample counts); the exercise cache also depends on the gap set
_DD = {}
def ddata(k, gap_key="main"):
	key = (k, gap_key)
	if key not in _DD:
		_DD[key] = A1.daily_data(A1.X, USERS, k)
	return _DD[key]
_PD = {k: A1.point_data(A1.P, USERS, k) for k in A1.POINT}


def ps_and_w(Uu, a, c, kind):
	"""Propensity score as in ana1.ps_fit (Firth fallback); stabilized IPTW truncated at the 1st/99th percentiles or overlap weights."""
	Xp = Uu[A1.PSV].values; Xp = Xp[:, S.independent_columns(Xp)]
	Xc = S.add_const(Xp)
	b, ok = S.glm_logit(Xc, a, c)
	if not ok or not np.all(np.isfinite(b)) or np.max(np.abs(b)) > 15:
		b, ok = S.firth_logit(Xc, a, c)
	ok = bool(ok and np.all(np.isfinite(b)))
	ps = np.clip(S.expit(Xc @ b), 1e-3, 1 - 1e-3)
	if kind == "ow":
		return MV.overlap_weights(ps, a), ok
	p1 = np.average(a, weights=c)
	w = np.where(a == 1, p1 / ps, (1 - p1) / (1 - ps))
	lo, hi = np.percentile(np.repeat(w, c.astype(int)), (1, 99)); return np.clip(w, lo, hi), ok


def group(x, e, contrast):
	"""Returns (a, keep) for a contrast; continuous returns the exposure itself and keep=all."""
	cu = CUTS[e]
	if contrast == "median":
		return (x >= cu["med"]).astype(float), np.ones(len(x), bool)
	if contrast == "tertile":
		return (x >= cu["t2"]).astype(float), (x >= cu["t2"]) | (x <= cu["t1"])
	return x.astype(float), np.ones(len(x), bool)


def spec_effect(k, cnt, expo, e, contrast, est, sample, gap_key="main"):
	"""Adjusted difference (high - low, or 75th - 25th percentile of exposure for the continuous contrast) for one spec."""
	x = expo[:, EXPOS.index(e)]
	a_all, keep_all = group(x, e, contrast)
	cnt = cnt * keep_all * (1.0 if sample == "all" else (U.plat1102.values == 0))
	cont = contrast == "continuous"
	if k in A1.DAILY:
		keep, base, rows = ddata(k, gap_key)
		ix = np.array([A1.UIDX[u] for u in keep]); c = cnt[ix].astype(float)
		sel = c > 0; ix, c = ix[sel], c[sel]; kk = [keep[j] for j in np.where(sel)[0]]
		b0 = base.reindex(kk).values; extra = None
	else:
		p, pfx, col = _PD[k]
		kk0 = [u for u in USERS if u in p.index]
		ix = np.array([A1.UIDX[u] for u in kk0], int); c = cnt[ix].astype(float) if len(ix) else np.array([])
		sel = c > 0; ix, c = ix[sel], c[sel]; kk = [kk0[j] for j in np.where(sel)[0]]
		b0 = p.loc[kk, "기준선_" + col].values.astype(float)
		site = (p.loc[kk, pfx + "기록출처"].astype(str).str.contains("현장")).astype(float).values
		extra = site if np.ptp(site) > 0 else None
	aa = a_all[ix]
	n, n1, n0 = c.sum(), c[aa == 1].sum() if not cont else c.sum(), c[aa == 0].sum() if not cont else c.sum()
	if n < 30 or (not cont and (n1 < 10 or n0 < 10)):
		return np.nan, False
	Uu = U.iloc[ix]
	if est in ("dr", "ipw", "ow"):
		w, ps_ok = ps_and_w(Uu, aa, c, "ow" if est == "ow" else "iptw")
	else:
		w, ps_ok = np.ones(len(ix)), True
	cols = [aa, b0] + ([Uu[A1.PSV].values] if est != "ipw" else [])
	if extra is not None and est != "ipw":
		cols.append(extra)
	Zm = np.column_stack(cols)
	Zm = Zm[:, S.independent_columns(Zm, protect=2)]
	Z = S.add_const(Zm)
	if k in A1.DAILY:
		rows = rows[rows.user_id.isin(kk)]
		s2, t2, ybar, nn, re_ok = A1.reml(rows, pd.DataFrame(Z, index=kk), c)
		beta = S.wls(Z, ybar, c * w / (t2 + s2 / nn))
	else:
		re_ok = True
		y = p.loc[kk, pfx + col].values.astype(float)
		beta = S.wls(Z, y, c * w)
	d = beta[1] * (CUTS[e]["q75"] - CUTS[e]["q25"]) if cont else beta[1]
	ok = bool(ps_ok and re_ok and np.isfinite(d))
	return (d if ok else np.nan), ok


def multiverse(cnt, expo=EXPO0, gap_key="main"):
	return {s: spec_effect(s[0], cnt, expo, *s[1:], gap_key=gap_key)[0] for s in SPECS}


# ---------------------------------------------------------------- observability
def has_data(k):
	if k in A1.DAILY:
		keep = set(ddata(k)[0])
	else:
		keep = set(_PD[k][0].index)
	return np.array([u in keep for u in USERS], float)
HAS = {k: has_data(k) for k in A1.ORDER}


def observability(cnt, expo=EXPO0):
	out = {}
	for k in A1.ORDER:
		y = HAS[k]
		for e in EXPOS:
			for contrast in ["median", "continuous"]:
				x = expo[:, EXPOS.index(e)]
				a, _ = group(x, e, contrast)
				Xp = U[A1.PSV].values
				Z = np.column_stack([a, Xp]); Z = Z[:, S.independent_columns(Z, protect=1)]
				Xc = S.add_const(Z); sel = cnt > 0
				b, ok = S.glm_logit(Xc[sel], y[sel], cnt[sel])
				if not ok or not np.all(np.isfinite(b)) or np.max(np.abs(b)) > 15:
					b, ok = S.firth_logit(Xc[sel], y[sel], cnt[sel])
				X1, X0 = Xc[sel].copy(), Xc[sel].copy()
				if contrast == "median":
					X1[:, 1], X0[:, 1] = 1, 0
				else:
					X1[:, 1], X0[:, 1] = CUTS[e]["q75"], CUTS[e]["q25"]
				p1, p0 = np.average(S.expit(X1 @ b), weights=cnt[sel]), np.average(S.expit(X0 @ b), weights=cnt[sel])
				good = bool(ok and np.all(np.isfinite(b)))
				out[(k, e, contrast, "rd")] = (p1 - p0) if good else np.nan
				out[(k, e, contrast, "rr")] = (p1 / p0) if good and p0 > 0 else np.nan
				out[(k, e, contrast, "p1")] = p1 if good else np.nan
				out[(k, e, contrast, "p0")] = p0 if good else np.nan
	return out


# ---------------------------------------------------------------- collection-gap rule grid
GAP_SOURCES = ["activity.csv", "sleep.csv", "oxygen_saturation.csv", "heartrate_days.csv"]
GRID = [(f, w, r) for f in [0.3, 0.4, 0.5, 0.6, 0.7] for w in [14, 28, 56] for r in [2, 3, 5]]


_B = ROOT / "01_wearable_metrics/00_Data/extract_20261120"
_DEN = pd.read_csv(_B / "steps.csv", parse_dates=["d"]).groupby("d").user_id.nunique()
_CAL = pd.date_range(_DEN.index.min(), _DEN.index.max(), freq="D"); _DEN = _DEN.reindex(_CAL)
_NUM = {s: pd.read_csv(_B / s, parse_dates=["d"]).groupby("d").user_id.nunique().reindex(_CAL).fillna(0) for s in GAP_SOURCES}


def gap_days(src, frac, window, min_run):
	"""Same rule as ana1.source_gap_table / source_gaps, on cached daily counts (min_obs = 75% of the window)."""
	r = _NUM[src] / _DEN
	thr = frac * r.rolling(window, min_periods=int(np.ceil(0.75 * window))).median().shift(1)
	flag = (r < thr).fillna(False)
	out, run = set(), []
	for d, f in flag.items():
		if f:
			run.append(d)
		else:
			if len(run) >= min_run:
				out.update(run)
			run = []
	if len(run) >= min_run:
		out.update(run)
	return out


if gap_days("activity.csv", 0.5, 28, 3) != A1.ACT_GAP:
	raise SystemExit("cached gap rule does not reproduce ana1.ACT_GAP")


def gap_grid():
	rows, sets = [], {}
	main = A1.ACT_GAP
	for src in GAP_SOURCES:
		for f, w, r in GRID:
			g = gap_days(src, f, w, r)
			rows.append(dict(source=src.replace(".csv", ""), frac=f, window=w, min_run=r, gap_days=len(g),
			                 overlap_main=len(g & main), only_this=len(g - main), main_missed=len(main - g) if src == "activity.csv" else np.nan))
			if src == "activity.csv":
				sets.setdefault(frozenset(g), []).append((f, w, r))
	return pd.DataFrame(rows), sets


GAPTAB, GAPSETS = gap_grid()
GAPKEYS = {gs: f"g{i}" for i, gs in enumerate(sorted(GAPSETS, key=len))}


def gap_effects(cnt):
	out = {}
	keep_gap = A1.ACT_GAP
	for gs, key in GAPKEYS.items():
		A1.ACT_GAP = set(gs)
		try:
			out[key] = spec_effect("active_min", cnt, EXPO0, "login", "median", "dr", "all", gap_key=key)[0]
		finally:
			A1.ACT_GAP = keep_gap
	return out


# ---------------------------------------------------------------- replicates
def one_boot(seed):
	rng = np.random.default_rng(seed)
	cnt = np.bincount(rng.integers(0, NU, NU), minlength=NU).astype(float)  # same draw as ana1.one_boot
	try:
		return dict(mv=multiverse(cnt), obs=observability(cnt), gap=gap_effects(cnt))
	except Exception as ex:
		return {"error": repr(ex)}


def one_perm(seed):
	rng = np.random.default_rng(seed)
	expo = EXPO0[rng.permutation(NU)]
	try:
		return multiverse(np.ones(NU), expo)
	except Exception as ex:
		return {"error": repr(ex)}


def check_primary(P0):
	"""The primary specification must reproduce the main analysis point estimates."""
	E = pd.read_pickle(OUT / "est_point.pkl")["main"]
	for k in A1.ORDER:
		m = E[k].get("diff", np.nan) if E[k].get("tested") else np.nan
		v = P0[PRIMARY(k)]
		if not ((np.isnan(m) and np.isnan(v)) or abs(m - v) < 1e-8):
			raise SystemExit(f"primary specification does not reproduce the main estimate for {k}: {v} vs {m}")
	print("primary specification reproduces the main point estimates for", len(A1.ORDER), "indicators")


if __name__ == "__main__":
	ap = argparse.ArgumentParser(); ap.add_argument("--boot", type=int, default=1000); ap.add_argument("--perm", type=int, default=500)
	ap.add_argument("--workers", type=int, default=10)
	a = ap.parse_args()
	print("users", NU, "specs", len(SPECS), "gap grid", len(GRID), "distinct exercise gap sets", len(GAPSETS))
	for j, e in enumerate(EXPOS):
		x = EXPO0[:, j]; print(f"exposure {e}: median {np.median(x):.0f}, IQR {CUTS[e]['q25']:.0f}-{CUTS[e]['q75']:.0f}, thirds <= {CUTS[e]['t1']:.1f} / >= {CUTS[e]['t2']:.1f}")
	P0 = multiverse(np.ones(NU)); check_primary(P0)
	O0 = observability(np.ones(NU)); G0 = gap_effects(np.ones(NU))
	with mp.get_context("fork").Pool(a.workers) as pool:
		BS = pool.map(one_boot, [71000 + i for i in range(a.boot)], chunksize=5)
		PM = pool.map(one_perm, [91000 + i for i in range(a.perm)], chunksize=5)
	print("bootstrap replicates", len(BS), "errors", sum("error" in b for b in BS), "; permutations", len(PM), "errors", sum("error" in p for p in PM))
	pd.to_pickle(dict(point=P0, obs=O0, gap=G0, boot=BS, perm=PM, gaptab=GAPTAB, gapsets={GAPKEYS[g]: (len(g), GAPSETS[g]) for g in GAPSETS},
	                  cuts=CUTS, specs=SPECS, factors=FACTORS), OUT / "robust_01.pkl")
	print("wrote robust_01.pkl")
