# -*- coding: utf-8 -*-
"""Study 03 post hoc analysis with IRS+ ranks (plan: 00_common/docs/local/SiBC_후향적연구_03_IRS+사후분석계획_20261127.md).

The disease-specific score displayed in the app matched the IRS+ rank field of the calculation records, so the primary
analysis of ana3.py is repeated with IRS+ in place of IRS: same comparison set, exposure, crosswalk method (isotonic,
shift beyond the bridge range, 5-fold cross-fitting, stable-period reference table), estimator and bootstrap (same
seeds and strata, crosswalk rebuilt in every resample). The IRS primary analysis itself is unchanged.

Run from retrospective_study/:  python3 03_irs_risk_rank/src/posthoc_irsp.py [--boot 1000] [--workers 10]
Reads the frozen comparison set (through ana3.py, read only) and 03_irs_risk_rank/00_Data/extract_20261127_irsp/res_irsp.csv
(sql/irs_extracts.sql, block res_irsp). Writes posthoc_irsp.pkl to 03_irs_risk_rank/01_Results/analysis/ (git-ignored).
Prints aggregates only.
"""
import argparse
import multiprocessing as mp
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "03_irs_risk_rank/src")); sys.path.insert(0, str(ROOT / "00_common/src"))
_argv = sys.argv; sys.argv = [sys.argv[0]]
import ana3 as A3  # noqa: E402  (module level: frozen comparison set, bridge pairs, exposure, covariates)
sys.argv = _argv
X, S = A3.X, A3.S
EXT = Path(os.environ.get("IRSP_EXTRACT", ROOT / "03_irs_risk_rank/00_Data/extract_20261127_irsp/res_irsp.csv"))  # override for code tests only
C = "irsp"
R, BB, LB = A3.R, A3.BB, A3.LB
band20 = lambda r: np.floor((np.asarray(r, float) - 1) / 20)

# ---------------------------------------------------------------- 1. IRS+ values; exact checks against the frozen extracts
E = pd.read_csv(EXT, dtype=str)
E["seq"] = E.seq.astype(int)
if E.duplicated(["seq", "disease"]).any():
	E = E.drop_duplicates(["seq", "disease"])
kr = pd.MultiIndex.from_arrays([R.seq.values, R.disease.values])
ke = pd.MultiIndex.from_arrays([E.seq.values, E.disease.values])
if set(kr) != set(ke):
	raise SystemExit("IRS+ extract does not cover exactly the frozen (seq, disease) set; analysis not run")
ev = E.set_index(["seq", "disease"])
for c in ["irs_p", "irs_r"]:
	if not np.array_equal(ev[c].reindex(kr).fillna("").values, R[c].fillna("").values):
		raise SystemExit(f"IRS field {c} differs from the frozen extracts; analysis not run")
R["irsp_pn"] = pd.to_numeric(ev.irsp_p.reindex(kr).values, errors="coerce")
R["irsp_rn"] = pd.to_numeric(ev.irsp_r.reindex(kr).values, errors="coerce")
_v = R.irsp_pn.dropna().values
X.SCALE[C] = "logit" if len(_v) and bool(np.all((_v > 0) & (_v < 1))) else "raw"

# analysis rows: baseline and follow-up seqs of the comparison set
sb = LB.user_id.map(A3.D2.seq_b).values; sf = LB.user_id.map(A3.D2.seq_f).values
for tag, sq in [("b", sb), ("f", sf)]:
	k = pd.MultiIndex.from_arrays([sq, LB.disease.values])
	chk = pd.to_numeric(ev.irs_p.reindex(k).values, errors="coerce")
	if not np.allclose(np.nan_to_num(chk, nan=-9), np.nan_to_num(LB["irs_p_" + tag].values.astype(float), nan=-9)):
		raise SystemExit("baseline/follow-up seq mapping does not reproduce the IRS values of L2")
	LB[f"{C}_p_{tag}"] = pd.to_numeric(ev.irsp_p.reindex(k).values, errors="coerce")
	LB[f"{C}_r_{tag}"] = pd.to_numeric(ev.irsp_r.reindex(k).values, errors="coerce")

# reference-table rows and bridge pairs (genomic calculations only, as for the IRS)
T = R[(R.t >= X.TS) & (R.t < X.B1)]
REF = {}
for (d, s), g in T.groupby(["disease", "sex"]):
	k = g.irsp_pn.notna() & g.irsp_rn.notna()
	A3.REFG[(d, s, C)] = (g.loc[k, "irsp_pn"].values, g.loc[k, "irsp_rn"].values, g.loc[k, "user_id"].values)
	t = g.loc[k, ["irsp_pn", "irsp_rn"]].sort_values(["irsp_pn", "irsp_rn"])
	if len(t):
		REF[(d, s, C)] = (t.irsp_pn.values, t.irsp_rn.values)
