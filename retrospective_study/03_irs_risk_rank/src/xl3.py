# -*- coding: utf-8 -*-
"""v4 workbook builder: comparison-set design (baseline = first complete IRS within 56 days). Usage: python xl3.py out.xlsx"""
import pandas as pd, numpy as np, sys, json
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as CL
from openpyxl.comments import Comment

OUT = sys.argv[1]
FONT = "맑은 고딕"
F_N = Font(name=FONT, size=10); F_B = Font(name=FONT, size=10, bold=True)
F_T = Font(name=FONT, size=14, bold=True); F_H2 = Font(name=FONT, size=11, bold=True)
F_IN = Font(name=FONT, size=10, color="0000FF", bold=True)
FILL_H = PatternFill("solid", fgColor="D9E1F2"); FILL_IN = PatternFill("solid", fgColor="FFFF00")
FILL_F = PatternFill("solid", fgColor="F2F2F2"); FILL_FX = PatternFill("solid", fgColor="E2EFDA")
THIN = Side(style="thin", color="BFBFBF"); WRAP = Alignment(wrap_text=True, vertical="top")

L = pd.read_pickle("L2.pkl"); M = pd.read_pickle("M2.pkl"); K = pd.read_pickle("K2.pkl"); REF = pd.read_pickle("REF.pkl"); DIS = pd.read_pickle("DIS.pkl")
VR = pd.read_pickle("VR.pkl"); MET = pd.read_pickle("MET.pkl"); CONF = pd.read_pickle("CONF.pkl"); REP = pd.read_pickle("REP.pkl"); REPR = pd.read_pickle("REPR.pkl")
ST = json.load(open("stats2.json"))
D2 = pd.read_pickle("D2.pkl"); BBu = set(pd.read_pickle("BB_final.pkl").user_id)
u = D2.reset_index().copy(); u["sex_k"] = u.sex.map({"M": "남", "F": "여"})
B0_ = pd.Timestamp("2026-07-01 10:00"); TS_ = pd.Timestamp("2026-07-01 15:00")
u["fu_type"] = np.where((u.t_f >= B0_) & (u.t_f < TS_), "7/1 일괄 산출(10~15시)", "개별 산출")
u["scale"] = np.where(u.model_f == "P0", "같은 모델(이전 모델, 환산 없음)", "7월 모델 기준(기준선 환산)")
u["model_b_k"] = u.model_b.map({"P0": "이전 모델(~7/1 09:59)"}); u["model_f_k"] = u.model_f.map({"P0": "이전 모델(~7/1 09:59)", "P1": "7월 모델(7/1 10:00~8/1)"})
u["geno_same_k"] = np.where(u.geno_same, "예", "아니오"); u["comparable"] = u.geno_same_k; u["sex_ok"] = np.where(u.sex == u.sex_f, "예", "아니오")
u["in_bridge"] = np.where(u.user_id.isin(BBu), "예", "아니오")
_X = pd.read_csv("irs_inputs.csv").set_index("seq")
def _med(s_):
    try: return json.loads(_X.med.get(s_) or "{}")
    except Exception: return {}
mb = pd.DataFrame([_med(s_) for s_ in u.seq_b]); mf = pd.DataFrame([_med(s_) for s_ in u.seq_f])
info = pd.read_csv("dis_info.csv").set_index("disease_id")
EXTRA_NM = {"cardiac_arrhythmia": "부정맥", "endometrial_cancer": "자궁내막암", "endometriosis": "자궁내막증", "polycystic_ovary_syndrome": "다낭성 난소 증후군"}
nm = lambda d: info.disease_nm.get(d, EXTRA_NM.get(d, d))
DIS = sorted(DIS, key=nm); DORD = {d: i for i, d in enumerate(DIS)}
SC = ["irs", "mrs", "lrs", "prs"]; SCN = {"irs": "IRS", "mrs": "MRS", "lrs": "LRS", "prs": "PRS"}
VAL = {"irs": "확률", "mrs": "확률", "lrs": "점수", "prs": "점수"}
SCK = {"irs": "통합", "mrs": "의학", "lrs": "생활습관", "prs": "유전"}
sexk = {"M": "남", "F": "여", "all": "전체"}
P4 = "0.0000"; R0 = "0"; DT = "yyyy-mm-dd hh:mm"; DD = "yyyy-mm-dd"; PC = "0.0%"

sid = dict(zip(u.user_id, u.sid))
L = L.copy(); L["sid"] = L.user_id.map(sid); L["dn"] = L.disease.map(nm); L["cat"] = L.disease.map(info.category_nm); L["sexk"] = L.sex.map(sexk)
L["dord"] = L.disease.map(DORD); L = L.sort_values(["sid", "dord"]).reset_index(drop=True)
LB = L.merge(u[["user_id", "t_b", "seq_b", "mode_b", "mode_f", "t_f", "seq_f", "fu_type", "scale"]], on="user_id", how="left")
NC = len(LB) + 1
wb = Workbook()

def nz(v):
    if v is None: return None
    if isinstance(v, (bool, np.bool_)): return "예" if v else "아니오"
    if isinstance(v, (float, np.floating)): return None if np.isnan(v) else float(v)
    if isinstance(v, (np.integer,)): return int(v)
    if isinstance(v, pd.Timestamp): return None if pd.isna(v) else v.to_pydatetime()
    if v is pd.NaT: return None
    if isinstance(v, str) and v == "": return None
    return v

def sheet(title, headers, rows, fmts=None, widths=None, notes=None, freeze="A2", filt=True, fx=()):
    ws = wb.create_sheet(title); ws.append(headers)
    for j, h in enumerate(headers, 1):
        c = ws.cell(1, j); c.font = F_B; c.fill = FILL_FX if h in fx else FILL_H
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center"); c.border = Border(bottom=THIN)
        if notes and h in notes: c.comment = Comment(notes[h], "분석")
    for r in rows: ws.append([nz(v) for v in r])
    n = ws.max_row
    for j, h in enumerate(headers, 1):
        f = (fmts or {}).get(h)
        for row in ws.iter_rows(min_row=2, max_row=n, min_col=j, max_col=j):
            for c in row:
                c.font = F_N
                if f: c.number_format = f
        ws.column_dimensions[CL(j)].width = (widths or {}).get(h, max(9, min(24, len(str(h)) * 1.5 + 2)))
    ws.row_dimensions[1].height = 48
    if freeze: ws.freeze_panes = freeze
    if filt: ws.auto_filter.ref = f"A1:{CL(len(headers))}{n}"
    return ws

W_ = "'설정'!$B$2"; SH = "'설정'!$B$3"; MG = "'설정'!$B$4"; TH = "'설정'!$B$5"
def bandf(ref): return f'IF({ref}="","",INT(({ref}-1+{SH})/{W_})+1)'
def nearf(ref):
    k = f"MOD({ref}-1+{SH},{W_})"
    return f'IF({ref}="","",IF(OR(AND({k}<{MG},{ref}-{k}-1>=1),AND({W_}-{k}<={MG},{ref}+{W_}-{k}<=100)),"예","아니오"))'

# ---- column maps decided up front (cross-sheet formulas need them) ----
KEYH = ["연구번호", "user_id", "성별", "질환코드", "질환명", "분류"]
PER = ["원순위", "기준선 환산순위", "재표집 하한", "재표집 상한", "추적 재부여순위", "기준선 구간", "추적 구간", "구간 이동", "기준선 최저 구간", "경계 근접", "재표집 구간 걸침",
       "환산 검증 일치율(성별)", "환산 검증 판정", "주 분석 적격", "제외 사유"]
H_C = KEYH + ["고유키", "비교 척도", "통합순위 비교 가능"]
for c in ["irs", "mrs", "lrs"]: H_C += [f"{SCN[c]} {p}" for p in PER]
H_C += ["PRS 기준선 환산순위", "PRS 추적 재부여순위", "PRS 기준선 구간"]
col = {h: CL(j) for j, h in enumerate(H_C, 1)}
H_U = ["연구번호", "user_id", "성별", "지역", "기준선 나이", "앱 등록일(첫 로그인)", "첫 IRS 산출일시(모든 산출)", "첫 IRS seq", "기준선 seq", "기준선 산출일시",
       "기준선-앱 등록(일)", "기준선 모드", "기준선 모델", "추적 seq", "추적 산출일시", "추적 모드", "추적 모델", "비교 척도", "추적 산출 구분",
       "산출 간격(일)", "180일 이상", "바뀐 검진 항목 수", "생활습관 설문 변경", "통합순위 비교 가능", "성별 일치(기준선=추적)", "연결 쌍 사용자(교차적합)",
       "기준선 전날까지 앱 활성일 수", "기준선 후 28일 앱 활성일 수(노출)", "앱 활성일 비율(28일)", "기준선~추적 앱 로그인 일수",
       "질환 행 수", "기대 질환 행 수", "행 수 확인",
       "IRS 분석 질환 수", "IRS 하락 질환 수", "IRS 하락 비율(주 결과)", "MRS 분석 질환 수", "MRS 하락 질환 수", "MRS 하락 비율", "LRS 분석 질환 수", "LRS 하락 질환 수", "LRS 하락 비율", "IRS 분석 질환 수(최저 구간 포함)", "IRS 하락 비율(최저 구간 포함, 민감도)"]
