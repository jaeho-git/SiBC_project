# -*- coding: utf-8 -*-
"""Study 01 analysis (engagement in the 28-day exposure window vs wearable / device indicators in the next 28 days),
following 00_common/docs/local/분석사양_결과분석.md.

Run from retrospective_study/:  python3 01_wearable_metrics/src/ana1.py [--boot 1000] [--workers 10]
Daily indicators: random-intercept REML (closed form for user-level covariates: within-user SS + GLS on user means), then
weighted least squares on user means with weights IPW / (tau2 + sigma2 / n_i). Measured indicators: weighted linear
regression of the first outcome-window measurement. Writes est_point.pkl / est_boot.pkl to
01_wearable_metrics/01_Results/analysis/ (git-ignored). Prints aggregates only. Heart rate is not analysed (values not
extracted).
"""
import argparse
import copy
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import optimize

ROOT = Path.cwd()
OUT = ROOT / "01_wearable_metrics/01_Results/analysis"
sys.path.insert(0, str(ROOT / "00_common/src")); sys.path.insert(0, str(ROOT / "01_wearable_metrics/src"))
import statlib as S  # noqa: E402
from common_cohort import load_common_cohort  # noqa: E402
_argv = sys.argv; sys.argv = [sys.argv[0]]
import build_analysis_data as BA  # noqa: E402
_A = BA.args(); sys.argv = _argv
END = _A.cutoff
C = load_common_cohort(_A.common_data_dir, END)
POST = pd.Timestamp("2026-05-01")
DAILY = {"steps": ("걸음", "steps"), "active_min": ("활동_분", "act"), "sleep_min": ("수면_분", "sleep"), "spo2": ("산소포화도", "spo2")}
POINT = {"weight": ("체중", "체중"), "fat_pct": ("체성분", "체지방률"), "muscle": ("체성분", "골격근량"),
         "sbp": ("혈압", "수축기혈압"), "dbp": ("혈압", "이완기혈압"), "grip": ("악력", "악력")}
ORDER = ["steps", "active_min", "weight", "fat_pct", "muscle", "sbp", "dbp", "sleep_min", "spo2", "grip"]  # protocol order without heart rate


def source_gap_table(src, ref="steps.csv", frac=0.5, window=28, min_obs=21):
	"""Daily table on the full calendar: users with a `src` record (numerator), users with a step record (denominator), their ratio,
	the threshold = `frac` x median ratio over the previous `window` calendar days (at least `min_obs` observable days; a day without
	any step record is unobservable) and the day flag."""
	b = ROOT / "01_wearable_metrics/00_Data/extract_20261120"
	st = pd.read_csv(b / ref, parse_dates=["d"]).groupby("d").user_id.nunique()
	cal = pd.date_range(st.index.min(), st.index.max(), freq="D")
	st = st.reindex(cal)
	x = pd.read_csv(b / src, parse_dates=["d"]).groupby("d").user_id.nunique().reindex(cal).fillna(0)
	r = x / st
	thr = frac * r.rolling(window, min_periods=min_obs).median().shift(1)
	return pd.DataFrame({"num": x, "den": st, "ratio": r, "threshold": thr, "flag": (r < thr).fillna(False)})


def source_gaps(src, min_run=3, **kw):
	"""Calendar days in runs of >= `min_run` consecutive flagged calendar days (see source_gap_table)."""
	t = source_gap_table(src, **kw)
	out, run = set(), []
	for d, f in t.flag.items():
		if f:
			run.append(d)
		else:
			if len(run) >= min_run:
				out.update(run)
			run = []
	if len(run) >= min_run:
		out.update(run)
	return out


ACT_GAP = source_gaps("activity.csv")  # session records lost for everyone: such days are missing, not 0 minutes


PLAUSIBLE = {"steps": ("걸음", 60000), "active_min": ("활동_분", 1440), "sleep_min": ("수면_분", 1440), "spo2": ("산소포화도", 100)}  # post hoc upper limits per day


