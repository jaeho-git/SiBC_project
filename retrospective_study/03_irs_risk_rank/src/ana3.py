# -*- coding: utf-8 -*-
"""Study 03 outcome analysis (engagement vs IRS band movement), following 00_common/docs/local/분석사양_결과분석.md.

Run from retrospective_study/:  python3 03_irs_risk_rank/src/ana3.py [--boot 1000] [--workers 10]
Reads the frozen comparison-set files (03_irs_risk_rank/00_Data/frozen_20261119/, read only), the common login /
activity extracts and the 01 step extract; writes tables, figures and a JSON of estimates to
03_irs_risk_rank/01_Results/analysis/ (git-ignored). Prints aggregates only.

Main steps
1. rebuild(): baseline rank on the comparison scale and follow-up rank for every user x disease x score. For a follow-up
   on the July model (P1) the baseline is converted with the cross-fitted isotonic crosswalk (xwlib.CW) and both are
   ranked with the July reference table; same-model follow-ups (P0) keep the service ranks. At the original data this
   reproduces L2.pkl (checked at start).
2. estimates(): propensity weights, representative outcome (fractional logit, marginal standardization), per-disease
   risk ratios / differences, dose-response, sensitivity analyses.
3. Bootstrap: users are resampled within membership strata (bridge pairs / reference table / analysis set) so that a
   user carries one count across all three; every replicate rebuilds the crosswalk, reference table, bands, weights
   and models.
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path.cwd()
FZ = ROOT / "03_irs_risk_rank/00_Data/frozen_20261119"
OUT = ROOT / "03_irs_risk_rank/01_Results/analysis"
sys.path.insert(0, str(ROOT / "03_irs_risk_rank/src"))
sys.path.insert(0, str(ROOT / "00_common/src"))
import statlib as S  # noqa: E402

_cwd = os.getcwd(); os.chdir(FZ)
import xwlib as X  # noqa: E402
R, I, D_old, BB = X.load()
os.chdir(_cwd)
D2 = pd.read_pickle(FZ / "D2.pkl")
L2 = pd.read_pickle(FZ / "L2.pkl")
DIS = list(pd.read_pickle(FZ / "DIS.pkl"))
MET = pd.read_pickle(FZ / "MET.pkl")
SCORES = ["irs", "mrs", "lrs"]
GENO = {"1", "4"}
POST = pd.Timestamp("2026-05-01")

# ---------------------------------------------------------------- fixed inputs
imode = I.set_index("seq")["mode"].astype(str)
BB["mode_o"] = BB.seq_o.map(imode)
FOLD, _ = X.folds(BB)
BB["fold"] = FOLD
ufold = BB.groupby("user_id").fold.first().to_dict()

Dr = D2.reset_index()
Dr["fold"] = Dr.user_id.map(ufold)
users = Dr.user_id.values
uidx = {u: i for i, u in enumerate(users)}

# crosswalk pass list (IRS/MRS): agreement after conversion >= 95% in every sex the disease has
def pass_list(score):
	m = MET[(MET.score == score) & MET.sex.isin(["F", "M"])]
	ok = m.groupby("disease").rate.min() >= 0.95
	return set(ok[ok].index)


PASS = {"irs": pass_list("irs"), "mrs": pass_list("mrs")}

# reference-table rows (stable July period) as arrays per (disease, sex, score)
T = R[(R.t >= X.TS) & (R.t < X.B1)].copy()
ref_users = T.user_id.unique()
REFG = {}
for (d, s), g in T.groupby(["disease", "sex"]):
	for c in SCORES:
		k = g[c + "_pn"].notna() & g[c + "_rn"].notna()
		REFG[(d, s, c)] = (g.loc[k, c + "_pn"].values, g.loc[k, c + "_rn"].values, g.loc[k, "user_id"].values)

# bridge pairs per (disease, score, sex): row indices into BB
BRG = {}
for d in DIS:
	for c in SCORES:
		xo, xn, ro, m = X.bridge_values(R, BB, d, c)
		if c in ("irs", "prs"):
			m = m & BB.mode_o.isin(GENO).values
		for s in X.SEXES:
			BRG[(d, c, s)] = (xo, xn, np.where(m & (BB.sex_o.values == s))[0])
bb_users = BB.user_id.values

# analysis long table (raw service values) from L2
base_cols = ["user_id", "disease", "sex", "model_f", "fold"] + [c + k for c in SCORES for k in ["_p_b", "_r_b", "_p_f", "_r_f"]] + ["prs_r_b"]
LB = L2[base_cols].copy()
LB["ui"] = LB.user_id.map(uidx)
P1 = (LB.model_f == "P1").values


def build_ref_counts(cnt_user):
	ref = {}
	for key, (p, r, u) in REFG.items():
		w = np.ones(len(p), int) if cnt_user is None else np.array([cnt_user.get(x, 0) for x in u])
		if w.sum() == 0:
			continue
		pp, rr = np.repeat(p, w), np.repeat(r, w)
		o = np.lexsort((rr, pp))
		ref[key] = (pp[o], rr[o])
	return ref


def rebuild(cnt_user=None):
	"""Comparison-scale baseline rank (r_c) and follow-up rank (r_fs) for each LB row and score."""
	ref = build_ref_counts(cnt_user)
	bbw = np.ones(len(BB), int) if cnt_user is None else np.array([cnt_user.get(x, 0) for x in bb_users])
	out = {}
	for c in SCORES:
		rc = np.where(P1, np.nan, LB[c + "_r_b"].values)
		rf = np.where(P1, np.nan, LB[c + "_r_f"].values)
		for d in DIS:
			for s in X.SEXES:
				ix = np.where(P1 & (LB.disease.values == d) & (LB.sex.values == s))[0]
				if not len(ix):
					continue
				xo, xn, rows = BRG[(d, c, s)]
				rep = np.repeat(rows, bbw[rows])
				full = X.CW(xo[rep], xn[rep], X.SCALE[c], "shift")
				byk = {k: X.CW(xo[rep[FOLD[rep] != k]], xn[rep[FOLD[rep] != k]], X.SCALE[c], "shift") for k in range(5)}
				pb = LB[c + "_p_b"].values[ix]; pf = LB[c + "_p_f"].values[ix]; fo = LB.fold.values[ix]
				pc = np.full(len(ix), np.nan)
				for k in [None, 0, 1, 2, 3, 4]:
					sel = np.isnan(fo) if k is None else (fo == k)
					if sel.any():
						fn = full if k is None else byk[k]
						pc[sel] = fn(pb[sel])
				rc[ix] = X.to_rank(ref, pc, d, s, c)
				rf[ix] = X.to_rank(ref, pf, d, s, c)
		nob = LB[c + "_r_b"].isna().values; nof = LB[c + "_r_f"].isna().values
		rc[nob] = np.nan; rf[nof] = np.nan
		out[c] = (rc, rf)
	return out


# ---------------------------------------------------------------- user-level covariates and exposure
steps = pd.read_csv(ROOT / "01_wearable_metrics/00_Data/extract_20261120/steps.csv", parse_dates=["d"])
first_step = steps.groupby("user_id").d.min()
Dr["d_b"] = pd.to_datetime(Dr.t_b).dt.normalize()
Dr["wear_pre"] = (Dr.user_id.map(first_step) < Dr.d_b).fillna(False).astype(float)
Dr["female"] = (Dr.sex == "F").astype(float)
t0 = Dr.d_b.min()
Dr["base_day"] = (Dr.d_b - t0).dt.days.astype(float)
Dr["age"] = pd.to_numeric(Dr.age_b, errors="coerce").astype(float)
PSV = ["age", "female", "k_b", "act_pre", "base_day", "wear_pre"]
for v in PSV:
	Dr[v] = Dr[v].astype(float)
if Dr[PSV].isna().any().any():
	raise SystemExit("missing propensity covariates")
LCH = (Dr.life_ch == "예").values  # lifestyle input changed between baseline and follow-up
if LCH.sum() + (Dr.life_ch == "아니오").sum() != len(Dr):
	raise SystemExit("unexpected life_ch values")
MED = float(np.median(Dr.act28))
A = (Dr.act28 >= MED).astype(float).values

# suspect login days inside each exposure window (rule 1: any source, rule 2: action events only)
EX = ROOT / "00_common/00_Data/extract_20261123"
lg = pd.read_csv(EX / "login_hours_days.csv", parse_dates=["d"])
lg = lg[lg.user_id.isin(users)]
def _days(f, col=None):
	x = pd.read_csv(EX / f, parse_dates=["d"])
	if col:
		x = x[x[col] > 0]
	return set(zip(x.user_id, x.d))
act = _days("event_days.csv", "n_action")
broad = act | _days("inbound_days.csv") | _days("mood_days.csv") | _days("weekly_checkup_days.csv")
key = list(zip(lg.user_id, lg.d))
lg["susp1"] = (lg.d >= POST) & (lg.n == 1) & ~np.array([k in broad for k in key])
lg["susp2"] = (lg.d >= POST) & (lg.n == 1) & ~np.array([k in act for k in key])
lg = lg.merge(Dr[["user_id", "d_b"]], on="user_id")
w_in = (lg.d > lg.d_b) & (lg.d <= lg.d_b + pd.Timedelta(days=28))
chk = lg[w_in].groupby("user_id").size().reindex(users).fillna(0).values
if not np.array_equal(chk, Dr.act28.values):
	raise SystemExit("exposure window login days differ from D2.act28")
for r in ["susp1", "susp2"]:
	Dr["act28_" + r] = Dr.act28 - lg[w_in & lg[r]].groupby("user_id").size().reindex(users).fillna(0).values


# ---------------------------------------------------------------- estimators
def bands(r, width=20.0, shift=0):
	return np.floor((np.asarray(r, float) - 1 + shift) / width)


def user_outcome(rc, rf, rows_mask, width=20.0, shift=0, include_lowest=False):
	"""Per-user count of eligible diseases, of those moving down, mean baseline band and within-band position."""
	ok = rows_mask & np.isfinite(rc) & np.isfinite(rf)
	bc, bf = bands(rc, width, shift), bands(rf, width, shift)
	low = bands(1, width, shift)
	elig = ok if include_lowest else ok & (bc > low)
	down = elig & (bf < bc)
	pos = ((np.asarray(rc, float) - 1 + shift) % width) / width
	ui = LB.ui.values
	n = np.bincount(ui[elig], minlength=len(users)).astype(float)
	k = np.bincount(ui[down], minlength=len(users)).astype(float)
	sb = np.bincount(ui[elig], weights=bc[elig], minlength=len(users))
	sp = np.bincount(ui[elig], weights=pos[elig], minlength=len(users))
	with np.errstate(invalid="ignore", divide="ignore"):
		return n, k, sb / n, sp / n


def ps_fit(cnt, sub, trunc=(1, 99), a=A):
	"""Stabilized ATE weights for users in `sub` with frequency counts `cnt` (bootstrap)."""
	Xp = Dr.loc[sub, PSV].values; aa = a[sub]; f = cnt[sub]
	Xc = S.add_const(Xp)
	b, ok = S.glm_logit(Xc, aa, f)
	if not ok or not np.all(np.isfinite(b)) or np.max(np.abs(b)) > 15:  # separation (rare binary covariate in a resample)
		b, ok = S.firth_logit(Xc, aa, f)
	ok = bool(ok and np.all(np.isfinite(b)))
	ps = S.expit(Xc @ b)
	p1 = np.average(aa, weights=f)
	w = np.where(aa == 1, p1 / ps, (1 - p1) / (1 - ps))
	if trunc is not None:
		lo, hi = np.percentile(np.repeat(w, f.astype(int)), trunc)
		w = np.clip(w, lo, hi)
	return w, ps, ok


def frac_standardize(y, X_cov, a, w, f, avg=None):
	"""Fractional logit E[y|a, X], fitted with weights w*f; standardized means (a=1, a=0) averaged with weights `avg`
	(default f: users count equally; for the disease-count-weighted estimand avg = f * denominator)."""
	Xm = S.add_const(np.column_stack([a, X_cov]))
	b, ok = S.glm_logit(Xm, y, w * f)
	avg = f if avg is None else avg
	X1 = Xm.copy(); X1[:, 1] = 1; X0 = Xm.copy(); X0[:, 1] = 0
	m1 = np.average(S.expit(X1 @ b), weights=avg); m0 = np.average(S.expit(X0 @ b), weights=avg)
	return m1, m0, ok and np.all(np.isfinite(b))


def representative(out, cnt, sub_users=None, width=20.0, shift=0, include_lowest=False, score="irs", diseases=None,
                   weighting="ps", trunc=(1, 99), pooled=False, a=A, extra=None):
	rc, rf = out[score]
	rm = np.ones(len(LB), bool) if diseases is None else LB.disease.isin(diseases).values
	n, k, mb, mp_ = user_outcome(rc, rf, rm, width, shift, include_lowest)
	sub = (n > 0) & (cnt > 0)
	if sub_users is not None:
		sub &= sub_users
	f_ = cnt[sub].astype(float); a_ = a[sub]
	if f_.sum() < 30 or f_[a_ == 1].sum() < 10 or f_[a_ == 0].sum() < 10 or len(np.unique(a_)) < 2:  # common minimum-n rule, resampling frequencies
		return dict(diff=np.nan, ratio=np.nan, m1=np.nan, m0=np.nan, n=int(f_.sum()), conv=False, min_n=True)
	f = cnt[sub].astype(float)
	ps_ok = True
	if weighting == "ps":
		w, _, ps_ok = ps_fit(cnt, sub, trunc, a)
		cov = np.column_stack([Dr.loc[sub, PSV].values, mb[sub], mp_[sub]] + ([extra[sub]] if extra is not None else []))
	else:
		w = np.ones(sub.sum()); cov = np.empty((sub.sum(), 0))
	y = k[sub] / n[sub]
	ww = w * n[sub] if pooled else w
	m1, m0, ok = frac_standardize(y, cov, a[sub], ww, f, avg=f * n[sub] if pooled else None)
	return dict(diff=m1 - m0, ratio=m1 / m0, m1=m1, m0=m0, n=int(f.sum()), n_hi=int(f[a[sub] == 1].sum()), conv=bool(ok and ps_ok))


def per_disease(out, cnt, score, sub_users, w_user, ps_ok=True):
	"""Marginal RR and RD of moving down per disease among eligible users."""
	rc, rf = out[score]
	res = {}
	bc, bf = bands(rc), bands(rf)
	pos = ((np.asarray(rc, float) - 1) % 20) / 20
	for d in DIS:
		ix = np.where((LB.disease.values == d) & np.isfinite(rc) & np.isfinite(rf) & (bc > 0))[0]
		ui = LB.ui.values[ix]
		keep = sub_users[ui] & (cnt[ui] > 0)
		ix, ui = ix[keep], ui[keep]
		f = cnt[ui].astype(float); a = A[ui]; y = (bf[ix] < bc[ix]).astype(float)
		n1, n0 = f[a == 1].sum(), f[a == 0].sum()
		e1, e0 = (f * y)[a == 1].sum(), (f * y)[a == 0].sum()
		r = dict(n=int(f.sum()), n1=int(n1), n0=int(n0), e1=int(e1), e0=int(e0), crude1=e1 / n1 if n1 else np.nan, crude0=e0 / n0 if n0 else np.nan,
		         rr=np.nan, rd=np.nan, rr_firth=np.nan, rr_cov=np.nan, tested=False)
		if f.sum() < 30 or n1 < 10 or n0 < 10:
			r["reason"] = "min_n"; res[d] = r; continue
		Xm = S.add_const(np.column_stack([a, bc[ix], pos[ix]]))
		X1 = Xm.copy(); X1[:, 1] = 1; X0 = Xm.copy(); X0[:, 1] = 0
		std = lambda b, A1=X1, A0=X0: (np.average(S.expit(A1 @ b), weights=f), np.average(S.expit(A0 @ b), weights=f))
		bF, okF = S.firth_logit(Xm, y, w_user[ui] * f)  # sparse-data sensitivity (defined even with separation)
		if okF:
			q1, q0 = std(bF); r["rr_firth"] = q1 / q0
		if not (0 < e1 < n1 and 0 < e0 < n0):
			r["reason"] = "no_variation"; res[d] = r; continue
		b, ok = S.glm_logit(Xm, y, w_user[ui] * f)
		if not ok or not np.all(np.isfinite(b)):
			r["reason"] = "nonconv"; res[d] = r; continue
		if np.max(np.abs(b)) > 15:
			r["reason"] = "large_coef"; res[d] = r; continue
		p1, p0 = std(b)
		r.update(rr=p1 / p0, rd=p1 - p0, p1=p1, p0=p0, tested=True, reason="tested", conv=bool(ps_ok))
		Xc = S.add_const(np.column_stack([a, bc[ix], pos[ix], Dr.loc[ui, PSV].values]))  # sensitivity: PS covariates also in the outcome model
		bc_, okc = S.glm_logit(Xc, y, w_user[ui] * f)
		if okc and np.all(np.isfinite(bc_)) and np.max(np.abs(bc_)) <= 15:
			C1 = Xc.copy(); C1[:, 1] = 1; C0 = Xc.copy(); C0[:, 1] = 0
			r["rr_cov"] = np.average(S.expit(C1 @ bc_), weights=f) / np.average(S.expit(C0 @ bc_), weights=f)
		res[d] = r
	return res


def dose_response(out, cnt, knots, q25, q75):
	rc, rf = out["irs"]
	n, k, mb, mp_ = user_outcome(rc, rf, np.ones(len(LB), bool))
	sub = (n > 0) & (cnt > 0)
	f = cnt[sub].astype(float); y = k[sub] / n[sub]
	x = Dr.act28.values[sub]
	Xm = S.add_const(np.column_stack([S.rcs(x, knots), Dr.loc[sub, PSV].values, mb[sub], mp_[sub]]))
	b, ok = S.glm_logit(Xm, y, f)
	def mean_at(v):
		Xv = Xm.copy(); Xv[:, 1:3] = S.rcs(np.full(len(x), v), knots)
		return np.average(S.expit(Xv @ b), weights=f)
	grid = np.arange(0, 29)
	return dict(diff=mean_at(q75) - mean_at(q25), nonlin=b[2], curve=[mean_at(v) for v in grid], conv=bool(ok and np.all(np.isfinite(b))))


def estimates(cnt):
	"""All estimates for one data set (cnt = per-user frequency; ones = original data)."""
	cu = None if np.all(cnt == 1) and cnt is CNT1 else CNT_USER
	out = rebuild(cu)
	allu = np.ones(len(users), bool)
	e = {"main": representative(out, cnt)}
	# sensitivity analyses
	e["pass18"] = representative(out, cnt, diseases=sorted(PASS["irs"]))
	e["same_model"] = representative(out, cnt, sub_users=(Dr.model_f == "P0").values)
	e["bands3"] = representative(out, cnt, width=100 / 3)
	e["bands10"] = representative(out, cnt, width=10.0)
	e["shift10"] = representative(out, cnt, shift=10)  # +10 and -10 give the same partition when the width is 20
	e["incl_lowest"] = representative(out, cnt, include_lowest=True)
	e["base28"] = representative(out, cnt, sub_users=(Dr.k_b <= 28).values)
	e["pooled"] = representative(out, cnt, pooled=True)
	e["life_ch"] = representative(out, cnt, sub_users=LCH)
	e["no_life_ch"] = representative(out, cnt, sub_users=~LCH)
	e["no_trunc"] = representative(out, cnt, trunc=None)
	e["unadjusted"] = representative(out, cnt, weighting="none")
	for r in ["susp1", "susp2"]:
		alt = Dr["act28_" + r].values
		e[r] = representative(out, cnt, a=(alt >= np.median(alt)).astype(float))
	e["mrs_rep"] = representative(out, cnt, score="mrs")
	e["lrs_rep"] = representative(out, cnt, score="lrs", sub_users=LCH)
	# per-disease (weights from the main PS model on all users with any eligible IRS disease)
	sub = cnt > 0
	w_all = np.zeros(len(users)); w, _, ok_all = ps_fit(cnt, sub); w_all[sub] = w
	e["dis_irs"] = per_disease(out, cnt, "irs", allu, w_all, ok_all)
	e["dis_mrs"] = per_disease(out, cnt, "mrs", allu, w_all, ok_all)
	lch = LCH
	w_l = np.zeros(len(users)); sl = sub & lch; wl, _, ok_l = ps_fit(cnt, sl); w_l[sl] = wl
	e["dis_lrs"] = per_disease(out, cnt, "lrs", lch, w_l, ok_l)
	e["dose"] = dose_response(out, cnt, KNOTS, Q25, Q75)
	# descriptive: engagement x lifestyle-input change (no mediation claim)
	n_, k_, _, _ = user_outcome(*out["irs"], np.ones(len(LB), bool))
	ok_ = (n_ > 0) & (cnt > 0); pr = np.where(ok_, k_ / np.where(n_ > 0, n_, 1), np.nan)
	e["four_group"] = {f"{int(hh)}_{int(ll)}": dict(n=int(cnt[ok_ & (A == hh) & (LCH == ll)].sum()),
	                   mean=float(np.average(pr[ok_ & (A == hh) & (LCH == ll)], weights=cnt[ok_ & (A == hh) & (LCH == ll)])) if (ok_ & (A == hh) & (LCH == ll) & (cnt > 0)).any() else np.nan)
	                   for hh in (1, 0) for ll in (True, False)}
	# follow-up interval (exploratory; the interval is measured after the exposure window)
	e["gap_common"] = representative(out, cnt, sub_users=(Dr.gap >= GAP_LO).values & (Dr.gap <= GAP_HI).values)
	e["gap_adj"] = representative(out, cnt, extra=np.log(Dr.gap.values.astype(float)))
	return e


_g1, _g0 = Dr.gap[A == 1], Dr.gap[A == 0]
GAP_LO = float(max(np.percentile(_g1, 5), np.percentile(_g0, 5))); GAP_HI = float(min(np.percentile(_g1, 95), np.percentile(_g0, 95)))
CNT1 = np.ones(len(users), int)
CNT_USER = None
KNOTS = np.percentile(Dr.act28, [10, 50, 90])
Q25, Q75 = np.percentile(Dr.act28, [25, 75])


# ---------------------------------------------------------------- bootstrap
ALL_USERS = np.array(sorted(set(users) | set(bb_users) | set(ref_users)))
memb = pd.DataFrame({"user_id": ALL_USERS})
memb["key"] = (memb.user_id.isin(users).astype(int).astype(str) + memb.user_id.isin(bb_users).astype(int).astype(str)
               + memb.user_id.isin(ref_users).astype(int).astype(str))
STRATA = [g.user_id.values for _, g in memb.groupby("key")]


def one_boot(seed):
	global CNT_USER
	rng = np.random.default_rng(seed)
	cu = {}
	for st in STRATA:
		draw = rng.choice(st, len(st), replace=True)
		u, c = np.unique(draw, return_counts=True)
		cu.update(dict(zip(u, c)))
	CNT_USER = cu
	cnt = np.array([cu.get(u, 0) for u in users])
	try:
		return estimates(cnt)
	except Exception as ex:  # keep the replicate count honest
		return {"error": repr(ex)}


def check_rebuild():
	out = rebuild(None)
	for c in SCORES:
		rc, rf = out[c]
		a1 = np.allclose(np.nan_to_num(rc, nan=-1), np.nan_to_num(L2[c + "_r_c"].values, nan=-1))
		a2 = np.allclose(np.nan_to_num(rf, nan=-1), np.nan_to_num(L2[c + "_r_fs"].values, nan=-1))
		if not (a1 and a2):
			raise SystemExit(f"rebuild does not reproduce L2 for {c}: r_c {a1}, r_fs {a2}")
	print("rebuild reproduces L2 (r_c, r_fs) for", SCORES)


if __name__ == "__main__":
	ap = argparse.ArgumentParser(); ap.add_argument("--boot", type=int, default=1000); ap.add_argument("--workers", type=int, default=10)
	a = ap.parse_args()
	OUT.mkdir(parents=True, exist_ok=True)
	print("pass lists:", len(PASS["irs"]), "IRS,", len(PASS["mrs"]), "MRS; median exposure", MED, "; high", int(A.sum()), "low", int((1 - A).sum()))
	check_rebuild()
	E0 = estimates(CNT1)
	pd.to_pickle(E0, OUT / "est_point.pkl")
	print("point estimates done")
	if a.boot > 0:
		ctx = mp.get_context("fork")
		with ctx.Pool(a.workers) as pool:
			BS = pool.map(one_boot, [20261123 + i for i in range(a.boot)], chunksize=5)
		pd.to_pickle(BS, OUT / "est_boot.pkl")
		print("bootstrap replicates", len(BS), "errors", sum("error" in b for b in BS))