for d in A3.DIS:
	xo, xn, ro, m = X.bridge_values(R, BB, d, C)
	m = m & BB.mode_o.isin(A3.GENO).values
	for s in X.SEXES:
		A3.BRG[(d, C, s)] = (xo, xn, np.where(m & (BB.sex_o.values == s))[0])
A3.SCORES = ["irs", C]


# ---------------------------------------------------------------- 2. data checks and crosswalk validation (original data)
def checks():
	conf = int(sum((pd.DataFrame({"x": x, "y": y}).groupby("x").y.nunique() > 1).sum() for x, y in REF.values()))
	p1 = (LB.model_f == "P1").values
	rr = np.full(len(LB), np.nan)
	for (d, s), ix in pd.Series(np.arange(len(LB))[p1]).groupby([LB.disease.values[p1], LB.sex.values[p1]]):
		rr[ix.values] = X.to_rank(REF, LB[C + "_p_f"].values[ix.values], d, s, C)
	ok = p1 & np.isfinite(rr) & np.isfinite(LB[C + "_r_f"].values)
	return dict(scale=X.SCALE[C], ref_conflicts=conf, ref_keys=len(REF),
	            followup_band_agree=float(np.mean(band20(rr[ok]) == band20(LB[C + "_r_f"].values[ok]))), followup_rows=int(ok.sum()),
	            rows_b=int(np.isfinite(LB[C + "_r_b"].values).sum()), rows_f=int(np.isfinite(LB[C + "_r_f"].values).sum()))


def oof_pairs():
	"""Cross-validated converted IRS+ ranks for bridge pairs (as x8b.oof with the full stable-period reference table)."""
	rows = []
	for d in A3.DIS:
		xo, xn, ro, m = X.bridge_values(R, BB, d, C)
		m = m & BB.mode_o.isin(A3.GENO).values
		idx = np.where(m)[0]
		if len(idx) < 30:
			continue
		fo = A3.FOLD[idx]; sx = BB.sex_o.values[idx]
		pred = np.full(len(idx), np.nan); truth = np.full(len(idx), np.nan)
		for k in range(5):
			for s in X.SEXES:
				trs = np.where((fo != k) & (sx == s))[0]; tes = np.where((fo == k) & (sx == s))[0]
				if not len(tes):
					continue
				pred[tes] = X.to_rank(REF, X.CW(xo[idx[trs]], xn[idx[trs]], X.SCALE[C])(xo[idx[tes]]), d, s, C)
				truth[tes] = X.to_rank(REF, xn[idx[tes]], d, s, C)
		rows.append(pd.DataFrame(dict(disease=d, sex=sx, user_id=BB.user_id.values[idx], raw=ro[idx], pred=pred, truth=truth)))
	return pd.concat(rows, ignore_index=True)


def agreement(V):
	v = V[np.isfinite(V.truth) & np.isfinite(V.pred) & np.isfinite(V.raw)].copy()
	v["after"] = band20(v.truth) == band20(v.pred); v["before"] = band20(v.truth) == band20(v.raw)
	per = v.groupby("disease")[["before", "after"]].mean()
	by_sex = v.groupby(["disease", "sex"]).after.mean().groupby("disease").min()
	passing = sorted(by_sex[by_sex >= 0.95].index)
	return dict(pairs_per_disease=float(v.groupby("disease").size().median()), median_before=float(per.before.median()),
	            median_after=float(per.after.median()), n_pass=len(passing), diseases=len(per)), passing


def reclass(V, w_user=None):
	"""Update-related reclassification on same-input pairs: down among pairs whose baseline band is above the lowest, up among all."""
	v = np.isfinite(V.truth.values) & np.isfinite(V.pred.values) & np.isfinite(V.raw.values)
	w = np.ones(len(V)) if w_user is None else V.user_id.map(w_user).fillna(0).values.astype(float)
	bt = band20(V.truth.values); out = {}
	for when, base in [("before", band20(V.raw.values)), ("after", band20(V.pred.values))]:
		el = v & (base > 0)
		out[(when, "down")] = 100 * np.sum(w * ((bt < base) & el)) / np.sum(w * el)
		out[(when, "up")] = 100 * np.sum(w * ((bt > base) & v)) / np.sum(w * v)
	return out


