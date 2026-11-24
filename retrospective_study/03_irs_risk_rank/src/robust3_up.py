# -*- coding: utf-8 -*-
"""Study 03 post hoc addition to robust3.py (added after its results were seen; see the change log): the same 1080
specifications with two further outcomes.

- up:  among a user's diseases whose baseline band is below the highest band (the mirror of the downward outcome; with
       "lowest band included" the highest band is included), the share that moved to a higher band at follow-up.
- net: on a common denominator, all of a user's evaluated diseases, (number moving down - number moving up) / number
       evaluated, a signed share in [-1, 1]. It is modelled as (net + 1) / 2 with the same fractional logistic estimators,
       and the difference is rescaled to the net scale. "Lowest band included" gives the same net outcome as 5 bands.
Run from retrospective_study/:  python3 03_irs_risk_rank/src/robust3_up.py [--boot 1000] [--perm 500] [--workers 10]
Uses the bootstrap seeds and strata of robust3.py / ana3.py. Writes robust_03_up.pkl (git-ignored). Prints aggregates only.
"""
import argparse
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "00_common/src")); sys.path.insert(0, str(ROOT / "03_irs_risk_rank/src"))
_argv = sys.argv; sys.argv = [sys.argv[0]]
import robust3 as R3  # noqa: E402
sys.argv = _argv
A3 = R3.A3
KINDS = ["up", "net"]


def user_outcome(kind, rc, rf, rows_mask, width=20.0, shift=0, incl=False):
	"""Per user: denominator, numerator (net: down minus up), mean baseline band and within-band position of the denominator rows."""
	ok = rows_mask & np.isfinite(rc) & np.isfinite(rf)
	bc, bf = A3.bands(rc, width, shift), A3.bands(rf, width, shift)
	if kind == "up":
		elig = ok if incl else ok & (bc < A3.bands(100, width, shift))
		num_w = (elig & (bf > bc)).astype(float)
	else:
		elig = ok
		num_w = (bf < bc).astype(float) - (bf > bc).astype(float)
	pos = ((np.asarray(rc, float) - 1 + shift) % width) / width
	ui = A3.LB.ui.values
	n = np.bincount(ui[elig], minlength=R3.NU).astype(float)
	k = np.bincount(ui[elig], weights=num_w[elig], minlength=R3.NU)
	sb = np.bincount(ui[elig], weights=bc[elig], minlength=R3.NU)
	sp = np.bincount(ui[elig], weights=pos[elig], minlength=R3.NU)
	with np.errstate(invalid="ignore", divide="ignore"):
		return n, k, sb / n, sp / n


def spec(kind, out, cnt, expo, e, contrast, est, odef, dset):
	"""robust3.spec_effect with the up or net outcome (identical estimators, covariates and rules)."""
	width, shift, incl = R3.OUTDEF[odef]
	rc, rf = out["irs"]
	rm = np.ones(len(A3.LB), bool) if R3.DSETS[dset] is None else A3.LB.disease.isin(R3.DSETS[dset]).values
	n, k, mb, mp_ = user_outcome(kind, rc, rf, rm, width, shift, incl)
	x = expo[:, R3.EXPOS.index(e)]
	a, keep = R3.group(x, e, contrast)
	sub = (n > 0) & (cnt > 0) & keep
	f = cnt[sub].astype(float); a_ = a[sub]
	cont = contrast == "continuous"
	if f.sum() < 30 or (not cont and (f[a_ == 1].sum() < 10 or f[a_ == 0].sum() < 10 or len(np.unique(a_)) < 2)):
		return np.nan
	y = k[sub] / n[sub]
	scale = 1.0
	if kind == "net":
		y = (y + 1) / 2; scale = 2.0
	cov = np.column_stack([R3.Dr.loc[sub, A3.PSV].values, mb[sub], mp_[sub]])
	if cont:
		Xm = R3.S.add_const(np.column_stack([a_, cov]))
		b, ok = R3.S.glm_logit(Xm, y, f)
		X1 = Xm.copy(); X1[:, 1] = R3.CUTS[e]["q75"]; X0 = Xm.copy(); X0[:, 1] = R3.CUTS[e]["q25"]
		if not (ok and np.all(np.isfinite(b))):
			return np.nan
		return scale * (np.average(R3.S.expit(X1 @ b), weights=f) - np.average(R3.S.expit(X0 @ b), weights=f))
	ps_ok = True
	if est in ("dr", "ipw"):
		w, _, ps_ok = A3.ps_fit(cnt, sub, (1, 99), a)
	elif est == "ow":
		_, ps, ps_ok = A3.ps_fit(cnt, sub, None, a); w = R3.MV.overlap_weights(ps, a_)
	else:
		w = np.ones(sub.sum())
	m1, m0, ok = A3.frac_standardize(y, cov if est != "ipw" else np.column_stack([mb[sub], mp_[sub]]), a_, w, f)
	return scale * (m1 - m0) if (ok and ps_ok) else np.nan


def multiverse(outs, cnt, expo=R3.EXPO0):
	return {kind: {s: spec(kind, outs[s[5]], cnt, expo, *s[:5]) for s in R3.SPECS} for kind in KINDS}


def one_boot(seed):
	cu, cnt = R3.boot_counts(seed)
	try:
		outs = {m: R3.rebuild(cu, m) for m in R3.METHODS}
		return multiverse(outs, cnt)
	except Exception as ex:
		return {"error": repr(ex)}


OUTS0 = None


def one_perm(seed):
	rng = np.random.default_rng(seed)
	try:
		return multiverse(OUTS0, np.ones(R3.NU), R3.EXPO0[rng.permutation(R3.NU)])
	except Exception as ex:
		return {"error": repr(ex)}


if __name__ == "__main__":
	ap = argparse.ArgumentParser(); ap.add_argument("--boot", type=int, default=1000); ap.add_argument("--perm", type=int, default=500)
	ap.add_argument("--workers", type=int, default=10)
	a = ap.parse_args()
	OUTS0 = {m: R3.rebuild(None, m) for m in R3.METHODS}
	P0 = multiverse(OUTS0, np.ones(R3.NU))
	print("specs per outcome", len(R3.SPECS), {k: int(np.sum(np.isfinite(list(v.values())))) for k, v in P0.items()})
	with mp.get_context("fork").Pool(a.workers) as pool:
		BS = pool.map(one_boot, [20261123 + i for i in range(a.boot)], chunksize=5)
		PM = pool.map(one_perm, [95000 + i for i in range(a.perm)], chunksize=5)
	print("bootstrap replicates", len(BS), "errors", sum("error" in b for b in BS), "; permutations", len(PM), "errors", sum("error" in p for p in PM))
	pd.to_pickle(dict(point=P0, boot=BS, perm=PM, specs=R3.SPECS, factors=R3.FACTORS, kinds=KINDS), R3.OUT / "robust_03_up.pkl")
	print("wrote robust_03_up.pkl")
