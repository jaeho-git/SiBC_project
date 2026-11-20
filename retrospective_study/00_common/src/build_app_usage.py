# -*- coding: utf-8 -*-
"""App usage (login days) per user for each study, kept apart from the outcome data.

Offline: reads 00_common/00_Data/login.csv (user x customer x KST day login counts) and the users of each study:
- 01: the users of the 01 analysis-data workbook (main analysis and supplementary steps group). Exposure window =
  28 days from the exposure start (later of baseline end + 1 and registration + 1).
- 02: the users with a baseline checkup. Engagement window = registration + 1 .. + 28 (the outcome of study 02).
- 03: the comparison users of the frozen 2026-11-19 design (03_irs_risk_rank/00_Data/frozen_20261119/D2.pkl). Exposure
  window = baseline IRS day + 1 .. + 28. The counts are checked against the frozen design (act28, act_pre, ldays).
A login day is a KST day with at least one login under any customer; login counts are kept for reference only.
Logins after the cutoff are not used. Study membership is taken from the same builders as the analysis data (which
read indicator availability internally), but no outcome value is written and no group is formed here: the median and
the high/low split are fixed from this distribution when the analysis plan is registered. For study 03 the baseline IRS
day itself is labelled separately and belongs to neither window.
Writes <study>/01_Results/SiBC_0X_앱사용량_<tag>.xlsx (user-level, never committed).
"""
import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from common_cohort import COMMON_DATA, END, load_common_cohort  # noqa: E402
from data_xlsx import write_data_workbook, yn  # noqa: E402

D = pd.Timedelta
WIN = 28
FROZEN03 = ROOT / "03_irs_risk_rank" / "00_Data" / "frozen_20261119"


def module(path, name):
	spec = importlib.util.spec_from_file_location(name, path)
	m = importlib.util.module_from_spec(spec)
	sys.path.insert(0, str(Path(path).parent))
	spec.loader.exec_module(m)
	return m


def args():
	ap = argparse.ArgumentParser(description="Build the per-study app-usage workbooks")
	ap.add_argument("--study", choices=["01", "02", "03", "all"], default="all")
	ap.add_argument("--common-data-dir", type=Path, default=COMMON_DATA, help="folder with users.csv and login.csv")
	ap.add_argument("--cutoff", type=pd.Timestamp, default=END, help="data cutoff date (YYYY-MM-DD)")
	ap.add_argument("--extract-date", default="2026-11-20", help="extraction date shown in the workbook")
	ap.add_argument("--tag", default="20261120", help="date tag in the output file name")
	ap.add_argument("--data-dir-01", type=Path, default=None, help="study 01 extract folder (default: the 01 builder default)")
	ap.add_argument("--min-days-01", type=int, default=4, help="study 01 wear-day threshold (same as the 01 analysis data)")
	ap.add_argument("--data-dir-02", type=Path, default=None, help="study 02 extract folder (default: the 02 builder default)")
	a = ap.parse_args()
	if not 1 <= a.min_days_01 <= 14:
		ap.error("--min-days-01 must be between 1 and 14")
	return a


def logins(data_dir, end):
	L = pd.read_csv(data_dir / "login.csv", parse_dates=["d"])
	L = L[L.d <= end].groupby(["user_id", "d"], as_index=False).n.sum()
	return L


def usage(U, L, end, anchor_label=None):
	"""U: index user_id, columns 기준일 (anchor day), 노출창_시작일, 등록일 and optional extra windows.
	Returns (per-user summary, day rows)."""
	X = L[L.user_id.isin(U.index)].merge(U[["기준일", "노출창_시작일", "등록일"]], left_on="user_id", right_index=True)
	X = X[X.d >= X.등록일]
	start, stop = X.노출창_시작일, X.노출창_시작일 + D(days=WIN - 1)
	X["기준일후일"] = (X.d - X.기준일).dt.days
	X["구간"] = np.select([X.d < start, X.d <= stop], ["노출창 이전", "노출창"], "노출창 이후")
	if anchor_label:  # the anchor day belongs to neither window (study 03 baseline IRS day)
		X.loc[X.d == X.기준일, "구간"] = anchor_label
	S = pd.DataFrame(index=U.index)
	S["노출창_종료일"] = U.노출창_시작일 + D(days=WIN - 1)
	S["노출창_확정"] = yn(S.노출창_종료일 <= end)
	inw = X[X.구간 == "노출창"]
	S["노출창_로그인일수"] = inw.groupby("user_id").size().reindex(S.index).fillna(0).astype(int)
	S["노출창_참여도"] = S.노출창_로그인일수 / WIN
	S["노출창_로그인건수"] = inw.groupby("user_id").n.sum().reindex(S.index).fillna(0).astype(int)
	S["노출창_이전_로그인일수"] = X[X.구간 == "노출창 이전"].groupby("user_id").size().reindex(S.index).fillna(0).astype(int)
	day = X[["user_id", "d", "기준일후일", "구간", "n"]].rename(columns={"d": "날짜", "n": "로그인건수"}).sort_values(["user_id", "날짜"])
	return S, X, day


