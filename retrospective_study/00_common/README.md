# 00_common

세 연구가 함께 쓰는 정의와 도구입니다.

## 공통 코호트

`src/common_cohort.py`의 `load_common_cohort()`가 정의합니다. 03의 `x7b.py`와 같은 규칙입니다.

1. 울산(`2e0a3387-…`) 또는 제주(`778d4ff7-…`) 배포 사이트에 연결된 사용자
2. 운영자 계정과 테스트 그룹 제외
3. 첫 앱 로그인(KST 날짜)이 있음. 이 날짜를 등록일(`d0`)로 씀
4. `d0 + 28일 ≤ 2026-11-17`이고, 그 안에 탈퇴하지 않음

## 파일

| 경로 | 내용 | git |
|---|---|---|
| `sql/common_extracts.sql` | users·login 추출문 원문(2026-11-18/19, `-- @extract` 블록) | 올림 |
| `sql/analysis_extracts_20261119.sql` | users·login·IRS 추출 요약(원문은 `common_extracts.sql`, `03_irs_risk_rank/sql/irs_extracts.sql`) | 올림 |
| `sql/login_day_check.sql` | 로그인일 점검용 추출문(2026-11-23, 앱 활동 기록과 로그인 시간대의 사용자×KST 날짜 집계) | 올림 |
| `src/common_cohort.py` | 공통 코호트, 03 비교 대상 겹침 표시(03 결과 파일이 없으면 '확인 불가'), 실행 옵션 | 올림 |
| `src/xlsx_util.py` | 사용자 목록 xlsx 작성 도구 | 올림 |
| `src/data_xlsx.py` | 분석 자료·앱 사용량 xlsx 작성 도구(안내, 열_설명, 자료 시트) | 올림 |
| `src/build_app_usage.py` | 연구별 앱 사용량(로그인한 날) xlsx. `--study 01/02/03/all` | 올림 |
| `src/login_day_check.py` | 로그인일 점검. 로그인한 날과 같은 날 앱 활동 기록을 대조하고, 의심 로그인일 규칙 1·2의 영향을 연구별로 집계해 화면에만 출력 | 올림 |
| `src/db_query.sh` | 조회 전용 DB 질의 도구 (`RETRO_DB_ENV` 필요, 읽기 전용 트랜잭션, 읽기 문장만 허용) | 올림 |
| `src/sql_guard.py` | `db_query.sh`가 접속 전에 쓰는 문장 검사 | 올림 |
| `src/run_extract.py` | `sql/` 파일의 이름 붙은 블록 하나를 `db_query.sh`로 실행해 csv로 저장(기존 파일에 쓰지 않음) | 올림 |
| `src/md2docx_sibc_ref.js` | md → SiBC 서식 docx 변환기 (03 방법 문서용). 기관·작성자 등 표지 문구는 로컬 JSON으로 받음 | 올림 |
| `00_Data/users.csv`, `login.csv` | 사용자 속성, 일별 로그인 (2026-11-18/19 추출, 공식 목록의 입력) | 올리지 않음 |
| `00_Data/extract_20261120/` | 같은 추출문으로 2026-11-20에 다시 뽑은 파일 | 올리지 않음 |
| `00_Data/extract_20261123/` | `sql/login_day_check.sql` 추출 결과 | 올리지 않음 |
| `docs/local/` | N 집계 문서, 연구계획서 원고 소스(`protocol_src/`), DB 작업 결과(2026-11-20), 논문 도표 구성안·분석 자료 점검·통계 분석 방법(2026-11-23, 결과 수치 포함) | 올리지 않음 |

## 앱 사용량 (`src/build_app_usage.py`)

연구마다 사용 가능 사용자의 앱 사용량을 결과 자료와 따로 만듭니다. 로그인한 날은 고객(사이트) 구분 없이 로그인 기록이 1건 이상인 KST 날짜이며, 자료 기준일 뒤의 로그인은 쓰지 않습니다. 중앙값과 고·저 참여 구분은 넣지 않습니다(통계분석계획서 등록 때 정함).

| 연구 | 창 | 결과 파일(git 제외) |
|---|---|---|
| 01 | 노출창: 기준선 종료 다음 날과 등록 다음 날 중 늦은 날부터 28일 | `01_wearable_metrics/01_Results/SiBC_01_앱사용량_<tag>.xlsx` |
| 02 | 참여도창(결과 변수): 등록 다음 날부터 28일 | `02_checkup_metrics/01_Results/SiBC_02_앱사용량_<tag>.xlsx` |
| 03 | 노출창: 기준선 IRS 산출 다음 날부터 28일. 실행 때 03 저장본(`D2.pkl`)의 값과 같음을 확인 | `03_irs_risk_rank/01_Results/SiBC_03_앱사용량_<tag>.xlsx` |

```bash
python3 00_common/src/build_app_usage.py --study all
```

연구계획서 docx는 `protocol_src/`에서 다시 만듭니다. 2026-11-18 판은 `python3 build.py`, 2026-11-20 개정판은 `python3 build_r.py`입니다(docx 모듈은 `medical_checkup_model/node_modules`).

## 로그인일 점검 (`src/login_day_check.py`)

로그인 이력은 한 행이 토큰 발급 한 건입니다. 그래서 "로그인한 날"이 앱을 연 날인지 점검합니다. 로그인한 날마다 같은 날의 앱 활동 기록과 대조합니다. 활동 기록은 행동 이벤트, 푸시 클릭·플로팅 닫기, 기분 기록 응답, 주간 체크업 응답입니다.

"의심 로그인일"은 2026-05-01 이후, 토큰이 1건이고, 앱 활동 기록이 없는 날입니다. 의심 로그인일을 뺀 참여도는 세 연구의 민감도 분석에 씁니다. 활동 기록을 무엇으로 보는지에 따라 규칙이 둘입니다.
- 규칙 1: 모든 원천을 씁니다.
- 규칙 2: 행동 이벤트만 씁니다.

스크립트는 결과를 화면에만 출력하며, 결과 수치는 git에 올리지 않습니다.

```bash
# retrospective_study/에서, 추출(조회 전용)
RETRO_DB_ENV=... python3 00_common/src/run_extract.py 00_common/sql/login_day_check.sql login_hours_days 00_common/00_Data/extract_<date>/login_hours_days.csv
# event_days, inbound_days, mood_days, weekly_checkup_days도 같은 방식
# 집계(연구별 앱 사용량 xlsx가 먼저 있어야 함)
python3 00_common/src/login_day_check.py
```

스크립트는 다음과 같은 경우 멈춥니다.
- 입력이 어긋날 때
  - 사용자-일 중복
  - 기존 `login.csv`와 로그인일 불일치
  - 토큰 수가 양의 정수가 아님
- 원천에 기록이 없는 달이 있을 때
- 연구별 창이 28일이 아니거나, 창의 로그인 일수가 다를 때
