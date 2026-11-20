# -*- coding: utf-8 -*-
"""Study 02: analysis-data workbook (checkup values) for local analysis without a database connection.

Offline: reads the saved version-3 extract (02_checkup_metrics/00_Data/extract_20261120/checkup_events_all.csv) and the
common cohort, and applies the same item, de-duplication and window rules as build_all_item_users.py, so users and
exam dates match the usable-user list (checked at run time).
Writes 02_checkup_metrics/01_Results/SiBC_02_건강검진_분석자료_<tag>.xlsx (user-level health data, never committed).

Users: the common-cohort users with a baseline checkup (registration -730..0 days).
Sheets
- 사용자: one row per user (site, sex, age, registration, baseline/follow-up status, the 11-component summary panel
  completeness).
- 기준선_값: one row per user, for each of the 22 items the value and the exam date of the baseline exam.
- 추적_값: the same for the first follow-up exam (registration +29..+365), users with a follow-up exam only.
- 검진_원자료: every item entry of these users (all dates up to the cutoff), with the normalised item, the parsed value,
  validity and whether it is the entry used (latest inserted entry of that user x exam date x item).
Abnormality flags are not computed: the cut-offs are fixed in the statistical analysis plan.
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
import build_all_item_users as B  # noqa: E402
from common_cohort import COMMON_DATA, END, IRS_OVERLAP_COL, irs_comparison_users, load_common_cohort, overlap_flag  # noqa: E402
from data_xlsx import write_data_workbook, yn  # noqa: E402

NAME = {k: n for k, n, _ in B.ITEMS}
PANEL = ["bmi", "waist", "bp", "fbg", "hb", "ast", "alt", "ggt", "cr", "gfr", "uprot"]  # 11 components, bp = sbp and dbp


def args():
	ap = argparse.ArgumentParser(description="Build the study 02 analysis-data workbook")
	ap.add_argument("--data-dir", type=Path, default=B.DATA, help="folder with checkup_events_all.csv")
	ap.add_argument("--common-data-dir", type=Path, default=COMMON_DATA, help="folder with users.csv and login.csv")
	ap.add_argument("--cutoff", type=pd.Timestamp, default=END, help="data cutoff date (YYYY-MM-DD)")
	ap.add_argument("--extract-date", default="2026-11-20", help="extraction date shown in the workbook")
	ap.add_argument("--tag", default="20261120", help="date tag in the output file name")
	return ap.parse_args()


def load_entries(data_dir: Path, end: pd.Timestamp, users):
	"""Every item entry (blood pressure split) with raw text, parsed value, validity and the used-entry flag."""
	E = pd.read_csv(data_dir / "checkup_events_all.csv", dtype=str, keep_default_na=False)
	E = E[E.measured_dt.str.match(r"^\d{4}-\d{2}-\d{2}$", na=False)].copy()
	E["d"] = pd.to_datetime(E.measured_dt, errors="coerce")
	E = E[E.d.notna() & (E.d <= end) & E.user_id.isin(users)]
	for c in ["health_sn", "elem_no", "det_no"]:
		E[c] = pd.to_numeric(E[c], errors="coerce")
	rows = []
	for r in E.itertuples():
		key = (r.ins_ts, r.health_sn, r.elem_no, r.det_no)
		v = r.value.strip()
		base = (r.user_id, r.d, r.src, r.ins_ts, r.health_sn, r.elem_no, r.det_no, key, r.field_nm, r.value)
		if r.field_nm == "bloodpressure":
			m = B.BP.match(v)
			rows.append(base + ("sbp", bool(m), float(m.group(1)) if m else np.nan, None))
			rows.append(base + ("dbp", bool(m), float(m.group(2)) if m else np.nan, None))
			continue
		item = B.FIELD.get(r.field_nm)
		if item is None:
			continue
		if B.KIND[item] == "num":
			ok = B.is_num(v)
			rows.append(base + (item, ok, float(v) if ok else np.nan, None))
		else:
			rows.append(base + (item, v != "", np.nan, v if v != "" else None))
	L = pd.DataFrame(rows, columns=["user_id", "d", "src", "ins_ts", "health_sn", "elem_no", "det_no", "ins_key", "field_nm", "raw",
									"item", "ok", "num", "cat"])
	L["d"] = pd.to_datetime(L["d"])
	L["ok"] = L["ok"].astype(bool)
	L["num"] = L["num"].astype(float)
	L = L.sort_values("ins_key", kind="mergesort")
	L["used"] = ~L.duplicated(["user_id", "d", "item"], keep="last")
	return L


def wide(L, sel, users, prefix):
	"""One row per user: value and exam date of the chosen exam per item (sel = rows already restricted to one exam per item)."""
	W = pd.DataFrame(index=users)
	for key, name, kind in B.ITEMS:
		s = sel[sel.item == key].set_index("user_id")
		W[f"{name}"] = s["num"] if kind == "num" else s["cat"]
		W[f"{name}_검진일"] = s["d"]
	W.index.name = "user_id"
	return W


def select_exams(a, C, end):
	"""Entries, baseline selection (latest valid exam per item), baseline users and follow-up selection."""
	L = load_entries(a.data_dir, end, set(C.index))
	ok = L[L.used & L.ok].copy()
	ok["k"] = (ok.d - ok.user_id.map(C.d0)).dt.days
	# same rule and result as the usable-user list
	ref, _ = B.load_items(a.data_dir, end)
	ref = ref[ref.user_id.isin(C.index)]
	assert set(map(tuple, ref[["user_id", "d", "item"]].astype(str).values)) == set(map(tuple, ok[["user_id", "d", "item"]].astype(str).values)), "valid used entries differ from the usable-user list"
	Bk = ok[ok.k.between(B.BASE_KMIN, B.BASE_KMAX)]
	Bsel = Bk.sort_values("d").drop_duplicates(["user_id", "item"], keep="last")  # latest valid exam per item
	users = sorted(set(Bsel.user_id), key=lambda u: (C.site[u], C.d0[u], u))
	Fk = ok[ok.k.between(B.FU_KMIN, B.FU_KMAX) & ok.user_id.isin(users)]
	Fsel = Fk.sort_values("d").drop_duplicates(["user_id", "item"], keep="first")  # first valid exam per item
	return L, Bsel, users, Fsel


def main():
	a = args()
	end = a.cutoff
	C = load_common_cohort(a.common_data_dir, end)
	L, Bsel, users, Fsel = select_exams(a, C, end)

	T = pd.DataFrame(index=pd.Index(users, name="user_id"))
	T["사이트"] = C.site
	T["성별"] = C.sex.map({"F": "여", "M": "남"})
	T["나이"] = pd.to_numeric(C.age, errors="coerce").astype("Int64")
	T["등록일"] = C.d0
	T["기준선_최근검진일"] = Bsel.groupby("user_id").d.max()
	T["기준선_항목수"] = Bsel.groupby("user_id").item.nunique().astype("Int64")
	have = Bsel.groupby("user_id").item.apply(set)
	def panel(items):  # blood pressure counts only when both components are measured
		items = set(items) | ({"bp"} if {"sbp", "dbp"} <= set(items) else set())
		return len(items & set(PANEL))
	T["요약패널_측정수"] = [panel(have.get(u, set())) for u in T.index]
	T["요약패널_완전"] = yn(T.요약패널_측정수 == len(PANEL))
	T["추적_검진있음"] = yn(T.index.isin(Fsel.user_id))
	T["추적_첫검진일"] = Fsel.groupby("user_id").d.min()
	T["추적창_종료일"] = T.등록일 + pd.Timedelta(days=B.FU_KMAX)
	T[IRS_OVERLAP_COL] = overlap_flag(T.index, irs_comparison_users())
	WB = wide(L, Bsel, T.index, "기준선")
	WF = wide(L, Fsel, sorted(set(Fsel.user_id), key=users.index), "추적")
	R = L[L.user_id.isin(users)].copy()
	R["등록후일"] = (R.d - R.user_id.map(C.d0)).dt.days
	R["구간"] = np.select([R.등록후일.between(B.BASE_KMIN, B.BASE_KMAX), R.등록후일.between(B.FU_KMIN, B.FU_KMAX)], ["기준선 범위", "추적 범위"], "그밖")
	R["항목"] = R.item.map(NAME)
	R["유효"] = yn(R.ok)
	R["사용"] = yn(R.used)
	R = R[["user_id", "d", "등록후일", "구간", "src", "ins_ts", "health_sn", "elem_no", "det_no", "field_nm", "raw", "항목", "num", "cat", "유효", "사용"]]
	R = R.rename(columns={"d": "검진일", "src": "원천구분", "ins_ts": "입력시각", "field_nm": "원천필드", "raw": "원값", "num": "수치", "cat": "범주"})
	R = R.sort_values(["user_id", "검진일", "항목", "입력시각"])
	for c in ["health_sn", "elem_no", "det_no"]:
		R[c] = R[c].astype("Int64")

	T = T.reset_index()
	WB = WB.reset_index()
	WF = WF.reset_index()
	doc = [
		("사용자", "user_id", "서비스 사용자 ID(연구용 키 변환 전)"), ("사용자", "사이트", "현재 소속 사이트(현재 시점 정보)"),
		("사용자", "성별", "여/남"), ("사용자", "나이", "서비스 기록 나이"), ("사용자", "등록일", "첫 앱 로그인 날짜(KST)"),
		("사용자", "기준선_최근검진일", "항목별 기준선 검진일 중 가장 늦은 날"), ("사용자", "기준선_항목수", "기준선 값이 있는 항목 수(22개 중)"),
		("사용자", "요약패널_측정수", "요약 패널 11개 구성 요소 중 기준선 값이 있는 수(혈압은 수축기·이완기가 함께 있으면 1)"),
		("사용자", "요약패널_완전", "예 = 11개 구성 요소가 모두 측정됨(요약 지표의 주 정의 대상)"),
		("사용자", "추적_검진있음", "예 = 등록 후 29~365일에 유효한 항목이 있는 검진이 있음(종단 확장 분석용)"),
		("사용자", "추적_첫검진일", "추적 범위의 첫 검진일"), ("사용자", "추적창_종료일", "등록일 + 365일"),
		("사용자", IRS_OVERLAP_COL, "예 = 03 비교 대상에도 포함"),
	]
	for sheet, w in [("기준선_값", "기준선(등록 전 24개월~등록일) 중 그 항목의 가장 최근 유효한 검진"), ("추적_값", "추적 범위(등록 후 29~365일) 중 그 항목의 첫 유효한 검진")]:
		doc.append((sheet, "user_id", "사용자 ID"))
		for key, name, kind in B.ITEMS:
			doc.append((sheet, name, f"{w}의 값. " + ("수치" if kind == "num" else "범주 표기(원문 그대로)")))
			doc.append((sheet, f"{name}_검진일", f"그 값의 검진일"))
	doc += [
		("검진_원자료", "user_id", "사용자 ID"), ("검진_원자료", "검진일", "measuredDt"), ("검진_원자료", "등록후일", "검진일 - 등록일"),
		("검진_원자료", "구간", "기준선 범위(등록 전 730일~등록일) / 추적 범위(등록 후 29~365일) / 그밖"),
		("검진_원자료", "원천구분", "검진 기록의 원천 구분 코드"), ("검진_원자료", "입력시각", "입력 시각(중복 입력 판정에 사용)"),
		("검진_원자료", "health_sn", "원천 레코드 번호"), ("검진_원자료", "elem_no", "원천 배열 위치"), ("검진_원자료", "det_no", "원천 세부 위치"),
		("검진_원자료", "원천필드", "원천 fieldNm"), ("검진_원자료", "원값", "원천 값 문자열"),
		("검진_원자료", "항목", "22개 항목 중 하나(혈압 'nnn/nn'은 수축기·이완기 두 행)"),
		("검진_원자료", "수치", "수치 항목의 값(형식이 잘못되면 빈칸)"), ("검진_원자료", "범주", "범주 항목의 표기"),
		("검진_원자료", "유효", "예 = 값이 있고 형식이 맞음"),
		("검진_원자료", "사용", "예 = 같은 사용자·검진일·항목 중 가장 늦게 입력된 기록(이 기록이 유효하지 않으면 그 항목은 그 검진에서 없음)"),
	]
	meta = [
		("연구", "02 건강검진 결과와 앱 참여도: 분석 자료(검진 값)"),
		("대상", f"공통 코호트 중 기준선 검진이 있는 {len(T)}명(추적 검진 있음 {int((T.추적_검진있음 == '예').sum())}명)"),
		("자료 기준일", f"{end.date()} (추출 {a.extract_date}, 조회 전용, 전 항목 추출 3판, 저장된 추출 파일만 사용)"),
		("검진 원천", "승인 원천만: discovery.disc_medical_user_info → disc_health_user_info.health_info_data, 검진일 = measuredDt"),
		("항목", "계획서 3.4절 번호 목록 22개(혈압은 수축기·이완기 각각). 두 가지 이름으로 기록된 필드는 같은 항목으로 합침"),
		("규칙", "사용 가능 사용자 목록(build_all_item_users.py)과 같은 중복 입력·기준선·추적 규칙. 실행할 때 유효한 사용 기록이 목록 도구와 같음을 확인함"),
		("요약 패널", "체질량지수, 허리둘레, 혈압, 공복혈당, 혈색소, AST, ALT, 감마지티피, 혈청 크레아티닌, 사구체여과율, 요단백(11개 구성 요소)"),
		("판정", "기준 밖(이상) 여부는 넣지 않음. 항목별 판정 기준은 통계분석계획서에서 확정"),
		("앱 사용량", "결과와 따로 둠: 00_common 앱 사용량 파일(SiBC_02_앱사용량_<tag>.xlsx). 이 파일에서는 집단 비교를 하지 않음"),
		("만든 방법", "retrospective_study/02_checkup_metrics/src/build_analysis_data.py"),
	]
	dcols = {f"{n}_검진일" for _, n, _ in B.ITEMS}
	sheets = [
		("사용자", T, {"등록일", "기준선_최근검진일", "추적_첫검진일", "추적창_종료일"}, None),
		("기준선_값", WB, dcols, None),
		("추적_값", WF, dcols, None),
		("검진_원자료", R, {"검진일"}, None),
	]
	B.OUT.mkdir(exist_ok=True)
	path = B.OUT / f"SiBC_02_건강검진_분석자료_{a.tag}.xlsx"
	write_data_workbook(path, "SiBC 02 건강검진 연구: 분석 자료", meta, sheets, doc)
	print(path)
	print("users", len(T), "| panel complete", int((T.요약패널_완전 == "예").sum()), ">=10", int((T.요약패널_측정수 >= 10).sum()),
		  "| follow-up", int((T.추적_검진있음 == "예").sum()), "| raw rows", len(R))
	print("baseline by item", {n: int(WB[n].notna().sum()) for _, n, _ in B.ITEMS})


if __name__ == "__main__":
	main()
