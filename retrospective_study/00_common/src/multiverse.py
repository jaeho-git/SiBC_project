# -*- coding: utf-8 -*-
"""Post hoc robustness tools shared by robust1.py, robust2.py and robust3.py (plan: 00_common/docs/local/견고성분석계획).

- ci_table: per-specification estimate, bootstrap percentile 95% CI, bootstrap SE and valid replicate count
- curve_summary: specification-curve summary for a set of specifications (median and its bootstrap CI, share of CIs
  excluding zero by direction)
- perm_test: joint test by permutation (number of specifications with |z| > 1.96 and the median z, with z from the
  observed bootstrap SE)
- overlap_weights, ordinal_fit: overlap weights and a weighted cumulative-logit (proportional odds) model
Specifications are tuples of factor levels; replicate dictionaries map a specification to its estimate (nan when the
replicate failed the minimum-n rule or did not converge).
"""
import numpy as np
import pandas as pd
from scipy import optimize, special

MIN_VALID = 900


def ci_table(point, boots, factors, min_valid=MIN_VALID):
	rows = []
	good = [b for b in boots if isinstance(b, dict) and "error" not in b]
	for s, e in point.items():
		v = np.array([b.get(s, np.nan) for b in good], float)
		v = v[np.isfinite(v)]
		ok = bool(np.isfinite(e) and len(v) >= min_valid)
		r = dict(zip(factors, s))
		r.update(est=e, lo=np.percentile(v, 2.5) if ok else np.nan, hi=np.percentile(v, 97.5) if ok else np.nan,
		         se=np.std(v, ddof=1) if ok else np.nan, valid=len(v), reported=ok)
		rows.append(r)
	t = pd.DataFrame(rows)
	t["spec"] = list(point.keys())
	return t


def curve_summary(tab, boots, specs):
	"""tab from ci_table; specs = list of specification tuples forming one curve."""
	t = tab[tab.spec.isin(specs) & tab.reported]
	good = [b for b in boots if isinstance(b, dict) and "error" not in b]
	sp = list(t.spec)
	r = dict(n_specs=len(specs), n_reported=len(t))
	if not len(t):
		return r
	vals = np.array([[b.get(s, np.nan) for s in sp] for b in good], float)
	nvalid = np.isfinite(vals).sum(axis=1)
	med_b = np.array([np.nanmedian(v) if np.isfinite(v).any() else np.nan for v in vals])  # median over the specifications valid in that replicate
	med_b = med_b[np.isfinite(med_b)]
	r.update(rep_complete=int(np.sum(nvalid == len(sp))), rep_valid_min=int(nvalid.min()) if len(nvalid) else 0, rep_valid_median=float(np.median(nvalid)) if len(nvalid) else 0.0)
	r.update(median=float(np.median(t.est)), median_lo=np.percentile(med_b, 2.5), median_hi=np.percentile(med_b, 97.5),
	         min=float(t.est.min()), max=float(t.est.max()), share_pos=float(np.mean(t.lo > 0)), share_neg=float(np.mean(t.hi < 0)),
	         n_pos=int(np.sum(t.lo > 0)), n_neg=int(np.sum(t.hi < 0)))
	return r


def perm_test(tab, perms, specs):
	"""Joint permutation test over a set of specifications (z = estimate / observed bootstrap SE)."""
	t = tab[tab.spec.isin(specs) & tab.reported & (tab.se > 0)]
	sp = list(t.spec); se = t.se.values
	if not len(sp):
		return dict(n_specs=0)
	z0 = t.est.values / se
	c0, m0 = int(np.sum(np.abs(z0) > 1.96)), float(np.median(z0))
	cs, ms, complete = [], [], 0
	for p in perms:
		if not isinstance(p, dict) or "error" in p:
			continue
		z = np.array([p.get(s, np.nan) for s in sp], float) / se
		complete += int(np.isfinite(z).all())
		z = z[np.isfinite(z)]  # specifications that failed in a permutation are left out of that permutation's count
		if not len(z):
			continue
		cs.append(int(np.sum(np.abs(z) > 1.96))); ms.append(float(np.median(z)))
	cs, ms = np.array(cs), np.array(ms)
	return dict(n_specs=len(sp), n_sig_obs=c0, n_sig_perm_mean=float(cs.mean()), n_sig_perm_95=float(np.percentile(cs, 95)),
	            p_count=(1 + np.sum(cs >= c0)) / (1 + len(cs)), median_z_obs=m0, p_median=(1 + np.sum(np.abs(ms) >= abs(m0))) / (1 + len(ms)),
	            n_perm=len(cs), n_perm_complete=complete)


