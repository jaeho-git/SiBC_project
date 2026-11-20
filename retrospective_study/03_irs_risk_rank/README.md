# 03 앱 참여도와 IRS 위험 순위

기준선 IRS 이후 앱 참여도와 다시 산출된 IRS의 위험 순위 변화를 봅니다. IRS는 시스템이 산출한 값을 그대로 씁니다. 다시 산출된 IRS에는 시스템이 계산한 MRS가 이미 들어 있으므로, 이 연구에는 건강검진 원천을 따로 쓰지 않습니다.

## 비교 대상 규칙 (2026-11-19 확정, `src/x7b.py`)

- **공통 코호트:** `00_common/README.md`
- **완성 IRS:** 유전체 모드 1/4, 실측 의료 입력(수축기·이완기혈압·공복혈당 정수), 생활습관 답변이 있는 산출
- **기준선:** 등록 후 0~56일 안의 첫 완성 IRS, 7월 모델 교체 전 산출
- **추적:** 기준선 90일 이후의 완성 IRS 중 첫 산출. 조건은 다음과 같습니다.
  - 유전체 해시가 기준선과 같음
  - 의료 입력 14항목 중 하나 이상이 양쪽에 있고 값이 다름
  - 2026-08-02 이전에 산출됨
- **노출:** 기준선 다음 날부터 28일 동안의 앱 활성일
- **주 결과:** 사용자별로 기준을 충족한 질환 IRS 중 하락한 비율

## 실행 순서

스크립트는 현재 폴더의 파일을 읽고 씁니다. 원본(`00_Data/frozen_20261119/`)을 덮어쓰지 않도록 작업 폴더에 복사한 뒤 그 안에서 실행합니다.

| 단계 | 스크립트 | 만드는 것 |
|---|---|---|
| 1 | `a5.py` | `I.pkl` (산출별 입력·모드 정리) |
| 2 | `b1.py` | `designB90.csv` |
| 3 | `x7.py` | `I_final.pkl`, `D_final.pkl`, `BB_final.pkl` |
| 4 | `x8.py` | `L.pkl`, `M.pkl`, `K.pkl`, `REF.pkl`, `DIS.pkl` (모델 버전 환산표) |
| 5 | `x8b.py`, `x8c.py` | 환산 검증 (`CONF`, `MET`, `REP`, `REPR`, `VR`, `NP`, `x8b_extra.json`, `x8c.json`) |
| 6 | `x9.py`, `stats.py` | `XL_users.pkl`, `stats.json` |
| 7 | `x7b.py` | `D2.pkl` (비교 대상), 선정 흐름 json |
| 8 | `x8v.py` | `K2`, `L2`, `M2` (비교 대상 환산) |
| 9 | `stats2.py` | `stats2.json` (문서·xlsx에 쓰는 숫자) |
| 10 | `xl3.py <출력.xlsx>` | 비교 xlsx |
| 11 | `mdoc2.py <출력 폴더>` | 방법 docx (`docs/local/`에 두고 git 제외). 아래 '방법 문서 만들기' 참고 |
| 검산 | `indep_recount.py 00_Data/indep` | 별도 추출·별도 코드로 대상 인원 재계산 |

`xwlib.py`는 공통 함수입니다. `load()`는 `res_b.csv`, `res_p1.csv`에 더해 `res_miss.csv`, `res_ob.csv`가 있으면 함께 읽으므로, 네 파일이 모두 있어야 같은 결과가 나옵니다.

1단계 전에 작업 폴더에 있어야 하는 추출 파일은 `irs_full.csv`, `irs_inputs.csv`, `res_b.csv`, `res_p1.csv`, `res_miss.csv`, `res_ob.csv`, `dis_info.csv`, `users.csv`, `login.csv`입니다. `irs.csv`는 이전 요약본이라 1~9단계에서 읽지 않습니다.

추출문 원문은 `sql/irs_extracts.sql`(`-- @extract` 블록)과 `00_common/sql/common_extracts.sql`(users·login), 독립 재계산용은 `sql/indep_*.sql`에 있습니다. `res_b`, `res_miss`, `res_ob`는 seq 목록을 `--list`로 넣어 뽑습니다.
- `seqs_b.txt`는 `b1.py`, `seqs_miss.txt`는 `x7.py`가 만듭니다. 새로 뽑을 때는 `frozen_20261119/`의 목록으로 추출하고, 1~9단계를 다시 돌린 뒤 두 스크립트가 다시 만든 목록이 입력 목록과 같은지 확인합니다.
- `seqs_ob.txt`는 2026-11-19 탐색 단계에서 만든 고정 목록(비교 대상 후보의 기준선·추적 산출 중 결과가 아직 없던 것)이며 `frozen_20261119/`에 있습니다.