def common_doc(sheet_users, anchor_text, window_text, pre_text):
	return [
		(sheet_users, "user_id", "서비스 사용자 ID(연구용 키 변환 전)"), (sheet_users, "사이트", "현재 소속 사이트(현재 시점 정보)"),
		(sheet_users, "성별", "여/남"), (sheet_users, "나이", "서비스 기록 나이"), (sheet_users, "등록일", "첫 앱 로그인 날짜(KST)"),
		(sheet_users, "기준일", anchor_text), (sheet_users, "노출창_시작일", window_text), (sheet_users, "노출창_종료일", "노출창 시작 + 27일"),
		(sheet_users, "노출창_확정", "예 = 노출창 마지막 날이 자료 기준일 이전"),
		(sheet_users, "노출창_로그인일수", "노출창 28일 중 로그인한 날 수(0~28)"), (sheet_users, "노출창_참여도", "노출창_로그인일수 ÷ 28"),
		(sheet_users, "노출창_로그인건수", "노출창의 로그인 건수 합(참고용. 2026-05부터 하루 건수가 늘어 분석에 쓰지 않음)"),
		(sheet_users, "노출창_이전_로그인일수", pre_text),
		("일별", "user_id", "사용자 ID"), ("일별", "날짜", "로그인한 KST 날짜(등록일~자료 기준일)"),
		("일별", "기준일후일", "날짜 - 기준일(일)"), ("일별", "구간", "노출창 이전 / 노출창 / 노출창 이후(03은 기준선 IRS 산출일을 '기준선일'로 따로 표시)"),
		("일별", "로그인건수", "그날 로그인 건수(참고용)"),
	]


def write(study, path, title, meta, S, day, doc, dates):
	sheets = [("사용자", S, dates, None), ("일별", day, {"날짜"}, None)]
	write_data_workbook(path, title, meta, sheets, doc)
	print(path)
	print(f"  users {len(S)} | day rows {len(day)}")


def meta_common(a, extra, values_note):
	return [
		("로그인한 날", "KST 날짜 기준, 고객(사이트) 구분 없이 로그인 기록이 1건 이상인 날. 앱 이벤트가 있는 날을 사실상 포함"),
		("자료 기준일", f"{a.cutoff.date()} (로그인 추출 2026-11-19, 같은 추출문으로 {a.extract_date} 재확인). 기준일 이후 로그인은 쓰지 않음"),
		("집단 구분", "중앙값과 고·저 참여 구분은 넣지 않음. 통계분석계획서 등록 때 이 분포만으로 정함"),
		("건강 자료", values_note),
	] + extra + [("만든 방법", "retrospective_study/00_common/src/build_app_usage.py")]


