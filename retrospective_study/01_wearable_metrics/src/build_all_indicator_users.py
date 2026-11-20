# -*- coding: utf-8 -*-
"""Study 01, all wearable indicators: usable-user workbook on the analysis-now timeline.

Offline: reads saved extracts (00_common/00_Data, 01_wearable_metrics/00_Data/extract_20261120). Writes
01_wearable_metrics/01_Results/SiBC_01_웨어러블_전지표_사용가능사용자_<tag>.xlsx (user-level, never committed).
The 2026-11-19 steps-only list stays reproducible with build_usable_users.py; this script does not replace it.

Timeline (one per user, anchored on wearable linkage)
- T0 = first valid step day, on or after registration - 30 days (no upper limit).
- Baseline = T0..T0+13. Exposure = 28 days from the later of (baseline end + 1, registration + 1).
- Follow-up = the 28 days right after the exposure window. It counts as closed only when its last day is at least
  28 days before the cutoff (allowance for late device sync).

Who is in the study (decided before the exposure window, never from follow-up data)
- Watch day = a day with both a step record (> 0) and a heart-rate record. Cohort member = at least --min-days watch
  days in the baseline window.
- Wear day = a day with a step or a heart-rate record. A cohort member whose closed follow-up window has fewer than
  --min-days wear days stays in the cohort with a missing outcome ("결과 결측"); they are not dropped.
Indicators (availability only; values are computed later on wear days)
- Steps, heart rate: at least --min-days days with that record in the baseline and in the follow-up window.
- Activity: sessions per wear day, a wear day without a session counts as 0, so it follows the wear-day rule.
- Sleep, SpO2, calories (optional): at least --min-days record days in each window.
- Weight, body composition, blood pressure, grip strength: a measurement in the 90 days before the exposure window and
  a measurement on or after the follow-up start.
- Supplementary steps group (any device, phone included): at least --min-days step days in each window.
Only availability is written (dates, day counts, status), never indicator values.
Defaults are a fixed combination on purpose: the official common cohort (00_common/00_Data, cutoff 2026-11-17) with the
2026-11-20 indicator extracts cut at the same cutoff. For another cutoff pass --data-dir, --common-data-dir, --cutoff
and --tag together.
"""
import argparse
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
T0_MIN, BASE_LEN, EXPO_LEN, FU_LEN, LAG, POINT_BACK = -30, 14, 28, 28, 28, 90
DAILY = ["걸음", "심박", "활동", "수면", "산소포화도", "칼로리"]
POINT = ["체중", "체성분", "혈압", "악력"]

S_COHORT = [
	("대상자, 결과 확보", "기준선 14일 중 워치 착용일(걸음과 심박이 모두 기록된 날)이 기준 이상이고, 닫힌 추적 28일 중 착용일(걸음 또는 심박 기록)이 기준 이상"),
	("대상자, 추적 대기", "기준선은 충족, 추적 창이 아직 닫히지 않음"),
	("대상자, 결과 결측", "기준선은 충족, 추적 창은 닫혔으나 착용일이 기준 미만. 대상자에서 빼지 않고 결과 결측으로 둠"),
	("기준선 수집 중", "기준선 창이 아직 닫히지 않음"),
	("기준선 착용 부족", "기준선 14일 중 워치 착용일이 기준 미만(휴대폰만 연동한 사용자 포함)"),
	("시간 0 없음", "걸음 기록이 없어 시간 0을 정할 수 없음"),
	("시간 0 범위 밖", "첫 걸음 기록이 등록 30일 전보다 이전"),
]
S_DAILY = [
	("사용 가능", "기준선·추적 창에 각각 기준 일수 이상 기록(활동은 착용일 기준), 추적 창이 동기화 여유 28일까지 지남"),
	("추적 대기", "기준선은 충족, 추적 창이 아직 닫히지 않음"),
	("추적 부족", "기준선은 충족, 추적 창은 닫혔으나 기록 일수가 기준 미만"),
	("기준선 수집 중", "기준선 창이 아직 닫히지 않음"),
	("기준선 부족", "기준선 14일의 기록 일수가 기준 미만"),
	("기록 없음", "자료 기준일까지 이 지표의 기록이 없음"),
	("시간 0 없음", "걸음 기록이 없어 시간 0을 정할 수 없음"),
	("시간 0 범위 밖", "첫 걸음 기록이 등록 30일 전보다 이전"),
]
S_POINT = [
	("사용 가능", "노출 창 전 90일 안의 측정과 추적 시작일 이후의 측정이 모두 있음"),
	("추적 대기", "기준선 측정은 있고, 추적 시작일이 자료 기준일 이후"),
	("추적 측정 아직 없음", "기준선 측정은 있으나 추적 시작일 이후 측정이 아직 없음"),
	("기준선 측정 없음", "측정은 있으나 노출 창 전 90일 안에는 없음"),
	("측정 없음", "자료 기준일까지 측정이 없음"),
	("시간 0 없음", "걸음 기록이 없어 시간 0을 정할 수 없음"),
	("시간 0 범위 밖", "첫 걸음 기록이 등록 30일 전보다 이전"),
]


