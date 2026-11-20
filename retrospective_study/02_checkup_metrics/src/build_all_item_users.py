# -*- coding: utf-8 -*-
"""Study 02, all checkup items: usable-user workbook for the cross-sectional analysis (and follow-up accrual).

Source: the approved checkup source only, version-3 extract (02_checkup_metrics/sql/checkup_extracts.sql,
block checkup_events_all). Site measurements, IRS inputs and user_checkup_log are not used.
Offline: reads saved extracts (00_common/00_Data, 02_checkup_metrics/00_Data/extract_20261120). Writes
02_checkup_metrics/01_Results/SiBC_02_건강검진_전항목_사용가능사용자_<tag>.xlsx (user-level, never committed).
The 2026-11-19 list stays reproducible with build_usable_users.py (version-2 extract); this script does not replace it.
Defaults are a fixed combination on purpose: the official common cohort (cutoff 2026-11-17) with the 2026-11-20
version-3 extract cut at the same cutoff. For another cutoff pass --data-dir, --common-data-dir, --cutoff and --tag.

Rules
- Exam date = measuredDt (YYYY-MM-DD); exams after the cutoff are ignored.
- Items: 21 items (blood pressure gives two columns). Fields recorded under two names are merged into one item
  (systolic/diastolic or "nnn/nn" blood pressure, both fasting-glucose names, both creatinine names, both urine-protein
  names, both chest-finding names). Rare fields (osteoporosis, BUN, haematocrit, platelets) are not used.
- Same user x exam date x item more than once: keep the most recently inserted entry (ins_ts, health_sn, elem_no,
  det_no). If that entry is blank or invalid (numeric item that is not a number, blood pressure that is not "nnn/nn"),
  the item counts as missing for that exam. Categorical items are valid when not blank; their coding is fixed in the
  analysis plan.
- Baseline = per item, the latest valid exam in registration -730..0 days. Follow-up = per item, the first valid exam
  in registration +29..+365 days (kept for the later change analysis; the current analysis is cross-sectional).
Only availability is written (dates, counts, status). Checkup values and app logins are never written, because in the
cross-sectional analysis the checkup result is the exposure and app engagement is the outcome.
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "00_common" / "src"))
from common_cohort import COMMON_DATA, END, IRS_OVERLAP_COL, irs_comparison_users, load_common_cohort, overlap_flag  # noqa: E402
from xlsx_util import write_workbook  # noqa: E402

DATA = HERE.parent / "00_Data" / "extract_20261120"
OUT = HERE.parent / "01_Results"
D = pd.Timedelta
BASE_KMIN, BASE_KMAX = -730, 0
FU_KMIN, FU_KMAX = 29, 365

# (item key, column name, kind); kind "num" = numeric value, "cat" = categorical label
ITEMS = [
	("height", "키", "num"), ("weight", "체중", "num"), ("bmi", "체질량지수", "num"), ("waist", "허리둘레", "num"),
	("sbp", "수축기혈압", "num"), ("dbp", "이완기혈압", "num"), ("fbg", "공복혈당", "num"),
	("tc", "총콜레스테롤", "num"), ("hdl", "HDL", "num"), ("ldl", "LDL", "num"), ("tg", "중성지방", "num"),
	("hb", "혈색소", "num"), ("ast", "AST", "num"), ("alt", "ALT", "num"), ("ggt", "감마지티피", "num"),
	("cr", "혈청크레아티닌", "num"), ("gfr", "사구체여과율", "num"),
	("uprot", "요단백", "cat"), ("sight", "시력", "cat"), ("hearing", "청력", "cat"), ("chest", "흉부소견", "cat"),
	("judge", "종합판정", "cat"),
]
KIND = {k: kind for k, _, kind in ITEMS}
FIELD = {  # source fieldNm -> item key (bloodpressure is split into sbp and dbp)
	"height": "height", "weight": "weight", "bmi": "bmi", "waist": "waist", "systolic": "sbp", "diastolic": "dbp",
	"fastingbloodsuger": "fbg", "fastingglucose": "fbg", "totalcholesterol": "tc", "hdlcholesterol": "hdl",
	"ldlcholesterol": "ldl", "triglyceride": "tg", "hemoglobin": "hb", "ast": "ast", "alt": "alt", "ygtp": "ggt",
	"serumcreatinine": "cr", "creatinine": "cr", "gfr": "gfr", "urinaryprotein": "uprot", "urineprotein": "uprot",
	"sight": "sight", "hearing": "hearing", "tbchestdisease": "chest", "chestdisease": "chest", "judgement": "judge",
}
BP = re.compile(r"^\s*(\d{2,3})\s*/\s*(\d{2,3})\s*$")

S_BASE = [
	("기준선 검진 있음", "등록 전 24개월~등록일 사이에 유효한 항목이 1개 이상 있는 검진이 있음"),
	("범위 밖 검진만 있음", "유효한 검진은 있으나 기준선 범위(등록 전 24개월~등록일) 안에는 없음"),
	("검진 기록 없음", "자료 기준일까지 유효한 검진 항목이 없음"),
]
S_FU = [
	("추적 검진 있음", "기준선 검진이 있고, 등록 후 29~365일에 유효한 항목이 1개 이상 있는 검진이 있음"),
	("추적 대기", "기준선 검진이 있고, 추적 검진은 아직 없으며 등록 후 365일이 자료 기준일 이후"),
	("추적 창 지남", "기준선 검진이 있으나 등록 후 365일 안에 추적 검진이 없음"),
	("기준선 없음", "기준선 검진이 없어 변화 분석 대상이 아님"),
]


def args():
	ap = argparse.ArgumentParser(description="Build the study 02 all-item usable-user workbook")
	ap.add_argument("--data-dir", type=Path, default=DATA, help="folder with checkup_events_all.csv")
	ap.add_argument("--common-data-dir", type=Path, default=COMMON_DATA, help="folder with users.csv and login.csv")
	ap.add_argument("--cutoff", type=pd.Timestamp, default=END, help="data cutoff date (YYYY-MM-DD)")
	ap.add_argument("--extract-date", default="2026-11-20", help="extraction date shown in the workbook")
	ap.add_argument("--tag", default="20261120", help="date tag in the output file name")
	return ap.parse_args()


def is_num(v):
	try:
		return np.isfinite(float(v))
	except (TypeError, ValueError):
		return False


def load_items(data_dir: Path, end: pd.Timestamp):
	"""Long table user x exam date x item with the validity of the latest inserted entry, plus ambiguous ties."""
	E = pd.read_csv(data_dir / "checkup_events_all.csv", dtype=str, keep_default_na=False)
	E = E[E.measured_dt.str.match(r"^\d{4}-\d{2}-\d{2}$", na=False)].copy()
	E["d"] = pd.to_datetime(E.measured_dt, errors="coerce")
	E = E[E.d.notna() & (E.d <= end)]
	for c in ["health_sn", "elem_no", "det_no"]:
		E[c] = pd.to_numeric(E[c], errors="coerce")
	rows = []
	for r in E.itertuples():
		key = (r.ins_ts, r.health_sn, r.elem_no, r.det_no)
		v = r.value.strip()
		# v_cmp is the value compared when counting ambiguous ties: numbers as floats (so 100 and 100.0 agree), each
		# blood-pressure component separately, categorical labels as text, invalid entries as their raw text
		if r.field_nm == "bloodpressure":
			m = BP.match(v)
			s_, d_ = (float(m.group(1)), float(m.group(2))) if m else ("raw:" + v, "raw:" + v)
			rows += [(r.user_id, r.d, key, "sbp", bool(m), s_), (r.user_id, r.d, key, "dbp", bool(m), d_)]
			continue
		item = FIELD.get(r.field_nm)
		if item is None:
			continue
		if KIND[item] == "num":
			ok = is_num(v)
			v_cmp = float(v) if ok else "raw:" + v
		else:
			ok = v != ""
			v_cmp = v
		rows.append((r.user_id, r.d, key, item, ok, v_cmp))
	L = pd.DataFrame(rows, columns=["user_id", "d", "ins_key", "item", "ok", "v_cmp"])
	L["d"] = pd.to_datetime(L["d"])
	L["ok"] = L["ok"].astype(bool)  # fixed dtype even when no row is usable
	if len(L):
		latest = L.groupby(["user_id", "d", "item"]).ins_key.transform("max")
		top = L[L.ins_key == latest]
		ties = int((top.groupby(["user_id", "d", "item"]).v_cmp.nunique() > 1).sum())
		L = L.sort_values("ins_key", kind="mergesort").drop_duplicates(["user_id", "d", "item"], keep="last")
	else:
		ties = 0
	return L.loc[L["ok"], ["user_id", "d", "item"]], ties


def main():
	a = args()
	end = a.cutoff
	C = load_common_cohort(a.common_data_dir, end)
	L, ties = load_items(a.data_dir, end)
	L = L[L.user_id.isin(C.index)].copy()
	L["k"] = (L.d - L.user_id.map(C.d0)).dt.days
	B = L[L.k.between(BASE_KMIN, BASE_KMAX)]
	F = L[L.k.between(FU_KMIN, FU_KMAX)]
	bi = B.groupby(["user_id", "item"]).d.max().unstack()
	fi = F.groupby(["user_id", "item"]).d.min().unstack()
	T = pd.DataFrame(index=C.index)
	T["사이트"] = C.site
	T["성별"] = C.sex.map({"F": "여", "M": "남"})
	T["나이"] = pd.to_numeric(C.age, errors="coerce")
	T["등록일"] = C.d0
	any_exam = set(L.user_id)
	has_b = T.index.isin(bi.index)
	T["기준선_상태"] = np.where(has_b, "기준선 검진 있음", np.where(T.index.isin(list(any_exam)), "범위 밖 검진만 있음", "검진 기록 없음"))
	T["기준선_검진일"] = B.groupby("user_id").d.max()
	T["기준선_등록후일"] = (T.기준선_검진일 - T.등록일).dt.days
	T["기준선_항목수"] = B.groupby("user_id").item.nunique()
	T["추적창_종료일"] = T.등록일 + D(days=FU_KMAX)
	has_f = T.index.isin(fi.index)
	T["추적_상태"] = np.where(~has_b, "기준선 없음", np.where(has_f, "추적 검진 있음",
								np.where(T.추적창_종료일 > end, "추적 대기", "추적 창 지남")))
	T["추적_검진일"] = F.groupby("user_id").d.min()
	T.loc[~has_b, "추적_검진일"] = pd.NaT  # follow-up only matters with a baseline
	for key, name, _ in ITEMS:
		T[f"기준선_{name}"] = bi[key] if key in bi.columns else pd.NaT
	for key, name, _ in ITEMS:
		col = fi[key] if key in fi.columns else pd.Series(dtype="datetime64[ns]")
		T[f"추적_{name}"] = col
		T.loc[~has_b, f"추적_{name}"] = pd.NaT
	T[IRS_OVERLAP_COL] = overlap_flag(T.index, irs_comparison_users())
	T = T.sort_values(["사이트", "등록일"])
	T.index.name = "user_id"
	T = T.reset_index()
	for c in ["나이", "기준선_등록후일", "기준선_항목수"]:
		T[c] = pd.to_numeric(T[c], errors="coerce").astype("Int64").astype(object).where(T[c].notna(), None)
	item_names = ", ".join(n for _, n, _ in ITEMS)
	meta = [
		("연구", "02 앱 참여도와 건강검진 지표 (전 항목, 단면 분석과 추적 검진 확보 현황)"),
		("대상", f"공통 코호트 {len(T)}명 (사이트 연결, 운영자·테스트 제외, 등록 후 28일 경과·그 안에 탈퇴 없음)"),
		("자료 기준일", f"{end.date()} (추출 {a.extract_date}, 조회 전용, 전 항목 추출 3판)"),
		("검진 원천", "승인 원천만 사용: discovery.disc_medical_user_info → disc_health_user_info.health_info_data, 검진일 = measuredDt. 현장 측정·IRS 입력값·user_checkup_log는 쓰지 않음"),
		("항목", f"{item_names}. 두 가지 이름으로 기록된 항목은 하나로 합침. 골다공증·요소질소·적혈구용적률·혈소판은 인원이 적어 쓰지 않음"),
		("기준선", "항목별로 등록 전 24개월~등록일 사이 가장 최근의 유효한 검진일"),
		("추적", "항목별로 등록 후 29~365일 사이 첫 유효한 검진일(나중의 변화 분석용, 기준선이 있는 사용자만)"),
		("중복 입력", f"같은 사용자·검진일·항목은 가장 늦게 입력된 값을 씀(ins_ts, health_sn, elem_no, det_no 순). 그 값이 비었거나 잘못되면 그 항목은 없는 것으로 봄. 가장 늦은 입력이 같은데 값이 다른 경우: {ties}건"),
		("값을 넣지 않은 이유", "단면 분석에서 검진 결과는 노출, 앱 참여도는 결과. 분석 계획 확정 전에 결과를 보지 않기 위해 날짜·개수·상태만 적음"),
		("03 겹침", f"'{IRS_OVERLAP_COL}' = 03 연구 비교 대상에도 들어가는 사용자. 투고 시 표본 겹침을 밝힘"),
		("만든 방법", "retrospective_study/02_checkup_metrics/src/build_all_item_users.py (저장된 추출 파일만 사용)"),
	]
	dates = ["등록일", "기준선_검진일", "추적창_종료일", "추적_검진일"] + [f"{w}_{n}" for w in ["기준선", "추적"] for _, n, _ in ITEMS]
	OUT.mkdir(exist_ok=True)
	path = OUT / f"SiBC_02_건강검진_전항목_사용가능사용자_{a.tag}.xlsx"
	write_workbook(path, "SiBC 02 건강검진 지표 연구: 전 항목 사용 가능 사용자", meta, [("기준선_상태", S_BASE), ("추적_상태", S_FU)],
				   T, date_cols=dates)
	print(path)
	print("기준선_상태", T.groupby(["사이트", "기준선_상태"]).size().to_dict())
	print("추적_상태", T.groupby(["사이트", "추적_상태"]).size().to_dict())
	print("기준선 보유 by item", {n: int(T[f"기준선_{n}"].notna().sum()) for _, n, _ in ITEMS})
	print("두 시점 보유 by item", {n: int((T[f"기준선_{n}"].notna() & T[f"추적_{n}"].notna()).sum()) for _, n, _ in ITEMS})
	print("ambiguous ties:", ties, "| 03 overlap among baseline:", int(((T.기준선_상태 == "기준선 검진 있음") & (T[IRS_OVERLAP_COL] == "예")).sum()))


if __name__ == "__main__":
	main()
