# -*- coding: utf-8 -*-
"""Study 02 analysis (baseline health checkup items vs login days in the first 28 days), following
00_common/docs/local/분석사양_결과분석.md.

Run from retrospective_study/:  python3 02_checkup_metrics/src/ana2.py [--boot 1000] [--workers 10]
Writes est_point.pkl / est_boot.pkl to 02_checkup_metrics/01_Results/analysis/ (git-ignored). Prints aggregates only.
"""
import argparse
import multiprocessing as mp
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path.cwd()
OUT = ROOT / "02_checkup_metrics/01_Results/analysis"
sys.path.insert(0, str(ROOT / "00_common/src")); sys.path.insert(0, str(ROOT / "02_checkup_metrics/src"))
import statlib as S  # noqa: E402
from common_cohort import END, load_common_cohort  # noqa: E402
_argv = sys.argv; sys.argv = [sys.argv[0]]
import build_analysis_data as BA  # noqa: E402
_a = BA.args(); sys.argv = _argv

C = load_common_cohort()
_L, BSEL, USERS, _F = BA.select_exams(_a, C, END)
U = C.loc[USERS].copy()
N_BASELINE = len(U)
U = U[U.age.notna() & U.sex.notna()].copy()  # complete-case for demographics (spec deviation: not specified beforehand)
N_DEMO_MISSING = N_BASELINE - len(U)
USERS = list(U.index)
U["female"] = (U.sex == "F").astype(float)
U["site_b"] = (U.site == "B").astype(float)  # enrolment site indicator (adjustment only)
U["age"] = U.age.astype(float)
q = U.d0.dt.to_period("Q").astype(str)
# quarters with fewer than 10 users are merged into the next later quarter (a single-user cell separates in resamples)
while True:
	vc = q.value_counts().sort_index()
	small = [k for k in vc.index if vc[k] < 10]
	if not small or len(vc) == 1:
		break
	k = small[0]; later = [j for j in vc.index if j > k]
	q = q.replace(k, later[0] if later else [j for j in vc.index if j < k][-1])
QUARTERS = sorted(q.unique())
QREF = q.value_counts().idxmax()
for qq in QUARTERS:
	if qq != QREF:
		U["q_" + qq] = (q == qq).astype(float)
QCOLS = [c for c in U.columns if c.startswith("q_")]
if U[["age", "female", "site_b"]].isna().any().any():
	raise SystemExit("missing demographics")

# outcome: login days on registration+1..+28 (KST), and the suspect-login-day versions
EX = ROOT / "00_common/00_Data/extract_20261123"
lg = pd.read_csv(EX / "login_hours_days.csv", parse_dates=["d"])
lg = lg[lg.user_id.isin(USERS)].merge(U[["d0"]], left_on="user_id", right_index=True)
lg = lg[(lg.d > lg.d0) & (lg.d <= lg.d0 + pd.Timedelta(days=28))]
def _days(f, col=None):
	x = pd.read_csv(EX / f, parse_dates=["d"])
	if col:
		x = x[x[col] > 0]
	return set(zip(x.user_id, x.d))
act = _days("event_days.csv", "n_action")
broad = act | _days("inbound_days.csv") | _days("mood_days.csv") | _days("weekly_checkup_days.csv")
key = list(zip(lg.user_id, lg.d))
POST = pd.Timestamp("2026-05-01")
lg["s1"] = (lg.d >= POST) & (lg.n == 1) & ~np.array([k in broad for k in key])
lg["s2"] = (lg.d >= POST) & (lg.n == 1) & ~np.array([k in act for k in key])
U["y"] = lg.groupby("user_id").size().reindex(USERS).fillna(0).values
U["y_s1"] = U.y - lg[lg.s1].groupby("user_id").size().reindex(USERS).fillna(0).values
U["y_s2"] = U.y - lg[lg.s2].groupby("user_id").size().reindex(USERS).fillna(0).values
wb = pd.read_excel(ROOT / "02_checkup_metrics/01_Results/SiBC_02_앱사용량_20261120.xlsx", sheet_name="사용자").set_index("user_id")
if not np.array_equal(U.y.values, wb.loc[USERS, "참여도창_로그인일수"].values):
	raise SystemExit("login days differ from the app-usage workbook")
MED = float(np.median(U.y))