def args():
	ap = argparse.ArgumentParser(description="Build the study 01 all-indicator usable-user workbook")
	ap.add_argument("--data-dir", type=Path, default=DATA, help="folder with the 01 indicator extracts")
	ap.add_argument("--common-data-dir", type=Path, default=COMMON_DATA, help="folder with users.csv and login.csv")
	ap.add_argument("--cutoff", type=pd.Timestamp, default=END, help="data cutoff date (YYYY-MM-DD)")
	ap.add_argument("--extract-date", default="2026-11-20", help="extraction date shown in the workbook")
	ap.add_argument("--tag", default="20261120", help="date tag in the output file name")
	ap.add_argument("--min-days", type=int, default=4, help="days needed in each window (watch, wear and record days)")
	a = ap.parse_args()
	if not 1 <= a.min_days <= BASE_LEN:
		ap.error(f"--min-days must be between 1 and {BASE_LEN}")
	return a


def load(a, C, end):
	def rd(name):
		t = pd.read_csv(a.data_dir / f"{name}.csv", parse_dates=["d"])
		return t[t.user_id.isin(C.index) & (t.d <= end)]
	st, sl, ac, hr, ox, ca = (rd(n) for n in ["steps", "sleep", "activity", "heartrate_days", "oxygen_saturation", "calories"])
	body, bf, bp, gr = (rd(n) for n in ["body", "bodyfat", "bp", "grip_strength"])
	src = {
		"걸음": st[st.steps > 0],
		"심박": hr,
		"활동": ac,
		"수면": sl[sl.mins > 0],
		"산소포화도": ox,
		"칼로리": ca[ca.total_kcal.fillna(0) + ca.active_kcal.fillna(0) > 0],
		"체중": body[body.weight.notna()],
		"체성분": bf[bf.fat_pct.notna() | bf.muscle_mass.notna() | bf.fat_mass.notna()],
		"혈압": bp[bp.sbp.notna()],
		"악력": gr[gr.grip.notna()],
	}
	return {k: t.groupby("user_id").d.apply(lambda s: np.sort(s.unique()).astype("datetime64[ns]")) for k, t in src.items()}


EMPTY = np.array([], dtype="datetime64[ns]")


def n_between(arr, a, b):
	return int(((arr >= np.datetime64(a)) & (arr <= np.datetime64(b))).sum())


def daily_status(nb, nf, has_any, need, base_closed, closed):
	if not has_any:
		return "기록 없음"
	if nb < need:
		return "기준선 부족" if base_closed else "기준선 수집 중"
	if not closed:
		return "추적 대기"
	return "사용 가능" if nf >= need else "추적 부족"


