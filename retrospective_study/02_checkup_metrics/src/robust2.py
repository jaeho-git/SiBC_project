# -*- coding: utf-8 -*-
"""Study 02 post hoc robustness analyses (plan: 00_common/docs/local/견고성분석계획, section 4).

Run from retrospective_study/:  python3 02_checkup_metrics/src/robust2.py [--boot 1000] [--perm 300] [--workers 10]
1. Multiverse over analysis paths: outcome (login days, login days without suspect rule-1 days, feature-use days) x item
   coding (study cutoff, disease-suspect cutoff where defined, continuous per SD for numeric items) x model (beta-binomial,
   quasi-binomial, cumulative-logit ordinal) x adjustment (full, age and sex only) x sample (all, results entered by the
   registration day). Each path covers all items; Benjamini-Hochberg within each path.
2. Checkup linkage status and engagement in the whole common cohort (adjusted standardized means by linkage group).
The bootstrap uses the seeds of ana2.py, so the primary path reproduces the main analysis. Writes robust_02.pkl to
02_checkup_metrics/01_Results/analysis/ (git-ignored). Prints aggregates only.
"""
import argparse
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "00_common/src")); sys.path.insert(0, str(ROOT / "02_checkup_metrics/src"))
_argv = sys.argv; sys.argv = [sys.argv[0]]
import ana2 as A2  # noqa: E402
sys.argv = _argv
import multiverse as MV  # noqa: E402
import statlib as S  # noqa: E402

OUT = A2.OUT
U, USERS = A2.U, A2.USERS
NU = len(USERS)
EX = A2.EX

# ---------------------------------------------------------------- outcomes (users x 3, permuted jointly by rows)
_ev = pd.read_csv(EX / "event_days.csv", parse_dates=["d"]); _ev = _ev[_ev.n_action > 0]


def feature_days(frame):
	"""Days with at least one user-response event on registration+1..+28 (KST)."""
	e = _ev[_ev.user_id.isin(frame.index)].merge(frame[["d0"]], left_on="user_id", right_index=True)
	e = e[(e.d > e.d0) & (e.d <= e.d0 + pd.Timedelta(days=28))]
	return e.groupby("user_id").size().reindex(frame.index).fillna(0).values.astype(float)


U["y_act"] = feature_days(U)
OUTCOMES = ["y", "y_s1", "y_act"]
Y0 = U[OUTCOMES].values.astype(float)

# ---------------------------------------------------------------- item frames per coding
def cont_frame(item):
	"""Numeric cutoff items as continuous values per SD (same SD rule as the height and weight items)."""
	b = A2.BSEL[A2.BSEL.item == item].set_index("user_id")
	f = A2.ITEMF[item].copy()
	v = b.num.reindex(USERS).astype(float)
	f["x"] = ((v - v.mean()) / v.std(ddof=1)).values
	return f


ITEMF_CONT = {it: cont_frame(it) for it in A2.NUM_CUT}


def eff_coding(item, coding):
	if coding == "alt" and item in A2.ITEMF_ALT:
		return "alt"
	if coding == "cont" and item in ITEMF_CONT:
		return "cont"
	return "cut"


def frame(item, eff):
	return {"alt": A2.ITEMF_ALT, "cont": ITEMF_CONT}.get(eff, A2.ITEMF)[item]


CODINGS = ["cut", "alt", "cont"]
MODELS = ["bb", "quasi", "ord"]
ADJS = ["full", "agesex"]
SAMPLES = ["all", "entry_reg"]
PATHS = [(o, c, m, a, s) for o in OUTCOMES for c in CODINGS for m in MODELS for a in ADJS for s in SAMPLES]
PRIMARY_PATH = ("y", "cut", "bb", "full", "all")
# effective (unique) specifications: (item, outcome, effective coding, model, adjustment, sample)
EFF = sorted({(it, o, eff_coding(it, c), m, a, s) for it in A2.ITEMS for (o, c, m, a, s) in PATHS})
FACTORS = ["item", "outcome", "coding", "model", "adjustment", "sample"]


