# -*- coding: utf-8 -*-
"""Study 02 supplementary analysis: continuous checkup values vs login days in the first 28 days.

Beta-binomial regression with a restricted cubic spline of the raw value (knots at the 10/50/90th percentiles of that item),
adjusted like the main model (age, sex, site, registration quarter, days from checkup to registration, checkup source).
The curve is the standardized mean of login days over the analysed users with the item, on a grid from the 5th to the 95th
percentile. Pointwise 95% CIs from the same 1,000 user resamples as ana2.py (seeds 42000+i). Descriptive figure only.

Run from retrospective_study/:  python3 02_checkup_metrics/src/ana2_spline.py [--boot 1000] [--workers 10]
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
import ana2 as A  # noqa: E402
sys.argv = _argv
import statlib as S  # noqa: E402

NUM = [it for it in A.ITEMS if it not in A.CAT]
SETUP = {}
for it in NUM:
	b = A.BSEL[A.BSEL.item == it].set_index("user_id")
	v = b.num.reindex(A.USERS).astype(float).values
	f = A.ITEMF[it]
	ok = np.isfinite(v) & np.isfinite(f.k.values) & np.isfinite(f.src104.values)
	knots = np.percentile(v[ok], [10, 50, 90])
	grid = np.linspace(*np.percentile(v[ok], [5, 95]), 25)
	SETUP[it] = dict(v=v, ok=ok, knots=knots, grid=grid)


def curve(it, cnt):
	s = SETUP[it]; f = A.ITEMF[it]
	ok = s["ok"] & (cnt > 0)
	Z = np.column_stack([S.rcs(s["v"][ok], s["knots"]), A.U[A.BASECOV].values[ok].astype(float), f.k.values[ok], f.src104.values[ok]])
	keep = S.independent_columns(Z, protect=2)
	Z = Z[:, keep]; Xc = S.add_const(Z)
	y = A.U.y.values[ok].astype(float); w = cnt[ok].astype(float)
	b, lt, conv = S.betabinom_fit(Xc, y, 28.0, w)
	out = []
	for g in s["grid"]:
		Xg = Xc.copy(); Xg[:, 1:3] = S.rcs(np.full(ok.sum(), g), s["knots"])
		out.append(28 * np.average(S.expit(Xg @ b), weights=w))
	return dict(curve=out, nonlin=b[2], conv=conv, n=int(w.sum()))


def one(seed):
	if seed is None:
		cnt = np.ones(len(A.U))
	else:
		rng = np.random.default_rng(seed)
		cnt = np.bincount(rng.integers(0, len(A.U), len(A.U)), minlength=len(A.U)).astype(float)
	return {it: curve(it, cnt) for it in NUM}


if __name__ == "__main__":
	ap = argparse.ArgumentParser(); ap.add_argument("--boot", type=int, default=1000); ap.add_argument("--workers", type=int, default=6)
	a = ap.parse_args()
	E0 = one(None)
	with mp.get_context("fork").Pool(a.workers) as pool:
		BS = pool.map(one, [42000 + i for i in range(a.boot)], chunksize=10)
	rows = []
	for it in NUM:
		cv = np.array([b[it]["curve"] for b in BS if b[it]["conv"]])
		nl = np.array([b[it]["nonlin"] for b in BS if b[it]["conv"]])
		ok = E0[it]["conv"] and len(cv) >= 900  # raw fit converged and >= 900 valid resamples
		for j, g in enumerate(SETUP[it]["grid"]):
			rows.append(dict(item=it, value=g, est=E0[it]["curve"][j], lo=np.percentile(cv[:, j], 2.5) if ok else np.nan, hi=np.percentile(cv[:, j], 97.5) if ok else np.nan,
			                 n=E0[it]["n"], boot_valid=len(cv), raw_converged=E0[it]["conv"], p_nonlin=S.wald_p(E0[it]["nonlin"], np.std(nl, ddof=1)) if ok else np.nan))
	R = pd.DataFrame(rows)
	R.to_csv(A.OUT / "spline_curves.csv", index=False)
	print(R.groupby("item").agg(n=("n", "first"), boot_valid=("boot_valid", "first"), p_nonlin=("p_nonlin", "first"),
	                            lo_end=("est", "first"), hi_end=("est", "last")).round(3).to_string())