def build(C, days, end, need):
	rows = {}
	for u, c in C.iterrows():
		r = {}
		arr = {k: days[k].get(u, EMPTY) for k in DAILY + POINT}
		st = arr["걸음"]
		if len(st) == 0 or (st[0] - np.datetime64(c.d0)) / np.timedelta64(1, "D") < T0_MIN:
			lab = "시간 0 없음" if len(st) == 0 else "시간 0 범위 밖"
			for k in DAILY + POINT:
				r[f"{k}_상태"] = lab
			r["대상자_상태"] = r["걸음_보조_상태"] = lab
			if len(st):
				r.update(시간0=pd.Timestamp(st[0]), 시간0_등록후일=int((pd.Timestamp(st[0]) - c.d0).days))
			rows[u] = r
			continue
		t0 = pd.Timestamp(st[0])
		be = t0 + D(days=BASE_LEN - 1)
		L = max(be + D(days=1), c.d0 + D(days=1))
		fa = L + D(days=EXPO_LEN)
		fb = fa + D(days=FU_LEN - 1)
		closed = fb <= end - D(days=LAG)
		base_closed = be <= end - D(days=LAG)
		r.update(시간0=t0, 시간0_등록후일=int((t0 - c.d0).days), 기준선_종료일=be, 노출_시작일=L,
				 노출_종료일=L + D(days=EXPO_LEN - 1), 추적_시작일=fa, 추적_종료일=fb, 확정가능일=fb + D(days=LAG))
		watch = np.intersect1d(st, arr["심박"])
		wear = np.union1d(st, arr["심박"])
		nwb, nwf = n_between(watch, t0, be), n_between(wear, fa, fb)
		r["기준선_워치착용일"] = nwb
		r["추적_착용일"] = nwf if closed else None
		if nwb < need:
			r["대상자_상태"] = "기준선 착용 부족" if base_closed else "기준선 수집 중"
		elif not closed:
			r["대상자_상태"] = "대상자, 추적 대기"
		else:
			r["대상자_상태"] = "대상자, 결과 확보" if nwf >= need else "대상자, 결과 결측"
		for k in DAILY:
			a = wear if k == "활동" else arr[k]  # activity: sessions per wear day, a day without a session counts as 0
			has_any = len(arr[k]) > 0 if k != "활동" else len(wear) > 0
			nb, nf = n_between(a, t0, be), n_between(a, fa, fb)
			r[f"{k}_기준선_일수"] = nb
			r[f"{k}_추적_일수"] = nf if closed else None  # window still open: the count is not final
			r[f"{k}_상태"] = daily_status(nb, nf, has_any, need, base_closed, closed)
		r["걸음_보조_상태"] = r["걸음_상태"]  # steps from any device (phone included), regardless of watch wearing
		for k in POINT:
			a = arr[k]
			if len(a) == 0:
				s = "측정 없음"
			else:
				b = a[(a >= np.datetime64(L - D(days=POINT_BACK))) & (a <= np.datetime64(L - D(days=1)))]
				f = a[a >= np.datetime64(fa)]
				if len(b) == 0:
					s = "기준선 측정 없음"
				else:
					r[f"{k}_기준선일"] = pd.Timestamp(b[-1])
					if len(f):
						r[f"{k}_추적일"] = pd.Timestamp(f[0])
						s = "사용 가능"
					else:
						s = "추적 대기" if fa > end else "추적 측정 아직 없음"
			r[f"{k}_상태"] = s
		rows[u] = r
	return pd.DataFrame.from_dict(rows, orient="index")