cu = {h: CL(j) for j, h in enumerate(H_U, 1)}
H_V = ["키", "질환코드", "질환명", "점수", "성별", "환산 방법", "검증 쌍 수", "검증 사용자 수", "같은 구간 일치 수", "환산 후 같은 구간 비율", "환산 전 같은 구간 비율",
       "판정", "환산 후 ±2순위 이내 비율", "환산 전 ±2순위 이내 비율", "Wilson 95% 하한", "Wilson 95% 상한", "사용자 재표집 95% 하한", "사용자 재표집 95% 상한",
       "재표집 통과 비율(성별 판정)", "재표집 통과 비율(합산 판정)", "카파(환산 전)", "카파(환산 후)", "가중 카파(환산 전)", "가중 카파(환산 후)", "낮은 구간으로 오분류", "높은 구간으로 오분류", "보류 순위표 검증 일치율"]
cv = {h: CL(j) for j, h in enumerate(H_V, 1)}
QV = "'질환별_환산검증'"; VS = "'검증_예측값'"; TC = "'통합비교'"

# ---------- 안내 (content at the end) ----------
ws0 = wb.active; ws0.title = "안내"

# ---------- 설정 ----------
ws1 = wb.create_sheet("설정"); ws1.append(["항목", "값", "설명"])
SET = [("구간 너비(순위)", 20, "위험 구간을 나누는 순위 폭. 20이면 1~20, 21~40, 41~60, 61~80, 81~100의 5개 구간. 10(10개 구간)이나 33.34(3개 구간)로 바꿀 수 있습니다. 바꾸면 통합비교·요약의 구간과 검증_예측값·질환별_환산검증의 일치율과 판정도 함께 다시 계산됩니다."),
       ("구간 경계 이동(순위)", 0, "구간 경계를 옮기는 값. 10이면 1~10, 11~30, 31~50 … 처럼 경계가 10순위씩 이동합니다."),
       ("경계 근접 기준(순위)", 2, "기준선 환산순위가 이 값 이하만 움직여도 다른 구간으로 넘어가는 위치이면 '경계 근접'으로 표시. 오차 한계가 아니라 민감도 분석용 표시입니다."),
       ("환산 검증 통과 기준(같은 구간 비율)", 0.95, "질환×점수마다 성별 각각의 '환산 후 같은 구간 비율'이 모두 이 값 이상이면 '통과'. 사전 지정한 관측 일치율 기준을 충족했다는 뜻이며 정확도 보증은 아닙니다.")]
for r in SET: ws1.append(list(r))
for j in range(1, 4): ws1.cell(1, j).font = F_B; ws1.cell(1, j).fill = FILL_H
for i in range(2, 6):
    ws1.cell(i, 1).font = F_N; ws1.cell(i, 3).font = F_N; ws1.cell(i, 3).alignment = WRAP; ws1.row_dimensions[i].height = 44
    c = ws1.cell(i, 2); c.font = F_IN; c.fill = FILL_IN
ws1["B5"].number_format = "0%"
ws1.append([]); ws1.append(["노란 칸(파란 글씨)만 바꾸십시오. 초록 머리글 열은 이 값을 참조하는 수식입니다. 질환별_환산검증의 신뢰구간·카파·재표집 통과 비율, 혼동행렬, 민감도_요약은 기본값(구간 너비 20, 이동 0)으로 계산한 고정값입니다."])
ws1.cell(7, 1).font = Font(name=FONT, size=10, italic=True)
ws1.column_dimensions["A"].width = 34; ws1.column_dimensions["B"].width = 10; ws1.column_dimensions["C"].width = 110

# ---------- 대상자 ----------
rows = []
def _cnt(c, i, extra=""):
    el = f"{TC}!${col[f'{SCN[c]} 주 분석 적격']}:${col[f'{SCN[c]} 주 분석 적격']},\"예\",{TC}!${col[f'{SCN[c]} 기준선 최저 구간']}:${col[f'{SCN[c]} 기준선 최저 구간']},\"아니오\""
    return f"COUNTIFS({TC}!$A:$A,{cu['연구번호']}{i},{el}{extra})"
for i, r in enumerate(u.itertuples(), start=2):
    g = lambda h: f"{cu[h]}{i}"
    row = [r.sid, r.user_id, r.sex_k, r.site, r.age_b, r.d0, r.first_t, r.first_seq, r.seq_b, r.t_b,
           f'=INT({g("기준선 산출일시")})-{g("앱 등록일(첫 로그인)")}', r.mode_b, r.model_b_k, r.seq_f, r.t_f, r.mode_f, r.model_f_k, r.scale, r.fu_type,
           f"=INT({g('추적 산출일시')})-INT({g('기준선 산출일시')})", f'=IF({g("산출 간격(일)")}>=180,"예","아니오")', r.n_core_changed, r.life_ch, r.comparable, r.sex_ok, r.in_bridge,
           r.act_pre, r.act28, f'={g("기준선 후 28일 앱 활성일 수(노출)")}/28', r.ldays,
           f"=COUNTIF({TC}!$A:$A,{g('연구번호')})", f'=IF({g("성별")}="여",32,33)', f'=IF({g("질환 행 수")}={g("기대 질환 행 수")},"일치","확인 필요")']
    for c in ["irs", "mrs", "lrs"]:
        n = SCN[c]; a = cu[f"{n} 분석 질환 수"]; b = cu[f"{n} 하락 질환 수"]
        row += ["=" + _cnt(c, i), "=" + _cnt(c, i, f',{TC}!${col[f"{n} 구간 이동"]}:${col[f"{n} 구간 이동"]},"하락"'), f'=IF({a}{i}=0,"",{b}{i}/{a}{i})']
    el2 = f"{TC}!$A:$A,{cu['연구번호']}{i},{TC}!${col['IRS 주 분석 적격']}:${col['IRS 주 분석 적격']},\"예\""
    a2 = cu["IRS 분석 질환 수(최저 구간 포함)"]
    row += [f"=COUNTIFS({el2})", f'=IF({a2}{i}=0,"",COUNTIFS({el2},{TC}!${col["IRS 구간 이동"]}:${col["IRS 구간 이동"]},"하락")/{a2}{i})']
    rows.append(row)
notes = {"연구번호": "기준선 산출일시 순으로 붙인 분석용 번호. 다른 시트와는 이 열(통합비교는 '고유키')로 연결하십시오.",
         "user_id": "서비스 내부 사용자 키. 외부로 반출할 때는 이 열을 지우고 연구번호만 남기십시오.",
         "첫 IRS 산출일시(모든 산출)": "유전체·실측 여부와 관계없는 첫 IRS 산출. 기준선(첫 완성 IRS)과 다를 수 있습니다.",
         "기준선 seq": "앱 등록 후 56일 이내의 첫 완성 IRS(유전체 포함 모드 1·4, 혈압·공복혈당이 정수인 실측 검진, 생활습관 응답 있음). 2026-07-01 10:00 이전 모델 산출. 같은 시각이면 seq가 작은 것.",
         "기준선-앱 등록(일)": "기준선 산출일 - 첫 로그인일(KST 날짜). 0~56일. 분석의 시간 0은 기준선 날짜입니다.",
         "추적 seq": "기준선 날짜로부터 90일 이후의 완성 IRS 가운데 유전체 입력 해시가 양쪽 모두 있고 같으며, 직접 측정 검진값 14개 중 하나 이상이 두 시점 모두 있고 다른 가장 이른 산출(2026-08-01까지).",
         "비교 척도": "같은 모델: 기준선·추적이 모두 이전 모델이라 환산 없이 서비스 순위를 비교. 7월 모델 기준: 기준선을 환산하고 추적은 순위기준표로 다시 매겨 비교.",
         "추적 산출 구분": "'7/1 일괄 산출(10~15시)'은 모델 교체 직후 일괄 재산출이지만, 이 대상자는 모두 검진값이 기준선과 다른 산출만 추적으로 씁니다.",
         "바뀐 검진 항목 수": "직접 측정 수치 14개(혈압 2, 공복혈당, 지질 3, 체중, 키, 허리둘레, 혈색소, 간 수치 3, 크레아티닌) 중 두 시점 모두 값이 있고 다른 항목 수(1 이상이 선정 조건). 값의 유무만 바뀐 경우는 세지 않습니다.",
         "통합순위 비교 가능": "기준선과 추적의 유전체 입력이 같으면 '예'(선정 조건이므로 모두 '예').",
         "연결 쌍 사용자(교차적합)": "환산 함수를 만든 연결 쌍에 이 사용자의 산출이 있으면 '예'. 이 사용자의 기준선은 그 사용자가 속한 검증 겹을 뺀 함수로 환산했습니다.",
         "산출 간격(일)": "추적 산출일 - 기준선 산출일(KST 날짜). 90일 이상이 선정 조건. 검진 측정일 간격이 아닙니다.",
         "기준선 전날까지 앱 활성일 수": "첫 로그인일부터 기준선 전날까지 로그인한 날 수(보정용 공변량). 기준선 당일은 넣지 않습니다.",
         "IRS 하락 비율(최저 구간 포함, 민감도)": "기준선이 가장 낮은 구간인 질환도 분모에 넣은 하락 비율(민감도 분석).",
         "기준선 후 28일 앱 활성일 수(노출)": "기준선 다음 날부터 28일 동안 로그인한 날 수(KST 날짜, 사용자×날짜 중복 제거). 03 연구의 노출(이 설계에서 시간 0은 기준선).",
         "기대 질환 행 수": "자료 구조상 기대값: 공통 30개 + 여성 질환 2개(여 32) 또는 남성 질환 3개(남 33).",
         "IRS 분석 질환 수": "통합비교에서 'IRS 주 분석 적격'이 '예'이고 기준선이 가장 낮은 구간이 아닌 질환 수(설정 시트 값에 따라 바뀜).",
         "IRS 하락 비율(주 결과)": "IRS 하락 질환 수 ÷ IRS 분석 질환 수. 사용자 단위 주 결과(낮은 위험 구간으로 이동한 질환의 비율)."}