def study01(a, C, L):
	m = module(ROOT / "01_wearable_metrics" / "src" / "build_analysis_data.py", "ad01")
	a1 = argparse.Namespace(data_dir=a.data_dir_01 or m.B.DATA, min_days=a.min_days_01)
	T = m.analysis_users(a1, C, a.cutoff)
	U = pd.DataFrame(index=T.index)
	U["사이트"], U["성별"], U["나이"], U["등록일"] = T.사이트, T.성별, pd.to_numeric(T.나이, errors="coerce").astype("Int64"), T.등록일
	U["주분석_대상"], U["걸음보조_대상"] = T.주분석_대상, T.걸음보조_대상
	U["기준일"] = U["노출창_시작일"] = T.노출_시작일
	U["시간0"] = T.시간0
	S, X, day = usage(U, L, a.cutoff)
	S["시간0_이전_로그인일수"] = X[X.d < X.user_id.map(T.시간0)].groupby("user_id").size().reindex(S.index).fillna(0).astype(int)
	out = U.join(S).reset_index()
	out = out[["user_id", "사이트", "성별", "나이", "등록일", "주분석_대상", "걸음보조_대상", "시간0", "기준일", "노출창_시작일", "노출창_종료일",
			   "노출창_확정", "노출창_로그인일수", "노출창_참여도", "노출창_로그인건수", "노출창_이전_로그인일수", "시간0_이전_로그인일수"]]
	doc = common_doc("사용자", "노출창 시작일(기준선 종료 다음 날과 등록 다음 날 중 늦은 날)", "기준일과 같음",
					 "등록일부터 노출창 시작 전날까지 로그인한 날 수(공변량)") + [
		("사용자", "주분석_대상", "예 = 01 주분석 대상(추적 확정 대상자)"), ("사용자", "걸음보조_대상", "예 = 01 걸음 보조 분석 대상"),
		("사용자", "시간0", "첫 걸음 기록일"), ("사용자", "시간0_이전_로그인일수", "등록일부터 시간 0 전날까지 로그인한 날 수(공변량. 시간 0이 등록 전이면 0)"),
	]
	meta = [("연구", "01 앱 참여도와 웨어러블 지표: 앱 사용량(노출)"),
			("대상", f"01 분석 자료와 같은 {len(out)}명(주분석 {int((out.주분석_대상 == '예').sum())}명, 걸음 보조 {int((out.걸음보조_대상 == '예').sum())}명)"),
			("노출창", "기준선 종료 다음 날과 등록 다음 날 중 늦은 날부터 28일")]
	path = ROOT / "01_wearable_metrics" / "01_Results" / f"SiBC_01_앱사용량_{a.tag}.xlsx"
	write("01", path, "SiBC 01 웨어러블 지표 연구: 앱 사용량", meta + meta_common(a, [], "웨어러블 지표 값은 없음. 결과 값은 01 분석 자료 파일에 따로 있음"), out, day, doc, {"등록일", "시간0", "기준일", "노출창_시작일", "노출창_종료일"})


def study02(a, C, L):
	m = module(ROOT / "02_checkup_metrics" / "src" / "build_analysis_data.py", "ad02")
	a2 = argparse.Namespace(data_dir=a.data_dir_02 or m.B.DATA)
	_, _, users, _ = m.select_exams(a2, C, a.cutoff)
	U = pd.DataFrame(index=pd.Index(users, name="user_id"))
	U["사이트"], U["성별"], U["나이"], U["등록일"] = C.site, C.sex.map({"F": "여", "M": "남"}), pd.to_numeric(C.age, errors="coerce").astype("Int64"), C.d0
	U["기준일"] = U.등록일
	U["노출창_시작일"] = U.등록일 + D(days=1)
	S, X, day = usage(U, L, a.cutoff)
	out = U.join(S).reset_index()
	out = out.rename(columns={"노출창_시작일": "참여도창_시작일", "노출창_종료일": "참여도창_종료일", "노출창_확정": "참여도창_확정",
							  "노출창_로그인일수": "참여도창_로그인일수", "노출창_참여도": "참여도창_참여도", "노출창_로그인건수": "참여도창_로그인건수"})
	out = out[["user_id", "사이트", "성별", "나이", "등록일", "기준일", "참여도창_시작일", "참여도창_종료일", "참여도창_확정", "참여도창_로그인일수",
			   "참여도창_참여도", "참여도창_로그인건수"]]
	day["구간"] = day.구간.str.replace("노출창", "참여도창")
	doc = [(s, c.replace("노출창", "참여도창"), t.replace("노출창", "참여도창")) for s, c, t in
		   common_doc("사용자", "등록일(첫 로그인 날)", "등록 다음 날", "") if c != "노출창_이전_로그인일수"]
	doc = [(s, c, t + (" 02에서는 이것이 결과 변수(주 결과)" if c == "참여도창_로그인일수" else "")) for s, c, t in doc]
	meta = [("연구", "02 건강검진 결과와 앱 참여도: 앱 사용량(결과 변수)"),
			("대상", f"02 분석 자료와 같은 기준선 검진 보유 {len(out)}명"),
			("참여도창", "등록 다음 날부터 28일. 02에서는 앱 참여도가 결과 변수이므로 '노출창' 대신 '참여도창'이라고 씀")]
	path = ROOT / "02_checkup_metrics" / "01_Results" / f"SiBC_02_앱사용량_{a.tag}.xlsx"
	write("02", path, "SiBC 02 건강검진 연구: 앱 사용량", meta + meta_common(a, [], "건강검진 값은 없음. 02에서는 이 파일의 참여도창 로그인 일수가 결과 변수이고, 설명 변수(검진 값)는 02 분석 자료 파일에 따로 있음"), out, day, doc, {"등록일", "기준일", "참여도창_시작일", "참여도창_종료일"})