def valid_rows(X, k, act_gap_zero=False, plausible=False):
	if plausible:  # post hoc sensitivity: drop physiologically impossible daily values (above the limit) before the usual rules
		col, lim = PLAUSIBLE[k]
		X = X[~(pd.to_numeric(X[col], errors="coerce") > lim)]
	if k == "steps":
		return X[X["걸음_유효"].astype(str).isin(["예", "True"]) & X["걸음"].notna() & (X["걸음"] > 0)]
	if k == "active_min":
		# per wear day; a wear day without any session counts as 0 minutes; a session day with unknown duration is left out
		w = X[X["착용일"].astype(str).isin(["예", "True"])].copy()
		if not act_gap_zero:
			w = w[~pd.to_datetime(w["날짜"]).isin(ACT_GAP)]
		nosess = w["활동_세션수"].isna()
		w.loc[nosess, "활동_분"] = 0.0
		return w[w["활동_분"].notna()]
	if k == "sleep_min":
		return X[X["수면_분"].notna() & (X["수면_분"] > 0)]
	return X[X["산소포화도"].notna()]


def assemble(min_days=4):
	a = copy.copy(_A); a.min_days = min_days
	T = BA.analysis_users(a, C, END)
	X = BA.daily_sheet(a, T, END)
	P = BA.point_summary(BA.point_sheet(a, T, END), T, END)
	return T, X, P


T, X, P = assemble(4)
MAIN = T.index[T["주분석_대상"] == "예"].tolist()
wb = pd.read_excel(ROOT / "01_wearable_metrics/01_Results/SiBC_01_앱사용량_20261120.xlsx", sheet_name="사용자").set_index("user_id")
steps_ext = pd.read_csv(ROOT / "01_wearable_metrics/00_Data/extract_20261120/steps.csv", parse_dates=["d"])
first_plat = steps_ext.sort_values("d").drop_duplicates("user_id").set_index("user_id").plat

# suspect login days inside the exposure window
EX = ROOT / "00_common/00_Data/extract_20261123"
lg = pd.read_csv(EX / "login_hours_days.csv", parse_dates=["d"])
def _days(f, col=None):
	x = pd.read_csv(EX / f, parse_dates=["d"])
	if col:
		x = x[x[col] > 0]
	return set(zip(x.user_id, x.d))
_act = _days("event_days.csv", "n_action")
_broad = _act | _days("inbound_days.csv") | _days("mood_days.csv") | _days("weekly_checkup_days.csv")
_k = list(zip(lg.user_id, lg.d))
lg["s1"] = (lg.d >= POST) & (lg.n == 1) & ~np.array([x in _broad for x in _k])
lg["s2"] = (lg.d >= POST) & (lg.n == 1) & ~np.array([x in _act for x in _k])


def user_table(T, users):
	U = pd.DataFrame(index=users)
	U["age"] = pd.to_numeric(T.loc[users, "나이"]).astype(float)
	sx = T.loc[users, "성별"].astype(str)
	if not sx.isin(["여", "남", "F", "M"]).all():
		raise SystemExit("unexpected sex codes")
	U["female"] = sx.isin(["여", "F"]).astype(float)
	U["q_other"] = (pd.to_datetime(T.loc[users, "등록일"]).dt.to_period("Q").astype(str) != "2026Q2").astype(float)
	U["t0_days"] = pd.to_numeric(T.loc[users, "시간0_등록후일"]).astype(float)
	t0 = pd.to_datetime(T.loc[users, "시간0"])
	s0, s1 = pd.to_datetime(T.loc[users, "노출_시작일"]), pd.to_datetime(T.loc[users, "노출_종료일"])
	ld = {u: g.d.values for u, g in lg[lg.user_id.isin(users)].groupby("user_id")}
	U["pre_login"] = [float(np.sum(ld.get(u, np.array([], "datetime64[ns]")) < np.datetime64(t))) for u, t in zip(users, t0)]
	U["exp"] = [float(np.sum((ld.get(u, np.array([], "datetime64[ns]")) >= np.datetime64(a_)) & (ld.get(u, np.array([], "datetime64[ns]")) <= np.datetime64(b_)))) for u, a_, b_ in zip(users, s0, s1)]
	inwb = [u for u in users if u in wb.index]
	if not (np.array_equal(U.loc[inwb, "exp"].values, wb.loc[inwb, "노출창_로그인일수"].values.astype(float)) and
	        np.array_equal(U.loc[inwb, "pre_login"].values, wb.loc[inwb, "시간0_이전_로그인일수"].values.astype(float))):
		raise SystemExit("exposure / pre-T0 login days differ from the app-usage workbook")
	pl = first_plat.reindex(users)
	U["plat1105"] = (pl == 20301105).astype(float); U["plat1102"] = (pl == 20301102).astype(float)
	U["base_wear"] = pd.to_numeric(T.loc[users, "기준선_워치착용일"]).astype(float)
	for r in ["s1", "s2"]:
		cnt = []
		for u, a_, b_ in zip(users, s0, s1):
			x = lg[(lg.user_id == u) & (lg.d >= a_) & (lg.d <= b_)]
			cnt.append(int(x[r].sum()))
		U["exp_" + r] = U.exp - np.array(cnt)
	U["site_b"] = (T.loc[users, "사이트"] == "B").astype(float)
	U["out_start"] = (pd.to_datetime(T.loc[users, "추적_시작일"]) - pd.Timestamp("2026-01-01")).dt.days.astype(float)  # calendar time of the outcome window
	if U.drop(columns=["site_b", "out_start"]).isna().any().any():
		raise SystemExit("missing user-level covariates")
	return U


