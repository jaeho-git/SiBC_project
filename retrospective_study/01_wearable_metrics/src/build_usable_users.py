# -*- coding: utf-8 -*-
"""Study 01 (app engagement x wearable indicators): usable-user workbook for the common cohort.

Offline: reads only saved extracts (00_common/00_Data, 01_wearable_metrics/00_Data). Writes
01_wearable_metrics/01_Results/SiBC_01_웨어러블_사용가능사용자_<tag>.xlsx (user-level, never committed).
Defaults reproduce the 2026-11-19 list; for a refreshed extract pass --data-dir, --common-data-dir, --cutoff and --tag.

Indicators
- Steps (main): valid day = steps > 0. T0 = first valid step day, which must fall within registration -28..+56 days.
  Baseline = T0..T0+13 (>= 7 valid days). Follow-up = T0+84..T0+111 (>= 7 valid days). A follow-up window counts as
  closed only when T0+111 <= cutoff - 28 days (allowance for late device sync).
- Sleep (auxiliary): valid-day counts in the same baseline / follow-up windows.
- Site measurement (wearable data measured on Ulsan center devices): lifelog platform 20301103
  (blood pressure: device 20301301; weight: same platform). Baseline = first measurement within registration
  -90..+56 days; follow-up = first measurement >= 90 days after the baseline measurement, up to the cutoff.
Only availability is written (dates, day counts, status). Outcome values are not written, so no group difference is
looked at before the analysis plan is fixed.
"""
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
LAG = 28
T0_MIN, T0_MAX = -28, 56
BASE_LEN, BASE_MIN = 14, 7
FU_START, FU_LEN, FU_MIN = 84, 28, 7
SITE_PLAT, SITE_BP_DEV = 20301103, 20301301
SITE_KMIN, SITE_KMAX, SITE_GAP = -90, 56, 90
D = pd.Timedelta

S_STEP = [
	("사용 가능", "기준선 14일 중 7일 이상, 추적 28일(84~111일) 중 7일 이상 걸음 기록, 추적 창이 동기화 여유 28일까지 지남"),
	("추적 대기", "기준선은 충족, 추적 창이 아직 닫히지 않음. '걸음_확정가능일' 이후 다시 판정"),
	("추적 기록 부족", "기준선은 충족, 추적 창은 닫혔으나 추적 28일 중 기록이 7일 미만"),
	("기준선 수집 중", "첫 기록이 최근이라 기준선 14일 판정이 아직 확정되지 않음"),
	("기준선 기록 부족", "기준선 14일 중 기록이 7일 미만"),
	("첫 기록이 등록 28일 전보다 이전", "첫 걸음 기록이 등록일보다 28일 넘게 앞섬 (현재 기준에서 제외)"),
	("첫 기록이 등록 56일 이후", "등록 후 56일이 지나서 첫 걸음 기록이 생김 (현재 기준에서 제외)"),
	("걸음 기록 없음", "자료 기준일까지 걸음 기록이 없음"),
]
S_SITE = [
	("사용 가능", "기준선 측정(등록 -90~+56일)과 그 90일 이후 측정이 모두 있음"),
	("추적 대기", "기준선 측정은 있고, 기준선 후 90일이 아직 지나지 않음. '확정가능일' 이후 다시 판정"),
	("추적 측정 아직 없음", "기준선 후 90일이 지났지만 그 뒤 측정이 아직 없음 (이후 측정되면 사용 가능)"),
	("기준선 범위 밖 측정만 있음", "측정은 있으나 등록 -90~+56일 안에는 없음"),
	("측정 없음", "자료 기준일까지 현장 측정이 없음"),
]