FXU = {"기준선-앱 등록(일)", "산출 간격(일)", "180일 이상", "앱 활성일 비율(28일)", "질환 행 수", "기대 질환 행 수", "행 수 확인"} | {h for h in H_U if h.startswith(("IRS ", "MRS ", "LRS "))}
sheet("대상자", H_U, rows, fmts={"앱 등록일(첫 로그인)": DD, "첫 IRS 산출일시(모든 산출)": DT, "기준선 산출일시": DT, "추적 산출일시": DT, "산출 간격(일)": R0, "기준선-앱 등록(일)": R0,
      "앱 활성일 비율(28일)": PC, "IRS 하락 비율(주 결과)": PC, "IRS 하락 비율(최저 구간 포함, 민감도)": PC, "MRS 하락 비율": PC, "LRS 하락 비율": PC, "기준선 나이": "0"},
      widths={"user_id": 38, "연구번호": 9, "추적 산출 구분": 22, "비교 척도": 26, "기준선 모델": 18, "추적 모델": 20}, notes=notes, freeze="C2", fx=FXU)

# ---------- long sheets ----------
def keyrow(r): return [r.sid, r.user_id, r.sexk, r.disease, r.dn, r.cat]
LONGW = {"user_id": 38, "질환명": 16, "분류": 18}
H = KEYH + ["산출일시", "seq", "모드"] + sum([[f"{SCN[c]} {VAL[c]}", f"{SCN[c]} 순위"] for c in SC], [])
rows = [keyrow(r) + [r.t_b, r.seq_b, r.mode_b] + sum([[getattr(r, c + "_p_b"), getattr(r, c + "_r_b")] for c in SC], []) for r in LB.itertuples()]
f = {"산출일시": DT}; f.update({f"{SCN[c]} {VAL[c]}": P4 for c in SC}); f.update({f"{SCN[c]} 순위": R0 for c in SC})
notes = {f"{SCN[c]} 순위": f"{SCK[c]} 위험 순위(1~100, 클수록 위험이 높음). 서비스 표시값 그대로. 빈칸은 원자료의 '-'(미산출)." for c in SC}
notes.update({"LRS 점수": "LRS·PRS 값은 0 미만·1 초과가 있어 확률이 아닌 점수로 다룹니다.", "산출일시": "기준선: 앱 등록 후 56일 이내의 첫 완성 IRS(2026-07-01 10:00 이전 모델)."})
sheet("1차_기준선", H, rows, fmts=f, widths=LONGW, notes=notes, freeze="F2")

H = KEYH[:]
for c in SC: H += [f"{SCN[c]} 환산 {VAL[c]}", f"{SCN[c]} 기준선 환산순위", f"{SCN[c]} 순위표 위치", f"{SCN[c]} 인접 순위 하한", f"{SCN[c]} 인접 순위 상한",
                   f"{SCN[c]} 재표집 하한", f"{SCN[c]} 재표집 상한", f"{SCN[c]} 외삽", f"{SCN[c]} 환산 방법", f"{SCN[c]} 학습 쌍 수(성별)"]
rows = []
for r in LB.itertuples():
    row = keyrow(r)
    for c in SC:
        has = not pd.isna(getattr(r, c + "_r_c")); mt = getattr(r, c + "_meth")
        row += [getattr(r, c + "_p_c"), getattr(r, c + "_r_c"), getattr(r, c + "_loc_c"), getattr(r, c + "_lo_c"), getattr(r, c + "_hi_c"),
                getattr(r, c + "_bs_lo"), getattr(r, c + "_bs_hi"), (bool(getattr(r, c + "_extrap")) if has else None), mt,
                (getattr(r, c + "_npairs") if (mt and has) else None)]
    rows.append(row)
f = {}
for c in SC: f.update({f"{SCN[c]} 환산 {VAL[c]}": P4, **{f"{SCN[c]} {k}": R0 for k in ["기준선 환산순위", "인접 순위 하한", "인접 순위 상한", "재표집 하한", "재표집 상한", "학습 쌍 수(성별)"]}})
notes = {"IRS 기준선 환산순위": "기준선 값을 7월 모델 기준으로 바꾼 순위. 연결 쌍 사용자는 그 사용자가 속한 검증 겹을 뺀 환산 함수로 바꿨습니다(5겹 교차적합, 검증과 같은 겹 배정). 2차_추적의 '재부여순위'와 같은 순위기준표를 씁니다. 추적도 이전 모델인 사용자(비교 척도 '같은 모델')는 환산하지 않고 원래 순위를 그대로 둡니다.",
         "IRS 순위표 위치": "관측 구간 안: 순위기준표에서 같은 순위로 관측된 값 범위 안(순위 확정). 순위 사이 빈 구간: 서로 다른 두 순위 사이라 선형 보간 후 반올림(0.5는 올림). 실제 순위는 인접 순위 하한~상한 중 하나. 범위 밖: 관측 범위 밖이라 끝 순위로 고정.",
         "IRS 재표집 하한": "연결 쌍 사용자를 200회 재표집해 같은 교차적합 규칙으로 환산 함수를 다시 만들었을 때 기준선 환산순위의 2.5 백분위(상한은 97.5 백분위). 순위기준표를 고정한 함수 추정의 변동이며 예측구간이 아닙니다.",
         "IRS 외삽": "기준선 값이 실제로 적용한 환산 함수의 학습 쌍 범위 밖이면 '예'. 범위 밖은 끝점 차이만큼 평행 이동(끝점 고정 결과는 환산_민감도 시트).",
         "IRS 학습 쌍 수(성별)": "실제로 적용한 환산 함수(교차적합이면 겹을 뺀 함수)의 학습 쌍 수.",
         "IRS 환산 방법": "등위회귀 환산: 교체 전후 같은 입력 쌍으로 값 환산 후 순위표 적용. 값 동일: 교체 전후 값이 같아 순위표만 적용. IRS·MRS는 로짓 척도, LRS·PRS는 원척도."}
sheet("1차_환산", H, rows, fmts=f, widths={**LONGW, **{f"{SCN[c]} 환산 방법": 20 for c in SC}, **{f"{SCN[c]} 순위표 위치": 14 for c in SC}}, notes=notes, freeze="F2")

H = KEYH + ["산출일시", "seq", "모드", "추적 산출 구분"]
for c in SC: H += [f"{SCN[c]} {VAL[c]}", f"{SCN[c]} 서비스 순위", f"{SCN[c]} 재부여순위", f"{SCN[c]} 순위표 위치", f"{SCN[c]} 인접 순위 하한", f"{SCN[c]} 인접 순위 상한"]
rows = [keyrow(r) + [r.t_f, r.seq_f, r.mode_f, r.fu_type] + sum([[getattr(r, c + "_p_f"), getattr(r, c + "_r_f"), getattr(r, c + "_r_fs"), getattr(r, c + "_loc_f"),
        getattr(r, c + "_lo_f"), getattr(r, c + "_hi_f")] for c in SC], []) for r in LB.itertuples()]