# ---------------------------------------------------------------- item coding
NUM_CUT = {  # main, alternative (disease-suspect) thresholds
	"bmi": (lambda v, s: v >= 25, lambda v, s: v >= 30),
	"waist": (lambda v, s: v >= np.where(s == "M", 90, 85), None),
	"sbp": (lambda v, s: v >= 130, lambda v, s: v >= 140),
	"dbp": (lambda v, s: v >= 85, lambda v, s: v >= 90),
	"fbg": (lambda v, s: v >= 100, lambda v, s: v >= 126),
	"tc": (lambda v, s: v >= 200, lambda v, s: v >= 240),
	"hdl": (lambda v, s: v < np.where(s == "M", 40, 50), None),
	"ldl": (lambda v, s: v >= 130, lambda v, s: v >= 160),
	"tg": (lambda v, s: v >= 150, lambda v, s: v >= 200),
	"hb": (lambda v, s: v < np.where(s == "M", 13, 12), None),
	"ast": (lambda v, s: v > 40, None),
	"alt": (lambda v, s: v > 35, None),
	"ggt": (lambda v, s: v > np.where(s == "M", 63, 35), None),
	"cr": (lambda v, s: v > 1.5, None),
	"gfr": (lambda v, s: v < 60, None),
}
CONT = ["height", "weight"]
CAT = ["uprot", "sight", "hearing", "chest", "judge"]
ITEMS = CONT + ["bmi", "waist", "sbp", "dbp", "fbg", "tc", "hdl", "ldl", "tg", "hb", "ast", "alt", "ggt", "cr", "gfr"] + CAT
PANEL = ["bmi", "waist", "bp", "fbg", "hb", "ast", "alt", "ggt", "cr", "gfr", "uprot"]


def code_cat(item, v, alt=False):
	v = "" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v).strip()
	if item == "uprot":
		if v in ("양성", "단백뇨의심"):
			return 1.0
		if v in ("약양성", "경계"):
			return 1.0 if alt else 0.0
		return 0.0 if v in ("음성", "정상", "Negative") else np.nan
	if item == "sight":
		m = re.match(r"^\s*([0-9.]+)\s*/\s*([0-9.]+)\s*$", v)
		if not m:
			return np.nan
		try:
			best = max(float(m.group(1)), float(m.group(2)))
		except ValueError:
			return np.nan
		return float(best < 0.5) if 0 < best <= 2.0 else np.nan
	if item == "hearing":
		t = [x.strip() for x in v.split("/")]
		if any(x in ("비정상", "질환의심") for x in t):
			return 1.0
		return 0.0 if len(t) == 2 and all(x in ("정상", "정삼") for x in t) else np.nan
	if item == "chest":
		if v == "정상":
			return 0.0
		if v in ("비결핵성질환", "비활동성", "순환기계질환", "비활동성폐결핵", "비활동성 폐결핵") or "질환의심" in v:
			return 1.0
		return np.nan
	if item == "judge":
		return 0.0 if v in ("정A", "정B") else (1.0 if v in ("유질", "의심") else np.nan)
	raise KeyError(item)


def item_frame(item, alt=False):
	b = BSEL[BSEL.item == item].set_index("user_id")
	f = pd.DataFrame(index=USERS)
	f["k"] = -b.k.reindex(USERS)  # days from checkup to registration (>= 0)
	f["src104"] = (b.src.reindex(USERS) == "20101104").astype(float)
	sex = U.sex.values
	if item in CONT:
		v = b.num.reindex(USERS).astype(float)
		f["x"] = (v - v.mean()) / v.std(ddof=1)
	elif item in CAT:
		f["x"] = [code_cat(item, c, alt) if u in b.index else np.nan for u, c in zip(USERS, b.cat.reindex(USERS))]
	else:
		v = b.num.reindex(USERS).astype(float).values
		fn = NUM_CUT[item][1] if (alt and NUM_CUT[item][1] is not None) else NUM_CUT[item][0]
		x = np.where(np.isfinite(v), fn(v, sex).astype(float), np.nan)
		f["x"] = x
	f["d_check"] = b.d.reindex(USERS)
	# entry into the service: day of the insert timestamp of the selected result relative to the registration day (0 = same day)
	ins = pd.to_datetime(b.ins_ts, errors="coerce").dt.normalize().reindex(USERS)
	f["entry_lag"] = (ins - pd.to_datetime(U.d0).dt.normalize()).dt.days.values
	f["entry_reg"] = np.where(np.isfinite(f.entry_lag.values.astype(float)), (f.entry_lag.values <= 0).astype(float), np.nan)
	return f


ITEMF = {it: item_frame(it) for it in ITEMS}
ITEMF_ALT = {it: item_frame(it, alt=True) for it in ["bmi", "sbp", "dbp", "fbg", "tc", "ldl", "tg", "uprot"]}