def step_status(C, st, sl, END):
	rows = {}
	first = st.groupby("user_id").d.min()
	for u, c in C.iterrows():
		t0 = first.get(u)
		r = dict(걸음_첫기록일=t0)
		if t0 is None or pd.isna(t0):
			r["걸음_상태"] = "걸음 기록 없음"
			rows[u] = r
			continue
		k = int((t0 - c.d0).days)
		r["걸음_첫기록_등록후일"] = k
		if k < T0_MIN:
			r["걸음_상태"] = "첫 기록이 등록 28일 전보다 이전"
			rows[u] = r
			continue
		if k > T0_MAX:
			r["걸음_상태"] = "첫 기록이 등록 56일 이후"
			rows[u] = r
			continue
		s = st[st.user_id == u]
		kt = (s.d - t0).dt.days
		nb = int(((kt >= 0) & (kt < BASE_LEN)).sum())
		nf = int(((kt >= FU_START) & (kt < FU_START + FU_LEN)).sum())
		q = sl[sl.user_id == u]
		qt = (q.d - t0).dt.days
		fu_end = t0 + D(days=FU_START + FU_LEN - 1)
		r.update(걸음_기준선_유효일=nb, 걸음_추적시작일=t0 + D(days=FU_START), 걸음_추적종료일=fu_end,
				 걸음_확정가능일=fu_end + D(days=LAG), 걸음_추적_유효일=nf,
				 수면_기준선_유효일=int(((qt >= 0) & (qt < BASE_LEN)).sum()),
				 수면_추적_유효일=int(((qt >= FU_START) & (qt < FU_START + FU_LEN)).sum()))
		closed = fu_end <= END - D(days=LAG)
		base_closed = t0 + D(days=BASE_LEN - 1) <= END - D(days=LAG)
		if nb < BASE_MIN:
			r["걸음_상태"] = "기준선 기록 부족" if base_closed else "기준선 수집 중"
		elif not closed:
			r["걸음_상태"] = "추적 대기"
		else:
			r["걸음_상태"] = "사용 가능" if nf >= FU_MIN else "추적 기록 부족"
		if not closed:
			r["걸음_추적_유효일"] = None  # window still open: the count is not final
			r["수면_추적_유효일"] = None
		rows[u] = r
	return pd.DataFrame.from_dict(rows, orient="index")


def site_status(C, m, prefix, END):
	x = m[m.user_id.isin(C.index) & (m.d <= END)].copy()
	x["k"] = (x.d - x.user_id.map(C.d0)).dt.days
	out = {}
	for u in C.index:
		g = x[x.user_id == u].sort_values("d")
		r = {}
		if g.empty:
			r[f"{prefix}_상태"] = "측정 없음"
			out[u] = r
			continue
		r[f"{prefix}_측정일수"] = int(g.d.nunique())
		b = g[g.k.between(SITE_KMIN, SITE_KMAX)]
		if b.empty:
			r[f"{prefix}_상태"] = "기준선 범위 밖 측정만 있음"
			out[u] = r
			continue
		db = b.d.iloc[0]
		r[f"{prefix}_기준선일"] = db
		r[f"{prefix}_기준선_등록후일"] = int(b.k.iloc[0])
		r[f"{prefix}_확정가능일"] = db + D(days=SITE_GAP)
		f = g[(g.d - db).dt.days >= SITE_GAP]
		if len(f):
			r[f"{prefix}_추적일"] = f.d.iloc[0]
			r[f"{prefix}_간격일"] = int((f.d.iloc[0] - db).days)
			r[f"{prefix}_상태"] = "사용 가능"
		else:
			r[f"{prefix}_상태"] = "추적 대기" if db + D(days=SITE_GAP) > END else "추적 측정 아직 없음"
		out[u] = r
	return pd.DataFrame.from_dict(out, orient="index")