f = {"산출일시": DT}
for c in SC: f.update({f"{SCN[c]} {VAL[c]}": P4, **{f"{SCN[c]} {k}": R0 for k in ["서비스 순위", "재부여순위", "인접 순위 하한", "인접 순위 상한"]}})
notes = {"IRS 재부여순위": f"값을 7월 모델 순위기준표(2026-07-01 15:00~08-01 산출 {ST['ref_calcs']:,}건)에 대입한 순위. 비교에는 이 열을 씁니다. 7월 모델 추적 중 일괄 산출이 아닌 것은 그 산출이 순위기준표에 들어 있어 서비스 순위와 같습니다. 추적이 이전 모델인 행은 서비스 순위를 그대로 씁니다.",
         "IRS 서비스 순위": "서비스 표시 순위 그대로. 추적이 이전 모델인 사용자는 이 값이 곧 비교에 쓰는 순위입니다."}
sheet("2차_추적", H, rows, fmts=f, widths={**LONGW, "추적 산출 구분": 22, **{f"{SCN[c]} 순위표 위치": 14 for c in SC}}, notes=notes, freeze="F2")

# ---------- 통합비교 ----------
rows = []
for i, r in enumerate(LB.itertuples(), start=2):
    row = keyrow(r) + [f'=A{i}&"|"&D{i}', r.scale, f"=IFERROR(INDEX('대상자'!${cu['통합순위 비교 가능']}:${cu['통합순위 비교 가능']},MATCH($A{i},'대상자'!$A:$A,0)),\"\")"]
    for c in ["irs", "mrs", "lrs"]:
        n = SCN[c]; g = lambda p: f"{col[f'{n} {p}']}{i}"
        cmp_cond = f'${col["통합순위 비교 가능"]}{i}<>"예"' if c == "irs" else "FALSE"
        row += [getattr(r, c + "_r_b"), getattr(r, c + "_r_c"), getattr(r, c + "_bs_lo"), getattr(r, c + "_bs_hi"), getattr(r, c + "_r_fs"),
                "=" + bandf(g("기준선 환산순위")), "=" + bandf(g("추적 재부여순위")),
                f'=IF(OR({g("기준선 구간")}="",{g("추적 구간")}=""),"",IF({g("추적 구간")}<{g("기준선 구간")},"하락",IF({g("추적 구간")}>{g("기준선 구간")},"상승","유지")))',
                f'=IF({g("기준선 구간")}="","",IF({g("기준선 구간")}=1,"예","아니오"))',
                "=" + nearf(g("기준선 환산순위")),
                f'=IF(OR({g("재표집 하한")}="",{g("재표집 상한")}=""),"",IF(INT(({g("재표집 하한")}-1+{SH})/{W_})<>INT(({g("재표집 상한")}-1+{SH})/{W_}),"예","아니오"))',
                f'=IFERROR(INDEX({QV}!${cv["환산 후 같은 구간 비율"]}:${cv["환산 후 같은 구간 비율"]},MATCH($D{i}&"|{n}|"&$C{i},{QV}!$A:$A,0)),"")',
                f'=IFERROR(INDEX({QV}!${cv["판정"]}:${cv["판정"]},MATCH($D{i}&"|{n}|전체",{QV}!$A:$A,0)),"검증 없음")',
                f'=IF(OR({g("기준선 환산순위")}="",{g("추적 재부여순위")}=""),"아니오",IF({cmp_cond},"아니오",IF({g("환산 검증 판정")}<>"통과","아니오","예")))',
                f'=IF({g("기준선 환산순위")}="",IF({g("원순위")}="","기준선 순위 없음","환산 안 함(유전체 없는 기준선)"),IF({g("추적 재부여순위")}="","추적 순위 없음",IF({cmp_cond},"유전체 입력 변경",IF({g("환산 검증 판정")}<>"통과","환산 검증 미달",""))))']
    row += [r.prs_r_c, r.prs_r_fs, "=" + bandf(f"{col['PRS 기준선 환산순위']}{i}")]
    rows.append(row)
f = {h: R0 for h in H_C if any(h.endswith(p) for p in ["원순위", "환산순위", "재표집 하한", "재표집 상한", "재부여순위", "구간"])}
f.update({h: PC for h in H_C if h.endswith("일치율(성별)")})
FXC = {h for h in H_C if any(h.endswith(p) for p in [" 구간", "이동", "근접", "걸침", "일치율(성별)", "판정", "적격", "사유"])} | {"고유키", "통합순위 비교 가능"}
FXC.discard("비교 척도")
notes = {"고유키": "연구번호|질환코드. 다른 분석 파일과는 행 위치가 아니라 이 키로 연결하십시오.",
         "비교 척도": "같은 모델(이전 모델, 환산 없음) 또는 7월 모델 기준(기준선 환산). 같은 모델 행은 환산 오차가 없습니다.",
         "통합순위 비교 가능": "대상자 시트 값(선정 조건상 모두 '예').",
         "IRS 기준선 최저 구간": "기준선 구간이 1(가장 낮은 위험 구간)이면 '예'. 더 낮아질 수 없으므로 하락 분석(요약·대상자의 하락 비율)에서는 뺍니다.",
         "IRS 원순위": "환산 전 서비스 표시 순위(1차_기준선). 참고용.",
         "IRS 기준선 환산순위": "7월 모델 기준으로 환산한 기준선 순위(1차_환산, 5겹 교차적합). 비교에는 이 값을 씁니다.",
         "IRS 추적 재부여순위": "추적 산출의 값을 순위기준표에 대입해 다시 매긴 순위(2차_추적).",
         "IRS 기준선 구간": "설정 시트의 구간 너비·경계 이동으로 계산. 1이 가장 낮은 위험 구간.",
         "IRS 구간 이동": "추적 구간이 기준선 구간보다 낮으면 하락(낮은 위험 구간으로 이동), 높으면 상승. 순위는 더하거나 빼지 않습니다.",
         "IRS 경계 근접": "기준선 환산순위가 설정 시트의 기준 이하만 움직여도 구간이 바뀌는 위치이면 '예'. 오차 한계가 아닌 민감도 분석용 표시입니다.",
         "IRS 재표집 구간 걸침": "환산 함수를 재표집으로 다시 추정했을 때 기준선 환산순위의 2.5~97.5 백분위가 서로 다른 구간에 걸치면 '예'. 순위기준표를 고정한 함수 추정의 변동이며 개별 환산 오차의 예측구간은 아닙니다. 민감도 분석용.",
         "IRS 환산 검증 일치율(성별)": "이 행의 질환·점수·성별의 환산 후 같은 구간 비율(질환별_환산검증).",
         "IRS 환산 검증 판정": "질환·점수 단위 판정. 모든 성별이 기준 이상이면 '통과'.",
         "IRS 주 분석 적격": "양 시점 순위가 있고, 통합순위 비교 가능이며, 환산 검증 판정이 '통과'인 질환이면 '예'. 같은 모델 행도 질환 목록을 맞추기 위해 같은 판정을 적용합니다.",
         "IRS 제외 사유": "주 분석 적격이 '아니오'인 이유."}
notes.update({f"{SCN[c]} 주 분석 적격": "양 시점 순위가 있고 환산 검증 판정이 '통과'이면 '예'. MRS·LRS는 유전체 입력 변경과 관계없이 비교합니다." for c in ["mrs", "lrs"]})
sheet("통합비교", H_C, rows, fmts=f, widths={**LONGW, "고유키": 26, "비교 척도": 24, **{f"{SCN[c]} 제외 사유": 22 for c in ["irs", "mrs", "lrs"]}}, notes=notes, freeze="J2", fx=FXC)

# ---------- 요약 ----------
H_S = ["질환코드", "질환명", "분류"]
for n in ["IRS", "MRS", "LRS"]: H_S += [f"{n} 주 분석 대상", f"{n} 하락", f"{n} 유지", f"{n} 상승", f"{n} 하락 비율", f"{n} 환산 검증 판정"]
H_S += ["IRS 전체 행 하락(기술)", "IRS 전체 행 비교 수(기술)"]
cs = {h: CL(j) for j, h in enumerate(H_S, 1)}
D_ = f"{TC}!$D$2:$D${NC}"
cc = lambda h: f"{TC}!${col[h]}$2:${col[h]}${NC}"
rows = []
for i, d in enumerate(DIS, start=2):
    row = [d, nm(d), info.category_nm.get(d)]
    for n in ["IRS", "MRS", "LRS"]:
        el = f'{cc(f"{n} 주 분석 적격")},"예",{cc(f"{n} 기준선 최저 구간")},"아니오"'
        cnt = lambda v: f'=COUNTIFS({D_},$A{i},{el},{cc(f"{n} 구간 이동")},"{v}")'
        a = cs[f"{n} 하락"]; b = cs[f"{n} 상승"]; t = cs[f"{n} 주 분석 대상"]
        row += [f"=SUM({a}{i}:{b}{i})", cnt("하락"), cnt("유지"), cnt("상승"), f'=IF({t}{i}=0,"",{a}{i}/{t}{i})',
                f'=IFERROR(INDEX({QV}!${cv["판정"]}:${cv["판정"]},MATCH($A{i}&"|{n}|전체",{QV}!$A:$A,0)),"검증 없음")']
    row += [f'=COUNTIFS({D_},$A{i},{cc("IRS 구간 이동")},"하락")', "=" + "+".join(f'COUNTIFS({D_},$A{i},{cc("IRS 구간 이동")},"{v}")' for v in ["하락", "유지", "상승"])]
    rows.append(row)
