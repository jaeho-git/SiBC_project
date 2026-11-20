# retrospective_study

SiBC 앱 사용자 자료를 쓰는 후향적 연구 3편의 작업 공간입니다. 세 연구는 같은 공통 코호트와 같은 앱 참여도 노출을 쓰고, 결과 지표만 다릅니다.

| 폴더 | 연구 | 결과 지표 자료 |
|---|---|---|
| `01_wearable_metrics/` | 01 앱 참여도와 웨어러블 지표 | 웨어러블 지표 전체(lifelog: 걸음·수면·활동·심박 등, 울산 거점 현장 측정은 플랫폼 20301103) |
| `02_checkup_metrics/` | 02 앱 참여도와 건강검진 지표 | 승인된 건강검진 원천의 검진 항목 전체 (`disc_medical_user_info → disc_health_user_info.health_info_data`, 검진일 `measuredDt`) |
| `03_irs_risk_rank/` | 03 앱 참여도와 IRS 위험 순위 | 시스템이 산출한 IRS(MRS·LRS·PRS 포함) 값 그대로, 평가된 전 질환 |
| `00_common/` | 3편 공통 | 공통 코호트, 앱 로그인, DB 조회 도구, 문서 변환기 |

## 투고 순서

1. 01과 02를 먼저 진행합니다.
2. 03은 01·02와 함께 준비하되, **01·02보다 먼저 투고하지 않습니다.**
3. 세 편은 대상자가 겹칩니다. 각 편의 사용자 목록에 `03_IRS_비교대상_포함` 열을 두었고, 투고할 때 표본 겹침을 밝힙니다. 세 편을 합친 통합본은 따로 내지 않습니다(중복 게재 방지).

## 공통 규칙

- **공통 코호트:** 울산·제주 사이트 연결, 운영자·테스트 그룹 제외, 첫 로그인(= 등록일) 있음, 등록 후 28일이 자료 기준일 안에 들어오고 그 안에 탈퇴하지 않은 사용자 (`00_common/src/common_cohort.py`).
- **자료 기준일:** 2026-11-17. 추출은 2026-11-19, 모든 DB 세션은 조회 전용(`default_transaction_read_only=on`)이고 시간대는 Asia/Seoul입니다.
- **2026-11-20 재추출:** 추출문 원문을 `*/sql/`에 저장하고 같은 문장으로 다시 뽑아, 같은 자료 기준일에서 01·02 목록과 03 비교 대상이 그대로 나오는지 확인했습니다. 자료 기준일을 2026-11-18로 옮긴 걸음 목록·02 목록 갱신판은 파일 이름이 `_20261120`입니다. 01 전 지표 목록(`…_전지표_…_20261120`)은 공식 기준일 2026-11-17로 만든 것입니다.
- **노출:** 기준선 이후 28일 동안의 앱 활성일. 기준선 이전 활성일은 공변량입니다.
- **건강검진과 현장 측정은 다른 자료입니다.** 현장 측정은 웨어러블 자료(01)에 속합니다. 02에는 승인된 건강검진 원천만 씁니다. 둘을 한 쌍으로 묶어 변화를 계산하지 않습니다.
- **분석 범위는 넓게 둡니다.** 특정 지표·항목·질환 하나로 좁히지 않고 전 항목을 같은 규칙으로 분석한 뒤, 사전 등록한 다중 비교 보정과 선정 기준을 넘은 항목을 집중 분석합니다.
- **분석 계획을 정하기 전에는 집단 간 결과 차이를 보지 않습니다.** 사용자 목록 xlsx에는 날짜, 일수, 상태만 적고 결과 값은 적지 않습니다.
- 현재 사이트는 현재 상태일 뿐입니다. 과거 사건의 사이트로 쓰지 않습니다.

## 저장소에 올리는 것과 로컬에만 두는 것

이 저장소는 **공개 저장소**입니다.