```bash
export RETRO_DB_ENV=<로컬 env 파일 경로>
python3 00_common/src/run_extract.py 03_irs_risk_rank/sql/irs_extracts.sql res_b 03_irs_risk_rank/00_Data/extract_YYYYMMDD/res_b.csv --list seqs_b=03_irs_risk_rank/00_Data/frozen_20261119/seqs_b.txt
```

## 방법 문서 만들기 (11단계)

`mdoc2.py`는 작업 폴더에서 다음 파일을 읽습니다.
- `mdoc2_body.md`: 본문 원고. 로컬 전용이며 `00_Data/frozen_20261119/`에 있습니다.
- `front_meta.json`: 표지의 기관·작성자·대외비 문구. 로컬 전용이며 `00_Data/frozen_20261119/`에 있습니다. 없으면 빈칸으로 만듭니다.
- `stats2.json`, `MET.pkl`, `DIS.pkl`, `dis_info.csv`: 9단계까지의 결과.

변환에는 Node와 `docx` 모듈이 필요합니다. 기본값은 `medical_checkup_model/node_modules`이며, 다른 위치면 `NODE_PATH`를 지정합니다. 변환기 경로는 `SIBC_MD2DOCX`로 바꿀 수 있습니다.

## 재현 확인 (2026-11-19, DB 접속 없이)

- 1단계 추출 파일만 빈 작업 폴더에 복사한 뒤 1~9단계를 새 위치의 스크립트로 다시 실행했습니다. 모든 중간 파일과 결과(`D2`, 환산표, `stats.json`, `stats2.json` 등)가 저장본과 같았습니다.
- 10단계 xlsx는 값과 수식이 저장본과 같았습니다.
- 독립 재계산도 같은 인원이 나왔습니다.
- 공개 저장소용으로 스크립트의 인원·결과 비율 문구를 지웠습니다(2026-11-19). xlsx 제목과 방법 docx 파일 이름에 들어가는 인원은 이제 `stats2.json`에서 읽습니다. 이 수정 뒤 7~11단계를 다시 실행해 결과 파일과 방법 docx가 같음을 확인했습니다. xlsx `안내` 시트의 검증 문장 한 칸만 고정 문구에서 `stats2.json` 계산값을 쓰는 문구로 바뀝니다.

## DB 재추출 대조 (2026-11-20)

- `sql/irs_extracts.sql`과 `00_common/sql/common_extracts.sql`로 다시 뽑은 파일을 저장본과 비교했습니다.
  - 결과값 파일(`res_*`)과 `dis_info`는 바이트까지 같았습니다.
  - 산출 로그와 사용자 표는 기존 행이 모두 같고, 11-19 이후의 새 행만 더해졌습니다.
  - 로그인 표는 저장본 추출 당일(2026-11-18)의 부분 집계 횟수만 늘었습니다.
- 새 추출로 1~9단계를 다시 돌리자 `b1.py`·`x7.py`가 만든 seq 목록이 입력 목록과 같았습니다. 비교 대상(`D2`)과 환산·검증 결과도 저장본과 같았습니다.
- 달라진 것은 산출 로그 규모와 사이트 사용자 수 같은 흐름 숫자(`stats*.json`의 `log_*`, `flow_site_users`, `flow_not_common`)뿐입니다. 모두 새로 쌓인 산출과 공통 코호트 밖의 새 사용자 때문입니다. 공식 결과는 계속 `frozen_20261119/`을 기준으로 합니다.

## 결과물 (git 제외)

- `01_Results/`: 기준선·추적 환산 비교 xlsx (10단계 결과). `_20261120` 판은 대상자 시트 끝에 2026-11-20 개정 계획서의 대표 결과 열(전 질환, 최저 구간 제외, LRS는 설문 변경자만)을 더한 판이며, 나머지 열은 `_20261119` 판과 같습니다. 앱 사용량 xlsx(`SiBC_03_앱사용량_<tag>.xlsx`, `00_common/src/build_app_usage.py`)
- `docs/local/`: 연구계획서 03, 기준선 정의·환산 방법 docx, IRS 재산출 현황 md, Codex 검토 기록