U = user_table(T, MAIN)
for _v in ["female", "q_other", "plat1105", "plat1102"]:
	if U[_v].nunique() < 2:
		raise SystemExit(f"binary covariate {_v} has a single value in the main set")
PSV = ["age", "female", "q_other", "t0_days", "pre_login", "plat1105", "plat1102", "base_wear"]
MED = float(np.median(U.exp))
A = (U.exp >= MED).astype(float).values
USERS = list(U.index); UIDX = {u: i for i, u in enumerate(USERS)}
W12 = (T.loc[USERS, "12주결과_확정"] == "예").values.astype(float)  # later outcome window closed by the cutoff


def daily_data(X, users, k, window="결과", base_window="기준선", base_from=0, zero_steps=False, act_gap_zero=False, plausible=False):
	"""Per indicator: user-level baseline mean (>=4 valid days) and outcome rows (>=4 valid days)."""
	Xu = X[X.user_id.isin(users)]
	if zero_steps and k == "steps":
		Xz = Xu.copy()
		wear = Xz["착용일"].astype(str).isin(["예", "True"])
		Xz.loc[wear & Xz["걸음"].isna(), "걸음"] = 0.0
		v = Xz[wear & Xz["걸음"].notna()]
	else:
		v = valid_rows(Xu, k, act_gap_zero, plausible)
	col = DAILY[k][0]
	bw = v[(v["구간"] == base_window) & (v["시간0후일"] >= base_from)]
	ow = v[v["구간"] == window]
	nb = bw.groupby("user_id").size(); no = ow.groupby("user_id").size()
	keep = [u for u in users if nb.get(u, 0) >= 4 and no.get(u, 0) >= 4]
	base = bw[bw.user_id.isin(keep)].groupby("user_id")[col].mean()
	rows = ow[ow.user_id.isin(keep)][["user_id", col]].rename(columns={col: "y"})
	return keep, base, rows


def pooled_sd(x, a, c):
	"""Pooled SD of x between groups a==1 and a==0 with resampling frequencies c (frequency-weighted variances)."""
	def wvar(v, f):
		m = np.average(v, weights=f); return np.sum(f * (v - m) ** 2) / (f.sum() - 1)
	return np.sqrt((wvar(x[a == 1], c[a == 1]) + wvar(x[a == 0], c[a == 0])) / 2)