| 종류 | 위치 | git |
|---|---|---|
| README, 설계 설명 md | 각 폴더 | 올림 |
| SQL (조회 전용 추출문) | `*/sql/` | 올림 |
| 분석 코드 | `*/src/` | 올림 |
| 연구계획서·방법 문서(docx), 그 md 판, 계획서 원고 소스, 검토 기록 | `*/docs/local/` | **올리지 않음** |
| 추출 원자료(csv·pkl) | `*/00_Data/` | **올리지 않음** |
| 사용자 단위 결과(xlsx 등) | `*/01_Results/` | **올리지 않음** |
| DB 접속 정보 | 로컬 env 파일 | **올리지 않음** (`.env.example`에는 변수 이름만) |

제외 규칙은 `retrospective_study/.gitignore`와 저장소 최상위 `.gitignore`에 있습니다. 결과 숫자(인원 등)는 로컬 문서와 xlsx의 `안내` 시트에만 둡니다.

## 폴더 구조

```text
retrospective_study/
├── README.md               # 이 문서
├── DB_TODO_20261120.md     # DB 작업 기록 (2026-11-20 진행)
├── .gitignore  .env.example  pyproject.toml
├── 00_common/   docs/local/  sql/  src/  00_Data/
├── 01_wearable_metrics/   docs/local/  sql/  src/  00_Data/  01_Results/
├── 02_checkup_metrics/    docs/local/  sql/  src/  00_Data/  01_Results/
└── 03_irs_risk_rank/      docs/local/  sql/  src/  00_Data/  01_Results/
```

## 실행 (DB 접속 없이)

저장된 추출 파일만 씁니다. 옵션 없이 실행하면 2026-11-19 목록을 그대로 다시 만듭니다.

```bash
python3 01_wearable_metrics/src/build_usable_users.py
python3 02_checkup_metrics/src/build_usable_users.py
```

새로 추출한 자료로 만들 때는 입력 폴더, 자료 기준일, 파일 이름 날짜를 모두 지정합니다. 그래야 기존 목록을 덮어쓰지 않습니다.

```bash
python3 01_wearable_metrics/src/build_usable_users.py --data-dir 01_wearable_metrics/00_Data/extract_YYYYMMDD --common-data-dir 00_common/00_Data/extract_YYYYMMDD --cutoff YYYY-MM-DD --extract-date YYYY-MM-DD --tag YYYYMMDD
```

03은 `03_irs_risk_rank/README.md`의 순서를 따릅니다.

## DB에서 다시 추출할 때

추출문은 각 연구의 `sql/` 파일에 `-- @extract <이름>` 블록으로 적혀 있습니다. `00_common/src/run_extract.py`가 블록 하나를 `00_common/src/db_query.sh`로 실행해 csv로 저장합니다. 접속 정보는 `RETRO_DB_ENV`가 가리키는 로컬 env 파일에서 읽습니다.

```bash
export RETRO_DB_ENV=<로컬 env 파일 경로>
python3 00_common/src/run_extract.py 00_common/sql/common_extracts.sql users 00_common/00_Data/extract_YYYYMMDD/users.csv
```

- 계정 권한은 먼저 `DB_TODO_20261120.md` 0단계로 점검합니다. 읽기 전용 역할을 쓰는 것이 원칙이고, 그렇지 않은 계정을 쓸 때는 책임자 확인을 받고 이 도구로 조회만 합니다.
- 도구는 질의를 읽기 전용 트랜잭션 안에서 실행하고 끝나면 되돌립니다(`default_transaction_read_only=on`).
- SELECT, WITH, COPY (...) TO STDOUT, SHOW, EXPLAIN, TABLE, VALUES로 시작하지 않는 문장은 접속 전에 거부합니다.
- `run_extract.py`는 이미 있는 파일에 쓰지 않습니다. 새 추출은 날짜가 붙은 새 폴더(`00_Data/extract_YYYYMMDD/`)에 둡니다.