def main():
	a = run_args(DATA, "Build the study 01 usable-user workbook")
	END = a.cutoff
	C = load_common_cohort(a.common_data_dir, END)
	st = pd.read_csv(a.data_dir / "steps.csv", parse_dates=["d"])
	st = st[st.user_id.isin(C.index) & (st.steps > 0) & (st.d <= END)]
	sl = pd.read_csv(a.data_dir / "sleep.csv", parse_dates=["d"])
	sl = sl[sl.user_id.isin(C.index) & (sl.mins > 0) & (sl.d <= END)]
	bp = pd.read_csv(a.data_dir / "bp.csv", parse_dates=["d"])
	body = pd.read_csv(a.data_dir / "body.csv", parse_dates=["d"])
	site_bp = bp[(bp.plat == SITE_PLAT) & (bp.dev == SITE_BP_DEV)]
	site_wt = body[(body.plat == SITE_PLAT) & body.weight.notna()]
	A = step_status(C, st, sl, END)
	B = site_status(C, site_bp, "현장혈압", END)
	W = site_status(C, site_wt, "현장체중", END)
	T = pd.DataFrame(index=C.index)
	T["사이트"] = C.site
	T["성별"] = C.sex.map({"F": "여", "M": "남"})
	T["나이"] = pd.to_numeric(C.age, errors="coerce")
	T["등록일"] = C.d0
	T = T.join(A).join(B).join(W)
	T[IRS_OVERLAP_COL] = overlap_flag(T.index, irs_comparison_users())
	order = ["사이트", "성별", "나이", "등록일", "걸음_상태", "걸음_첫기록일", "걸음_첫기록_등록후일", "걸음_기준선_유효일",
			 "걸음_추적시작일", "걸음_추적종료일", "걸음_확정가능일", "걸음_추적_유효일", "수면_기준선_유효일", "수면_추적_유효일",
			 "현장혈압_상태", "현장혈압_측정일수", "현장혈압_기준선일", "현장혈압_기준선_등록후일", "현장혈압_확정가능일", "현장혈압_추적일", "현장혈압_간격일",
			 "현장체중_상태", "현장체중_측정일수", "현장체중_기준선일", "현장체중_기준선_등록후일", "현장체중_확정가능일", "현장체중_추적일", "현장체중_간격일",
			 IRS_OVERLAP_COL]
	T = T.reindex(columns=order).sort_values(["사이트", "등록일"])
	T.index.name = "user_id"
	T = T.reset_index()
	for c in ["나이", "걸음_첫기록_등록후일", "걸음_기준선_유효일", "걸음_추적_유효일", "수면_기준선_유효일", "수면_추적_유효일",
			  "현장혈압_측정일수", "현장혈압_기준선_등록후일", "현장혈압_간격일", "현장체중_측정일수", "현장체중_기준선_등록후일", "현장체중_간격일"]:
		T[c] = T[c].astype("Int64").astype(object).where(T[c].notna(), None)
	dates = [c for c in T.columns if c.endswith("일") and ("기록일" in c or "시작일" in c or "종료일" in c or "가능일" in c or c.endswith("기준선일") or c.endswith("추적일") or c == "등록일")]
	meta = [
		("연구", "01 앱 참여도와 웨어러블 지표 (걸음·수면 + 현장 측정)"),
		("대상", f"공통 코호트 {len(T)}명 (사이트 연결, 운영자·테스트 제외, 등록 후 28일 경과·그 안에 탈퇴 없음)"),
		("자료 기준일", f"{END.date()} (추출 {a.extract_date}, 조회 전용)"),
		("걸음 기준", "시간 0 = 첫 걸음 기록일(등록 -28~+56일). 기준선 0~13일 중 7일 이상, 추적 84~111일 중 7일 이상. 추적 창 종료 후 28일(동기화 여유)이 지나야 확정"),
		("수면", "걸음과 같은 창의 유효일 수(보조 지표). 추적 창이 닫히기 전에는 비워 둠"),
		("현장 측정", "울산 거점 기기(lifelog 플랫폼 20301103; 혈압은 기기 20301301). 기준선 = 등록 -90~+56일 첫 측정, 추적 = 기준선 90일 이후 첫 측정. 제주는 현장 기기가 없음"),
		("값을 넣지 않은 이유", "분석 계획 확정 전에 집단 간 결과 차이를 보지 않기 위해 날짜·일수·상태만 적음"),
		("03 겹침", f"'{IRS_OVERLAP_COL}' = 03 연구 비교 대상에도 들어가는 사용자. 투고 시 표본 겹침을 밝힘. 03 결과 파일이 없으면 '확인 불가'"),
		("만든 방법", "retrospective_study/01_wearable_metrics/src/build_usable_users.py (저장된 추출 파일만 사용)"),
	]
	OUT.mkdir(exist_ok=True)
	path = OUT / f"SiBC_01_웨어러블_사용가능사용자_{a.tag}.xlsx"
	write_workbook(path, "SiBC 01 웨어러블 지표 연구: 사용 가능 사용자", meta,
				   [("걸음_상태", S_STEP), ("현장혈압_상태", S_SITE), ("현장체중_상태", S_SITE)], T, date_cols=dates)
	print(path)
	for c in ["걸음_상태", "현장혈압_상태", "현장체중_상태"]:
		print(c, T.groupby(["사이트", c]).size().to_dict())
	print("03 overlap among steps usable:", int(((T.걸음_상태 == "사용 가능") & (T[IRS_OVERLAP_COL] == "예")).sum()))


if __name__ == "__main__":
	main()
