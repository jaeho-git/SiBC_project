# -*- coding: utf-8 -*-
"""Study 03 post hoc robustness analyses (plan: 00_common/docs/local/견고성분석계획, section 5).

Run from retrospective_study/:  python3 03_irs_risk_rank/src/robust3.py [--boot 1000] [--perm 500] [--workers 10]
1. Multiverse: exposure (login days, without suspect rule-1 days, feature-use days) x contrast (median, top vs bottom
   third, continuous) x estimator (IPTW + outcome model, outcome model only, IPTW only, overlap weights + outcome model;
   continuous: outcome model only) x outcome definition (5 x 20 ranks, 3 bands, 10 bands, boundaries shifted by 10,
   lowest band included) x disease set (all, 18 passing the crosswalk rule) x crosswalk method (isotonic with shifted
   extrapolation, isotonic clipped, linear, equipercentile).
2. False band movement on same-input bridge pairs for every crosswalk method (cross-validated predictions).
3. Quantitative bias analysis of the residual false downward movement in the analysis set.
The bootstrap uses the seeds and strata of ana3.py, so the primary specification reproduces the main analysis. Writes
robust_03.pkl to 03_irs_risk_rank/01_Results/analysis/ (git-ignored). Prints aggregates only.
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
import ana3 as A3  # noqa: E402
sys.argv = _argv
import multiverse as MV  # noqa: E402
import statlib as S  # noqa: E402

X = A3.X
OUT = A3.OUT
Dr, users = A3.Dr, A3.users
NU = len(users)

# ---------------------------------------------------------------- crosswalk methods
class Linear:
	"""Least-squares line on the transformed scale (logit for IRS/MRS, raw for LRS); identity / none as in xwlib.CW."""

	def __init__(s, xo, xn, scale="logit"):
		xo = np.asarray(xo, float); xn = np.asarray(xn, float); k = np.isfinite(xo) & np.isfinite(xn); xo, xn = xo[k], xn[k]
		s.f = (X.lg, X.ilg) if scale == "logit" else (lambda v: v, lambda v: v)
		if len(xo) >= 1 and np.allclose(xo, xn, atol=1e-12, rtol=0):
			s.kind = "identity"
		elif len(xo) >= 5 and np.ptp(s.f[0](xo)) > 0:
			s.kind = "fit"; s.b, s.a = np.polyfit(s.f[0](xo), s.f[0](xn), 1)
		else:
			s.kind = "none"

	def __call__(s, p):
		p = np.asarray(p, float); out = np.full(len(p), np.nan); ok = np.isfinite(p)
		if not ok.any() or s.kind == "none":
			return out
		if s.kind == "identity":
			out[ok] = p[ok]; return out
		out[ok] = s.f[1](s.a + s.b * s.f[0](p[ok])); return out


class Equip:
	"""Equipercentile mapping of the old value's percentile among the bridge pairs to the same percentile of the new values;
	beyond the bridge range the end difference is carried (shift)."""

	def __init__(s, xo, xn, scale="logit"):
		xo = np.asarray(xo, float); xn = np.asarray(xn, float); k = np.isfinite(xo) & np.isfinite(xn); xo, xn = xo[k], xn[k]
		s.f = (X.lg, X.ilg) if scale == "logit" else (lambda v: v, lambda v: v)
		if len(xo) >= 1 and np.allclose(xo, xn, atol=1e-12, rtol=0):
			s.kind = "identity"
		elif len(xo) >= 5:
			s.kind = "fit"; s.za = np.sort(s.f[0](xo)); s.zb = np.sort(s.f[0](xn)); s.q = (np.arange(len(xo)) + 0.5) / len(xo)
		else:
			s.kind = "none"

	def __call__(s, p):
		p = np.asarray(p, float); out = np.full(len(p), np.nan); ok = np.isfinite(p)
		if not ok.any() or s.kind == "none":
			return out
		if s.kind == "identity":
			out[ok] = p[ok]; return out
		z = s.f[0](p[ok])
		u = np.interp(z, s.za, s.q)
		y = np.interp(u, s.q, s.zb)
		y = np.where(z < s.za[0], s.zb[0] + (z - s.za[0]), np.where(z > s.za[-1], s.zb[-1] + (z - s.za[-1]), y))
		out[ok] = s.f[1](y); return out


CWS = {"iso_shift": lambda xo, xn, sc: X.CW(xo, xn, sc, "shift"), "iso_clip": lambda xo, xn, sc: X.CW(xo, xn, sc, "clip"),
       "linear": lambda xo, xn, sc: Linear(xo, xn, sc), "equip": lambda xo, xn, sc: Equip(xo, xn, sc)}


def rebuild(cnt_user=None, method="iso_shift"):
	"""ana3.rebuild with a choice of crosswalk method (identical code path for iso_shift)."""
	make = CWS[method]
	ref = A3.build_ref_counts(cnt_user)
	bbw = np.ones(len(A3.BB), int) if cnt_user is None else np.array([cnt_user.get(x, 0) for x in A3.bb_users])
	FOLD, LB, P1 = A3.FOLD, A3.LB, A3.P1
	out = {}
	for c in A3.SCORES:
		rc = np.where(P1, np.nan, LB[c + "_r_b"].values)
		rf = np.where(P1, np.nan, LB[c + "_r_f"].values)
		for d in A3.DIS:
			for s in X.SEXES:
				ix = np.where(P1 & (LB.disease.values == d) & (LB.sex.values == s))[0]
				if not len(ix):
					continue
				xo, xn, rows = A3.BRG[(d, c, s)]
				rep = np.repeat(rows, bbw[rows])
				full = make(xo[rep], xn[rep], X.SCALE[c])
				byk = {k: make(xo[rep[FOLD[rep] != k]], xn[rep[FOLD[rep] != k]], X.SCALE[c]) for k in range(5)}
				pb = LB[c + "_p_b"].values[ix]; pf = LB[c + "_p_f"].values[ix]; fo = LB.fold.values[ix]
				pc = np.full(len(ix), np.nan)
				for k in [None, 0, 1, 2, 3, 4]:
					sel = np.isnan(fo) if k is None else (fo == k)
					if sel.any():
						pc[sel] = (full if k is None else byk[k])(pb[sel])
				rc[ix] = X.to_rank(ref, pc, d, s, c)
				rf[ix] = X.to_rank(ref, pf, d, s, c)
		rc[LB[c + "_r_b"].isna().values] = np.nan; rf[LB[c + "_r_f"].isna().values] = np.nan
		out[c] = (rc, rf)
	return out


# ---------------------------------------------------------------- exposures (users x 3, permuted jointly by rows)
_ev = pd.read_csv(A3.EX / "event_days.csv", parse_dates=["d"]); _ev = _ev[(_ev.n_action > 0) & _ev.user_id.isin(users)]
_ev = _ev.merge(Dr[["user_id", "d_b"]], on="user_id")
ACTION = _ev[(_ev.d > _ev.d_b) & (_ev.d <= _ev.d_b + pd.Timedelta(days=28))].groupby("user_id").size().reindex(users).fillna(0).values.astype(float)
EXPOS = ["login", "login_s1", "action"]
EXPO0 = np.column_stack([Dr.act28.values.astype(float), Dr.act28_susp1.values.astype(float), ACTION])
CUTS = {e: dict(med=np.median(EXPO0[:, j]), t1=np.percentile(EXPO0[:, j], 100 / 3), t2=np.percentile(EXPO0[:, j], 200 / 3),
                q25=np.percentile(EXPO0[:, j], 25), q75=np.percentile(EXPO0[:, j], 75)) for j, e in enumerate(EXPOS)}
CONTRASTS = ["median", "tertile", "continuous"]
ESTS = ["dr", "reg", "ipw", "ow"]
OUTDEF = {"bands5": (20.0, 0, False), "bands3": (100 / 3, 0, False), "bands10": (10.0, 0, False), "shift10": (20.0, 10, False), "incl_lowest": (20.0, 0, True)}
DSETS = {"all": None, "pass18": sorted(A3.PASS["irs"])}
METHODS = list(CWS)
SPECS = [(e, c, m, o, d, cw) for e in EXPOS for c in CONTRASTS for m in (ESTS if c != "continuous" else ["reg"]) for o in OUTDEF for d in DSETS for cw in METHODS]
FACTORS = ["exposure", "contrast", "estimator", "outcome", "diseases", "crosswalk"]
PRIMARY = ("login", "median", "dr", "bands5", "all", "iso_shift")


def group(x, e, contrast):
	cu = CUTS[e]
	if contrast == "median":
		return (x >= cu["med"]).astype(float), np.ones(len(x), bool)
	if contrast == "tertile":
		return (x >= cu["t2"]).astype(float), (x >= cu["t2"]) | (x <= cu["t1"])
	return x.astype(float), np.ones(len(x), bool)


def spec_effect(out, cnt, expo, e, contrast, est, odef, dset, y_override=None):
	width, shift, incl = OUTDEF[odef]
	rc, rf = out["irs"]
	rm = np.ones(len(A3.LB), bool) if DSETS[dset] is None else A3.LB.disease.isin(DSETS[dset]).values
	n, k, mb, mp_ = A3.user_outcome(rc, rf, rm, width, shift, incl)
	x = expo[:, EXPOS.index(e)]
	a, keep = group(x, e, contrast)
	sub = (n > 0) & (cnt > 0) & keep
	f = cnt[sub].astype(float); a_ = a[sub]
	cont = contrast == "continuous"
	if f.sum() < 30 or (not cont and (f[a_ == 1].sum() < 10 or f[a_ == 0].sum() < 10 or len(np.unique(a_)) < 2)):
		return np.nan
	y = (k[sub] / n[sub]) if y_override is None else y_override[sub]
	cov = np.column_stack([Dr.loc[sub, A3.PSV].values, mb[sub], mp_[sub]])
	if cont:
		Xm = S.add_const(np.column_stack([a_, cov]))
		b, ok = S.glm_logit(Xm, y, f)
		X1 = Xm.copy(); X1[:, 1] = CUTS[e]["q75"]; X0 = Xm.copy(); X0[:, 1] = CUTS[e]["q25"]
		if not (ok and np.all(np.isfinite(b))):
			return np.nan
		return np.average(S.expit(X1 @ b), weights=f) - np.average(S.expit(X0 @ b), weights=f)
	ps_ok = True
	if est in ("dr", "ipw"):
		w, _, ps_ok = A3.ps_fit(cnt, sub, (1, 99), a)
	elif est == "ow":
		_, ps, ps_ok = A3.ps_fit(cnt, sub, None, a); w = MV.overlap_weights(ps, a_)
	else:
		w = np.ones(sub.sum())
	m1, m0, ok = A3.frac_standardize(y, cov if est != "ipw" else np.column_stack([mb[sub], mp_[sub]]), a_, w, f)  # IPTW only: baseline band terms only (plan 2.4)
	return (m1 - m0) if (ok and ps_ok) else np.nan


def multiverse(outs, cnt, expo=EXPO0):
	return {s: spec_effect(outs[s[5]], cnt, expo, *s[:5]) for s in SPECS}


# ---------------------------------------------------------------- false movement by crosswalk method (bridge pairs)
REF = pd.read_pickle(A3.FZ / "REF.pkl")
VR = pd.read_pickle(A3.FZ / "VR.pkl")
band = lambda r: np.floor((np.asarray(r, float) - 1) / 20)


def oof_pairs(method):
	"""Cross-validated converted ranks for bridge pairs (as x8b.oof, with the fixed July reference table)."""
	rows = []
	make = CWS[method]
	for d in A3.DIS:
		for c in ["irs", "mrs"]:
			xo, xn, ro, m = X.bridge_values(A3.R, A3.BB, d, c)
			if c == "irs":
				m = m & A3.BB.mode_o.isin(A3.GENO).values
			idx = np.where(m)[0]
			if len(idx) < 30:
				continue
			fo = A3.FOLD[idx]; sx = A3.BB.sex_o.values[idx]
			pred = np.full(len(idx), np.nan); truth = np.full(len(idx), np.nan)
			for k in range(5):
				for s in X.SEXES:
					trs = np.where((fo != k) & (sx == s))[0]; tes = np.where((fo == k) & (sx == s))[0]
					if not len(tes):
						continue
					pred[tes] = X.to_rank(REF, make(xo[idx[trs]], xn[idx[trs]], X.SCALE[c])(xo[idx[tes]]), d, s, c)
					truth[tes] = X.to_rank(REF, xn[idx[tes]], d, s, c)
			rows.append(pd.DataFrame(dict(disease=d, score=c, user_id=A3.BB.user_id.values[idx], raw=ro[idx], pred=pred, truth=truth)))
	return pd.concat(rows, ignore_index=True)


PAIRS = {m: oof_pairs(m) for m in METHODS}
_chk = PAIRS["iso_shift"]; _v = VR[VR.score.isin(["irs", "mrs"])]
if not (len(_chk) == len(_v) and np.allclose(np.nan_to_num(_chk.pred.values, nan=-1), np.nan_to_num(_v.pred.values, nan=-1))
        and np.allclose(np.nan_to_num(_chk.truth.values, nan=-1), np.nan_to_num(_v.truth.values, nan=-1))):
	raise SystemExit("isotonic cross-validated predictions do not reproduce VR.pkl")
BUSERS = np.array(sorted(A3.BB.user_id.unique()))


def false_rates(cu=None):
	"""False down (among eligible pairs, baseline band above the lowest) and false up (all pairs), before and after conversion."""
	out = {}
	for m, V in PAIRS.items():
		w = np.ones(len(V)) if cu is None else V.user_id.map(cu).fillna(0).values.astype(float)
		for sc in ["irs", "mrs"]:
			v = (V.score == sc).values & np.isfinite(V.truth.values) & np.isfinite(V.pred.values) & np.isfinite(V.raw.values)
			bt = band(V.truth.values)
			for when, base in [("before", band(V.raw.values)), ("after", band(V.pred.values))]:
				el = v & (base > 0)
				out[(m, sc, when, "down")] = 100 * np.sum(w * ((bt < base) & el)) / np.sum(w * el)
				out[(m, sc, when, "up")] = 100 * np.sum(w * ((bt > base) & v)) / np.sum(w * v)
	return out


# ---------------------------------------------------------------- quantitative bias analysis (primary crosswalk)
def qba(out, cnt, cu_bridge=None):
	"""Scenario-based sensitivity analysis: the expected false-down share per user from the band-specific false-down probability
	among the cross-validated bridge pairs (same inputs; transported to the analysed users, false down only) and the group
	difference in that share with the primary estimator. The corrected primary difference (primary minus this difference, in
	the same replicate) is formed in robust_report.py. The bridge-pair predictions are fixed, so intervals are conditional on them."""
	V = PAIRS["iso_shift"]; V = V[(V.score == "irs") & np.isfinite(V.truth) & np.isfinite(V.pred)]
	w = np.ones(len(V)) if cu_bridge is None else V.user_id.map(cu_bridge).fillna(0).values.astype(float)
	bp, bt = band(V.pred.values), band(V.truth.values)
	pfd = {}
	for b in range(1, 5):
		m = bp == b
		pfd[b] = np.sum(w * (m & (bt < bp))) / np.sum(w * m) if np.sum(w * m) > 0 else 0.0
	rc, rf = out["irs"]
	ok = np.isfinite(rc) & np.isfinite(rf); bc = band(rc); elig = ok & (bc > 0)
	pr = np.where(elig & A3.P1, np.vectorize(lambda b: pfd.get(int(b), 0.0) if np.isfinite(b) else 0.0)(bc), 0.0)
	ui = A3.LB.ui.values
	n = np.bincount(ui[elig], minlength=NU).astype(float); k = np.bincount(ui[elig & (band(rf) < bc)], minlength=NU).astype(float)
	e = np.bincount(ui, weights=pr, minlength=NU)
	with np.errstate(invalid="ignore", divide="ignore"):
		exp_share = np.where(n > 0, e / n, np.nan)
	r = {f"pfd_band{b}": 100 * v for b, v in pfd.items()}
	r["exp_diff"] = spec_effect(out, cnt, EXPO0, "login", "median", "dr", "bands5", "all", y_override=exp_share)
	sub = (n > 0) & (cnt > 0); A = A3.A
	r["exp_share_high"] = 100 * np.average(exp_share[sub & (A == 1)], weights=cnt[sub & (A == 1)])
	r["exp_share_low"] = 100 * np.average(exp_share[sub & (A == 0)], weights=cnt[sub & (A == 0)])
	return r


# ---------------------------------------------------------------- replicates
def boot_counts(seed):
	rng = np.random.default_rng(seed)
	cu = {}
	for st in A3.STRATA:  # same draw as ana3.one_boot
		draw = rng.choice(st, len(st), replace=True)
		u, c = np.unique(draw, return_counts=True)
		cu.update(dict(zip(u, c)))
	return cu, np.array([cu.get(u, 0) for u in users]).astype(float)


def one_boot(seed):
	cu, cnt = boot_counts(seed)
	try:
		outs = {m: rebuild(cu, m) for m in METHODS}
		return dict(mv=multiverse(outs, cnt), fr=false_rates(cu), qba=qba(outs["iso_shift"], cnt, cu))
	except Exception as ex:
		return {"error": repr(ex)}


OUTS0 = None


def one_perm(seed):
	rng = np.random.default_rng(seed)
	try:
		return multiverse(OUTS0, np.ones(NU), EXPO0[rng.permutation(NU)])
	except Exception as ex:
		return {"error": repr(ex)}


if __name__ == "__main__":
	ap = argparse.ArgumentParser(); ap.add_argument("--boot", type=int, default=1000); ap.add_argument("--perm", type=int, default=500)
	ap.add_argument("--workers", type=int, default=10)
	a = ap.parse_args()
	print("users", NU, "specs", len(SPECS), "bridge pairs per method", {m: len(v) for m, v in PAIRS.items()})
	for j, e in enumerate(EXPOS):
		x = EXPO0[:, j]; print(f"exposure {e}: median {np.median(x):.0f}, IQR {CUTS[e]['q25']:.0f}-{CUTS[e]['q75']:.0f}, thirds <= {CUTS[e]['t1']:.1f} / >= {CUTS[e]['t2']:.1f}")
	OUTS0 = {m: rebuild(None, m) for m in METHODS}
	for c in A3.SCORES:  # iso_shift path must equal ana3.rebuild
		r0, r1 = A3.rebuild(None)[c], OUTS0["iso_shift"][c]
		if not (np.allclose(np.nan_to_num(r0[0], nan=-1), np.nan_to_num(r1[0], nan=-1)) and np.allclose(np.nan_to_num(r0[1], nan=-1), np.nan_to_num(r1[1], nan=-1))):
			raise SystemExit("rebuild(iso_shift) differs from ana3.rebuild")
	P0 = multiverse(OUTS0, np.ones(NU))
	E = pd.read_pickle(OUT / "est_point.pkl")["main"]["diff"]
	if not (abs(P0[PRIMARY] - E) <= 1e-10):  # also fails when the estimate is NaN
		raise SystemExit(f"primary specification does not reproduce the main estimate: {P0[PRIMARY]} vs {E}")
	print("primary specification reproduces the main point estimate")
	F0 = false_rates(); Q0 = qba(OUTS0["iso_shift"], np.ones(NU))
	with mp.get_context("fork").Pool(a.workers) as pool:
		BS = pool.map(one_boot, [20261123 + i for i in range(a.boot)], chunksize=5)
		PM = pool.map(one_perm, [95000 + i for i in range(a.perm)], chunksize=5)
	print("bootstrap replicates", len(BS), "errors", sum("error" in b for b in BS), "; permutations", len(PM), "errors", sum("error" in p for p in PM))
	pd.to_pickle(dict(point=P0, fr=F0, qba=Q0, boot=BS, perm=PM, specs=SPECS, factors=FACTORS, cuts=CUTS,
	                  pair_n={m: int(len(v)) for m, v in PAIRS.items()}), OUT / "robust_03.pkl")
	print("wrote robust_03.pkl")