# summary panel: count of out-of-range components (bp = sbp or dbp)
def panel_counts():
	comp = {}
	for c in PANEL:
		if c == "bp":
			s, d = ITEMF["sbp"].x, ITEMF["dbp"].x
			comp[c] = np.where(s.notna() & d.notna(), np.maximum(s.fillna(0), d.fillna(0)), np.nan)
		else:
			comp[c] = ITEMF[c].x.values
	M = pd.DataFrame(comp, index=USERS)
	return M.notna().sum(axis=1).values, M.sum(axis=1, min_count=1).values
N_MEAS, N_OUT = panel_counts()

BASECOV = ["age", "female", "site_b"] + QCOLS


def fit_item(item, ycol="y", sub=None, cnt=None, alt=False, model="bb"):
	f = (ITEMF_ALT if alt else ITEMF)[item]
	X = np.column_stack([f.x.values, U[BASECOV].values, f.k.values, f.src104.values])
	y = U[ycol].values.astype(float)
	ok = np.isfinite(X).all(axis=1)
	if sub is not None:
		ok &= sub
	cnt = np.ones(len(U)) if cnt is None else cnt
	ok &= cnt > 0
	X, y, w = X[ok], y[ok], cnt[ok].astype(float)
	if len(y) < 2:  # empty subset (e.g. an item never recorded by one checkup source); the minimum-n rule below uses resampling frequencies
		return dict(n=int(w.sum()), n1=0, n0=0, tested=False)
	X = X[:, S.independent_columns(X, protect=1)]  # drop constant or collinear covariates (e.g. site in a site subset, or site and quarter in a resample)
	binary = item not in CONT
	r = dict(n=int(w.sum()))
	if binary:
		r.update(n1=int(w[X[:, 0] == 1].sum()), n0=int(w[X[:, 0] == 0].sum()))
		if r["n"] < 30 or r["n1"] < 10 or r["n0"] < 10:
			r["tested"] = False; return r
	elif r["n"] < 30:
		r["tested"] = False; return r
	Xc = S.add_const(X)
	if model == "bb":
		b, lt, conv = S.betabinom_fit(Xc, y, 28.0, w)
		r["at_bound"] = bool(lt <= -10 + 1e-8 or lt >= 12 - 1e-8)
		if not conv:
			b, conv = S.glm_logit(Xc, y / 28, w); r["fallback"] = True
	else:
		b, conv = S.glm_logit(Xc, y / 28, w)
	if binary:
		X1 = Xc.copy(); X1[:, 1] = 1; X0 = Xc.copy(); X0[:, 1] = 0
	else:
		X1 = Xc.copy(); X1[:, 1] = X1[:, 1] + 1; X0 = Xc
	m1 = 28 * np.average(S.expit(X1 @ b), weights=w); m0 = 28 * np.average(S.expit(X0 @ b), weights=w)
	r.update(diff=m1 - m0, m1=m1, m0=m0, tested=True, conv=bool(conv))
	return r


# checkup timing and source across the summary-panel components (for the adjusted summary sensitivity)
_PK = np.column_stack([ITEMF["sbp" if c == "bp" else c].k.values for c in PANEL])
_PS = np.column_stack([ITEMF["sbp" if c == "bp" else c].src104.values * np.isfinite(ITEMF["sbp" if c == "bp" else c].k.values) for c in PANEL])
PANEL_K = np.nanmean(np.where(np.isfinite(_PK), _PK, np.nan), axis=1)  # mean days from checkup to registration over measured components
PANEL_SRC = (np.nansum(_PS, axis=1) > 0).astype(float)  # any component from source 20101104


def fit_summary(cnt=None, ycol="y", prop=False, adj_timing=False):
	cnt = np.ones(len(U)) if cnt is None else cnt
	if prop:
		ok = (N_MEAS >= 10) & (cnt > 0); xv = (N_OUT / N_MEAS)[ok] * 11  # proportion scaled to "components out of 11"
	else:
		ok = (N_MEAS == 11) & (cnt > 0); xv = N_OUT[ok]
	extra = [PANEL_K[ok], PANEL_SRC[ok]] if adj_timing else []
	Z = np.column_stack([xv, U.loc[ok, BASECOV].values.astype(float)] + extra)
	X = S.add_const(Z[:, S.independent_columns(Z, protect=1)])
	y = U[ycol].values[ok].astype(float); w = cnt[ok].astype(float)
	b, lt, conv = S.betabinom_fit(X, y, 28.0, w)
	p = S.expit(X @ b)
	ame = np.average(28 * b[1] * p * (1 - p), weights=w)
	grid = np.arange(0, 8)
	curve = [28 * np.average(S.expit(np.column_stack([np.ones(ok.sum()), np.full(ok.sum(), g), X[:, 2:]]) @ b), weights=w) for g in grid]
	return dict(ame=ame, n=int(w.sum()), curve=curve, conv=bool(conv))