n_ = len(DIS) + 1; tot = ["합계(사용자×질환 행)", None, None]
for n in ["IRS", "MRS", "LRS"]:
    for k in ["주 분석 대상", "하락", "유지", "상승"]: tot.append(f"=SUM({cs[f'{n} {k}']}2:{cs[f'{n} {k}']}{n_})")
    t = cs[f"{n} 주 분석 대상"]; a = cs[f"{n} 하락"]; tot.append(f'=IF({t}{n_+1}=0,"",{a}{n_+1}/{t}{n_+1})')
    v = cs[f"{n} 환산 검증 판정"]; tot.append(f'=COUNTIF({v}2:{v}{n_},"통과")&"개 질환 통과"')
tot += [f"=SUM({cs['IRS 전체 행 하락(기술)']}2:{cs['IRS 전체 행 하락(기술)']}{n_})", f"=SUM({cs['IRS 전체 행 비교 수(기술)']}2:{cs['IRS 전체 행 비교 수(기술)']}{n_})"]
rows.append(tot)
notes = {"IRS 주 분석 대상": "통합비교의 'IRS 주 분석 적격'이 '예'이고 기준선이 가장 낮은 구간이 아닌 행 수(설정 시트 값에 따라 바뀜).",
         "IRS 하락 비율": "앱 참여도로 나누지 않은 전체 비율. 기술 통계이며 효과 추정이 아닙니다.",
         "IRS 전체 행 하락(기술)": "적격 여부와 관계없이 IRS 구간 이동이 계산된 모든 행. 주 분석에 쓰지 마십시오.",
         "IRS 환산 검증 판정": "모든 성별의 환산 후 같은 구간 비율이 기준 이상이면 '통과'."}
ws = sheet("요약", H_S, rows, fmts={f"{n} 하락 비율": PC for n in ["IRS", "MRS", "LRS"]}, widths={"질환코드": 24, "질환명": 14, "분류": 16}, notes=notes, freeze="C2", filt=False, fx=set(H_S[3:]))
for j in range(1, len(H_S) + 1): ws.cell(n_ + 1, j).font = F_B; ws.cell(n_ + 1, j).fill = FILL_F
UA = "'대상자'"; ws.append([])
ws.append(["사용자 단위 주 결과(대상자 시트)", "분석 사용자 수", "하락 비율 평균"]); r0_ = ws.max_row
for j in range(1, 4): ws.cell(r0_, j).font = F_B; ws.cell(r0_, j).fill = FILL_H
for n in ["IRS", "MRS", "LRS"]:
    a = cu[f"{n} 분석 질환 수"]; b = cu[f"{n} 하락 비율(주 결과)" if n == "IRS" else f"{n} 하락 비율"]
    ws.append([f"{n}: 사용자별 하락 비율(분석 질환 1개 이상)", f'=COUNTIF({UA}!${a}:${a},">0")', f"=AVERAGE({UA}!${b}:${b})"])
    ws.cell(ws.max_row, 3).number_format = PC
    for j in range(1, 4): ws.cell(ws.max_row, j).font = F_N

# ---------- 질환별_환산검증 ----------
VRs = VR[VR.disease.isin(DIS)].copy(); VRs["dord"] = VRs.disease.map(DORD); VRs["sord"] = VRs.score.map({c: i for i, c in enumerate(SC)})
VRs = VRs.sort_values(["dord", "sord", "pair"]).reset_index(drop=True); NVR = len(VRs) + 1
MT = MET[MET.disease.isin(DIS)].copy(); MT["dord"] = MT.disease.map(DORD); MT["sord"] = MT.score.map({c: i for i, c in enumerate(SC)}); MT["xo"] = MT.sex.map({"all": 0, "F": 1, "M": 2})
MT = MT.sort_values(["dord", "sord", "xo"]); NMT = len(MT) + 1
rows = []
for i, r in enumerate(MT.itertuples(), start=2):
    ms = M[(M.disease == r.disease) & (M.score == r.score) & (M.n_pairs > 0) & ((M.sex == r.sex) if r.sex != "all" else True)]
    mtxt = " / ".join(f"{sexk[m.sex]}: {m.method}" for m in ms.itertuples())
    crit = f'{VS}!$D$2:$D${NVR},$B{i},{VS}!$E$2:$E${NVR},$D{i}' + (f',{VS}!$F$2:$F${NVR},$E{i}' if r.sex != "all" else "")
    verdict = (f'=IF(J{i}="","검증 없음",IF(_xlfn.MINIFS($J$2:$J${NMT},$B$2:$B${NMT},$B{i},$D$2:$D${NMT},$D{i},$E$2:$E${NMT},"<>전체")>={TH},"통과","미달"))'
               if r.sex == "all" else f'=IF(J{i}="","검증 없음",IF(J{i}>={TH},"통과","미달"))')
    rows.append([f"{r.disease}|{SCN[r.score]}|{sexk[r.sex]}", r.disease, nm(r.disease), SCN[r.score], sexk[r.sex], mtxt, f"=COUNTIFS({crit})", r.n_users,
                 f"=COUNTIFS({crit},{VS}!$O$2:$O${NVR},1)", f'=IF(G{i}=0,"",I{i}/G{i})', f'=IF(G{i}=0,"",COUNTIFS({crit},{VS}!$P$2:$P${NVR},1)/G{i})',
                 verdict, r.within2, r.raw_within2, r.w_lo, r.w_hi, r.bs_lo, r.bs_hi, r.pass_share, r.pass_share_pool, r.k_raw, r.k_cw, r.kw_raw, r.kw_cw, r.to_lower, r.to_higher, r.ind_rate])
fv = {h: PC for h in H_V if any(k in h for k in ["비율", "하한", "상한", "오분류", "일치율"])}; fv.update({h: "0.000" for h in H_V if "카파" in h})
notes = {"키": "질환코드|점수|성별. 통합비교는 성별 행의 비율과 '전체' 행의 판정을 가져갑니다.",
         "검증 쌍 수": "모델 교체 직전(7/1 10:00 이전)과 직후에 같은 사용자가 같은 입력(모드·검진·생활습관·유전체 해시·성별·나이)으로 산출받은 쌍. 운영자 계정 포함(모델 특성 확인용). IRS·PRS는 유전체 포함 쌍만.",
         "환산 후 같은 구간 비율": "사용자 단위 5겹 교차검증 예측(검증_예측값)으로 설정 시트의 구간에서 다시 계산합니다.",
         "판정": "성별 행: 그 성별 비율 ≥ 기준이면 '통과'. 전체 행: 모든 성별이 기준 이상일 때만 '통과'(한 성별의 낮은 성능이 합산에 가려지지 않도록). 사전 지정한 관측 일치율 기준 충족이라는 뜻이며 정확도 보증은 아닙니다.",
         "Wilson 95% 하한": "단순 이항 근사 신뢰구간(같은 사용자의 반복 쌍과 함수 적합 변동은 반영하지 않음). 기본 구간 기준 고정값.",
         "사용자 재표집 95% 하한": "사용자 단위 1,000회 재표집 구간(예측은 고정). 성별 행과 전체 행 각각. 기본 구간 기준 고정값.",
         "재표집 통과 비율(성별 판정)": "전체 행만. 사용자를 200회 재표집해 환산 적합과 5겹 검증을 반복하고, 주 분석과 같은 성별 판정을 적용했을 때 '통과'였던 비율. 재표집 표본은 고유 사용자 수가 원자료와 달라 확률로 직접 해석하는 데 제한이 있습니다.",
         "재표집 통과 비율(합산 판정)": "같은 재표집에서 성별 합산 비율 ≥ 95%였던 비율.",
         "가중 카파(환산 후)": "5개 구간의 이차 가중 카파(보조 지표). 같은 구간 비율을 대체하지 않습니다.",
         "보류 순위표 검증 일치율": "검증 겹 사용자의 산출을 뺀 순위기준표로 예측과 정답을 모두 다시 정의했을 때의 같은 구간 비율. 순위기준표를 검증 자료와 공유한 영향을 보는 값이며, 순위기준표 오차 전체를 독립적으로 평가한 것은 아닙니다. 기본 구간 기준 고정값."}
