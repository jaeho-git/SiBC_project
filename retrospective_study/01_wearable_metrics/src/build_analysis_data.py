# -*- coding: utf-8 -*-
"""Study 01: analysis-data workbook (indicator values) for local analysis without a database connection.

Offline: reads the saved extracts (00_common/00_Data, 01_wearable_metrics/00_Data/extract_20261120) and reuses the
timeline and status rules of build_all_indicator_users.py, so users, windows and statuses match the usable-user list.
Writes 01_wearable_metrics/01_Results/SiBC_01_웨어러블_분석자료_<tag>.xlsx (user-level health data, never committed).

Users: the main analysis (cohort members whose follow-up window has closed: 결과 확보 or 결과 결측) plus the
supplementary steps group (any device). Users still waiting for follow-up are added when their windows close.
Sheets
- 사용자: one row per user, statuses and window dates (same as the usable-user list) and the 12-week window.
- 일별: one row per user x day with any daily record from T0 to the end of the 12-week window (or the cutoff).
  Daily extracts are already one row per user x KST day (values summed or averaged across platforms in SQL).
- 창별_요약: per user, record days and means of each daily indicator in the baseline, outcome and 12-week windows,
  using the protocol rules (steps > 0; activity per wear day with 0 for a wear day without a session; sleep > 0;
  calories when total + active > 0). Heart-rate values are not extracted yet (only record days).
- 측정: every intermittent-measure row (weight/height, body composition, blood pressure, grip strength) from
  90 days before the exposure window to the cutoff, with source (site device vs personal device) and site location.
- 측정_요약: per user x measure, the baseline measurement (last in the 90 days before exposure), the first measurement
  inside the 28-day outcome window (primary) and the first measurement up to the cutoff (sensitivity). Rows recorded at
  the excluded location (마곡부스) are not used; several rows on the chosen day are averaged and counted.
No group comparison is made here: app usage is in a separate workbook (00_common/src/build_app_usage.py).
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "00_common" / "src"))
import build_all_indicator_users as B  # noqa: E402
from common_cohort import COMMON_DATA, END, IRS_OVERLAP_COL, irs_comparison_users, load_common_cohort, overlap_flag  # noqa: E402
from data_xlsx import write_data_workbook, yn  # noqa: E402

D = pd.Timedelta
SITE_PLAT = 20301103  # site devices (Ulsan measurement points)
EXCLUDED_LOC = {"마곡부스"}  # not an Ulsan measurement point
W12 = (70, 97)  # 12-week outcome window, days after the exposure start
MAIN = {"대상자, 결과 확보", "대상자, 결과 결측"}


def args():
	ap = argparse.ArgumentParser(description="Build the study 01 analysis-data workbook")
	ap.add_argument("--data-dir", type=Path, default=B.DATA, help="folder with the 01 indicator extracts")
	ap.add_argument("--common-data-dir", type=Path, default=COMMON_DATA, help="folder with users.csv and login.csv")
	ap.add_argument("--cutoff", type=pd.Timestamp, default=END, help="data cutoff date (YYYY-MM-DD)")
	ap.add_argument("--extract-date", default="2026-11-20", help="extraction date shown in the workbook")
	ap.add_argument("--tag", default="20261120", help="date tag in the output file name")
	ap.add_argument("--min-days", type=int, default=4, help="days needed in each window (same as the usable-user list)")
	a = ap.parse_args()
	if not 1 <= a.min_days <= B.BASE_LEN:
		ap.error(f"--min-days must be between 1 and {B.BASE_LEN}")
	return a


def rd(a, name, users, end):
	t = pd.read_csv(a.data_dir / f"{name}.csv", parse_dates=["d"])
	return t[t.user_id.isin(users) & (t.d <= end)].copy()


def users_sheet(C, A, end):
	T = pd.DataFrame(index=C.index)
	T["사이트"] = C.site
	T["성별"] = C.sex.map({"F": "여", "M": "남"})
	T["나이"] = pd.to_numeric(C.age, errors="coerce")
	T["등록일"] = C.d0
	T = T.join(A)
	main = T.대상자_상태.isin(MAIN)
	aux = T.걸음_보조_상태 == "사용 가능"
	T = T[main | aux].copy()
	T.insert(4, "주분석_대상", yn(T.대상자_상태.isin(MAIN)))
	T.insert(5, "매일지표_결과확보", yn(T.대상자_상태 == "대상자, 결과 확보"))
	T.insert(6, "걸음보조_대상", yn(T.걸음_보조_상태 == "사용 가능"))
	T["12주결과_시작일"] = T.노출_시작일 + D(days=W12[0])
	T["12주결과_종료일"] = T.노출_시작일 + D(days=W12[1])
	T["12주결과_확정"] = yn(T["12주결과_종료일"] <= end - D(days=B.LAG))
	T[IRS_OVERLAP_COL] = overlap_flag(T.index, irs_comparison_users())
	return T


def label_days(d, u):
	"""Window label of each day for the users in u (columns 시간0, 기준선_종료일, 노출_시작일)."""
	t0, be, L = u["시간0"], u["기준선_종료일"], u["노출_시작일"]
	lab = np.select(
		[(d >= t0) & (d <= be), (d >= L) & (d <= L + D(days=27)), (d >= L + D(days=28)) & (d <= L + D(days=55)),
		 (d >= L + D(days=W12[0])) & (d <= L + D(days=W12[1]))],
		["기준선", "노출", "결과", "12주결과"], "그밖")
	return lab


def daily_sheet(a, T, end):
	ids = set(T.index)
	st, hr, ac, sl, ox, ca = (rd(a, n, ids, end) for n in ["steps", "heartrate_days", "activity", "sleep", "oxygen_saturation", "calories"])
	org = pd.read_csv(a.data_dir / "check_step_origin.csv", parse_dates=["d"])
	multi = org.groupby(["user_id", "d"]).plat.nunique().rename("n_plat").reset_index()
	parts = [
		st.rename(columns={"steps": "걸음", "plat": "걸음_플랫폼"})[["user_id", "d", "걸음", "걸음_플랫폼"]],
		hr.assign(심박_기록=1).rename(columns={"plat": "심박_플랫폼"})[["user_id", "d", "심박_기록", "심박_플랫폼"]],
		ac.rename(columns={"n_sessions": "활동_세션수", "mins": "활동_분"})[["user_id", "d", "활동_세션수", "활동_분"]],
		sl.rename(columns={"mins": "수면_분"})[["user_id", "d", "수면_분"]],
		ox.rename(columns={"spo2": "산소포화도"})[["user_id", "d", "산소포화도"]],
		ca.rename(columns={"total_kcal": "칼로리_총", "active_kcal": "칼로리_활동"})[["user_id", "d", "칼로리_총", "칼로리_활동"]],
	]
	for p in parts:
		assert not p.duplicated(["user_id", "d"]).any(), "daily extract must be one row per user x day"
	X = parts[0]
	for p in parts[1:]:
		X = X.merge(p, on=["user_id", "d"], how="outer")
	X = X.merge(multi, on=["user_id", "d"], how="left")
	u = T.loc[X.user_id, ["시간0", "기준선_종료일", "노출_시작일"]].reset_index(drop=True)
	X = X.reset_index(drop=True)
	last = (u.노출_시작일 + D(days=W12[1])).clip(upper=end)
	X = X[(X.d >= u.시간0) & (X.d <= last)].copy()
	u = u.loc[X.index]
	X["구간"] = label_days(X.d, u)
	X["시간0후일"] = (X.d - u.시간0).dt.days
	X["노출시작후일"] = (X.d - u.노출_시작일).dt.days
	step_ok = X.걸음.fillna(0) > 0
	hr_ok = X.심박_기록.fillna(0) > 0
	X["걸음_유효"] = yn(step_ok)
	X["걸음_복수플랫폼"] = yn(X.n_plat.fillna(1) > 1)
	X["심박_기록"] = hr_ok.astype(int)
	X["워치착용일"] = yn(step_ok & hr_ok)
	X["착용일"] = yn(step_ok | hr_ok)
	cols = ["user_id", "d", "구간", "시간0후일", "노출시작후일", "착용일", "워치착용일", "걸음", "걸음_유효", "걸음_플랫폼",
			"걸음_복수플랫폼", "심박_기록", "심박_플랫폼", "활동_세션수", "활동_분", "수면_분", "산소포화도", "칼로리_총", "칼로리_활동"]
	X = X[cols].rename(columns={"d": "날짜"}).sort_values(["user_id", "날짜"])
	for c in ["걸음_플랫폼", "심박_플랫폼", "활동_세션수"]:
		X[c] = X[c].astype("Int64")
	return X


def window_summary(X, T):
	"""Per user: record days and means of each daily indicator in the baseline, outcome and 12-week windows."""
	out = pd.DataFrame(index=T.index)
	wear = X.착용일 == "예"
	rules = {  # indicator -> (row mask, value column(s)); activity fills 0 on wear days without a session
		"걸음": (X.걸음_유효 == "예", "걸음"),
		"활동_분": (wear & ~(X.활동_세션수.fillna(0).gt(0) & X.활동_분.isna()), "활동_분"),  # a session with unknown duration is not 0
		"활동_세션수": (wear, "활동_세션수"),
		"수면_분": (X.수면_분.fillna(0) > 0, "수면_분"),
		"산소포화도": (X.산소포화도.notna(), "산소포화도"),
		"칼로리_총": (X.칼로리_총.fillna(0) + X.칼로리_활동.fillna(0) > 0, "칼로리_총"),
	}
	for w, tag in [("기준선", "기준선"), ("결과", "결과"), ("12주결과", "12주")]:
		inw = X.구간 == w
		for k, (m, col) in rules.items():
			sub = X[inw & m].copy()
			v = sub[col].astype(float)
			if k.startswith("활동"):
				v = v.fillna(0)  # wear day without a session = 0 (sessions with unknown duration are excluded above)
			g = v.groupby(sub.user_id)
			out[f"{k}_{tag}_일수"] = g.size().reindex(out.index).fillna(0).astype(int)
			out[f"{k}_{tag}_평균"] = g.mean().reindex(out.index)
		out[f"심박_{tag}_기록일수"] = X[inw & (X.심박_기록 == 1)].groupby("user_id").size().reindex(out.index).fillna(0).astype(int)
	closed = T["12주결과_확정"] == "예"
	for c in [c for c in out.columns if "_12주_" in c]:
		out.loc[~closed, c] = np.nan  # window not closed yet: counts and means are not final
	out = out.reset_index().rename(columns={"index": "user_id"})
	return out


def location_map(a):
	l = pd.read_csv(a.data_dir / "check_site_location_user.csv", parse_dates=["d"])
	l["loc"] = l["loc"].str.strip().str.replace(r"\s+", " ", regex=True)
	return l.groupby(["user_id", "tbl", "dev", "d"])["loc"].apply(lambda s: "|".join(sorted(set(s)))).rename("측정장소").reset_index()


def point_sheet(a, T, end):
	ids = set(T.index)
	loc = location_map(a)
	frames = []
	spec = [
		("체중", "body", "body", {"weight": "체중", "height": "키"}),
		("체성분", "bodyfat", None, {"fat_pct": "체지방률", "fat_mass": "체지방량", "muscle_mass": "골격근량", "n": "기록수"}),
		("혈압", "bp", "bp", {"sbp": "수축기혈압", "dbp": "이완기혈압", "n": "기록수"}),
		("악력", "grip_strength", None, {"grip": "악력", "n": "기록수"}),
	]
	for name, fn, tbl, ren in spec:
		t = rd(a, fn, ids, end).rename(columns=ren)
		if tbl:
			# site locations exist only for site devices (platform 20301103); never attach them to personal-device rows
			t = t.merge(loc[loc.tbl == tbl].drop(columns="tbl").assign(plat=SITE_PLAT), on=["user_id", "plat", "dev", "d"], how="left")
		t["지표"] = name
		frames.append(t)
	M = pd.concat(frames, ignore_index=True)
	L = M.user_id.map(T.노출_시작일)
	M = M[M.d >= L - D(days=B.POINT_BACK)].copy()
	L = L.loc[M.index]
	M["노출시작후일"] = (M.d - L).dt.days
	M["구간"] = np.select([M.노출시작후일 < 0, M.노출시작후일 <= 27, M.노출시작후일 <= 55], ["기준선 범위", "노출", "결과"], "결과창 이후")
	M["기록출처"] = np.where(M.plat == SITE_PLAT, "현장 기기", "개인 기기")
	M["제외장소"] = yn(M.측정장소.fillna("").str.split("|").apply(lambda s: bool(set(s) & EXCLUDED_LOC)))
	M["체질량지수"] = M.체중 / (M.키 / 100) ** 2
	M.loc[~(M.키 > 0), "체질량지수"] = np.nan
	cols = ["user_id", "지표", "d", "구간", "노출시작후일", "plat", "dev", "기록출처", "측정장소", "제외장소", "체중", "키", "체질량지수",
			"체지방률", "체지방량", "골격근량", "수축기혈압", "이완기혈압", "악력", "기록수"]
	M = M[cols].rename(columns={"d": "날짜", "plat": "플랫폼", "dev": "기기"}).sort_values(["user_id", "지표", "날짜", "플랫폼", "기기"])
	M["기록수"] = M.기록수.astype("Int64")
	return M


VALUES = {"체중": ["체중", "체질량지수"], "체성분": ["체지방률", "체지방량", "골격근량"], "혈압": ["수축기혈압", "이완기혈압"], "악력": ["악력"]}


VALID = {"체중": ["체중"], "체성분": ["체지방률", "체지방량", "골격근량"], "혈압": ["수축기혈압"], "악력": ["악력"]}  # list-builder masks


def point_summary(M, T, end):
	"""Per user x measure: baseline, outcome-window and extended follow-up measurement (day, values, rows, source).
	Only valid rows (the list builder's masks) at allowed locations are used; each value is averaged over the rows of the
	chosen day that have it."""
	ok = pd.Series(False, index=M.index)
	for k, cols in VALID.items():
		ok |= (M.지표 == k) & M[cols].notna().any(axis=1)
	P = M[(M.제외장소 == "아니오") & ok]
	rows = []
	for (u, k), g in P.groupby(["user_id", "지표"]):
		r = {"user_id": u, "지표": k}
		pick = {
			"기준선": g[g.구간 == "기준선 범위"].날짜.max(),
			"결과창": g[g.노출시작후일.between(28, 55)].날짜.min(),
			"연장": g[g.노출시작후일 >= 28].날짜.min(),
		}
		for w, day in pick.items():
			r[f"{w}_날짜"] = day
			if pd.isna(day):
				continue
			s = g[g.날짜 == day]
			r[f"{w}_노출시작후일"] = int(s.노출시작후일.iloc[0])
			r[f"{w}_행수"] = len(s)
			r[f"{w}_기록출처"] = "|".join(sorted(set(s.기록출처)))
			for v in VALUES[k]:
				r[f"{w}_{v}"] = s[v].mean()  # mean over the rows that have this value
		rows.append(r)
	S = pd.DataFrame(rows, columns=["user_id", "지표"] + [f"{w}_날짜" for w in ["기준선", "결과창", "연장"]] if not rows else None)
	base = pd.MultiIndex.from_product([T.index, list(VALUES)], names=["user_id", "지표"]).to_frame(index=False)
	S = base.merge(S, on=["user_id", "지표"], how="left")
	for w in ["기준선", "결과창", "연장"]:
		S[f"{w}_날짜"] = pd.to_datetime(S[f"{w}_날짜"])
	S["주분석_쌍"] = yn(S.기준선_날짜.notna() & S.결과창_날짜.notna())
	S["연장_쌍"] = yn(S.기준선_날짜.notna() & S.연장_날짜.notna())
	vcols = []
	for w in ["기준선", "결과창", "연장"]:
		vcols += [f"{w}_날짜", f"{w}_노출시작후일", f"{w}_행수", f"{w}_기록출처"] + [f"{w}_{v}" for v in sorted({x for vs in VALUES.values() for x in vs}, key=lambda x: list(_ORDER).index(x))]
	S = S.reindex(columns=["user_id", "지표", "주분석_쌍", "연장_쌍"] + vcols)
	for c in [c for c in S.columns if c.endswith(("_행수", "_노출시작후일"))]:
		S[c] = S[c].astype("Int64")
	return S.sort_values(["user_id", "지표"])


_ORDER = ["체중", "체질량지수", "체지방률", "체지방량", "골격근량", "수축기혈압", "이완기혈압", "악력"]


def coldoc():
	d = [
		("사용자", "user_id", "서비스 사용자 ID(연구용 키 변환 전)"),
		("사용자", "사이트", "현재 소속 사이트(현재 시점 정보)"), ("사용자", "성별", "여/남"), ("사용자", "나이", "서비스 기록 나이"),
		("사용자", "등록일", "첫 앱 로그인 날짜(KST)"),
		("사용자", "주분석_대상", "예 = 대상자 중 추적 창이 확정된 사용자(결과 확보 또는 결과 결측)"),
		("사용자", "매일지표_결과확보", "예 = 추적 28일 착용일이 기준 이상(매일 지표의 결과 확보)"),
		("사용자", "걸음보조_대상", "예 = 워치 착용과 무관하게 두 창에 걸음 기록이 기준 일수 이상"),
		("사용자", "12주결과_시작일", "노출 시작 + 70일"), ("사용자", "12주결과_종료일", "노출 시작 + 97일"),
		("사용자", "12주결과_확정", "예 = 12주 결과 창 종료 후 28일(동기화 여유)이 자료 기준일 안"),
		("사용자", IRS_OVERLAP_COL, "예 = 03 비교 대상에도 포함"),
	]
	for c in ["대상자_상태", "기준선_워치착용일", "추적_착용일", "걸음_보조_상태", "시간0", "시간0_등록후일", "기준선_종료일", "노출_시작일",
			  "노출_종료일", "추적_시작일", "추적_종료일", "확정가능일"]:
		d.append(("사용자", c, "사용 가능 사용자 목록(build_all_indicator_users.py)과 같은 값"))
	for k in B.DAILY:
		for s in ["상태", "기준선_일수", "추적_일수"]:
			d.append(("사용자", f"{k}_{s}", "사용 가능 사용자 목록과 같은 값"))
	for k in B.POINT:
		for s in ["상태", "기준선일", "추적일"]:
			d.append(("사용자", f"{k}_{s}", "사용 가능 사용자 목록의 값(마곡부스 측정도 포함한 자료 유무, 추적일은 추적 시작일 이후 첫 측정). 분석 쌍 여부는 측정_요약의 주분석_쌍·연장_쌍을 씀"))
	d += [
		("일별", "user_id", "사용자 ID"), ("일별", "날짜", "KST 날짜"),
		("일별", "구간", "기준선(시간0~13일) / 노출(28일) / 결과(노출 직후 28일) / 12주결과(노출 시작 70~97일) / 그밖"),
		("일별", "시간0후일", "날짜 - 시간 0(일)"), ("일별", "노출시작후일", "날짜 - 노출 시작일(일)"),
		("일별", "착용일", "예 = 걸음(0보 초과) 또는 심박 기록이 있는 날"),
		("일별", "워치착용일", "예 = 걸음(0보 초과)과 심박 기록이 모두 있는 날"),
		("일별", "걸음", "하루 걸음 수. 같은 날 여러 플랫폼 기록은 추출 단계에서 합산됨"),
		("일별", "걸음_유효", "예 = 0보 초과"), ("일별", "걸음_플랫폼", "그날 걸음 기록의 플랫폼 코드(여럿이면 가장 작은 코드)"),
		("일별", "걸음_복수플랫폼", "예 = 그날 걸음 기록이 2개 이상 플랫폼에서 옴(합산값에 중복이 섞였을 수 있음)"),
		("일별", "심박_기록", "1 = 그날 심박 기록 있음. 심박 값은 DevOps 용량 확인 뒤 추출 예정"),
		("일별", "심박_플랫폼", "그날 심박 기록의 플랫폼 코드(여럿이면 가장 작은 코드)"),
		("일별", "활동_세션수", "그날 운동 세션 수(기록이 없으면 빈칸, 분석에서는 착용일이면 0)"),
		("일별", "활동_분", "그날 운동 세션 시간 합(분)"), ("일별", "수면_분", "수면 종료일 기준 수면 시간 합(분)"),
		("일별", "산소포화도", "그날 산소포화도 평균(%)"), ("일별", "칼로리_총", "그날 총 소모 칼로리 합"), ("일별", "칼로리_활동", "그날 활동 칼로리 합"),
		("창별_요약", "user_id", "사용자 ID"),
	]
	for tag, w in [("기준선", "기준선 14일"), ("결과", "결과 28일"), ("12주", "12주 결과 창(확정되지 않으면 빈칸)")]:
		d += [
			("창별_요약", f"걸음_{tag}_일수", f"{w} 중 걸음 0보 초과인 날 수"), ("창별_요약", f"걸음_{tag}_평균", f"그 날들의 평균 걸음 수"),
			("창별_요약", f"활동_분_{tag}_일수", f"{w} 중 착용일 수"), ("창별_요약", f"활동_분_{tag}_평균", "착용일당 운동 분(세션 없는 착용일 0)"),
			("창별_요약", f"활동_세션수_{tag}_일수", f"{w} 중 착용일 수"), ("창별_요약", f"활동_세션수_{tag}_평균", "착용일당 운동 세션 수(세션 없는 착용일 0)"),
			("창별_요약", f"수면_분_{tag}_일수", f"{w} 중 수면 기록(0분 초과) 날 수"), ("창별_요약", f"수면_분_{tag}_평균", "그 날들의 평균 수면 분"),
			("창별_요약", f"산소포화도_{tag}_일수", f"{w} 중 산소포화도 기록 날 수"), ("창별_요약", f"산소포화도_{tag}_평균", "그 날들의 평균"),
			("창별_요약", f"칼로리_총_{tag}_일수", f"{w} 중 칼로리 기록(총+활동 > 0) 날 수"), ("창별_요약", f"칼로리_총_{tag}_평균", "그 날들의 평균 총 칼로리"),
			("창별_요약", f"심박_{tag}_기록일수", f"{w} 중 심박 기록 날 수(값은 추출 전)"),
		]
	d += [
		("측정", "user_id", "사용자 ID"), ("측정", "지표", "체중(체중·키) / 체성분 / 혈압 / 악력"), ("측정", "날짜", "측정 KST 날짜"),
		("측정", "구간", "기준선 범위(노출 전 90일) / 노출 / 결과(노출 시작 28~55일) / 결과창 이후"),
		("측정", "노출시작후일", "날짜 - 노출 시작일(일)"), ("측정", "플랫폼", "측정 플랫폼 코드(20301103 = 현장 기기)"), ("측정", "기기", "측정 기기 코드"),
		("측정", "기록출처", "현장 기기 / 개인 기기"), ("측정", "측정장소", "현장 측정 장소(혈압·체중 표만 있음, 같은 날 여러 곳이면 | 로 구분)"),
		("측정", "제외장소", "예 = 울산 거점이 아닌 장소(마곡부스). 요약에서 쓰지 않음"),
		("측정", "체중", "같은 날·플랫폼·기기의 평균(kg)"), ("측정", "키", "같은 날·플랫폼·기기의 평균(cm)"),
		("측정", "체질량지수", "체중 ÷ (키/100)² (같은 행의 키가 있을 때만 계산)"),
		("측정", "체지방률", "평균(%)"), ("측정", "체지방량", "평균(kg)"), ("측정", "골격근량", "평균(kg)"),
		("측정", "수축기혈압", "평균(mmHg)"), ("측정", "이완기혈압", "평균(mmHg)"), ("측정", "악력", "좌우 중 큰 값의 평균(kg)"),
		("측정", "기록수", "그 행으로 합친 원 기록 수(체중 표는 추출하지 않음)"),
		("측정_요약", "user_id", "사용자 ID"), ("측정_요약", "지표", "체중 / 체성분 / 혈압 / 악력"),
		("측정_요약", "주분석_쌍", "예 = 기준선 측정과 결과창(노출 시작 28~55일) 첫 측정이 모두 있음"),
		("측정_요약", "연장_쌍", "예 = 기준선 측정과 자료 기준일까지의 첫 측정(노출 시작 28일 이후)이 모두 있음(민감도 분석)"),
	]
	for w, txt in [("기준선", "노출 전 90일 안의 마지막 측정"), ("결과창", "결과창 안 첫 측정(주 분석)"), ("연장", "노출 시작 28일 이후 첫 측정(민감도 분석)")]:
		d += [(("측정_요약", f"{w}_날짜", f"{txt}의 날짜")), ("측정_요약", f"{w}_노출시작후일", "그 날짜 - 노출 시작일"),
			  ("측정_요약", f"{w}_행수", "그 날 합친 측정 행 수(플랫폼·기기별 행)"), ("측정_요약", f"{w}_기록출처", "그 날 행들의 기록출처")]
		d += [("측정_요약", f"{w}_{v}", "그 날 행들의 평균") for v in _ORDER]
	return d


def analysis_users(a, C, end):
	"""Users of the analysis-data workbook (indexed by user_id) with statuses and window dates."""
	days = B.load(a, C, end)
	A = B.build(C, days, end, a.min_days)
	return users_sheet(C, A, end)


def main():
	a = args()
	end = a.cutoff
	C = load_common_cohort(a.common_data_dir, end)
	T = analysis_users(a, C, end)
	X = daily_sheet(a, T, end)
	S = window_summary(X, T)
	M = point_sheet(a, T, end)
	P = point_summary(M, T, end)
	order = ["사이트", "성별", "나이", "등록일", "주분석_대상", "매일지표_결과확보", "걸음보조_대상", "대상자_상태", "기준선_워치착용일", "추적_착용일",
			 "걸음_보조_상태", "시간0", "시간0_등록후일", "기준선_종료일", "노출_시작일", "노출_종료일", "추적_시작일", "추적_종료일", "확정가능일",
			 "12주결과_시작일", "12주결과_종료일", "12주결과_확정"]
	for k in B.DAILY:
		order += [f"{k}_상태", f"{k}_기준선_일수", f"{k}_추적_일수"]
	for k in B.POINT:
		order += [f"{k}_상태", f"{k}_기준선일", f"{k}_추적일"]
	order.append(IRS_OVERLAP_COL)
	T = T.reindex(columns=order).sort_values(["사이트", "등록일"])
	T.index.name = "user_id"
	T = T.reset_index()
	for c in ["나이", "시간0_등록후일", "기준선_워치착용일", "추적_착용일"] + [f"{k}_{w}_일수" for k in B.DAILY for w in ["기준선", "추적"]]:
		T[c] = pd.to_numeric(T[c], errors="coerce").astype("Int64")
	main_n, aux_n = int((T.주분석_대상 == "예").sum()), int((T.걸음보조_대상 == "예").sum())
	meta = [
		("연구", "01 앱 참여도와 웨어러블 지표: 분석 자료(지표 값)"),
		("대상", f"주분석 대상(추적 확정 대상자) {main_n}명과 걸음 보조 분석 {aux_n}명의 합집합 {len(T)}명. 추적 대기 대상자는 추적 창이 닫힌 뒤 다시 만들 때 들어감"),
		("자료 기준일", f"{end.date()} (추출 {a.extract_date}, 조회 전용, 저장된 추출 파일만 사용)"),
		("시간 축", "시간 0 = 첫 걸음 기록일, 기준선 0~13일, 노출 = 기준선 종료 다음 날과 등록 다음 날 중 늦은 날부터 28일, 결과 = 노출 직후 28일, 12주 결과 = 노출 시작 70~97일"),
		("기준", f"착용일 기준 {a.min_days}일. 사용자·창·상태는 사용 가능 사용자 목록과 같은 규칙으로 다시 계산함"),
		("측정 지표", "주 분석은 결과창(노출 시작 28~55일) 안 첫 측정, 자료 기준일까지 연장은 민감도 분석. 값이 있는 행만 쓰고, 마곡부스 측정은 요약에서 쓰지 않음. 같은 날 여러 행은 값마다 평균. 추출 단계에서 같은 날·플랫폼·기기 기록이 평균되어 있으므로, 같은 날 마곡부스와 다른 장소가 섞이면 그 행은 통째로 빠짐(나눌 수 없음)"),
		("활동 시간", "추출 단계에서 하루 운동 시간은 시작·종료 시각이 있는 세션만 합산됨. 일부 세션만 시간이 빈 날은 현재 추출로는 구분할 수 없음(다음 추출에서 시간 있는 세션 수를 함께 뽑아 확인)"),
		("시간 0 규칙", "첫 걸음 기록일이 등록 30일 전보다 이전이면 시간 0 범위 밖으로 둠(계획서 규칙, 사용 가능 사용자 목록과 같음)"),
		("심박", "현재는 기록이 있는 날만 있음. 일별 심박 값은 큰 표 전체를 훑어야 하므로 DevOps 용량 확인 뒤 추출해 추가"),
		("주의", "일별 걸음은 같은 날 여러 플랫폼 기록이 추출 단계에서 합산되어 있음(걸음_복수플랫폼 = 예인 날). 처리 규칙은 통계분석계획서에서 정함"),
		("앱 사용량", "결과와 따로 둠: 00_common 앱 사용량 파일(SiBC_01_앱사용량_<tag>.xlsx). 이 파일에서는 집단 비교를 하지 않음"),
		("만든 방법", "retrospective_study/01_wearable_metrics/src/build_analysis_data.py"),
	]
	sheets = [
		("사용자", T, {"등록일", "시간0", "기준선_종료일", "노출_시작일", "노출_종료일", "추적_시작일", "추적_종료일", "확정가능일", "12주결과_시작일",
					 "12주결과_종료일"} | {f"{k}_{w}" for k in B.POINT for w in ["기준선일", "추적일"]}, None),
		("일별", X, {"날짜"}, None),
		("창별_요약", S, set(), None),
		("측정", M, {"날짜"}, None),
		("측정_요약", P, {"기준선_날짜", "결과창_날짜", "연장_날짜"}, None),
	]
	B.OUT.mkdir(exist_ok=True)
	path = B.OUT / f"SiBC_01_웨어러블_분석자료_{a.tag}.xlsx"
	write_data_workbook(path, "SiBC 01 웨어러블 지표 연구: 분석 자료", meta, sheets, coldoc())
	print(path)
	print("users", len(T), "main", main_n, "aux", aux_n, "| daily rows", len(X), "| point rows", len(M))
	pm = P[P.user_id.isin(T.user_id[T.주분석_대상 == "예"])]
	print("main pairs (window / extended):", {k: (int((g.주분석_쌍 == "예").sum()), int((g.연장_쌍 == "예").sum())) for k, g in pm.groupby("지표")})


if __name__ == "__main__":
	main()
