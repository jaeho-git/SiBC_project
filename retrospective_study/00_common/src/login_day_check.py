"""Login-day check (2026-11-23): how far cohort login days overlap recorded in-app activity. Prints aggregates only.

Run from retrospective_study/:  python3 00_common/src/login_day_check.py
Extracts come from 00_common/sql/login_day_check.sql (run_extract.py). Results are printed, never written to a file.
Inputs (git-ignored): 00_common/00_Data/extract_20261123/*.csv, 00_common/00_Data/login.csv and users.csv,
01_wearable_metrics/00_Data/extract_20261120/check_step_origin.csv, each study's app-usage workbook.
Activity sources and the dates they start recording:
  action  = sibc.user_event_log codes 40303101/104/105/106/117 (user responses), recorded from 2025-12-08
  inbound = push click / floating dismiss
  mood    = mood record responses (responded_at)
  weekly  = weekly check-up answers
  (first recorded dates are taken from the data and printed in section J)
Sensitivity exposure (final definition, see section I): login days minus "suspect login days" = days on/after
2026-05-01 with exactly one token and no recorded activity from any source (`broad`). Because sources start at
different dates, this is a removal scenario whose reach depends on record availability; section J checks it by
site x coverage period and section K repeats it with `action` only (scenario 2). Section F compares an
action-event exposure only as a reference (it depends on participation in the programme that records those events).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

R = Path.cwd()
sys.path.insert(0, str(R / "00_common/src"))
from common_cohort import load_common_cohort, END  # noqa: E402

O = R / "00_common/00_Data/extract_20261123"
ACTION_START = pd.Timestamp("2025-12-08")
POST = pd.Timestamp("2026-05-01")


def stop(msg):
	raise SystemExit("CHECK FAILED: " + msg)


C = load_common_cohort()
if not C.index.is_unique:
	stop("cohort user_id not unique")

lg = pd.read_csv(O / "login_hours_days.csv", parse_dates=["d"])
if lg.duplicated(["user_id", "d"]).any():
	stop("duplicate user-day in login extract")
lg = lg[lg.user_id.isin(C.index)].merge(C[["site", "d0"]], left_on="user_id", right_index=True)
lg = lg[(lg.d >= lg.d0) & (lg.d <= END)].copy()
old = pd.read_csv(R / "00_common/00_Data/login.csv", parse_dates=["d"])[["user_id", "d"]].drop_duplicates()
old = old[old.user_id.isin(C.index)].merge(C[["d0"]], left_on="user_id", right_index=True)
old = old[(old.d >= old.d0) & (old.d <= END)]
if set(zip(lg.user_id, lg.d)) != set(zip(old.user_id, old.d)):
	stop("login user-days differ from login.csv")
print(f"cohort {len(C)} users, login user-days {len(lg)} (identical to login.csv), END {END.date()}")


if lg.n.isna().any() or (lg.n < 1).any() or (lg.n != lg.n.round()).any():
	stop("token count n must be a positive integer")
START = {}  # first recorded date of each source, taken from the data


def days(name, src, col=None):
	x = pd.read_csv(O / name, parse_dates=["d"])
	if x.duplicated(["user_id", "d"]).any():
		stop(f"duplicate user-day in {name}")
	if col:
		x = x[x[col] > 0]
	if x.empty:
		stop(f"{name}: no records")
	START[src] = x.d.min()
	# no gap month between the first record and the cutoff month
	months = set(x.d.dt.to_period("M"))
	need = set(pd.period_range(START[src], END, freq="M"))
	if not need <= months:
		stop(f"{name}: no records in {sorted(str(m) for m in need - months)}")
	return set(zip(x.user_id, x.d))


SRC = {"action": days("event_days.csv", "action", "n_action"), "inbound": days("inbound_days.csv", "inbound"),
       "mood": days("mood_days.csv", "mood"), "weekly": days("weekly_checkup_days.csv", "weekly")}
so = pd.read_csv(R / "01_wearable_metrics/00_Data/extract_20261120/check_step_origin.csv", parse_dates=["ins_d"])
UP = set(zip(so.user_id, so.ins_d))
key = list(zip(lg.user_id, lg.d))
for k, s in SRC.items():
	lg[k] = [x in s for x in key]
lg["broad"] = lg[list(SRC)].any(axis=1)
lg["upload"] = [x in UP for x in key]
lg["tok"] = np.where(lg.n == 1, "1", "2+")
lg["first_band"] = pd.cut(lg.first_h, [-1, 5, 11, 17, 23], labels=["00-05", "06-11", "12-17", "18-23"])
lg["night_only"] = (lg.first_h >= 1) & (lg.last_h <= 5)  # every login between 01:00 and 05:59
lg["ym"] = lg.d.dt.to_period("M").astype(str)
lg["period"] = np.where(lg.d >= POST, "2026-05~", "~2026-04")
pct = lambda s: round(100 * s.mean(), 1) if len(s) else np.nan

print("\n== 0. overall: % of login days with any recorded activity:", pct(lg.broad), "%")
logset = set(key)
obs = [k for s in SRC.values() for k in s]
obs = {k for k in obs if k[0] in C.index and C.loc[k[0], "d0"] <= k[1] <= END}
print("   % of observed activity user-days that also have a login the same day:",
      round(100 * np.mean([k in logset for k in obs]), 1), "% of", len(obs))

print("\n== A. same source only (action events), from 2025-12-08, by month and site: % of login days with an action event")
A = lg[lg.d >= ACTION_START]
t = A.pivot_table(index="ym", columns="site", values="action", aggfunc="mean").mul(100).round(1)
t["all"] = A.groupby("ym").action.mean().mul(100).round(1)
t["login_days"] = A.groupby("ym").size()
t["tokens_per_day"] = A.groupby("ym").n.mean().round(2)
print(t.to_string())

print("\n== B. each source's coverage (share of login days with that source, by month)")
print(lg.groupby("ym")[list(SRC)].mean().mul(100).round(1).to_string())

print("\n== C. tokens per day x period: % with action event, % with step upload")
B = lg[lg.d >= ACTION_START]
g = B.groupby(["period", "tok"]).agg(days=("d", "size"), pct_action=("action", "mean"), pct_upload=("upload", "mean"))
g[["pct_action", "pct_upload"]] = g[["pct_action", "pct_upload"]].mul(100).round(1)
print(g.to_string())
print("\n  % of days with tokens = 1, by period")
print(B.groupby("period").tok.apply(lambda s: round(100 * (s == "1").mean(), 1)).to_string())

print("\n== D. 2026-05 onward: tokens x step upload: % with action event")
P = lg[lg.d >= POST]
g = P.groupby(["tok", "upload"]).agg(days=("d", "size"), pct_action=("action", "mean"), pct_broad=("broad", "mean"))
g[["pct_action", "pct_broad"]] = g[["pct_action", "pct_broad"]].mul(100).round(1)
print(g.to_string())

print("\n== E. first-login hour band x period, days with tokens = 1: % with action event")
g = B[B.tok == "1"].groupby(["period", "first_band"], observed=True).agg(days=("d", "size"), pct_action=("action", "mean"))
g["pct_action"] = g.pct_action.mul(100).round(1)
print(g.to_string())
print("\n  share of login days whose every login is 01:00-05:59:", pct(lg.night_only), "%")

# F. study windows: sensitivity exposure = login days with an action event (same source over the window)
X = {
	"01": ("01_wearable_metrics/01_Results/SiBC_01_앱사용량_20261120.xlsx", "노출창", True),
	"02": ("02_checkup_metrics/01_Results/SiBC_02_앱사용량_20261120.xlsx", "참여도창", False),
	"03": ("03_irs_risk_rank/01_Results/SiBC_03_앱사용량_20261120.xlsx", "노출창", False),
}
print("\n== F. study windows (exposure side only; no outcome or checkup values are linked)")
for k, (p, w, main_only) in X.items():
	U = pd.read_excel(R / p, sheet_name="사용자")
	for c in ["user_id", f"{w}_시작일", f"{w}_종료일", f"{w}_확정", f"{w}_로그인일수"]:
		if c not in U:
			stop(f"{k}: missing column {c}")
	if main_only:
		U = U[U["주분석_대상"] == "예"]
	U = U[U[f"{w}_확정"] == "예"].copy()
	if not U.user_id.is_unique:
		stop(f"{k}: user_id not unique")
	U["s0"], U["s1"] = pd.to_datetime(U[f"{w}_시작일"]), pd.to_datetime(U[f"{w}_종료일"])
	if ((U.s1 - U.s0).dt.days != 27).any():
		stop(f"{k}: window is not 28 days")
	rows = []
	for uid, a, b in zip(U.user_id, U.s0, U.s1):
		x = lg[(lg.user_id == uid) & (lg.d >= a) & (lg.d <= b)]
		rows.append((uid, a, len(x), int(x.action.sum())))
	D = pd.DataFrame(rows, columns=["uid", "s0", "login", "login_act"])
	if (D.login.values != U[f"{w}_로그인일수"].values).any():
		stop(f"{k}: login days differ from the app-usage workbook")
	n_all = len(D)
	D = D[D.s0 >= ACTION_START]  # window must lie inside the action-event recording period
	if D.empty or D.login.sum() == 0:
		stop(f"{k}: empty comparison set")
	m_a, m_b = D.login.median(), D.login_act.median()
	hi_a, hi_b = D.login >= m_a, D.login_act >= m_b
	tab = pd.crosstab(hi_a.map({True: "login high", False: "login low"}), hi_b.map({True: "action high", False: "action low"}))
	print(f"\nstudy {k}: confirmed users {n_all}; window inside action-event period {len(D)} "
	      f"(excluded {n_all - len(D)} whose window starts before {ACTION_START.date()})")
	print(f"  login days: median {m_a} (IQR {D.login.quantile(.25)}~{D.login.quantile(.75)}); "
	      f"ties at median {int((D.login == m_a).sum())}; high {int(hi_a.sum())} / low {int((~hi_a).sum())}")
	print(f"  login days with action event: median {m_b} (IQR {D.login_act.quantile(.25)}~{D.login_act.quantile(.75)}); "
	      f"ties at median {int((D.login_act == m_b).sum())}; high {int(hi_b.sum())} / low {int((~hi_b).sum())}; zero days {int((D.login_act == 0).sum())}")
	print(f"  per-user drop in days: median {(D.login - D.login_act).median()} (IQR {(D.login - D.login_act).quantile(.25)}~{(D.login - D.login_act).quantile(.75)}); "
	      f"share of login days with action event {round(100 * D.login_act.sum() / D.login.sum(), 1)}%")
	print("  2x2 (rows: login-day groups, columns: action-day groups)")
	print("  " + tab.to_string().replace("\n", "\n  "))
	print(f"  same group {round(100 * (hi_a == hi_b).mean(), 1)}%")

# G-I (added after the Codex review): single-token days by site, and "suspect login days"
print("\n== G. single-token days by site and period (from 2025-12-08)")
t = B.groupby(["site", "period", "tok"]).agg(days=("d", "size"), pct_action=("action", "mean"), pct_broad=("broad", "mean"), pct_upload=("upload", "mean"))
t[["pct_action", "pct_broad", "pct_upload"]] = t[["pct_action", "pct_broad", "pct_upload"]].mul(100).round(1)
print(t.to_string())
print("\n== H. Site A, 2026-05 onward, single-token days: step upload x activity")
H = lg[(lg.site == "A") & (lg.d >= POST) & (lg.tok == "1")]
h = H.groupby("upload").agg(days=("d", "size"), pct_action=("action", "mean"), pct_broad=("broad", "mean"))
h[["pct_action", "pct_broad"]] = h[["pct_action", "pct_broad"]].mul(100).round(1)
print(h.to_string())
# suspect login day: on/after 2026-05-01, exactly one token, no recorded activity from any source
lg["susp"] = (lg.d >= POST) & (lg.tok == "1") & ~lg.broad
print("\n== I. suspect login days, % of login days by site:", lg.groupby("site").susp.mean().mul(100).round(1).to_dict())
for k, (p, w, main_only) in X.items():
	U = pd.read_excel(R / p, sheet_name="사용자")
	if main_only:
		U = U[U["주분석_대상"] == "예"]
	U = U[U[f"{w}_확정"] == "예"]
	rows = []
	for uid, a, b, site in zip(U.user_id, pd.to_datetime(U[f"{w}_시작일"]), pd.to_datetime(U[f"{w}_종료일"]), U["사이트"]):
		x = lg[(lg.user_id == uid) & (lg.d >= a) & (lg.d <= b)]
		rows.append((site, len(x), int(x.susp.sum())))
	D = pd.DataFrame(rows, columns=["site", "login", "susp"])
	D["login_ns"] = D.login - D.susp
	if D.login.sum() == 0:
		stop(f"{k}: empty login total")
	hi_a, hi_c = D.login >= D.login.median(), D.login_ns >= D.login_ns.median()
	by_site = {s: f"{len(z)} users, {round(100 * z.susp.sum() / max(z.login.sum(), 1), 1)}%" for s, z in D.groupby("site")}
	print(f"\nstudy {k}: users {len(D)}; suspect days {D.susp.sum()} of {D.login.sum()} ({round(100 * D.susp.sum() / D.login.sum(), 1)}%); "
	      f"users with any {int((D.susp > 0).sum())}; by site {by_site}")
	print(f"  median login days {D.login.median()} -> {D.login_ns.median()} without suspect days; "
	      f"same median group {round(100 * (hi_a == hi_c).mean(), 1)}% (switch {int((hi_a != hi_c).sum())})")

# J (added after Codex review 2): suspect-day rate by site x coverage period (periods with the same set of sources)
print("\n   first recorded date of each source:", {k: str(v.date()) for k, v in START.items()})
cuts = sorted({POST} | {v for v in START.values() if v > POST}) + [END + pd.Timedelta(days=1)]
names = {v: k for k, v in START.items()}
COV = []
for a_, b_ in zip(cuts[:-1], cuts[1:]):
	srcs = [k for k, v in START.items() if v <= a_]
	COV.append((f"{a_.date()}~{(b_ - pd.Timedelta(days=1)).date()} [{'+'.join(srcs)}]", str(a_.date()), str((b_ - pd.Timedelta(days=1)).date())))
lg["susp_act"] = (lg.d >= POST) & (lg.tok == "1") & ~lg.action  # scenario 2: action events only (one source throughout)
print("\n== J. suspect-day rate (% of login days) by site x coverage period; scenario 1 = any source, scenario 2 = action only")
rows = []
for lab, a, b in COV:
	for s, z in lg[(lg.d >= pd.Timestamp(a)) & (lg.d <= pd.Timestamp(b))].groupby("site"):
		rows.append((lab, s, len(z), round(100 * (z.tok == "1").mean(), 1), round(100 * z.susp.mean(), 1), round(100 * z.susp_act.mean(), 1)))
print(pd.DataFrame(rows, columns=["period", "site", "login_days", "pct_one_token", "pct_susp_any", "pct_susp_action"]).to_string(index=False))

print("\n== K. study windows under both scenarios (exposure side only)")
for k, (p, w, main_only) in X.items():
	U = pd.read_excel(R / p, sheet_name="사용자")
	if main_only:
		U = U[U["주분석_대상"] == "예"]
	U = U[U[f"{w}_확정"] == "예"]
	rows = []
	for uid, a, b in zip(U.user_id, pd.to_datetime(U[f"{w}_시작일"]), pd.to_datetime(U[f"{w}_종료일"])):
		x = lg[(lg.user_id == uid) & (lg.d >= a) & (lg.d <= b)]
		rows.append((len(x), int(x.susp.sum()), int(x.susp_act.sum()), int((x.d >= POST).sum())))
	D = pd.DataFrame(rows, columns=["login", "s1", "s2", "post"])
	hi = D.login >= D.login.median()
	out = [f"study {k}: users {len(D)}; share of window login days on/after 2026-05-01 {round(100 * D.post.sum() / D.login.sum(), 1)}%"]
	for lab, col in [("scenario 1 (any source)", "s1"), ("scenario 2 (action only)", "s2")]:
		alt = D.login - D[col]
		hi2 = alt >= alt.median()
		rho = "not computable" if D.login.nunique() < 2 or alt.nunique() < 2 else round(D.login.corr(alt, method="spearman"), 3)
		out.append(f"  {lab}: suspect {round(100 * D[col].sum() / D.login.sum(), 1)}%; median {D.login.median()} -> {alt.median()}; "
		           f"group switch {int((hi != hi2).sum())} ({round(100 * (hi == hi2).mean(), 1)}% same); Spearman {rho}")
	print("\n".join(out))
