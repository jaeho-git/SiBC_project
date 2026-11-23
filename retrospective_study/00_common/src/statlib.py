# -*- coding: utf-8 -*-
"""Small statistics toolkit for the retrospective studies (numpy/scipy only; statsmodels is not installed).

- glm_logit: weighted IRLS for a logit mean; y may be 0/1 or a fraction (quasi-binomial / fractional logit)
- ps_weights: stabilized ATE weights from a logistic propensity model, truncated at percentiles
- smd, ess: balance diagnostics
- rcs: restricted cubic spline basis (Harrell)
- betabinom_fit: weighted beta-binomial regression (logit mean, common overdispersion)
- wls: weighted least squares
- bh: Benjamini-Hochberg q values
- evalue_rr: E-value for a risk ratio and its CI limit nearer the null
Checked against R (glm quasibinomial / binomial with weights, lme4) in statlib_check.py.
"""
import numpy as np
from scipy import optimize, special, stats


def expit(z):
	return special.expit(z)


def add_const(X):
	X = np.asarray(X, float)
	return np.column_stack([np.ones(len(X)), X]) if X.ndim == 2 else np.column_stack([np.ones(len(X)), X[:, None]])


def glm_logit(X, y, w=None, maxit=100, tol=1e-10, dtol=1e-10):
	"""Weighted IRLS for E[y]=expit(Xb). X must already contain the intercept column. Returns (beta, converged).
	The deviance is computed from the linear predictor (log-sum-exp, no probability clipping). A step that raises the deviance is
	halved (up to 30 times; failure -> not converged). Converged when the coefficients stop changing, or (as in R glm) when the
	relative change in deviance is below `dtol`; with a separated sparse covariate its coefficient grows while the fit is settled."""
	X = np.asarray(X, float); y = np.asarray(y, float)
	w = np.ones(len(y)) if w is None else np.asarray(w, float)
	sat = np.sum(w * (special.xlogy(y, y) + special.xlogy(1 - y, 1 - y)))

	def dev(b):
		eta = X @ b
		return 2 * (sat + np.sum(w * (y * np.logaddexp(0, -eta) + (1 - y) * np.logaddexp(0, eta))))

	beta = np.zeros(X.shape[1])
	ybar = np.clip(np.average(y, weights=w), 1e-6, 1 - 1e-6); beta[0] = np.log(ybar / (1 - ybar))
	d_old = dev(beta)
	for _ in range(maxit):
		eta = X @ beta; mu = np.clip(expit(eta), 1e-12, 1 - 1e-12)  # clipping only for the IRLS weights
		v = mu * (1 - mu); z = eta + (y - mu) / v; W = w * v
		XtW = X.T * W
		try:
			new = np.linalg.solve(XtW @ X, XtW @ z)
		except np.linalg.LinAlgError:
			new = np.linalg.lstsq(XtW @ X, XtW @ z, rcond=None)[0]
		d_new = dev(new) if np.all(np.isfinite(new)) else np.inf
		k = 0
		while not (np.isfinite(d_new) and d_new <= d_old + 1e-10 * (abs(d_old) + 0.1)) and k < 30:  # step-halving
			new = beta + (new - beta) / 2; d_new = dev(new); k += 1
		if not (np.isfinite(d_new) and d_new <= d_old + 1e-10 * (abs(d_old) + 0.1)):
			return beta, False
		if np.max(np.abs(new - beta)) < tol or abs(d_new - d_old) / (abs(d_new) + 0.1) < dtol:
			return new, True
		beta, d_old = new, d_new
	return beta, False


def ps_weights(Xps, a, trunc=(1, 99)):
	"""Stabilized ATE weights. Xps without intercept. Returns (weights, ps, converged)."""
	a = np.asarray(a, float)
	b, ok = glm_logit(add_const(Xps), a)
	ps = expit(add_const(Xps) @ b)
	p1 = a.mean()
	w = np.where(a == 1, p1 / ps, (1 - p1) / (1 - ps))
	if trunc is not None:
		lo, hi = np.percentile(w, trunc)
		w = np.clip(w, lo, hi)
	return w, ps, ok


def smd(x, a, w=None):
	"""Standardized mean difference (treated - control), pooled unweighted SD as denominator."""
	x = np.asarray(x, float); a = np.asarray(a).astype(bool)
	w = np.ones(len(x)) if w is None else np.asarray(w, float)
	m1 = np.average(x[a], weights=w[a]); m0 = np.average(x[~a], weights=w[~a])
	s = np.sqrt((np.var(x[a], ddof=1) + np.var(x[~a], ddof=1)) / 2)
	return (m1 - m0) / s if s > 0 else 0.0


