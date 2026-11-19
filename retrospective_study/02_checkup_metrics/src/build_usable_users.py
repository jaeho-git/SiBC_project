# -*- coding: utf-8 -*-
"""Study 02 (app engagement x health checkup indicators): usable-user workbook for the common cohort.

Source: the approved checkup source only (02_checkup_metrics/sql/checkup_extracts.sql). Site measurements (lifelog),
IRS medical inputs and user_checkup_log are not used.

Offline: reads saved extracts (00_common/00_Data, 02_checkup_metrics/00_Data/checkup_events.csv). Writes
02_checkup_metrics/01_Results/SiBC_02_건강검진_사용가능사용자_<tag>.xlsx (user-level, never committed).
Defaults reproduce the 2026-11-19 list; for a refreshed extract pass --data-dir, --common-data-dir, --cutoff and --tag.

Rules
- Exam date = measuredDt. Same user x exam date x item reported more than once: keep the most recently inserted row;
  if that row's value is invalid (not a number, or blood pressure not "nnn/nn"), the item counts as missing for that exam.
  The 2026-11-19 extract has the insertion date only (ins_d); a newer extract with ins_ts, health_sn, elem_no and det_no
  is ordered by those. Ties that remain ambiguous (same latest insertion, different values) are counted and reported.
- Blood pressure "120/80" is split into systolic and diastolic.
- Baseline = latest exam within the 24 months up to the registration date (registration -730..0 days).
- Follow-up = first exam 29..365 days after registration (12-month window of the protocol).
Per item, the baseline is that item's latest exam in the baseline window and the follow-up is its first exam in the
follow-up window. Only availability (dates, status) is written, not values.
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "00_common" / "src"))
from common_cohort import IRS_OVERLAP_COL, irs_comparison_users, load_common_cohort, overlap_flag, run_args  # noqa: E402
from xlsx_util import write_workbook  # noqa: E402

DATA = HERE.parent / "00_Data"
OUT = HERE.parent / "01_Results"
BASE_KMIN, BASE_KMAX = -730, 0
FU_KMIN, FU_KMAX = 29, 365
ALIAS = {"systolic": "sbp", "diastolic": "dbp", "fastingbloodsuger": "fbg", "fastingglucose": "fbg", "totalcholesterol": "tc",
		 "triglyceride": "tg", "hdlcholesterol": "hdl", "ldlcholesterol": "ldl"}
ITEMS = [("sbp", "수축기혈압"), ("dbp", "이완기혈압"), ("fbg", "공복혈당"), ("tc", "총콜레스테롤"), ("hdl", "HDL"), ("tg", "중성지방"),
		 ("ldl", "LDL"), ("weight", "체중"), ("waist", "허리둘레"), ("bmi", "BMI")]
D = pd.Timedelta

S_CK = [
	("변화 분석 가능", "기준선 검진(등록 전 24개월~등록일)과 등록 29~365일 검진이 모두 있고, 두 검진에 같이 있는 항목이 1개 이상"),
	("두 검진 있음, 공통 항목 없음", "기준선·추적 검진은 모두 있으나 두 검진에 같이 있는 항목이 없음"),
	("기준선 있음, 추적 검진 대기", "기준선 검진은 있고, 등록 후 365일이 아직 지나지 않았으며 아직 추적 검진이 없음. '추적창_종료일'까지 기다림"),
	("기준선 있음, 추적 창 지남", "기준선 검진은 있으나 등록 후 365일 안에 검진이 없음"),
	("추적 검진만 있음", "등록 29~365일 검진은 있으나 기준선 검진이 없음"),
	("범위 밖 검진만 있음", "검진 기록은 있으나 기준선·추적 범위 안에는 없음"),
	("검진 기록 없음", "승인 원천에 검진 기록이 없음"),
]
HEAD = ["user_id", "사이트", "성별", "나이", "등록일", "검진_상태", "검진_횟수", "기준선_검진일", "기준선_등록후일", "추적_검진일",
		"추적_등록후일", "추적창_종료일", "두 검진 공통 항목"]
COLUMNS = HEAD + [f"{w}_{name}" for w in ["기준선", "추적"] for _, name in ITEMS] + [IRS_OVERLAP_COL]


def num(v):
	try:
		return float(v)
	except (TypeError, ValueError):
		return np.nan


def load_checkups(data_dir: Path):
	"""Long table user x exam date x item with the latest inserted value, plus the number of ambiguous ties."""
	E = pd.read_csv(data_dir / "checkup_events.csv", dtype=str, keep_default_na=False)
	E = E[E.measured_dt.str.match(r"^\d{4}-\d{2}-\d{2}$", na=False)].copy()
	E["d"] = pd.to_datetime(E.measured_dt, errors="coerce")
	E = E[E.d.notna()]
	order = [c for c in ["ins_ts", "health_sn", "elem_no", "det_no"] if c in E.columns] or ["ins_d"]
	for c in ["health_sn", "elem_no", "det_no"]:
		if c in order:
			E[c] = pd.to_numeric(E[c], errors="coerce")
	rows = []
	for r in E.itertuples():
		key = tuple(getattr(r, c) for c in order)
		f = r.field_nm
		v = r.value if isinstance(r.value, str) else ""
		if f == "bloodpressure":
			m = re.match(r"^\s*(\d{2,3})\s*/\s*(\d{2,3})\s*$", v)
			s_, d_ = (float(m.group(1)), float(m.group(2))) if m else (np.nan, np.nan)
			rows += [(r.user_id, r.d, key, "sbp", s_), (r.user_id, r.d, key, "dbp", d_)]
			continue
		rows.append((r.user_id, r.d, key, ALIAS.get(f, f), num(v)))
	# invalid values stay in until the latest insertion is chosen, so a newer invalid entry is not replaced by an older one
	L = pd.DataFrame(rows, columns=["user_id", "d", "ins_key", "item", "v"])
	L["d"] = pd.to_datetime(L["d"])  # fixed dtype even when no row is usable
	if len(L):
		latest = L.groupby(["user_id", "d", "item"]).ins_key.transform("max")
		top = L[L.ins_key == latest]
		ties = int((top.groupby(["user_id", "d", "item"]).v.nunique(dropna=False) > 1).sum())
		L = L.sort_values("ins_key", kind="mergesort").drop_duplicates(["user_id", "d", "item"], keep="last")
	else:
		ties = 0
	return L.dropna(subset=["v"]), ties, order


def main():
	a = run_args(DATA, "Build the study 02 usable-user workbook")
	end = a.cutoff
	C = load_common_cohort(a.common_data_dir, end)
	L, ties, order = load_checkups(a.data_dir)
	if ties:
		print(f"WARNING: {ties} user x exam date x item keys have different values at the same latest insertion ({'/'.join(order)})")
	L = L[L.user_id.isin(C.index) & (L.d <= end)].copy()
	L["k"] = (L.d - L.user_id.map(C.d0)).dt.days
	recs = []
	for u, c in C.iterrows():
		g = L[L.user_id == u]
		r = dict(user_id=u, 사이트=c.site, 성별={"F": "여", "M": "남"}.get(c.sex, c.sex), 나이=pd.to_numeric(c.age, errors="coerce"),
				 등록일=c.d0, 추적창_종료일=c.d0 + D(days=FU_KMAX))
		r["검진_횟수"] = int(g.d.nunique()) if len(g) else 0
		b = g[g.k.between(BASE_KMIN, BASE_KMAX)]
		f = g[g.k.between(FU_KMIN, FU_KMAX)]
		if len(b):
			db = b.d.max()
			r.update(기준선_검진일=db, 기준선_등록후일=int((db - c.d0).days))
		if len(f):
			df_ = f.d.min()
			r.update(추적_검진일=df_, 추적_등록후일=int((df_ - c.d0).days))
		# per item: baseline = that item's latest exam in the baseline window, follow-up = its first exam in the follow-up window
		bi, fi = {}, {}
		for key, name in ITEMS:
			x = b[b.item == key].d
			y = f[f.item == key].d
			if len(x):
				bi[key] = x.max()
			if len(y):
				fi[key] = y.min()
			r[f"기준선_{name}"] = bi.get(key)
		for key, name in ITEMS:
			r[f"추적_{name}"] = fi.get(key)
		pair = [name for key, name in ITEMS if key in bi and key in fi]
		r["두 검진 공통 항목"] = ", ".join(pair) if pair else None
		if len(b) and len(f):
			s = "변화 분석 가능" if pair else "두 검진 있음, 공통 항목 없음"
		elif len(b):
			s = "기준선 있음, 추적 검진 대기" if c.d0 + D(days=FU_KMAX) > end else "기준선 있음, 추적 창 지남"
		elif len(f):
			s = "추적 검진만 있음"
		elif len(g):
			s = "범위 밖 검진만 있음"
		else:
			s = "검진 기록 없음"
		r["검진_상태"] = s
		recs.append(r)
	T = pd.DataFrame(recs).reindex(columns=COLUMNS)  # fixed schema even when a window is empty for everyone
	T[IRS_OVERLAP_COL] = overlap_flag(T.user_id, irs_comparison_users())
	T = T.sort_values(["사이트", "등록일"])
	for c in ["나이", "기준선_등록후일", "추적_등록후일"]:
		T[c] = pd.to_numeric(T[c], errors="coerce").astype("Int64").astype(object).where(T[c].notna(), None)
	meta = [
		("연구", "02 앱 참여도와 건강검진 지표"),
		("대상", f"공통 코호트 {len(T)}명 (사이트 연결, 운영자·테스트 제외, 등록 후 28일 경과·그 안에 탈퇴 없음)"),
		("자료 기준일", f"{end.date()} (추출 {a.extract_date}, 조회 전용)"),
		("검진 원천", "승인 원천만 사용: discovery.disc_medical_user_info → disc_health_user_info.health_info_data, 검진일 = measuredDt. 현장 측정·IRS 입력값·user_checkup_log는 쓰지 않음"),
		("기준선", "등록 전 24개월~등록일 사이 가장 최근 검진. 항목별 열(기준선_수축기혈압 등)에는 그 항목의 가장 최근 검진일을 적음"),
		("추적", "등록 후 29~365일 사이 첫 검진 (계획서의 12개월 결과 창). 항목별 열에는 그 항목의 첫 검진일을 적음"),
		("중복 입력", f"같은 사용자·검진일·항목이 여러 번 있으면 가장 늦게 입력된 값을 씀(정렬 기준: {', '.join(order)}). 가장 늦은 입력이 같은데 값이 다른 경우: {ties}건"),
		("현재 판단", "추적 검진이 있는 사람이 아직 적어 변화 분석은 검진이 쌓일 때까지 대기. '추적창_종료일'이 지나면 다시 만듦"),
		("값을 넣지 않은 이유", "분석 계획 확정 전에 집단 간 결과 차이를 보지 않기 위해 날짜·항목 유무·상태만 적음"),
		("03 겹침", f"'{IRS_OVERLAP_COL}' = 03 연구 비교 대상에도 들어가는 사용자. 투고 시 표본 겹침을 밝힘. 03 결과 파일이 없으면 '확인 불가'"),
		("만든 방법", "retrospective_study/02_checkup_metrics/src/build_usable_users.py (저장된 추출 파일만 사용)"),
	]
	OUT.mkdir(exist_ok=True)
	path = OUT / f"SiBC_02_건강검진_사용가능사용자_{a.tag}.xlsx"
	dates = ["등록일", "기준선_검진일", "추적_검진일", "추적창_종료일"] + [f"{w}_{name}" for w in ["기준선", "추적"] for _, name in ITEMS]
	write_workbook(path, "SiBC 02 건강검진 지표 연구: 사용 가능 사용자", meta, [("검진_상태", S_CK)], T, date_cols=dates)
	print(path)
	print(T.groupby(["사이트", "검진_상태"]).size().to_dict())
	for key, name in ITEMS[:4]:
		print(name, "baseline", int(T[f"기준선_{name}"].notna().sum()), "followup", int(T[f"추적_{name}"].notna().sum()),
			  "pair", int((T[f"기준선_{name}"].notna() & T[f"추적_{name}"].notna()).sum()))
	print("users with any exam day>=29:", int(L[L.k >= FU_KMIN].user_id.nunique()), "| 03 overlap among baseline:",
		  int((T.기준선_검진일.notna() & (T[IRS_OVERLAP_COL] == "예")).sum()), "| ambiguous ties:", ties)
	print("follow-up window end range:", T.추적창_종료일.min().date(), T.추적창_종료일.max().date())


if __name__ == "__main__":
	main()