# ---------------------------------------------------------------- 3. estimates
def user_outcome(kind, rc, rf, rows_mask):
	"""down: ana3.user_outcome; up and net: robust3_up.user_outcome (5 bands of 20, lowest band excluded for down)."""
	if kind == "down":
		return A3.user_outcome(rc, rf, rows_mask)
	ok = rows_mask & np.isfinite(rc) & np.isfinite(rf)
	bc, bf = A3.bands(rc), A3.bands(rf)
	if kind == "up":
		elig = ok & (bc < A3.bands(100)); num = (elig & (bf > bc)).astype(float)
	else:
		elig = ok; num = (bf < bc).astype(float) - (bf > bc).astype(float)
	pos = ((np.asarray(rc, float) - 1) % 20) / 20
	ui = LB.ui.values; nu = len(A3.users)
	n = np.bincount(ui[elig], minlength=nu).astype(float)
	k = np.bincount(ui[elig], weights=num[elig], minlength=nu)
	sb = np.bincount(ui[elig], weights=bc[elig], minlength=nu); sp = np.bincount(ui[elig], weights=pos[elig], minlength=nu)
	with np.errstate(invalid="ignore", divide="ignore"):
		return n, k, sb / n, sp / n


def estimate(out, cnt, score, kind="down", sub_users=None, diseases=None):
	"""Primary estimator of ana3.representative (truncated stabilized IPTW + fractional logit, standardized)."""
	rc, rf = out[score]
	rm = np.ones(len(LB), bool) if diseases is None else LB.disease.isin(diseases).values
	n, k, mb, mp_ = user_outcome(kind, rc, rf, rm)
	sub = (n > 0) & (cnt > 0)
	if sub_users is not None:
		sub &= sub_users
	f = cnt[sub].astype(float); a = A3.A[sub]
	if f.sum() < 30 or f[a == 1].sum() < 10 or f[a == 0].sum() < 10 or len(np.unique(a)) < 2:
		return dict(diff=np.nan, m1=np.nan, m0=np.nan, n=int(f.sum()), conv=False)
	w, _, ps_ok = A3.ps_fit(cnt, sub, (1, 99), A3.A)
	cov = np.column_stack([A3.Dr.loc[sub, A3.PSV].values, mb[sub], mp_[sub]])
	y = k[sub] / n[sub]
	if kind == "net":
		y = (y + 1) / 2
	m1, m0, ok = A3.frac_standardize(y, cov, a, w, f)
	if kind == "net":
		m1, m0 = 2 * m1 - 1, 2 * m0 - 1
	return dict(diff=m1 - m0, m1=m1, m0=m0, n=int(f.sum()), n_hi=int(f[a == 1].sum()), conv=bool(ok and ps_ok))


PASS = None


def estimates(cnt, cu):
	out = A3.rebuild(cu)
	e = {}
	for sc in ["irs", C]:
		for kind in ["down", "up", "net"]:
			e[(sc, kind)] = estimate(out, cnt, sc, kind)
	e[(C, "down", "same_model")] = estimate(out, cnt, C, "down", sub_users=(A3.Dr.model_f == "P0").values)
	e[(C, "down", "pass")] = estimate(out, cnt, C, "down", diseases=PASS) if PASS else dict(diff=np.nan)
	return e, out


def describe(out):
	rc_i, rf_i = out["irs"]; rc_p, rf_p = out[C]
	ok = np.isfinite(rc_i) & np.isfinite(rf_i) & np.isfinite(rc_p) & np.isfinite(rf_p)
	di = np.sign(band20(rf_i) - band20(rc_i)); dp = np.sign(band20(rf_p) - band20(rc_p))
	lab = {-1: "down", 0: "same", 1: "up"}
	tab = pd.crosstab(pd.Series(di[ok]).map(lab).rename("irs"), pd.Series(dp[ok]).map(lab).rename("irsp"))
	ni, ki, _, _ = A3.user_outcome(rc_i, rf_i, np.ones(len(LB), bool)); npp, kp, _, _ = A3.user_outcome(rc_p, rf_p, np.ones(len(LB), bool))
	both = (ni > 0) & (npp > 0)
	return dict(crosstab=tab, rows=int(ok.sum()), corr_users=int(both.sum()),
	            corr=float(np.corrcoef(ki[both] / ni[both], kp[both] / npp[both])[0, 1]),
	            elig_rows_irs=int(ni.sum()), elig_rows_irsp=int(npp.sum()))