def overlap_weights(ps, a):
	ps = np.asarray(ps, float); a = np.asarray(a, float)
	return np.where(a == 1, 1 - ps, ps)


class Ordinal:
	"""Weighted cumulative-logit model P(Y <= c_j) = expit(theta_j - x'b) on the observed values of y (ordered categories).
	X has no intercept. Covariates are centred and scaled inside the fit. mean(Xnew) gives E[Y | x] = sum_j c_j P(Y = c_j)."""

	def __init__(self, X, y, w):
		X = np.asarray(X, float); y = np.asarray(y, float); w = np.asarray(w, float)
		keep = w > 0
		self.cats = np.unique(y[keep]); K = len(self.cats)
		if K < 3:  # fewer than 3 observed categories: not fitted (checked before the starting values are built)
			self.conv = False; self.p = X.shape[1]; self.b = np.full(X.shape[1], np.nan); self.th = np.full(max(K - 1, 1), np.nan)
			self.m = np.zeros(X.shape[1]); self.s = np.ones(X.shape[1]); return
		self.m = np.average(X[keep], axis=0, weights=w[keep]); s = np.sqrt(np.average((X[keep] - self.m) ** 2, axis=0, weights=w[keep])); s[s == 0] = 1.0
		self.s = s
		Z = (X[keep] - self.m) / s; yi = np.searchsorted(self.cats, y[keep]); ww = w[keep]
		p = Z.shape[1]; self.p = p
		cum = np.cumsum(np.bincount(yi, weights=ww, minlength=K))[:-1] / ww.sum()
		th0 = np.log(np.clip(cum, 1e-4, 1 - 1e-4) / (1 - np.clip(cum, 1e-4, 1 - 1e-4)))
		th0 = np.maximum.accumulate(th0 + np.arange(K - 1) * 1e-6)
		par0 = np.r_[np.zeros(p), th0[0], np.log(np.maximum(np.diff(th0), 1e-3))]

		def f(par):
			b = par[:p]; th = np.cumsum(np.r_[par[p], np.exp(par[p + 1:])])
			eta = Z @ b
			thx = np.r_[-np.inf, th, np.inf]
			up, lo = thx[yi + 1] - eta, thx[yi] - eta
			Fu, Fl = special.expit(up), special.expit(lo)
			P = np.maximum(Fu - Fl, 1e-300)
			fu, fl = Fu * (1 - Fu), Fl * (1 - Fl)
			nll = -np.sum(ww * np.log(P))
			gb = Z.T @ (ww * (fu - fl) / P)
			gth = np.zeros(K - 1)
			np.add.at(gth, yi[yi < K - 1], -(ww * fu / P)[yi < K - 1])
			np.add.at(gth, yi[yi > 0] - 1, (ww * fl / P)[yi > 0])
			tail = np.cumsum(gth[::-1])[::-1]
			g = np.r_[gb, tail[0], np.exp(par[p + 1:]) * tail[1:]]
			return nll, g

		r = optimize.minimize(f, par0, jac=True, method="L-BFGS-B", options={"maxiter": 5000, "ftol": 1e-14, "gtol": 1e-9})
		_, g = f(r.x)
		self.conv = bool(np.all(np.isfinite(r.x)) and np.max(np.abs(g)) / ww.sum() < 1e-5)
		self.b = r.x[:p]; self.th = np.cumsum(np.r_[r.x[p], np.exp(r.x[p + 1:])])

	def mean(self, Xnew):
		Z = (np.asarray(Xnew, float) - self.m) / self.s
		eta = Z @ self.b
		F = special.expit(self.th[None, :] - eta[:, None])
		F = np.column_stack([np.zeros(len(eta)), F, np.ones(len(eta))])
		P = np.diff(F, axis=1)
		return P @ self.cats