def fit_spec(item, ycol, eff, model, adj, sample, cnt, Y):
	f = frame(item, eff)
	cov = U[A2.BASECOV].values if adj == "full" else U[["age", "female"]].values
	cols = [f.x.values, cov] + ([f.k.values, f.src104.values] if adj == "full" else [])
	X = np.column_stack(cols)
	y = Y[:, OUTCOMES.index(ycol)]
	ok = np.isfinite(X).all(axis=1) & (cnt > 0)
	if sample == "entry_reg":
		ok &= A2.ITEMF[item].entry_reg.values == 1
	X, y, w = X[ok], y[ok], cnt[ok].astype(float)
	if len(y) < 2:
		return np.nan
	X = X[:, S.independent_columns(X, protect=1)]
	binary = not (item in A2.CONT or eff == "cont")
	n = w.sum()
	if binary:
		n1, n0 = w[X[:, 0] == 1].sum(), w[X[:, 0] == 0].sum()
		if n < 30 or n1 < 10 or n0 < 10:
			return np.nan
	elif n < 30:
		return np.nan
	Xc = S.add_const(X)
	if binary:
		X1 = Xc.copy(); X1[:, 1] = 1; X0 = Xc.copy(); X0[:, 1] = 0
	else:
		X1 = Xc.copy(); X1[:, 1] = X1[:, 1] + 1; X0 = Xc
	if model == "ord":
		mo = MV.Ordinal(X, y, w)
		if not mo.conv:
			return np.nan
		return np.average(mo.mean(X1[:, 1:]), weights=w) - np.average(mo.mean(X0[:, 1:]), weights=w)
	if model == "bb":
		b, lt, conv = S.betabinom_fit(Xc, y, 28.0, w)
		if not conv:  # as in ana2.fit_item
			b, conv = S.glm_logit(Xc, y / 28, w)
	else:
		b, conv = S.glm_logit(Xc, y / 28, w)
	if not (conv and np.all(np.isfinite(b))):
		return np.nan
	return 28 * (np.average(S.expit(X1 @ b), weights=w) - np.average(S.expit(X0 @ b), weights=w))


def multiverse(cnt, Y=Y0):
	return {e: fit_spec(*e, cnt, Y) for e in EFF}


# ---------------------------------------------------------------- linkage status in the whole common cohort
C = A2.C[A2.C.age.notna() & A2.C.sex.notna()].copy()
_valid = set(A2._L[A2._L.used & A2._L.ok].user_id); _base = set(A2.BSEL.user_id.unique())
C["grp"] = np.where(C.index.isin(list(_base)), "baseline", np.where(C.index.isin(list(_valid)), "outside", "none"))
_lg = pd.read_csv(EX / "login_hours_days.csv", parse_dates=["d"]); _lg = _lg[_lg.user_id.isin(C.index)].merge(C[["d0"]], left_on="user_id", right_index=True)
_lg = _lg[(_lg.d > _lg.d0) & (_lg.d <= _lg.d0 + pd.Timedelta(days=28))]
_k = list(zip(_lg.user_id, _lg.d))
_s1 = (_lg.d >= A2.POST) & (_lg.n == 1) & ~np.array([k in A2.broad for k in _k])
C["y"] = _lg.groupby("user_id").size().reindex(C.index).fillna(0).values
C["y_s1"] = C.y - _lg[_s1].groupby("user_id").size().reindex(C.index).fillna(0).values
C["y_act"] = feature_days(C)
if not np.array_equal(C.loc[USERS, "y"].values, U.y.values):
	raise SystemExit("cohort login days differ from the analysis set")
C["female"] = (C.sex == "F").astype(float); C["site_b"] = (C.site == "B").astype(float); C["age"] = C.age.astype(float)
_q = C.d0.dt.to_period("Q").astype(str)
while True:  # same merging rule as ana2 (quarters with fewer than 10 users merged into the next later quarter)
	vc = _q.value_counts().sort_index(); small = [k for k in vc.index if vc[k] < 10]
	if not small or len(vc) == 1:
		break
	k0 = small[0]; later = [j for j in vc.index if j > k0]
	_q = _q.replace(k0, later[0] if later else [j for j in vc.index if j < k0][-1])
_qref = _q.value_counts().idxmax()
CQ = [f"q_{x}" for x in sorted(_q.unique()) if x != _qref]
for x in sorted(_q.unique()):
	if x != _qref:
		C[f"q_{x}"] = (_q == x).astype(float)
GRPS = ["baseline", "outside", "none"]
LCOV = ["age", "female", "site_b"] + CQ
NC = len(C)