def one_boot(seed):
	rng = np.random.default_rng(seed)
	cu = {}
	for st in A3.STRATA:  # same draw as ana3.one_boot
		draw = rng.choice(st, len(st), replace=True)
		u, c = np.unique(draw, return_counts=True)
		cu.update(dict(zip(u, c)))
	cnt = np.array([cu.get(u, 0) for u in A3.users])
	try:
		return estimates(cnt, cu)[0]
	except Exception as ex:
		return {"error": repr(ex)}


def summarize(E0, BS):
	"""As report3.py: a resample counts only if its propensity score and outcome models converged (which also requires the
	minimum sample size rule); with fewer than 900 such resamples, or if the original-data fit did not converge, only the
	point estimate is reported."""
	ok = [b for b in BS if "error" not in b]
	rows = []
	for key, v in E0.items():
		vals = np.array([b[key]["diff"] for b in ok if key in b and b[key].get("conv", False)], float)
		vals = vals[np.isfinite(vals)]
		show = len(vals) >= 900 and bool(v.get("conv", False)) and np.isfinite(v["diff"])
		se = vals.std(ddof=1) if show else np.nan
		lo, hi = (np.percentile(vals, 2.5), np.percentile(vals, 97.5)) if show else (np.nan, np.nan)
		p = S.wald_p(v["diff"], se) if show else np.nan
		rows.append(dict(key=" / ".join(key), diff=100 * v["diff"], m1=100 * v.get("m1", np.nan), m0=100 * v.get("m0", np.nan),
		                 lo=100 * lo, hi=100 * hi, p=p, n_valid=len(vals), conv_original=bool(v.get("conv", False)), n=v.get("n")))
	return pd.DataFrame(rows)


if __name__ == "__main__":
	ap = argparse.ArgumentParser(); ap.add_argument("--boot", type=int, default=1000); ap.add_argument("--workers", type=int, default=10)
	args = ap.parse_args()
	A3.OUT.mkdir(parents=True, exist_ok=True)
	_o = A3.rebuild(None)  # the IRS crosswalk and ranks must reproduce L2 (as ana3.check_rebuild for the IRS)
	if not (np.allclose(np.nan_to_num(_o["irs"][0], nan=-1), np.nan_to_num(A3.L2.irs_r_c.values, nan=-1))
	        and np.allclose(np.nan_to_num(_o["irs"][1], nan=-1), np.nan_to_num(A3.L2.irs_r_fs.values, nan=-1))):
		raise SystemExit("IRS rebuild does not reproduce L2")
	CHK = checks(); print("checks", CHK)
	V = oof_pairs(); AGR, PASS = agreement(V); print("crosswalk agreement", AGR)
	RC0 = reclass(V)
	busers = np.array(sorted(V.user_id.unique())); rng = np.random.default_rng(20261127); RCB = []
	for _ in range(1000):
		u, c = np.unique(rng.choice(busers, len(busers), replace=True), return_counts=True)
		RCB.append(reclass(V, dict(zip(u, c))))
	RC = {k: (v, np.percentile([b[k] for b in RCB], 2.5), np.percentile([b[k] for b in RCB], 97.5)) for k, v in RC0.items()}
	print("update-related reclassification (%, 95% CI)", {f"{a}_{b}": tuple(round(x, 1) for x in v) for (a, b), v in RC.items()})
	E0, OUT0 = estimates(A3.CNT1, None)
	ref_main = A3.representative(OUT0, A3.CNT1)["diff"]
	if not np.isclose(E0[("irs", "down")]["diff"], ref_main):
		raise SystemExit("IRS downward estimate does not reproduce the ana3 primary estimate")
	DESC = describe(OUT0)
	BS = []
	if args.boot > 0:
		with mp.get_context("fork").Pool(args.workers) as pool:
			BS = pool.map(one_boot, [20261123 + i for i in range(args.boot)], chunksize=5)
	SUM = summarize(E0, BS)
	pd.to_pickle(dict(checks=CHK, agreement=AGR, passing=PASS, reclass=RC, point=E0, boot=BS, summary=SUM, describe=DESC,
	                  oof=V), Path(os.environ.get("IRSP_OUT", A3.OUT / "posthoc_irsp.pkl")))
	print("bootstrap replicates", len(BS), "errors", sum("error" in b for b in BS))
	print(SUM.round(2).to_string(index=False))
	print("IRS vs IRS+ direction (rows)\n", DESC["crosstab"].to_string(), "\nuser-level correlation of downward proportions", round(DESC["corr"], 3))