sheet("질환별_환산검증", H_V, rows, fmts=fv, widths={"키": 34, "질환코드": 24, "질환명": 14, "환산 방법": 40}, notes=notes, freeze="F2",
      fx={"검증 쌍 수", "같은 구간 일치 수", "환산 후 같은 구간 비율", "환산 전 같은 구간 비율", "판정"})

# ---------- 검증_예측값 ----------
H_R = ["쌍 번호", "사용자군 번호", "검증 겹", "질환코드", "점수", "성별", "재부여순위(정답)", "환산 전 순위", "환산순위(교차검증)", "보류 순위표 환산순위",
       "정답 구간", "환산 구간", "환산 전 구간", "보류 순위표 환산 구간", "환산 일치", "환산 전 일치", "보류 순위표 정답", "보류 순위표 정답 구간", "보류 순위표 일치"]
rows = []
for i, r in enumerate(VRs.itertuples(), start=2):
    rows.append([r.pair, int(r.g) + 1, int(r.fold) + 1, r.disease, SCN[r.score], sexk[r.sex], r.truth, r.raw, r.pred, r.pred_h,
                 "=" + bandf(f"G{i}"), "=" + bandf(f"I{i}"), "=" + bandf(f"H{i}"), "=" + bandf(f"J{i}"),
                 f'=IF(OR(K{i}="",L{i}=""),"",IF(K{i}=L{i},1,0))', f'=IF(OR(K{i}="",M{i}=""),"",IF(K{i}=M{i},1,0))',
                 r.truth_h, "=" + bandf(f"Q{i}"), f'=IF(OR(R{i}="",N{i}=""),"",IF(R{i}=N{i},1,0))'])
notes = {"쌍 번호": "연결 쌍 번호(B001~). 사용자 식별 정보는 넣지 않았습니다.", "사용자군 번호": "같은 사용자의 쌍은 같은 번호이며 같은 검증 겹에 들어갑니다.",
         "재부여순위(정답)": "7월 모델 쪽 값을 (전체) 순위기준표에 대입한 순위. 일괄 산출의 서비스 순위는 불안정하므로 쓰지 않습니다. 이 정답은 순위기준표에 조건부입니다.",
         "환산순위(교차검증)": "그 쌍이 속한 겹을 빼고 만든 환산 함수로 바꾼 순위.", "보류 순위표 환산순위": "환산 함수와 순위기준표를 모두 그 겹 사용자의 산출을 빼고 만들었을 때의 순위.",
         "보류 순위표 정답": "7월 쪽 값을 그 겹 사용자의 산출을 뺀 순위기준표에 대입한 순위."}
sheet("검증_예측값", H_R, rows, fmts={h: R0 for h in H_R[6:10] + ["보류 순위표 정답"]}, widths={"질환코드": 24}, notes=notes, freeze="D2", fx={"정답 구간", "환산 구간", "환산 전 구간", "보류 순위표 환산 구간", "환산 일치", "환산 전 일치", "보류 순위표 정답 구간", "보류 순위표 일치"})

# ---------- 혼동행렬 ----------
CF = CONF[CONF.disease.isin(DIS)].copy(); CF["dord"] = CF.disease.map(DORD); CF["sord"] = CF.score.map({c: i for i, c in enumerate(SC)})
CF = CF.sort_values(["dord", "sord", "sex", "truth_band", "conv_band"])
rows = [[r.disease, nm(r.disease), SCN[r.score], sexk[r.sex], r.truth_band, r.conv_band, r.n] for r in CF.itertuples()]
sheet("혼동행렬", ["질환코드", "질환명", "점수", "성별", "기준표 구간(정답)", "환산 구간", "쌍 수"], rows, widths={"질환코드": 24, "질환명": 14},
      notes={"쌍 수": "검증_예측값의 교차검증 예측을 기본 구간(20)으로 나눈 5×5 혼동행렬(긴 형식). 대각선이 일치입니다."})

# ---------- 민감도_요약 ----------
rows = []
for c in SC:
    rows += [[SCN[c], "교차적합 대신 전체 적합(자기 쌍 포함)", ST[f"{c}_sens_full"]], [SCN[c], "범위 밖: 평행 이동 대신 끝점 고정(교차적합 동일)", ST[f"{c}_sens_clip"]],
             [SCN[c], "연결 쌍에서 운영자·테스트 계정 제외(교차적합 동일)", ST[f"{c}_sens_noop"]], [SCN[c], "실측 입력 연결 쌍만 사용(교차적합 동일)", ST[f"{c}_sens_meas"]],
             [SCN[c], "기준선 값이 연결 쌍 범위 밖(외삽)인 행 비율", ST[f"{c}_extrap"]], [SCN[c], "순위표 빈 구간이고 인접 순위가 다른 구간에 걸치는 행 비율", ST[f"{c}_gap_amb"]],
             [SCN[c], "환산 함수 재표집 2.5~97.5 백분위가 구간에 걸치는 행 비율", ST[f"{c}_cross"]]]
rows += [["IRS", "같은 모델 사용자: 두 시점을 모두 7월 척도로 환산해도 구간 이동 방향이 같은 비율", ST["same_model_dir"]],
         ["IRS", "나이 항 추가 환산(교차검증 같은 구간 비율 중앙값)", ST["age_irs"]], ["MRS", "나이 항 추가 환산(교차검증 같은 구간 비율 중앙값)", ST["age_mrs"]]]
sheet("민감도_요약", ["점수", "비교", "주 결과와 같은 구간 비율 / 해당 비율"], rows, widths={"비교": 70, "주 결과와 같은 구간 비율 / 해당 비율": 26},
      notes={"비교": "7월 모델 기준(기준선 환산) 행에서 주 환산과 대안 환산의 20순위 구간이 같은 비율, 또는 해당 행의 비율. 같은 모델 행은 환산이 없어 대상이 아닙니다(마지막 비교 제외)."})

# ---------- 환산_민감도 ----------
H = KEYH + ["비교 척도"]
for c in SC: H += [f"{SCN[c]} 주 환산순위", f"{SCN[c]} 전체 적합", f"{SCN[c]} 끝점 고정", f"{SCN[c]} 운영자 제외", f"{SCN[c]} 실측 쌍만", f"{SCN[c]} 7월 척도 기준선", f"{SCN[c]} 7월 척도 추적"]
rows = [keyrow(r) + [r.scale] + sum([[getattr(r, c + k) for k in ["_r_c", "_r_full", "_r_clip", "_r_noop", "_r_meas", "_rj_b", "_rj_f"]] for c in SC], []) for r in LB.itertuples()]
sheet("환산_민감도", H, rows, fmts={h: R0 for h in H[7:]}, widths={**LONGW, "비교 척도": 24}, freeze="G2",
      notes={"IRS 전체 적합": "자기 연결 쌍을 포함한 환산 함수(교차적합하지 않음). 7월 모델 기준 행만.", "IRS 끝점 고정": "연결 쌍 범위 밖에서 평행 이동 대신 끝점 값으로 고정(교차적합 동일).",
             "IRS 운영자 제외": "운영자·테스트 계정의 연결 쌍을 뺀 환산 함수.", "IRS 실측 쌍만": "이전 모델 쪽 산출이 실측 입력인 연결 쌍만 사용한 환산 함수.",
             "IRS 7월 척도 기준선": "모든 행에서 기준선을 7월 척도로 환산한 순위. 같은 모델 행의 민감도 분석용(추적도 7월 척도로 환산).",
             "IRS 7월 척도 추적": "같은 모델 행: 추적(이전 모델)도 같은 함수로 7월 척도로 환산한 순위. 7월 모델 기준 행: 재부여순위와 같음."})

# ---------- 대표성_비교 ----------
rows = [["나이 중앙값(사분위 범위)", ST["repr_age_bridge"], ST["repr_age_anal"]], ["수축기 혈압 입력", ST["repr_sbp_bridge"], ST["repr_sbp_anal"]],
        ["교체 전 IRS 순위(질환 행 전체)", ST["repr_irs_bridge"], ST["repr_irs_anal"]], ["교체 전 MRS 순위(질환 행 전체)", ST["repr_mrs_bridge"], ST["repr_mrs_anal"]],
        ["유전체 포함 산출", ST["repr_geno_bridge"], "100%(선정 조건)"], ["실측 입력 산출", ST["repr_meas_bridge"], "100%(선정 조건)"],
        ["운영자·테스트 계정", f"{ST['bridge_bad']}명", "0명(제외)"], ["겹치는 사용자", f"{ST['bridge_overlap']}명", f"{ST['bridge_overlap']}명"],
        ["기준선 값이 연결 쌍 범위 안인 비율(7월 기준 행)", "", f"IRS {ST['cov_irs']}, MRS {ST['cov_mrs']}"]]