def ess(w):
	w = np.asarray(w, float)
	return w.sum() ** 2 / (w ** 2).sum()


def rcs(x, knots):
	"""Restricted cubic spline basis without the linear term's intercept: returns [x, s1..s(k-2)] (Harrell)."""
	x = np.asarray(x, float); k = np.asarray(knots, float); K = len(k)
	cols = [x]
	scale = (k[-1] - k[0]) ** 2
	pp = lambda v: np.maximum(v, 0) ** 3
	for j in range(K - 2):
		s = pp(x - k[j]) - pp(x - k[K - 2]) * (k[K - 1] - k[j]) / (k[K - 1] - k[K - 2]) + pp(x - k[K - 1]) * (k[K - 2] - k[j]) / (k[K - 1] - k[K - 2])
		cols.append(s / scale)
	return np.column_stack(cols)


def wls(X, y, w):
	X = np.asarray(X, float); y = np.asarray(y, float); w = np.asarray(w, float)
	XtW = X.T * w
	return np.linalg.solve(XtW @ X, XtW @ y)


def betabinom_negll(par, X, y, n, w):
	beta, lt = par[:-1], par[-1]
	mu = np.clip(expit(X @ beta), 1e-9, 1 - 1e-9); th = np.exp(lt)
	a, b = mu * th, (1 - mu) * th
	ll = special.gammaln(n + 1) - special.gammaln(y + 1) - special.gammaln(n - y + 1) + special.betaln(y + a, n - y + b) - special.betaln(a, b)
	return -np.sum(w * ll)


def betabinom_grad(par, X, y, n, w):
	"""Gradient of betabinom_negll (analytic)."""
	beta, lt = par[:-1], par[-1]
	mu = np.clip(expit(X @ beta), 1e-9, 1 - 1e-9); th = np.exp(lt)
	a, b = mu * th, (1 - mu) * th
	common = special.digamma(th) - special.digamma(n + th)
	da = special.digamma(y + a) - special.digamma(a) + common
	db = special.digamma(n - y + b) - special.digamma(b) + common
	g_eta = w * th * mu * (1 - mu) * (da - db)
	g_lt = np.sum(w * (a * da + b * db))
	return -np.r_[X.T @ g_eta, g_lt]


def betabinom_fit(X, y, n, w=None):
	"""Weighted beta-binomial MLE. X contains the intercept (column 0). Returns (beta, log_theta, converged).
	Var(y) = n mu (1-mu) (n + theta)/(1 + theta); larger theta = less overdispersion.
	Covariates are centred and scaled inside the fit (a linear reparametrisation) and the analytic gradient is used,
	because unscaled covariates (age, days) left the quasi-Newton search short of the optimum."""
	X = np.asarray(X, float); y = np.asarray(y, float); n = np.broadcast_to(np.asarray(n, float), y.shape).astype(float)
	w = np.ones(len(y)) if w is None else np.asarray(w, float)
	m = np.average(X[:, 1:], axis=0, weights=w); s = np.sqrt(np.average((X[:, 1:] - m) ** 2, axis=0, weights=w)); s[s == 0] = 1.0
	Xs = np.column_stack([np.ones(len(X)), (X[:, 1:] - m) / s])
	b0, _ = glm_logit(Xs, y / n, w)
	bounds = [(None, None)] * Xs.shape[1] + [(-10.0, 12.0)]  # theta = e^12 is practically binomial
	best = None
	for lt0 in (np.log(5.0), 0.0, 2.0):
		r = optimize.minimize(betabinom_negll, np.r_[b0, lt0], args=(Xs, y, n, w), jac=betabinom_grad, method="L-BFGS-B", bounds=bounds,
		                      options={"ftol": 1e-15, "gtol": 1e-9, "maxiter": 5000})
		if best is None or r.fun < best.fun - 1e-10:
			best = r
	g = betabinom_grad(best.x, Xs, y, n, w)
	lt = best.x[-1]  # projected gradient: at a bound, a gradient pointing outward satisfies the KKT condition
	if (lt <= -10.0 + 1e-8 and g[-1] > 0) or (lt >= 12.0 - 1e-8 and g[-1] < 0):
		g[-1] = 0.0
	gn = np.max(np.abs(g)) / max(1.0, w.sum())
	conv = bool(np.all(np.isfinite(best.x)) and gn < 1e-5)
	bs = best.x[:-1]
	beta = np.r_[bs[0] - np.sum(bs[1:] * m / s), bs[1:] / s]
	return beta, best.x[-1], conv


