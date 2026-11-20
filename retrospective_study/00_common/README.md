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
| `src/common_cohort.py` | 공통 코호트, 03 비교 대상 겹침 표시(03 결과 파일이 없으면 '확인 불가'), 실행 옵션 | 올림 |
| `src/xlsx_util.py` | 사용자 목록 xlsx 작성 도구 | 올림 |
| `src/db_query.sh` | 조회 전용 DB 질의 도구 (`RETRO_DB_ENV` 필요, 읽기 전용 트랜잭션, 읽기 문장만 허용) | 올림 |
| `src/sql_guard.py` | `db_query.sh`가 접속 전에 쓰는 문장 검사 | 올림 |
| `src/run_extract.py` | `sql/` 파일의 이름 붙은 블록 하나를 `db_query.sh`로 실행해 csv로 저장(기존 파일에 쓰지 않음) | 올림 |
| `src/md2docx_sibc_ref.js` | md → SiBC 서식 docx 변환기 (03 방법 문서용). 기관·작성자 등 표지 문구는 로컬 JSON으로 받음 | 올림 |
| `00_Data/users.csv`, `login.csv` | 사용자 속성, 일별 로그인 (2026-11-18/19 추출, 공식 목록의 입력) | 올리지 않음 |
| `00_Data/extract_20261120/` | 같은 추출문으로 2026-11-20에 다시 뽑은 파일 | 올리지 않음 |
| `docs/local/` | N 집계 문서, 연구계획서 원고 소스(`protocol_src/`), DB 작업 결과(2026-11-20) | 올리지 않음 |

연구계획서 docx는 `protocol_src/`에서 다시 만듭니다. 2026-11-18 판은 `python3 build.py`, 2026-11-20 개정판은 `python3 build_r.py`입니다(docx 모듈은 `medical_checkup_model/node_modules`).