def fit_high(item, cnt=None):
	f = ITEMF[item]
	X = np.column_stack([f.x.values, U[BASECOV].values, f.k.values, f.src104.values])
	a = (U.y.values >= MED).astype(float)
	cnt = np.ones(len(U)) if cnt is None else cnt
	ok = np.isfinite(X).all(axis=1) & (cnt > 0)
	X, a, w = X[ok], a[ok], cnt[ok].astype(float)
	if item not in CONT and (w[X[:, 0] == 1].sum() < 10 or w[X[:, 0] == 0].sum() < 10):
		return dict(tested=False, n=int(w.sum()), n1=int(w[X[:, 0] == 1].sum()), n0=int(w[X[:, 0] == 0].sum()))
	X = X[:, S.independent_columns(X, protect=1)]
	Xc = S.add_const(X); b, conv = S.glm_logit(Xc, a, w)
	if item in CONT:
		X1 = Xc.copy(); X1[:, 1] += 1; X0 = Xc
	else:
		X1 = Xc.copy(); X1[:, 1] = 1; X0 = Xc.copy(); X0[:, 1] = 0
	p1, p0 = np.average(S.expit(X1 @ b), weights=w), np.average(S.expit(X0 @ b), weights=w)
	return dict(rd=p1 - p0, rr=p1 / p0, tested=True, conv=bool(conv and np.all(np.isfinite(b))), n=int(w.sum()))


def estimates(cnt=None):
	e = {"main": {it: fit_item(it, cnt=cnt) for it in ITEMS}}
	e["quasi"] = {it: fit_item(it, cnt=cnt, model="quasi") for it in ITEMS}
	e["alt"] = {it: fit_item(it, cnt=cnt, alt=True) for it in ITEMF_ALT}
	yr = np.ones(len(U), bool)
	e["year1"] = {it: fit_item(it, cnt=cnt, sub=(ITEMF[it].k.values <= 365)) for it in ITEMS}
	e["src101"] = {it: fit_item(it, cnt=cnt, sub=(ITEMF[it].src104.values == 0)) for it in ITEMS}
	e["susp1"] = {it: fit_item(it, ycol="y_s1", cnt=cnt) for it in ITEMS}
	e["susp2"] = {it: fit_item(it, ycol="y_s2", cnt=cnt) for it in ITEMS}
	e["high"] = {it: fit_high(it, cnt=cnt) for it in ITEMS}
	e["summary"] = fit_summary(cnt)
	e["summary_prop10"] = fit_summary(cnt, prop=True)
	e["summary_s1"] = fit_summary(cnt, ycol="y_s1")
	e["summary_adj"] = fit_summary(cnt, adj_timing=True)
	e["src104"] = {it: fit_item(it, cnt=cnt, sub=(ITEMF[it].src104.values == 1)) for it in ITEMS}
	e["entry_reg"] = {it: fit_item(it, cnt=cnt, sub=(ITEMF[it].entry_reg.values == 1)) for it in ITEMS}  # post hoc: result already in the service at registration
	return e


def one_boot(seed):
	rng = np.random.default_rng(seed)
	draw = rng.integers(0, len(U), len(U))
	cnt = np.bincount(draw, minlength=len(U)).astype(float)
	try:
		return estimates(cnt)
	except Exception as ex:
		return {"error": repr(ex)}


if __name__ == "__main__":
	ap = argparse.ArgumentParser(); ap.add_argument("--boot", type=int, default=1000); ap.add_argument("--workers", type=int, default=10)
	a = ap.parse_args()
	OUT.mkdir(parents=True, exist_ok=True)
	print("baseline users", N_BASELINE, "excluded for missing age/sex", N_DEMO_MISSING, "analysed", len(U), "median login days", MED, "panel complete", int((N_MEAS == 11).sum()), ">=10", int((N_MEAS >= 10).sum()))
	E0 = estimates()
	pd.to_pickle(E0, OUT / "est_point.pkl")
	print("point estimates done; tested items", sum(r.get("tested", False) for r in E0["main"].values()))
	if a.boot > 0:
		with mp.get_context("fork").Pool(a.workers) as pool:
			BS = pool.map(one_boot, [42000 + i for i in range(a.boot)], chunksize=5)
		pd.to_pickle(BS, OUT / "est_boot.pkl")
		print("bootstrap replicates", len(BS), "errors", sum("error" in b for b in BS))