sheet("대표성_비교", ["특성", f"연결 쌍({ST['bridge_pairs']}쌍)", f"분석 대상({ST['n']}명)"], rows, widths={"특성": 40, f"연결 쌍({ST['bridge_pairs']}쌍)": 22, f"분석 대상({ST['n']}명)": 24}, filt=False,
      notes={"특성": "연결 쌍은 교체 전 쪽 산출 기준, 분석 대상은 기준선 산출 기준."})

# ---------- 순위표_재현검증 ----------
rows = [[SCN[c], int(REP.loc[c, "n"]), REP.loc[c, "exact_rate"], REP.loc[c, "same_rate"]] for c in SC]
sheet("순위표_재현검증", ["점수", "검증 산출 행 수", "순위 정확 일치", "같은 구간 일치"], rows, fmts={"순위 정확 일치": PC, "같은 구간 일치": PC}, filt=False,
      notes={"검증 산출 행 수": "안정기(7/1 15:00~8/1) 산출을 사용자 단위 5겹으로 나눠, 다른 사용자로 만든 순위기준표로 각 산출의 순위를 다시 매겨 서비스 순위와 비교."})

# ---------- 검진입력_비교 ----------
ITEMS = [("SBP", "수축기 혈압(mmHg)"), ("DBP", "이완기 혈압(mmHg)"), ("FastingGlucose", "공복 혈당(mg/dL)"), ("2_TCHL", "총콜레스테롤(mg/dL)"), ("2_HDL", "HDL 콜레스테롤(mg/dL)"),
         ("2_TG", "중성지방(mg/dL)"), ("ldlcholesterol", "LDL 콜레스테롤 측정값(mg/dL)"), ("LDL", "LDL 모델 입력값(mg/dL)"), ("HEIGHT", "키(cm)"), ("WEIGHT", "몸무게(kg)"),
         ("BMI", "체질량지수(kg/m²)"), ("2_WAIST", "허리둘레(cm)"), ("2_HB", "혈색소(g/dL)"), ("2_AST", "AST(U/L)"), ("2_ALT", "ALT(U/L)"), ("2_R_GTP", "감마지티피(U/L)"),
         ("2_CREATINE", "혈청 크레아티닌(mg/dL)"), ("gfr", "사구체여과율 검진 표기값"), ("eGFR", "eGFR 모델 입력값"), ("urineprotein", "요단백"), ("sight", "시력(좌/우)"),
         ("hearing", "청력(좌/우)"), ("chestdisease", "흉부 소견"), ("1_AGE", "나이(입력)")]
H_K = ["연구번호", "user_id", "바뀐 검진 항목 수", "생활습관 설문 변경"]
for k, n in ITEMS: H_K += [f"{n} 1차", f"{n} 2차"]
def num(v):
    if v is None or (isinstance(v, float) and np.isnan(v)): return None
    try: return float(v)
    except Exception: return v
rows = []
for idx, r in enumerate(u.itertuples()):
    row = [r.sid, r.user_id, r.n_core_changed, r.life_ch]
    for k, n in ITEMS: row += [num(mb[k].iloc[idx]) if k in mb else None, num(mf[k].iloc[idx]) if k in mf else None]
    rows.append(row)
sheet("검진입력_비교", H_K, rows, widths={"user_id": 38}, freeze="E2",
      notes={"LDL 모델 입력값(mg/dL) 1차": "IRS 모델에 들어간 값. 측정값이 없으면 계산값(소수)이 들어갑니다.", "eGFR 모델 입력값 1차": "IRS 모델에 들어간 계산값.",
             "바뀐 검진 항목 수": "기준선과 추적에서 값이 다른 검진 항목 수(14개 중). 검진 측정일은 원자료에 없습니다."})

# ---------- 환산표 / 순위기준표 ----------
Ks = K[K.disease.isin(DIS)].copy(); Ks["dord"] = Ks.disease.map(DORD); Ks["ford"] = Ks.fit.map(lambda v: 0 if v == "전체" else int(v[1]))
Ks = Ks.sort_values(["dord", "score", "sex", "ford", "old"])
rows = [[r.disease, nm(r.disease), SCN[r.score], sexk[r.sex], r.fit, r.n_pairs, "로짓" if r.scale == "logit" else "원척도", r.old, r.new] for r in Ks.itertuples()]
sheet("환산표", ["질환코드", "질환명", "점수", "성별", "적합", "학습 쌍 수", "적합 척도", "이전 모델 값", "7월 모델 값"], rows, fmts={"이전 모델 값": "0.000000", "7월 모델 값": "0.000000"},
      widths={"질환코드": 24, "질환명": 14}, notes={"적합": "'전체'는 모든 연결 쌍으로 만든 함수(연결 쌍에 없는 분석 대상에 적용). '겹k 제외'는 검증 겹 k의 사용자를 뺀 함수(그 겹에 속한 연결 쌍 사용자의 기준선에 적용, 5겹 교차적합).", "이전 모델 값": "등위회귀의 꺾이는 점. 점 사이는 적합 척도에서 직선으로 잇고, 범위 밖은 끝점 차이만큼 평행 이동합니다. '값 동일'인 질환·점수는 이 표에 없습니다(환산 없이 순위기준표만 적용)."})
rows = []
for d in DIS:
    for c in SC:
        for s in ["F", "M"]:
            if (d, s, c) not in REF: continue
            x, y = REF[(d, s, c)]; t = pd.DataFrame({"p": x, "r": y}).groupby("r").p.agg(["min", "max", "size"])
            for rk, q in t.iterrows(): rows.append([d, nm(d), SCN[c], sexk[s], int(rk), q["min"], q["max"], int(q["size"])])
sheet("순위기준표", ["질환코드", "질환명", "점수", "성별", "순위", "최소 값", "최대 값", "산출 수"], rows, fmts={"최소 값": "0.000000", "최대 값": "0.000000", "순위": R0},
      widths={"질환코드": 24, "질환명": 14}, notes={"순위": f"7월 모델 순위기준표. 2026-07-01 15:00~08-01 산출 {ST['ref_calcs']:,}건(운영자 포함)에서 질환·점수·성별마다 각 순위로 관측된 값의 범위. 이 기간에는 값이 높은데 순위가 낮은 경우가 없었습니다."})