def reml(rows, Z, c):
	"""Random-intercept REML with user-level design Z (rows: user_id, y; c: frequency per user)."""
	g = rows.groupby("user_id").y
	ybar = g.mean().reindex(Z.index).values; n = g.size().reindex(Z.index).values.astype(float)
	ssw = (rows.y - rows.user_id.map(g.mean())).pow(2).groupby(rows.user_id).sum().reindex(Z.index).values
	Zm = Z.values
	def nll(th):
		s2, t2 = np.exp(th)
		v = t2 + s2 / n; w = c / v
		ZtW = Zm.T * w
		M = ZtW @ Zm
		beta = np.linalg.solve(M, ZtW @ ybar); r = ybar - Zm @ beta
		ll_w = -0.5 * (np.sum(c * (n - 1)) * np.log(s2) + np.sum(c * ssw) / s2)
		ll_b = -0.5 * (np.sum(c * np.log(v)) + np.linalg.slogdet(M)[1] + np.sum(w * r * r))
		return -(ll_w + ll_b)
	s0 = max(np.sum(c * ssw) / max(np.sum(c * (n - 1)), 1), 1e-8)
	t0 = max(np.cov(ybar, aweights=c) - np.average(s0 / n, weights=c), s0 * 0.05)
	res = optimize.minimize(nll, np.log([s0, t0]), method="Nelder-Mead", options={"xatol": 1e-8, "fatol": 1e-10, "maxiter": 4000})
	s2, t2 = np.exp(res.x)
	return s2, t2, ybar, n, bool(res.success and np.all(np.isfinite(res.x)))


def ps_fit(Uu, a, c, trunc=(1, 99)):
	Xp = Uu[PSV].values; Xp = Xp[:, S.independent_columns(Xp)]
	Xc = S.add_const(Xp)
	b, ok = S.glm_logit(Xc, a, c)
	if not ok or not np.all(np.isfinite(b)) or np.max(np.abs(b)) > 15:  # separation in a subset or resample -> Firth
		b, ok = S.firth_logit(Xc, a, c)
	ok = bool(ok and np.all(np.isfinite(b)))
	ps = np.clip(S.expit(Xc @ b), 1e-3, 1 - 1e-3); p1 = np.average(a, weights=c)  # guard against separation in small subsets
	w = np.where(a == 1, p1 / ps, (1 - p1) / (1 - ps))
	if trunc is not None:
		lo, hi = np.percentile(np.repeat(w, c.astype(int)), trunc); w = np.clip(w, lo, hi)
	return w, ok


def daily_effect(k, cnt, Xd=None, users=None, Uu=None, a=None, equal_users=False, trunc=(1, 99), weighting=True, extra=None, **kw):
	Xd = X if Xd is None else Xd; users = USERS if users is None else users; Uu = U if Uu is None else Uu
	a = A if a is None else a
	keep, base, rows = daily_data(Xd, users, k, **kw)
	ix = np.array([users.index(u) for u in keep]); c = cnt[ix].astype(float)
	sel = c > 0; ix, c = ix[sel], c[sel]; kk = [keep[j] for j in np.where(sel)[0]]
	aa = a[ix]
	r = dict(n=int(c.sum()), n1=int(c[aa == 1].sum()), n0=int(c[aa == 0].sum()))
	if r["n"] < 30 or r["n1"] < 10 or r["n0"] < 10:
		r["tested"] = False; return r
	w, ps_ok = ps_fit(Uu.iloc[ix], aa, c, trunc) if weighting else (np.ones(len(ix)), True)
	cols = [aa, base.reindex(kk).values] + ([Uu.iloc[ix][PSV].values] if weighting else [])
	if extra is not None:
		cols.append(extra(kk))
	Zm_ = np.column_stack(cols)
	keepc = S.independent_columns(Zm_, protect=2)  # drop covariates constant or collinear in this subset
	Zd = pd.DataFrame(Zm_[:, keepc], index=kk)
	Zd.insert(0, "const", 1.0)
	rows = rows[rows.user_id.isin(kk)]
	s2, t2, ybar, n, re_ok = reml(rows, Zd, c)
	wt = c * w * (1.0 if equal_users else 1 / (t2 + s2 / n))
	beta = S.wls(Zd.values, ybar, wt)
	bvals = base.reindex(kk).values
	sd = pooled_sd(bvals, aa, c)
	r["conv"] = bool(ps_ok and (re_ok or equal_users) and np.all(np.isfinite(beta)))
	r.update(diff=beta[1], std=beta[1] / sd, base1=np.average(bvals[aa == 1], weights=c[aa == 1]), base0=np.average(bvals[aa == 0], weights=c[aa == 0]),
	         out1=np.average(ybar[aa == 1], weights=c[aa == 1]), out0=np.average(ybar[aa == 0], weights=c[aa == 0]), tau2=t2, sigma2=s2, tested=True)
	return r