def study03(a, C, L):
	D2 = pd.read_pickle(FROZEN03 / "D2.pkl")
	U = pd.DataFrame(index=D2.index)
	U["연구번호"] = D2.sid
	U["사이트"], U["성별"] = D2.site, D2.sex.map({"F": "여", "M": "남"}).fillna(D2.sex)
	U["나이"] = pd.to_numeric(D2.age_b, errors="coerce").astype("Int64")
	U["등록일"] = D2.d0
	U["기준일"] = D2.t_b.dt.normalize()
	U["노출창_시작일"] = U.기준일 + D(days=1)
	U["추적_산출일"] = D2.t_f.dt.normalize()
	S, X, day = usage(U, L, a.cutoff, anchor_label="기준선일")
	S["기준선_추적_로그인일수"] = X[(X.기준일후일 >= 1) & (X.d <= X.user_id.map(U.추적_산출일))].groupby("user_id").size().reindex(S.index).fillna(0).astype(int)
	# the frozen design counted the same login days (baseline day excluded from both windows)
	assert (S.노출창_로그인일수 == D2.act28).all() and (S.기준선_추적_로그인일수 == D2.ldays).all(), "03 exposure differs from the frozen design"
	S["기준선일_로그인"] = yn(S.index.isin(X[X.구간 == "기준선일"].user_id))
	S["기준선_전날까지_로그인일수"] = S.노출창_이전_로그인일수
	assert (S.기준선_전날까지_로그인일수 == D2.act_pre).all(), "03 pre-baseline days differ from the frozen design"
	out = U.join(S).reset_index()
	out = out[["연구번호", "user_id", "사이트", "성별", "나이", "등록일", "기준일", "노출창_시작일", "노출창_종료일", "노출창_확정", "노출창_로그인일수",
			   "노출창_참여도", "노출창_로그인건수", "기준선_전날까지_로그인일수", "기준선일_로그인", "추적_산출일", "기준선_추적_로그인일수"]]
	doc = [d for d in common_doc("사용자", "기준선 IRS 산출일", "기준일 다음 날", "") if d[1] != "노출창_이전_로그인일수"] + [
		("사용자", "연구번호", "03 비교 xlsx(03_irs_risk_rank/01_Results의 기준선·추적 환산 비교 파일)의 연구번호와 같음"),
		("사용자", "기준선_전날까지_로그인일수", "등록일부터 기준선 전날까지 로그인한 날 수(공변량. 03 비교 xlsx의 '기준선 전날까지 앱 활성일 수'와 같음)"),
		("사용자", "기준선일_로그인", "예 = 기준선 산출일에 로그인함(어느 창에도 넣지 않음)"),
		("사용자", "추적_산출일", "추적 IRS 산출일"),
		("사용자", "기준선_추적_로그인일수", "기준선 다음 날부터 추적 산출일까지 로그인한 날 수(03 비교 xlsx의 '기준선~추적 앱 로그인 일수'와 같음)"),
	]
	meta = [("연구", "03 앱 참여도와 IRS 위험 구간 이동: 앱 사용량(노출)"),
			("대상", f"03 비교 대상 {len(out)}명(2026-11-19 확정 설계, 저장본 frozen_20261119)"),
			("노출창", "기준선 IRS 산출일 다음 날부터 28일. 값은 03 비교 xlsx의 '기준선 후 28일 앱 활성일 수(노출)'와 사용자마다 같음(실행 때 확인)")]
	path = ROOT / "03_irs_risk_rank" / "01_Results" / f"SiBC_03_앱사용량_{a.tag}.xlsx"
	write("03", path, "SiBC 03 IRS 연구: 앱 사용량", meta + meta_common(a, [], "IRS 값과 순위는 없음. 결과 값은 03 비교 xlsx에 따로 있음"), out, day, doc, {"등록일", "기준일", "노출창_시작일", "노출창_종료일", "추적_산출일"})


def main():
	a = args()
	C = load_common_cohort(a.common_data_dir, a.cutoff)
	L = logins(a.common_data_dir, a.cutoff)
	for s, f in [("01", study01), ("02", study02), ("03", study03)]:
		if a.study in (s, "all"):
			f(a, C, L)


if __name__ == "__main__":
	main()