def main():
	a = args()
	end = a.cutoff
	C = load_common_cohort(a.common_data_dir, end)
	days = load(a, C, end)
	A = build(C, days, end, a.min_days)
	T = pd.DataFrame(index=C.index)
	T["사이트"] = C.site
	T["성별"] = C.sex.map({"F": "여", "M": "남"})
	T["나이"] = pd.to_numeric(C.age, errors="coerce")
	T["등록일"] = C.d0
	T = T.join(A)
	T[IRS_OVERLAP_COL] = overlap_flag(T.index, irs_comparison_users())
	order = ["사이트", "성별", "나이", "등록일", "대상자_상태", "기준선_워치착용일", "추적_착용일", "걸음_보조_상태", "시간0",
			 "시간0_등록후일", "기준선_종료일", "노출_시작일", "노출_종료일", "추적_시작일", "추적_종료일", "확정가능일"]
	for k in DAILY:
		order += [f"{k}_상태", f"{k}_기준선_일수", f"{k}_추적_일수"]
	for k in POINT:
		order += [f"{k}_상태", f"{k}_기준선일", f"{k}_추적일"]
	order.append(IRS_OVERLAP_COL)
	T = T.reindex(columns=order).sort_values(["사이트", "등록일"])
	T.index.name = "user_id"
	T = T.reset_index()
	ints = ["나이", "시간0_등록후일", "기준선_워치착용일", "추적_착용일"] + [f"{k}_{w}_일수" for k in DAILY for w in ["기준선", "추적"]]
	for c in ints:
		T[c] = T[c].astype("Int64").astype(object).where(T[c].notna(), None)
	dates = ["등록일", "시간0", "기준선_종료일", "노출_시작일", "노출_종료일", "추적_시작일", "추적_종료일", "확정가능일"] + \
			[f"{k}_{w}" for k in POINT for w in ["기준선일", "추적일"]]
	n = a.min_days
	meta = [
		("연구", "01 앱 참여도와 웨어러블 지표 (전 지표, 지금 분석 설계)"),
		("대상", f"공통 코호트 {len(T)}명 (사이트 연결, 운영자·테스트 제외, 등록 후 28일 경과·그 안에 탈퇴 없음)"),
		("자료 기준일", f"{end.date()} (추출 {a.extract_date}, 조회 전용)"),
		("시간 축", "시간 0 = 첫 걸음 기록일(등록 -30일 이후, 상한 없음). 기준선 0~13일, 노출 = 기준선 종료 다음 날과 등록 다음 날 중 늦은 날부터 28일, 추적 = 노출 직후 28일. 추적 창 종료 후 28일(동기화 여유)이 지나야 확정"),
		("대상자", f"기준선 14일 중 워치 착용일(걸음과 심박이 모두 기록된 날) {n}일 이상. 노출 전 정보로만 정하며, 추적 자료가 부족해도 대상자에서 빼지 않고 '결과 결측'으로 둠"),
		("결과 확보", f"닫힌 추적 28일 중 착용일(걸음 또는 심박 기록) {n}일 이상"),
		("지표별 판정", f"걸음·심박·수면·산소포화도·칼로리: 두 창에 각각 기록 {n}일 이상. 활동: 착용일 기준(운동이 없던 착용일은 0회). 체중·체성분·혈압·악력: 노출 창 전 90일 안 측정 + 추적 시작일 이후 측정"),
		("걸음 보조 분석", f"'걸음_보조_상태' = 워치 착용과 무관하게(휴대폰 연동 포함) 걸음 기록이 두 창에 각각 {n}일 이상"),
		("값을 넣지 않은 이유", "분석 계획 확정 전에 집단 간 결과 차이를 보지 않기 위해 날짜·일수·상태만 적음"),
		("03 겹침", f"'{IRS_OVERLAP_COL}' = 03 연구 비교 대상에도 들어가는 사용자. 투고 시 표본 겹침을 밝힘"),
		("만든 방법", "retrospective_study/01_wearable_metrics/src/build_all_indicator_users.py (저장된 추출 파일만 사용)"),
	]
	specs = [("대상자_상태", S_COHORT), ("걸음_보조_상태", S_DAILY)] + [(f"{k}_상태", S_DAILY) for k in DAILY] + \
			[(f"{k}_상태", S_POINT) for k in POINT]
	OUT.mkdir(exist_ok=True)
	path = OUT / f"SiBC_01_웨어러블_전지표_사용가능사용자_{a.tag}.xlsx"
	write_workbook(path, "SiBC 01 웨어러블 지표 연구: 전 지표 사용 가능 사용자", meta, specs, T, date_cols=dates)
	print(path)
	print("대상자_상태", T.groupby(["사이트", "대상자_상태"]).size().to_dict())
	cohort = T.대상자_상태 == "대상자, 결과 확보"
	print("결과 확보 대상자 중 지표별 사용 가능", {k: int((cohort & (T[f"{k}_상태"] == "사용 가능")).sum()) for k in DAILY + POINT})
	print("걸음 보조 분석 사용 가능:", int((T.걸음_보조_상태 == "사용 가능").sum()))
	print("03 overlap among 결과 확보:", int((cohort & (T[IRS_OVERLAP_COL] == "예")).sum()))


if __name__ == "__main__":
	main()