def linkage(cnt):
	out = {}
	G = np.column_stack([(C.grp == g).astype(float).values for g in GRPS[1:]])  # reference: baseline
	Xcov = C[LCOV].values.astype(float)
	for ycol in OUTCOMES:
		y = C[ycol].values.astype(float)
		for model in MODELS:
			Z = np.column_stack([G, Xcov]); sel = cnt > 0
			Z = Z[:, S.independent_columns(Z[sel], protect=2)]
			w = cnt[sel].astype(float); Zs = Z[sel]
			means = {}
			if model == "ord":
				mo = MV.Ordinal(Zs, y[sel], w); conv = mo.conv
				for j, g in enumerate(GRPS):
					Zg = Zs.copy(); Zg[:, :2] = 0
					if j > 0:
						Zg[:, j - 1] = 1
					means[g] = np.average(mo.mean(Zg), weights=w) if conv else np.nan
			else:
				Xc = S.add_const(Zs)
				if model == "bb":
					b, lt, conv = S.betabinom_fit(Xc, y[sel], 28.0, w)
				else:
					b, conv = S.glm_logit(Xc, y[sel] / 28, w)
				for j, g in enumerate(GRPS):
					Xg = Xc.copy(); Xg[:, 1:3] = 0
					if j > 0:
						Xg[:, j] = 1
					means[g] = 28 * np.average(S.expit(Xg @ b), weights=w) if conv else np.nan
			for g in GRPS:
				out[(ycol, model, "mean", g)] = means[g]
			out[(ycol, model, "diff", "baseline-none")] = means["baseline"] - means["none"]
			out[(ycol, model, "diff", "baseline-outside")] = means["baseline"] - means["outside"]
			out[(ycol, model, "diff", "outside-none")] = means["outside"] - means["none"]
	return out


# ---------------------------------------------------------------- replicates
def one_boot(seed):
	rng = np.random.default_rng(seed)
	cnt = np.bincount(rng.integers(0, NU, NU), minlength=NU).astype(float)  # same draw as ana2.one_boot
	rng2 = np.random.default_rng(seed + 500000)
	cntc = np.bincount(rng2.integers(0, NC, NC), minlength=NC).astype(float)
	try:
		return dict(mv=multiverse(cnt), link=linkage(cntc))
	except Exception as ex:
		return {"error": repr(ex)}


def one_perm(seed):
	rng = np.random.default_rng(seed)
	try:
		return multiverse(np.ones(NU), Y0[rng.permutation(NU)])
	except Exception as ex:
		return {"error": repr(ex)}


def check_primary(P0):
	E = pd.read_pickle(OUT / "est_point.pkl")["main"]
	for it in A2.ITEMS:
		m = E[it].get("diff", np.nan) if E[it].get("tested") else np.nan
		v = P0[(it,) + PRIMARY_PATH[:1] + (eff_coding(it, "cut"),) + PRIMARY_PATH[2:]]
		if not ((np.isnan(m) and np.isnan(v)) or abs(m - v) < 1e-8):
			raise SystemExit(f"primary path does not reproduce the main estimate for {it}: {v} vs {m}")
	print("primary path reproduces the main point estimates for", len(A2.ITEMS), "items")


if __name__ == "__main__":
	ap = argparse.ArgumentParser(); ap.add_argument("--boot", type=int, default=1000); ap.add_argument("--perm", type=int, default=300)
	ap.add_argument("--workers", type=int, default=10)
	a = ap.parse_args()
	print("users", NU, "paths", len(PATHS), "unique specifications", len(EFF), "cohort for linkage", NC, dict(C.grp.value_counts()))
	print("feature-use days: median", np.median(U.y_act), "IQR", np.percentile(U.y_act, [25, 75]))
	P0 = multiverse(np.ones(NU)); check_primary(P0)
	L0 = linkage(np.ones(NC))
	with mp.get_context("fork").Pool(a.workers) as pool:
		BS = pool.map(one_boot, [42000 + i for i in range(a.boot)], chunksize=5)
		PM = pool.map(one_perm, [93000 + i for i in range(a.perm)], chunksize=5)
	print("bootstrap replicates", len(BS), "errors", sum("error" in b for b in BS), "; permutations", len(PM), "errors", sum("error" in p for p in PM))
	pd.to_pickle(dict(point=P0, link=L0, boot=BS, perm=PM, paths=PATHS, eff=EFF, factors=FACTORS, items=A2.ITEMS,
	                  link_n=dict(C.grp.value_counts())), OUT / "robust_02.pkl")
	print("wrote robust_02.pkl")