def point_data(Pd, users, k, ext=False):
	ind, col = POINT[k]
	p = Pd[(Pd["지표"] == ind) & Pd.user_id.isin(users)]
	pfx = "연장_" if ext else "결과창_"
	p = p[p["연장_쌍" if ext else "주분석_쌍"] == "예"]
	p = p[p["기준선_" + col].notna() & p[pfx + col].notna()]
	return p.set_index("user_id"), pfx, col


def point_effect(k, cnt, Pd=None, users=None, Uu=None, a=None, trunc=(1, 99), weighting=True, ext=False, sub=None):
	Pd = P if Pd is None else Pd; users = USERS if users is None else users; Uu = U if Uu is None else Uu; a = A if a is None else a
	p, pfx, col = point_data(Pd, users, k, ext)
	kk = [u for u in users if u in p.index and (sub is None or sub(p.loc[u]))]
	ix = np.array([users.index(u) for u in kk], int); c = cnt[ix].astype(float) if len(ix) else np.array([])
	sel = c > 0; ix, c = ix[sel], c[sel]; kk = [kk[j] for j in np.where(sel)[0]]
	aa = a[ix] if len(ix) else np.array([])
	r = dict(n=int(c.sum()), n1=int(c[aa == 1].sum()) if len(c) else 0, n0=int(c[aa == 0].sum()) if len(c) else 0)
	if r["n"] < 30 or r["n1"] < 10 or r["n0"] < 10:
		r["tested"] = False; return r
	w, ps_ok = ps_fit(Uu.iloc[ix], aa, c, trunc) if weighting else (np.ones(len(ix)), True)
	y = p.loc[kk, pfx + col].values.astype(float); b0 = p.loc[kk, "기준선_" + col].values.astype(float)
	site = (p.loc[kk, pfx + "기록출처"].astype(str).str.contains("현장")).astype(float).values
	cols = [aa, b0] + ([Uu.iloc[ix][PSV].values] if weighting else [])
	if weighting and np.ptp(site) > 0:
		cols.append(site)
	if ext:
		cols.append(p.loc[kk, pfx + "노출시작후일"].values.astype(float))
	Zm_ = np.column_stack(cols)
	keepc = S.independent_columns(Zm_, protect=2)
	Z = S.add_const(Zm_[:, keepc])
	beta = S.wls(Z, y, c * w)
	sd = pooled_sd(b0, aa, c)
	r["conv"] = bool(ps_ok and np.all(np.isfinite(beta)))
	r.update(diff=beta[1], std=beta[1] / sd, base1=np.average(b0[aa == 1], weights=c[aa == 1]), base0=np.average(b0[aa == 0], weights=c[aa == 0]),
	         out1=np.average(y[aa == 1], weights=c[aa == 1]), out0=np.average(y[aa == 0], weights=c[aa == 0]), tested=True)
	return r


KNOTS = np.percentile(U.exp, [10, 50, 90])  # from the exposure distribution only
Q25, Q75 = np.percentile(U.exp, [25, 75])
GRID = np.arange(0, 29)


