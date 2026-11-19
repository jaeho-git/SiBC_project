# -*- coding: utf-8 -*-
"""Common cohort shared by studies 01-03.

Rule (same as 03_irs_risk_rank/src/x7b.py and the 2026-11-19 feasibility check):
- linked to an approved deployment site (Ulsan or Jeju), not an operator account, not in a test group;
- has a first app login (first login date in KST = registration date d0);
- d0 + 28 days <= data cutoff, and no withdrawal on or before d0 + 28 days.

Inputs are read-only extracts in 00_common/00_Data (users.csv, login.csv); they are never committed.
"""
from pathlib import Path

import numpy as np
import pandas as pd

COMMON_DATA = Path(__file__).resolve().parents[1] / "00_Data"
END = pd.Timestamp("2026-11-17")  # data cutoff used by all three studies (extracts taken 2026-11-19)
EXTRACT_TAG = "20261119"  # extraction date used in output file names
RETRO_ROOT = Path(__file__).resolve().parents[2]


def run_args(study_data_dir: Path, description: str):
	"""Command-line options shared by the usable-user builders. Defaults reproduce the 2026-11-19 lists.
	For a refreshed extract pass all of: --data-dir, --common-data-dir, --cutoff and --tag (so nothing is overwritten)."""
	import argparse
	ap = argparse.ArgumentParser(description=description)
	ap.add_argument("--data-dir", type=Path, default=study_data_dir, help="folder with this study's extracts")
	ap.add_argument("--common-data-dir", type=Path, default=COMMON_DATA, help="folder with users.csv and login.csv")
	ap.add_argument("--cutoff", type=pd.Timestamp, default=END, help="data cutoff date (YYYY-MM-DD)")
	ap.add_argument("--extract-date", default="2026-11-19", help="extraction date shown in the workbook")
	ap.add_argument("--tag", default=EXTRACT_TAG, help="date tag in the output file name")
	return ap.parse_args()


def load_common_cohort(data_dir: Path = COMMON_DATA, end: pd.Timestamp = END) -> pd.DataFrame:
	"""Return the common cohort indexed by user_id with site, sex, age, d0 (registration date) and wdd (withdrawal date)."""
	U = pd.read_csv(data_dir / "users.csv")
	for c in ["is_operator", "in_test_group"]:
		U[c] = U[c] == "t"
	U["site"] = np.where(U.ulsan_linked.notna(), "울산", np.where(U.jeju_linked.notna(), "제주", ""))
	login = pd.read_csv(data_dir / "login.csv", parse_dates=["d"])[["user_id", "d"]].drop_duplicates()
	d0 = login.groupby("user_id").d.min()
	C = U[(U.site != "") & ~U.is_operator & ~U.in_test_group].copy()
	C["d0"] = C.user_id.map(d0)
	C = C[C.d0.notna()].copy()
	C["wdd"] = pd.to_datetime(C.withdraw_dt, utc=True).dt.tz_convert("Asia/Seoul").dt.tz_localize(None).dt.normalize()
	keep = (C.d0 + pd.Timedelta(days=28) <= end) & ~(C.wdd <= C.d0 + pd.Timedelta(days=28))
	C = C[keep].set_index("user_id")
	return C[["site", "sex", "age", "d0", "wdd"]]


IRS_OVERLAP_COL = "03_IRS_비교대상_포함"


def irs_comparison_users(root: Path = RETRO_ROOT):
	"""User ids of the 03 IRS comparison set, used only to flag overlap between papers.
	Returns None when the 03 result file is not available, so callers can mark the overlap as unknown instead of "no"."""
	p = root / "03_irs_risk_rank" / "00_Data" / "frozen_20261119" / "D2.pkl"
	if not p.exists():
		print(f"WARNING: {p} not found; overlap with study 03 is written as '확인 불가'")
		return None
	return set(pd.read_pickle(p).index)


def overlap_flag(user_ids, members):
	"""'예' / '아니오' per user, or '확인 불가' for everyone when the 03 membership is unavailable."""
	if members is None:
		return ["확인 불가"] * len(user_ids)
	return ["예" if u in members else "아니오" for u in user_ids]