# ---------- 안내 ----------
T = [(f"SiBC IRS 기준선·추적 환산 비교 자료 ({ST['n']}명 설계)", F_T),
     ("작성일 2026-11-19 · 자료 기준일 2026-11-19 · 기준선을 '앱 등록 후 56일 이내 첫 완성 IRS'로 다시 정의한 판 · 내부 분석용(건강 정보 포함, 외부 반출 시 user_id 열 삭제)", F_N), ("", None),
     ("1. 자료의 성격과 대상", F_H2),
     ("· 실제 산출 입력을 쓴 탐색적 버전 보정 비교 자료입니다. 03 계획서의 '생활습관·유전 순위를 기준선 값으로 고정한 재산출'과는 다르며, 그 결과에는 개발 부서 재산출이 필요합니다.", F_N),
     ("· 대상은 온보딩 뒤 검진 입력이 갱신되어 IRS가 다시 산출된 사용자로 한정됩니다. 결과를 모든 앱 등록자로 일반화하지 마십시오.", F_N),
     (f"· 대상: {ST['n']}명(여 {ST['n_f']}, 남 {ST['n_m']}, 전원 울산). 사이트 연결 {ST['flow_site_users']:,}명 → 운영자·테스트 제외 → 로그인 기록 → 공통 코호트 {ST['flow_common_cohort']}명 → 완성 IRS {ST['flow_with_complete_irs']}명 → 등록 후 56일 이내 {ST['flow_within_window']}명 → 기준선이 7월 이전 모델 {ST['flow_baseline_model_ok']}명 → 추적 조건 충족 {ST['n']}명.", F_N),
     (f"· 기준선(1차): 앱 등록 후 56일 이내의 첫 완성 IRS. 완성 IRS는 유전(PRS)·의학(MRS)·생활습관(LRS)이 모두 반영된 산출(유전체 포함 모드 1·4, 혈압·공복혈당이 정수인 실측 검진, 생활습관 응답 있음)입니다. 완성 IRS는 등록 후 중앙값 {ST['ob_comp_med']}일, 90%가 {ST['ob_comp_q90']}일 이내에 나왔고, 56일 안에 {ST['ob_comp_56_share']}가 들어옵니다.", F_N),
     (f"· 추적(2차): 기준선 날짜로부터 90일 이후의 완성 IRS 가운데 유전체 입력이 같고 직접 측정 검진값이 바뀐 가장 이른 산출(2026-08-01까지). 산출 간격 중앙값 {ST['gap']}일, 180일 이상 {ST['ge180']}명. 검진 측정일은 원자료에 없어 산출 시점 기준의 순서만 보장됩니다.", F_N),
     ("· 시간 0은 기준선 날짜입니다. 노출은 기준선 다음 날부터 28일째까지의 앱 활성일이고, 기준선 전날까지의 활성일은 공변량으로 씁니다(01·02의 등록 기준 노출과 다르므로 계획서 개정 사항).", F_N),
     (f"· 비교 척도: {ST['n_p1']}명은 추적이 7월 모델이라 기준선을 환산해 비교하고, {ST['n_p0']}명은 두 시점 모두 이전 모델이라 환산 없이 비교합니다. 두 척도의 구간 경계가 같지 않으므로 모델 경로별 추정과 전원 7월 척도 비교를 민감도 분석으로 함께 보고하십시오(같은 모델 사용자의 주 결과는 {ST['sm_users']}명 중 {ST['sm_same_share']}명이 두 척도에서 같음).", F_N),
     ("· 원천: 운영 DB invites_loop의 irs.irs_data_log(raw_data의 Results·medicalRecord·lifestyleLog·genotypes·Mode·SEX·age), ichms.auth_user_login_history. 조회 전용 세션, 시각은 모두 KST.", F_N), ("", None),
     ("2. 환산 방법(요약)", F_H2),
     (f"· 2026-07-01 10:00에 모델이 바뀌었습니다. 교체 직후 10~15시 일괄 재산출 {ST['batch_calcs']}건은 값은 이후와 같지만 순위가 이후 순위기준표와 정확히 같은 비율이 {ST['batch_exact']}(같은 구간 {ST['batch_band']})여서, 순위기준표는 7/1 15:00~8/1 산출 {ST['ref_calcs']:,}건으로 만들었습니다.", F_N),
     (f"· 같은 사용자·같은 입력의 교체 전 마지막·교체 후 첫 산출 {ST['bridge_pairs']}쌍으로 질환·점수·성별마다 단조 환산 함수(등위회귀; IRS·MRS 로짓 척도, LRS·PRS 원척도)를 만들고, 환산 값을 순위기준표로 순위화합니다. 연결 쌍 사용자({ST['bridge_overlap']}명)는 5겹 교차적합.", F_N),
     (f"· 검증(사용자 단위 5겹 교차검증): 같은 20순위 구간 비율의 질환별 중앙값 IRS {ST['irs_raw']}→{ST['irs_cw']}, MRS {ST['mrs_raw']}→{ST['mrs_cw']}, LRS {ST['lrs_cw']}·PRS {ST['prs_cw']}. 성별 모두 95% 이상인 질환: IRS {ST['irs_sex_pass']}개, MRS {ST['mrs_sex_pass']}개, LRS {ST['lrs_sex_pass']}개.", F_N), ("", None),
     ("3. 주 분석 규칙", F_H2),
     ("· 주 분석 적격(통합비교): 양 시점 순위 있음 + 질환의 환산 검증 판정 '통과'. 같은 모델 행도 질환 목록을 맞추기 위해 같은 판정을 적용합니다.", F_N),
     ("· 하락 분석은 기준선이 가장 낮은 구간(1~20)인 행을 뺍니다. 주 결과는 사용자 단위 'IRS 하락 비율'(대상자 시트) = 낮은 위험 구간으로 이동한 질환 수 ÷ 분석 질환 수입니다. 고혈압 등 개별 질환은 부 결과입니다.", F_N),
     (f"· 민감도 분석: 최저 구간을 분모에 포함한 하락 비율(대상자 시트), 검진값이 바뀌지 않은 추적까지 포함({ST['n_nochange']}명), 같은 모델 사용자를 7월 척도로 환산(환산_민감도), 경계 근접·재표집 구간 걸침 제외, 성별 합산 판정, 안정 통과 질환만, 기준선 기간 28일({ST['n_w28']}명)·90일({ST['n_w90']}명), 구간 너비·경계 변경(설정 시트).", F_N), ("", None),
     ("4. 분석 시 유의점", F_H2),
     ("· 순위는 1~100의 위치 값이므로 더하거나 빼지 않습니다. 순위가 클수록 위험이 높고, '하락'은 낮은 위험 구간으로의 이동입니다.", F_N),
     (f"· 추적 IRS에는 생활습관 응답 변화도 반영됩니다({ST['life_ch']}명이 응답 변경). 검진 측정일은 원자료에 없고, 추적에서 바뀐 항목은 주로 혈압·체격·지질입니다.", F_N),
     ("· 환산 일치도는 버전 간 일치도이며 IRS의 질환 예측 타당도를 뜻하지 않습니다. 한 사용자가 여러 질환 행을 가지므로 질환을 묶어 분석할 때는 사용자 내 상관을 고려하십시오.", F_N), ("", None),
     ("5. 시트 안내", F_H2)]
SHEETS = [("설정", "구간 너비, 경계 이동, 경계 근접 기준, 검증 통과 기준(노란 칸만 수정)"),
          ("대상자", "사용자 1명당 1행. 기준선·추적 산출, 비교 척도, 노출(기준선 후 28일 활성일), 행 수 검산, 사용자 단위 주 결과(하락 비율)"),
          ("1차_기준선", "사용자×질환 1행. 기준선 IRS·MRS 확률, LRS·PRS 점수와 서비스 순위"),
          ("1차_환산", "같은 키. 7월 모델 기준 환산 값·순위(같은 모델 행은 원래 값), 순위표 위치, 재표집 범위, 외삽, 환산 방법"),
          ("2차_추적", "같은 키. 추적 값, 서비스 순위, 재부여순위"),
          ("통합비교", "같은 키. 기준선 환산순위·추적 재부여순위, 구간, 구간 이동, 최저 구간, 경계 근접, 재표집 구간 걸침, 검증 판정, 주 분석 적격(초록 머리글은 수식)"),
          ("요약", "질환별 주 분석 대상과 구간 이동 수, 사용자 단위 주 결과 평균(수식)"),
          ("질환별_환산검증", "질환×점수×성별 환산 정확도, 판정, 구간 추정, 카파, 오분류 방향, 재표집 통과 비율"),
          ("검증_예측값", "검증에 쓴 연결 쌍별 정답·환산 전·환산 순위(식별 정보 없음). 설정에 따라 일치율 재계산"),
          ("혼동행렬", "질환×점수×성별 5×5 혼동행렬(기본 구간)"),
          ("민감도_요약", "대안 환산과의 구간 일치, 외삽·빈 구간·재표집 걸침 비율, 같은 모델 사용자의 7월 척도 민감도"),
          ("환산_민감도", "행별 대안 환산 순위와 7월 척도 순위"),
          ("대표성_비교", "연결 쌍과 분석 대상의 특성 비교"),
          ("순위표_재현검증", "순위기준표가 다른 사용자의 서비스 순위를 재현하는 정도"),
          ("검진입력_비교", "사용자 1명당 1행. 기준선(1차)·추적(2차) 검진 입력값"),
          ("환산표", "등위회귀 환산의 꺾이는 점(전체 함수와 겹별 교차적합 함수)"),
          ("순위기준표", "7월 모델의 순위별 값 범위")]
for txt, ft in T:
    ws0.append([txt])
    if ft: ws0.cell(ws0.max_row, 1).font = ft
    ws0.cell(ws0.max_row, 1).alignment = Alignment(wrap_text=True, vertical="top")
    ws0.merge_cells(start_row=ws0.max_row, start_column=1, end_row=ws0.max_row, end_column=2)
    if len(txt) > 90: ws0.row_dimensions[ws0.max_row].height = 15 * (len(txt) // 90 + 1)
r0 = ws0.max_row + 1; ws0.append(["시트", "내용"])
for j in (1, 2): ws0.cell(r0, j).font = F_B; ws0.cell(r0, j).fill = FILL_H
for s, d in SHEETS:
    ws0.append([s, d]); ws0.cell(ws0.max_row, 1).font = F_B; ws0.cell(ws0.max_row, 2).font = F_N; ws0.cell(ws0.max_row, 1).hyperlink = f"#'{s}'!A1"
ws0.append([]); ws0.append([f"재현 정보: {ST['sw']}. 스크립트 x7(연결 쌍), x7b({ST['n']}명 설계), xwlib(환산 함수), x8b(검증), x8c(나이 항 대안), x8v({ST['n']}명 환산), stats2(수치), xl3(워크북)."])
ws0.cell(ws0.max_row, 1).font = Font(name=FONT, size=9, italic=True)
ws0.column_dimensions["A"].width = 18; ws0.column_dimensions["B"].width = 130; ws0.sheet_view.showGridLines = False
wb.save(OUT)
print("saved", {w.title: (w.max_row, w.max_column) for w in wb.worksheets})