def dose_response(k, cnt):
	"""Login days as a restricted cubic spline (knots at the 10/50/90th percentiles of exposure) in the outcome model,
	adjusted for the baseline value and the propensity-score covariates (no weighting). Returns the predicted difference
	between the 25th and 75th percentiles, the nonlinear spline coefficient and the standardized curve."""
	if k in DAILY:
		keep, base, rows = daily_data(X, USERS, k)
		ix = np.array([USERS.index(u) for u in keep]); c = cnt[ix].astype(float)
		sel = c > 0; ix, c = ix[sel], c[sel]; kk = [keep[j] for j in np.where(sel)[0]]
		b0 = base.reindex(kk).values
	else:
		p, pfx, col = point_data(P, USERS, k)
		kk0 = [u for u in USERS if u in p.index]
		ix = np.array([USERS.index(u) for u in kk0], int); c = cnt[ix].astype(float)
		sel = c > 0; ix, c = ix[sel], c[sel]; kk = [kk0[j] for j in np.where(sel)[0]]
		b0 = p.loc[kk, "기준선_" + col].values.astype(float)
	if c.sum() < 30:
		return dict(tested=False)
	x = U.exp.values[ix]
	cols = [S.rcs(x, KNOTS), b0[:, None], U.iloc[ix][PSV].values]
	if k not in DAILY:
		site = (p.loc[kk, pfx + "기록출처"].astype(str).str.contains("현장")).astype(float).values
		if np.ptp(site) > 0:
			cols.append(site[:, None])
	Zm_ = np.column_stack(cols)
	keepc = S.independent_columns(Zm_, protect=2)
	Z = S.add_const(Zm_[:, keepc])
	if k in DAILY:
		Zd = pd.DataFrame(Z, index=kk)
		rows = rows[rows.user_id.isin(kk)]
		s2, t2, ybar, n, re_ok = reml(rows, Zd, c)
		beta = S.wls(Z, ybar, c / (t2 + s2 / n))
	else:
		re_ok = True
		y = p.loc[kk, pfx + col].values.astype(float)
		beta = S.wls(Z, y, c)
	def mean_at(v):
		Zv = Z.copy(); Zv[:, 1:3] = S.rcs(np.full(len(x), float(v)), KNOTS)
		return np.average(Zv @ beta, weights=c)
	return dict(diff=mean_at(Q75) - mean_at(Q25), nonlin=beta[2], curve=[mean_at(v) for v in GRID], n=int(c.sum()), tested=True,
	            conv=bool(re_ok and np.all(np.isfinite(beta))), exp_n=np.bincount(x.astype(int), weights=c, minlength=29).tolist())


def effect(k, cnt, **kw):
	return daily_effect(k, cnt, **kw) if k in DAILY else point_effect(k, cnt, **{x: v for x, v in kw.items() if x in ("trunc", "weighting", "a", "ext", "sub", "Pd", "users", "Uu")})


# baseline strata (interpretation direction)
def _bmi_base(row):
	return row.get("기준선_체질량지수", np.nan)


BMI_BASE = P[(P["지표"] == "체중")].set_index("user_id")["기준선_체질량지수"]
BP_BASE = P[(P["지표"] == "혈압")].set_index("user_id")[["기준선_수축기혈압", "기준선_이완기혈압"]]