def bh(p):
	p = np.asarray(p, float); m = np.isfinite(p).sum(); q = np.full(len(p), np.nan)
	idx = np.where(np.isfinite(p))[0]
	if m == 0:
		return q
	order = idx[np.argsort(p[idx])]
	ranked = p[order] * m / np.arange(1, m + 1)
	ranked = np.minimum.accumulate(ranked[::-1])[::-1]
	q[order] = np.minimum(ranked, 1)
	return q


def evalue_rr(rr, lo=None, hi=None):
	"""E-value for the point estimate and for the CI limit nearer the null (1 if the CI includes 1)."""
	def ev(r):
		r = 1 / r if r < 1 else r
		return r + np.sqrt(r * (r - 1))
	if not np.isfinite(rr):
		return np.nan, np.nan
	e_pt = ev(rr)
	if lo is None or hi is None or not (np.isfinite(lo) and np.isfinite(hi)):
		return e_pt, np.nan
	if lo <= 1 <= hi:
		return e_pt, 1.0
	return e_pt, ev(lo if rr > 1 else hi)


def wald_p(est, se, null=0.0):
	if not (np.isfinite(est) and np.isfinite(se)) or se <= 0:
		return np.nan
	return 2 * stats.norm.sf(abs((est - null) / se))


def independent_columns(X, protect=0, tol=1e-9):
	"""Indices of columns kept when adding columns left to right and dropping any that do not raise the rank
	(constant or collinear covariates in a subset). The first `protect` columns are always kept."""
	X = np.asarray(X, float)
	keep = list(range(protect))
	for j in range(protect, X.shape[1]):
		if np.ptp(X[:, j]) == 0:
			continue
		cand = keep + [j]
		if np.linalg.matrix_rank(np.column_stack([np.ones(len(X)), X[:, cand]]), tol=tol * max(1.0, np.abs(X[:, cand]).max())) == len(cand) + 1:
			keep = cand
	return keep


def firth_logit(X, y, w=None, maxit=5000, gtol=1e-5):
	"""Weighted Firth-penalized logistic regression (bias reduction; finite under separation). X has the intercept.
	Returns (beta, converged). Maximizes the penalized log-likelihood l(b) + 0.5 log|X'WX| directly (BFGS) with its analytic
	gradient, the modified score U* = X'(w(y-mu) + h(1/2-mu)), on internally centred and scaled covariates (a linear
	reparametrisation). Converged = max|U*| < gtol (1e-5) on the scaled covariates (logistf-type gradient criterion)."""
	X = np.asarray(X, float); y = np.asarray(y, float)
	w = np.ones(len(y)) if w is None else np.asarray(w, float)
	m = np.average(X[:, 1:], axis=0, weights=w); s = np.sqrt(np.average((X[:, 1:] - m) ** 2, axis=0, weights=w)); s[s == 0] = 1.0
	Z = np.column_stack([np.ones(len(X)), (X[:, 1:] - m) / s])

	def parts(b):
		mu = np.clip(expit(Z @ b), 1e-12, 1 - 1e-12); W = w * mu * (1 - mu)
		I = (Z.T * W) @ Z
		sign, ld = np.linalg.slogdet(I)
		if sign <= 0:
			return np.inf, np.full(len(b), np.nan)
		h = W * np.einsum("ij,jk,ik->i", Z, np.linalg.inv(I), Z)
		f = -(np.sum(w * (y * np.log(mu) + (1 - y) * np.log(1 - mu))) + 0.5 * ld)
		g = -(Z.T @ (w * (y - mu) + h * (0.5 - mu)))
		return f, g

	ybar = np.clip(np.average(y, weights=w), 1e-6, 1 - 1e-6)
	b0 = np.zeros(Z.shape[1]); b0[0] = np.log(ybar / (1 - ybar))
	try:
		r = optimize.minimize(parts, b0, jac=True, method="BFGS", options={"gtol": gtol / 10, "maxiter": maxit})
	except (np.linalg.LinAlgError, ValueError):
		return np.full(X.shape[1], np.nan), False
	f, g = parts(r.x)
	ok = bool(np.isfinite(f) and np.all(np.isfinite(r.x)) and np.max(np.abs(g)) < gtol)
	bs = r.x
	beta = np.r_[bs[0] - np.sum(bs[1:] * m / s), bs[1:] / s]
	return beta, ok