def estimates(cnt):
	e = {"main": {k: effect(k, cnt) for k in ORDER}}
	e["equal_users"] = {k: daily_effect(k, cnt, equal_users=True) for k in DAILY}
	e["no_trunc"] = {k: effect(k, cnt, trunc=None) for k in ORDER}
	e["unadjusted"] = {k: effect(k, cnt, weighting=False) for k in ORDER}
	for r in ["s1", "s2"]:
		alt = U["exp_" + r].values
		aa = (alt >= np.median(alt)).astype(float)
		e["susp" + r[1]] = {k: effect(k, cnt, a=aa) for k in ORDER}
	# later outcome window: only users whose window had closed by the data cutoff (12주결과_확정), as in the primary window
	e["week12"] = {k: daily_effect(k, cnt * W12, window="12주결과") for k in DAILY}
	e["base2_13"] = {k: daily_effect(k, cnt, base_from=2) for k in DAILY}
	e["zero_steps"] = {"steps": daily_effect("steps", cnt, zero_steps=True)}
	e["act_gap_zero"] = {"active_min": daily_effect("active_min", cnt, act_gap_zero=True)}  # collection-gap days counted as 0 minutes
	e["act_calendar"] = {"active_min": daily_effect("active_min", cnt, extra=lambda kk: U.loc[kk, "out_start"].values)}  # calendar-time adjustment
	e["plausible"] = {k: daily_effect(k, cnt, plausible=True) for k in DAILY}  # post hoc: impossible daily values removed
	e["extended"] = {k: point_effect(k, cnt, ext=True) for k in POINT}
	e["no_plat1102"] = {k: effect(k, np.where(U.plat1102.values == 1, 0, cnt)) for k in ORDER}
	e["dose"] = {k: dose_response(k, cnt) for k in ORDER}  # positivity: this platform has no high-engagement user
	t0m = U.t0_days.values <= 56
	e["t0_le56"] = {k: effect(k, np.where(t0m, cnt, 0)) for k in ORDER}
	# baseline strata
	hi_bmi = lambda u: BMI_BASE.get(u, np.nan) >= 25
	e["strata"] = {}
	for k in ["weight", "fat_pct"]:
		for lab, f in [("bmi>=25", lambda r: r.name in BMI_BASE.index and BMI_BASE[r.name] >= 25), ("bmi<25", lambda r: r.name in BMI_BASE.index and BMI_BASE[r.name] < 25)]:
			e["strata"][f"{k}|{lab}"] = point_effect(k, cnt, sub=f)
	for k in ["sbp", "dbp"]:
		for lab, f in [(">=130/85", lambda r: (r["기준선_수축기혈압"] >= 130) or (r["기준선_이완기혈압"] >= 85)), ("<130/85", lambda r: (r["기준선_수축기혈압"] < 130) and (r["기준선_이완기혈압"] < 85))]:
			e["strata"][f"{k}|{lab}"] = point_effect(k, cnt, sub=f)
	for lab, lo, hi in [("sleep<7h", 0, 420), ("sleep>=7h", 420, 1e9)]:
		keep, base, _ = daily_data(X, USERS, "sleep_min")
		mask = np.array([(u in keep) and lo <= base.get(u, np.nan) < hi for u in USERS])
		e["strata"][f"sleep_min|{lab}"] = daily_effect("sleep_min", np.where(mask, cnt, 0))
	return e


DATA7 = DATA1 = None


def wear_sensitivity(cnt_by_user=None):
	"""Wear-day thresholds 7 and 1: rebuild users and data with the same tools (point estimates)."""
	out = {}
	for md in [7, 1]:
		T2, X2, P2 = assemble(md)
		users2 = T2.index[T2["주분석_대상"] == "예"].tolist()
		U2 = user_table(T2, users2)
		a2 = (U2.exp >= np.median(U2.exp)).astype(float).values
		c2 = np.ones(len(users2))
		out[md] = {k: (daily_effect(k, c2, Xd=X2, users=users2, Uu=U2, a=a2) if k in DAILY else point_effect(k, c2, Pd=P2, users=users2, Uu=U2, a=a2)) for k in ORDER}
		out[md]["_n_users"] = len(users2)
	return out


def one_boot(seed):
	rng = np.random.default_rng(seed)
	cnt = np.bincount(rng.integers(0, len(USERS), len(USERS)), minlength=len(USERS)).astype(float)
	try:
		return estimates(cnt)
	except Exception as ex:
		return {"error": repr(ex)}


if __name__ == "__main__":
	ap = argparse.ArgumentParser(); ap.add_argument("--boot", type=int, default=1000); ap.add_argument("--workers", type=int, default=10)
	a = ap.parse_args()
	OUT.mkdir(parents=True, exist_ok=True)
	print("main users", len(USERS), "median exposure", MED, "high", int(A.sum()), "low", int((1 - A).sum()))
	for k in DAILY:
		keep, _, _ = daily_data(X, USERS, k); print("daily", k, "analysable", len(keep))
	for k in POINT:
		print("point", k, "pairs", len(point_data(P, USERS, k)[0]))
	E0 = estimates(np.ones(len(USERS)))
	E0["wear"] = wear_sensitivity()
	pd.to_pickle(E0, OUT / "est_point.pkl")
	print("point estimates done")
	if a.boot > 0:
		with mp.get_context("fork").Pool(a.workers) as pool:
			BS = pool.map(one_boot, [71000 + i for i in range(a.boot)], chunksize=5)
		pd.to_pickle(BS, OUT / "est_boot.pkl")
		print("bootstrap replicates", len(BS), "errors", sum("error" in b for b in BS))
