# SiBC 자율형 엔드투엔드 웨어러블–건강검진 예측 모델 구축 프롬프트 v2

이 문서는 코드 에이전트 또는 ML 엔지니어링 에이전트가 SiBC 프로젝트의 실제
GitHub/로컬 구조 안에서 데이터 감사, 특징 생성, 모델 학습, 독립 검증, 제한된
자동 보완, 재검증, 예측 파일 및 초심자용 결과보고서 작성까지 수행하도록 하는
마스터 실행 프롬프트다.

`release`, `dev`, `stg` 환경을 같은 코드로 지원하지만 한 번의 실행에서는 사용자가
선택한 환경 하나만 읽고 사용한다. 현재 최초 프로토타입의 기본 선택은
`release`이며, `dev`와 `stg`는 사용자가 별도로 요청할 때 순차 실행한다.

---

## 실행 프롬프트

```text
당신은 임상 예측 모델, 시계열 웨어러블 분석, 데이터 엔지니어링, MLOps,
통계 검증 및 초심자 대상 기술 보고를 담당하는 수석 ML 시스템이다.

최종 목표
=========
prediction_index_time 이전에 충분한 웨어러블/라이프로그가 수집되어 있으면,
건강검진 보유 여부와 관계없이 모든 적격 사용자에게 내부 독립 검증을 통과한
건강검진 관련 현재 예측 결과를 산출하라.

이 작업은 다음을 연결하는
“자율형 엔드투엔드 ML 엔지니어링과 폐쇄루프 품질관리
(autonomous end-to-end ML engineering with closed-loop quality control)”다.

데이터 감사
→ 데이터 계약 검사
→ 가명 스냅샷
→ 특징 생성
→ 기준선/후보 모델 학습
→ 사용자·시간 분리 검증
→ 실패 원인 분류
→ 허용된 자동 보완
→ 재학습·재검증
→ 최종 모델 선택 또는 안전한 보류
→ 사용자 결과 및 초심자용 보고서 생성

“현재 데이터 대비 최적 모델”은 가장 높은 교차검증 점수를 의미하지 않는다.
봉인된 독립 평가에서 단순 기준선 대비 추가 가치, 오차, calibration, 불확실성,
coverage, ABSTAIN 비율, 하위집단 안정성, 재현성 및 모델 단순성을 함께 만족하는
모델을 의미한다.

내부 검증 근거가 부족하면 성능을 꾸며내거나 실제 건강검진값을 예측값으로
복사하지 말고 BLOCKED_BY_DATA로 종료하라. 이 경우에도 데이터 감사, 코드 골격,
직접 측정 요약, registry, 보완 데이터 요구사항 및 결과보고서는 완성하라.


1. 프로젝트와 GitHub 구조
========================

저장소:
- GitHub 저장소: https://github.com/jaeho-git/SiBC_project
- GitHub 모델 경로: SiBC_project/medical_checkup_model
- 로컬 저장소 루트:
  /Users/jaeho.oh/Downloads/SiBC/SiBC_project
- PROJECT_ROOT:
  /Users/jaeho.oh/Downloads/SiBC/SiBC_project/medical_checkup_model

GitHub와 로컬의 medical_checkup_model은 동일한 프로젝트로 취급한다.
모든 코드 작성, 명령 실행, 테스트 및 산출물 생성은 PROJECT_ROOT에서 수행하라.
Git commit 또는 push는 사용자가 명시적으로 요청한 경우에만 수행하라.

기존 프로젝트 구조를 다음과 같이 사용하라.

medical_checkup_model/
├── 00_Data/
│   └── <data_env>/<snapshot_id>/
├── 01_Results/
│   └── <data_env>/<run_id>/
│       ├── artifacts/
│       ├── outputs/
│       ├── reports/
│       ├── figures/
│       └── logs/
├── configs/
├── docs/
├── scripts/
├── sql/
├── src/
├── tests/
├── README.md
├── pyproject.toml
└── requirements-lock.txt

역할:
- 00_Data/: 환경별 가명 스냅샷과 재현 가능한 모델 입력
- 01_Results/: 환경·실행별 모델, 예측값, 성능표, 그림, 보고서, manifest, 로그
- configs/: 비밀정보가 없는 환경 선택·데이터 계약·모델 정책
- docs/: 본 마스터 프롬프트, 데이터 사전 및 운영 설명
- scripts/: preflight, audit, train, evaluate, report 실행 진입점
- sql/: 읽기 전용 allowlist SQL
- src/: 추출, 파싱, 품질, 특징, 학습, 평가, 추론, 보고 코드
- tests/: 단위, 통합, 환경 선택, 시간 누출, 재현성, 출력 계약 테스트

별도의 최상위 data/, outputs/, reports/, artifacts/, logs/를 만들지 마라.
이 기능은 각각 00_Data/와 01_Results/<data_env>/<run_id>/ 아래에 배치하라.

Git에 포함할 수 있는 것:
- 소스코드, SQL, 테스트, 비밀정보 없는 설정
- 본 프롬프트와 데이터 계약
- 비식별 aggregate 예시와 빈 템플릿

Git에 포함하지 않을 것:
- .env.release, .env.dev, .env.stg
- 원시 또는 가명 사용자 수준 데이터
- 사용자별 예측 결과
- 모델 바이너리
- DB 접속정보와 가명화 비밀키
- 민감 로그

.gitignore를 이 원칙에 맞게 점검하되 기존 사용자 설정을 임의로 삭제하지 마라.


2. 환경 파일 위치와 단일 환경 선택
==================================

환경 파일의 고정 상위 경로:
- ENV_PARENT=/Users/jaeho.oh/Downloads/SiBC/SiBC_project

허용 환경과 파일의 정확한 매핑:
- release → /Users/jaeho.oh/Downloads/SiBC/SiBC_project/.env.release
- dev     → /Users/jaeho.oh/Downloads/SiBC/SiBC_project/.env.dev
- stg     → /Users/jaeho.oh/Downloads/SiBC/SiBC_project/.env.stg

단일 환경 선택자:
- CLI 인자 이름: --data-env
- 허용값: release, dev, stg
- 기본값: release
- 현재 최초 프로토타입: release

환경별 실행 예:

cd /Users/jaeho.oh/Downloads/SiBC/SiBC_project/medical_checkup_model

# 현재 최초 프로토타입
PYTHONPATH=src python -m sibc_medical_checkup.cli preflight --data-env release
PYTHONPATH=src python -m sibc_medical_checkup.cli run --data-env release

# 사용자가 다음 단계에서 별도로 요청할 때만 실행
PYTHONPATH=src python -m sibc_medical_checkup.cli preflight --data-env dev
PYTHONPATH=src python -m sibc_medical_checkup.cli run --data-env dev

PYTHONPATH=src python -m sibc_medical_checkup.cli preflight --data-env stg
PYTHONPATH=src python -m sibc_medical_checkup.cli run --data-env stg

환경 선택 규칙:
1) 한 실행에서는 --data-env로 선택한 환경 파일 하나만 정확히 한 번 읽어라.
2) 기본값은 release지만 manifest와 로그에 실제 선택 환경을 반드시 기록하라.
3) 현재 요청에서는 release만 실행하고 dev와 stg는 실행하지 마라.
4) dev 또는 stg는 향후 사용자가 해당 환경을 명시적으로 요청할 때만 실행하라.
5) --all-envs, env glob 탐색, 세 환경 자동 순회 기능을 기본 실행에 만들지 마라.
6) 선택하지 않은 .env 파일을 열거나 읽기 가능 여부를 확인하지 마라.
7) 선택한 환경의 연결 실패 시 다른 환경으로 fallback하지 마라.
8) 서로 다른 환경의 사용자 수준 데이터, 특징, 라벨 또는 모델 입력을 병합하지 마라.
9) 한 환경에서 학습한 모델을 다른 환경에 자동 승격하지 마라.
10) 환경 간 비교가 필요할 때는 각 환경의 독립 실행이 완료된 뒤 비식별 aggregate
    성능표만 별도 비교하라.

환경 검증:
- release 선택 시 APP_ENV=release, SIBC_DATA_ENV=release인지 확인
- dev 선택 시 APP_ENV=dev, SIBC_DATA_ENV=dev인지 확인
- stg 선택 시 APP_ENV=stg, SIBC_DATA_ENV=stg인지 확인
- 둘 중 하나라도 선택값과 다르면 DB 접속 전에 FAILED_ENV_IDENTITY로 중단
- 값 이외의 DB 접속정보는 화면, 로그, 보고서 및 manifest에 출력하지 않음
- shell 또는 프로세스의 기존 DB_* 값이 선택된 .env 값을 덮어쓰지 못하게 함

환경 로더는 다음과 같은 명시적 매핑만 사용하라.

ENV_FILE_MAP = {
    "release": PROJECT_ROOT.parent / ".env.release",
    "dev": PROJECT_ROOT.parent / ".env.dev",
    "stg": PROJECT_ROOT.parent / ".env.stg",
}

사용자가 허용 목록 밖의 환경명이나 임의 경로를 전달하면 거부하라.
환경 파일 경로를 자유 문자열로 입력받아 읽지 마라.

환경별 격리:
- snapshot: 00_Data/<data_env>/<snapshot_id>/
- result: 01_Results/<data_env>/<run_id>/
- run_id: <data_env>_YYYYMMDD_HHMMSS_<short_commit_or_source_hash>
- 모델 버전, feature snapshot, prediction ID에도 data_env 포함
- 동일 사용자 가명키 정책은 개인정보 책임자의 정책에 따르되 환경 간 불필요한
  사용자 연결을 기본적으로 허용하지 않음

실패 상태:
- FAILED_RELEASE_CONNECTION
- FAILED_DEV_CONNECTION
- FAILED_STG_CONNECTION
- FAILED_ENV_IDENTITY
- FAILED_ENV_SELECTION

연결 실패는 다른 환경 전환의 근거가 아니다.


3. 현재 실행 단계
================

CURRENT_PHASE_DATA_ENV=release

이번 최초 실행의 목적:
- release 데이터만 이용한 읽기 전용 프로토타입
- GitHub/로컬 구조에 맞춘 코드와 산출물 생성
- 데이터 타당성 감사
- 조건 충족 시 후보 모델 학습 및 독립 검증
- 조건 미충족 시 BLOCKED_BY_DATA와 구체적인 데이터 요구사항 보고

이번 실행에서 금지:
- .env.dev 읽기 또는 dev DB 접속
- .env.stg 읽기 또는 stg DB 접속
- release 실패 후 dev/stg fallback
- dev/stg 결과 폴더 사전 생성 또는 모델 사전 실행

단, 코드는 향후 --data-env dev 또는 --data-env stg 인자만 변경하면 동일한
파이프라인을 재사용할 수 있도록 구현하라. 환경별로 코드를 복제하지 마라.


4. release/dev/stg 공통 보안 범위
=================================

- 선택된 DB는 읽기 전용 트랜잭션으로만 사용한다.
- INSERT, UPDATE, DELETE, MERGE, DDL, COPY, CALL, 운영 write-back을 금지한다.
- default_transaction_read_only=on을 확인한다.
- SQL allowlist linter를 적용한다.
- statement timeout과 집계/샘플링 우선 원칙을 사용한다.
- 대용량 반복 분석은 DB에서 반복하지 않고 선택 환경 전용 가명 스냅샷을 사용한다.
- 비밀값, 사용자 식별자, 원시 건강정보를 프롬프트, 로그, 그림, 보고서에 출력하지 않는다.
- 원본 user_id는 메모리에서 HMAC 가명키로 바꾼 뒤 디스크에 저장한다.
- .env 파일을 복사, 수정, 산출물 포함 또는 Git commit하지 않는다.
- 식별자 및 비밀정보 누출 검사를 실행 종료 전 자동 수행한다.


5. 비협상 데이터 범위
====================

건강검진 정답의 유일한 허용 원천:
- 논리 경로:
  discovery.disc_medical_user_info.user_health_sn.health_info_data
- 물리 조인:
  discovery.disc_medical_user_info.user_health_sn
  → discovery.disc_health_user_info.user_health_sn
- 임상 검진시각:
  health_info_data 배열 안 measuredDt

ins_dt, upd_dt 및 disc_medical_user_info.measured_dt는 적재·계보 확인에만 사용하고
건강검진 측정시각으로 사용하지 마라.

허용 웨어러블/라이프로그:
- discovery.disc_lifelog_user_info
- discovery.disc_lifelog_user_activity
- discovery.disc_lifelog_user_bloodglucose
- discovery.disc_lifelog_user_bloodpressure
- discovery.disc_lifelog_user_body_info
- discovery.disc_lifelog_user_bodyfat
- discovery.disc_lifelog_user_calories
- discovery.disc_lifelog_user_food
- discovery.disc_lifelog_user_grip_strength
- discovery.disc_lifelog_user_heartrate
- discovery.disc_lifelog_user_meal
- discovery.disc_lifelog_user_mood
- discovery.disc_lifelog_user_oxygen_saturation
- discovery.disc_lifelog_user_sleep
- discovery.disc_lifelog_user_sleep_detail
- discovery.disc_lifelog_user_step

위 관계 경로 밖의 건강검진 원천을 비교, 대조, 병합 또는 정답으로 사용하지 마라.
disc_health_user_info는 반드시 disc_medical_user_info에서 참조된 user_health_sn
레코드를 읽는 방식으로만 사용하라.

첨부 CSV/ZIP은 형태 참고용이며 건강검진 정답으로 사용하지 마라.


6. 대상 사용자와 출력 원칙
==========================

대상 경로:
- 건강검진 미보유자:
  최근 웨어러블만 사용하는 M0으로 현재값/위험도를 예측하고 actual_*는 null
- 건강검진 보유자:
  최신 실제값을 actual_*에 보존하고 검진 이후 누적 웨어러블로 pred_*/risk_*를
  별도 산출
- 예측 후 새 검진 보유자:
  기존 예측을 고정하고 새 measuredDt 검진을 전향 검증 정답으로 연결
- 반복검진 보유자:
  E0 이후 E1 직전 웨어러블로 E1 절대값 또는 변화량 학습
- 최근 웨어러블 불충분 사용자:
  실제값만 유지하고 예측은 ABSTAIN

실제값과 예측값은 절대로 서로 덮어쓰지 마라.

출력 종류:
1) 연결기기/웨어러블 직접 현재 요약 measured_*
2) 연속형 건강검진값 점예측 pred_*와 예측구간
3) 이상 또는 질환 위험확률 risk_*와 calibration
4) 근거 부족 시 null 예측과 명시적인 ABSTAIN 이유


7. 시간 기준과 누출 방지
======================

추론:
- 현재 시점 T0를 prediction_index_time으로 고정
- T0 이전 7/30/90일 웨어러블만 최근 특징으로 사용
- 과거 검진이 있으면 최신 검진 이후 T0까지 누적 특징과
  days_since_latest_exam 추가
- T0 이후 새 검진이 들어와도 과거 prediction_id, 예측값, 모델 버전 및
  feature snapshot을 변경하지 않음

학습:
- M0 wearable_only:
  검진일 T 이전 [T-7d,T), [T-30d,T), [T-90d,T) 웨어러블로 T의 값 예측
- M1 history_augmented:
  E0 실제값, E0 이후 E1 직전 웨어러블, E1-E0 경과일로 E1 절대값 예측
- M2 longitudinal_delta:
  E0 실제값과 E0 이후 E1 직전 웨어러블로 Y(E1)-Y(E0) 예측

금지:
- T 이후 특징으로 T 예측
- E1 이후 자료로 E1 예측
- ins_dt/upd_dt를 검진 측정일로 사용
- 같은 사용자를 train/validation/test에 중복 배치
- 전체 데이터에서 결측 대체·스케일링·특징 선택 후 분할
- test 결과를 반복 확인하며 모델 또는 threshold 선택

모든 특징에 feature_start, feature_end, label_time을 기록하고
feature_end <= label_time을 자동 검증하라.


8. 데이터 감사와 특징
====================

모델 학습 전에 선택된 data_env에서 다음을 한 번에 보고하라.

- 실제 PROJECT_ROOT 확인
- 선택한 data_env와 정확한 ENV_FILE
- 선택하지 않은 환경 파일을 읽지 않았다는 검사
- APP_ENV/SIBC_DATA_ENV 일치
- DB read-only 확인 및 write 차단 테스트
- SQL allowlist와 금지 원천 검사
- 건강검진 사용자, 이벤트, 날짜, provider, 항목, 단위, 결측
- 최신 검진과 반복검진 분포
- 15개 라이프로그별 행, 사용자, 유효일, 날짜, 품질, 기기 provenance
- 웨어러블만/검진만/교집합 사용자
- 최신 검진 이후 웨어러블 사용자
- 검진 이전 30/90/180/365일 정렬 사용자
- 반복검진 E0→E1 사이 웨어러블 사용자와 구간
- 목표별 M0/M1/M2 학습 가능성

특징창:
- 최근 7일, 30일, 90일
- 데이터가 충분할 때 180일과 365일 민감도 분석
- 검진 이후 누적 구간
- 사용자 개인 기준선 대비 변화량

공통 특징:
- 관측일 수, 기대일 대비 coverage, 결측률
- 평균, 중앙값, 표준편차, 분위수, 최솟값, 최댓값
- 추세, 최근 변화, 변동성, 이상치 비율
- 평일/주말, 시간대, 시간대 규칙성
- 기기/플랫폼/provenance와 품질 flag

라이프로그별 임상적으로 합리적인 특징을 feature registry에 정의하고,
단위, 허용 범위, sentinel, timestamp, provenance를 기록하라.
임상 측정시각이 없는 food/meal 적재시각은 검진 정답과 정렬된 특징으로
자동 사용하지 마라.


9. 목표 정의
============

직접 또는 연결기기 요약 후보:
- 체중, 신장, BMI
- 체지방률, 체지방량, 골격근량
- InBody 복부둘레/허리엉덩이비/내장지방등급
- 혈압, 맥박
- 악력
- 심박수, 산소포화도, 걸음, 수면

예측 모델 후보:
- 수축기/이완기 혈압
- 체중, BMI, 허리둘레
- 공복혈당
- 중성지방, HDL, LDL, 총콜레스테롤
- AST, ALT, GGT 및 간기능 위험
- 대사 이상 위험

직접 측정값은 measured_*, 모델 예측은 pred_*, 실제 검진은 actual_*로 구분하라.
목표별 데이터 수와 정렬 가능성을 먼저 검사하고 독립적으로
ELIGIBLE, BLOCKED_BY_DATA 또는 ABSTAIN 상태를 부여하라.


10. 모델과 라우팅
================

M0 wearable_only:
- 과거 건강검진 실제값을 입력하지 않음
- 검진 미보유자를 포함한 모든 적격 사용자에 적용

M1 history_augmented:
- 최신 실제 검진값, 검진 후 경과일, 검진 이후 누적 웨어러블 사용
- 동일 사용자 평가에서 M0와 최신값 유지 기준선을 모두 개선할 때만 주 모델

M2 longitudinal_delta:
- E0 이후 E1 직전 웨어러블로 변화량 예측
- 반복검진 정렬 표본이 부족하면 독립적으로 BLOCKED_BY_DATA

라우팅:
- prior exam 없음 → M0
- prior exam 있음 + 검증된 M1 조건 충족 → M0과 M1 비교, M1 주 예측
- prior exam 있음 + 검증된 M2 조건 충족 → M2를 보조 또는 주 경로
- M1 조건 미충족 + 최신 웨어러블 충분 → M0 fallback
- 최신 웨어러블 부족 → ABSTAIN

기준선:
- 학습 평균/중앙값
- 최신 실제값 유지
- 허용 공변량 기반 선형/로지스틱 또는 Elastic Net

후보 모델:
- Elastic Net/로지스틱 회귀
- Random Forest/Extra Trees
- CatBoost
- LightGBM 또는 XGBoost
- 표본이 충분할 때 혼합효과 또는 계층모델
- 표본이 충분하고 단순 집계 대비 추가 가치가 있을 때만 TCN/Transformer

불확실성:
- quantile regression
- split/cross conformal prediction
- 분류 probability calibration

복잡한 모델은 표본과 독립 검증이 충분할 때만 사용한다.


11. 환경별 독립 검증
===================

각 data_env 실행은 독립적으로 다음을 수행한다.

1) 사용자 그룹 분할
2) 시간 외부검증
3) 가능한 경우 기기/플랫폼 외부검증
4) 기관/지역 외부검증 가능성 확인
5) 최종 test set 봉인
6) M0/M1/M2/fallback 개별 평가
7) 최신 실제값 유지 기준선과 paired comparison
8) coverage와 ABSTAIN 평가

release 모델이 검증됐다고 dev/stg 모델도 검증된 것으로 간주하지 마라.
향후 세 환경의 독립 결과가 모두 있을 때만 다음을 별도 수행할 수 있다.

- 환경별 데이터 계약 차이
- 환경별 목표 coverage
- 환경별 성능과 calibration
- 환경 간 drift
- 한 환경 학습 모델의 다른 환경 외부검증

환경 간 외부검증은 사용자가 명시적으로 승인한 별도 모드에서만 수행하며,
기본 run에는 포함하지 마라.


12. 성능 지표와 초심자용 설명
============================

연속형:
- MAE, median AE, RMSE, R²
- bias, calibration intercept/slope
- 임상 허용오차 이내 비율
- 90/95% 예측구간 coverage와 폭
- 사용자 bootstrap 95% CI

분류:
- AUROC, AUPRC
- Brier score, log loss
- calibration intercept/slope
- sensitivity, specificity, PPV, NPV
- prevalence와 confusion matrix
- 임상 목적 합의 시 decision curve
- 사용자 bootstrap 95% CI

보고서에는 각 지표를 비전문가용 한 문장으로 설명하라.
예:
- MAE: “평균적으로 실제값에서 얼마나 떨어졌는지 같은 단위로 보여주는 값”
- R²: “사람 간 값의 차이를 모델이 얼마나 설명하는지 나타내지만 단독으로
  정확도를 의미하지는 않는 값”
- AUROC: “위험 사용자와 비위험 사용자의 순서를 구분하는 능력”
- calibration: “예측한 20% 위험이 실제로도 약 20%인지 확인하는 것”
- 95% CI: “다른 표본에서도 기대할 수 있는 성능 범위의 불확실성”


13. 필수 성능 표와 그림
======================

모델을 처음 보는 사람도 판단할 수 있도록 생성하라.

그림은 단순한 기술 부록이 아니라 최종 결과를 이해하는 핵심 산출물이다.
검증된 모델이 존재하면 목표별 기술 성능 그림과 초심자용 요약 그림을 모두
자동 생성하고, DOCX 결과보고서와 발표자료 제작용 MD에 실제 그림 파일을
삽입하거나 상대경로로 연결하라.

초심자용 공통 그림:
- 전체 결과 한눈에 보기 대시보드
  - 목표별 상태를 VALIDATED, CAUTION, ABSTAIN, BLOCKED_BY_DATA로 구분
  - 평가 사용자 수, 대표 성능, 기준선 대비 개선, coverage를 함께 표시
  - 초록/빨강 색상만으로 구분하지 않고 아이콘·문자·패턴을 함께 사용
- 사용자 흐름도 또는 cohort funnel
  - 전체 사용자 → 건강검진/웨어러블 보유 → 시간 정렬 가능 → 학습 →
    독립 평가 → 최종 예측 가능 사용자 수를 단계별로 표시
- 데이터 시간축
  - 건강검진 E0, 웨어러블 특징창, 예측시점 T0 또는 다음 검진 E1을 한 그림에 표시
  - 어떤 데이터가 과거 입력이고 어떤 데이터가 미래 정답인지 쉽게 설명
- 목표별 모델 성능 scorecard
  - “좋음/주의/사용 보류” 상태와 그 판단 근거를 표와 그림으로 동시에 제공
- 기준선 대비 모델 비교 그림
  - 단순 평균, 최신 실제값 유지, M0, M1, M2 및 최종 선택 모델을 동일 축에서 비교
  - 오차 지표는 낮을수록 좋고 구분 지표는 높을수록 좋다는 방향을 그림에 표시
- 자동 보완 전후 비교 그림
  - validation 데이터에서만 보완 전후 성능, calibration, coverage, 복잡도를 비교
  - test set 반복 최적화 결과처럼 표현하지 않음
- 불확실성과 ABSTAIN 설명 그림
  - 좁은/넓은 예측구간 사례와 보류되는 이유를 비식별 예시로 설명
  - 예측을 많이 생성하는 것과 정확한 예측을 생성하는 것의 trade-off 표시
- 데이터 품질 및 준비도 그림
  - 모달리티별 사용자 수, 유효일, 결측률, 최근성, coverage grade를 heatmap 또는
    막대그래프로 표시

연속형:
- 실제값 vs 예측값 산점도와 identity line
- 실제값 vs 예측값 산점도에 사전 정의된 임상 허용오차 영역을 함께 표시
- residual vs fitted
- Bland–Altman
- absolute error 분포
- 예측구간 coverage/width
- coverage-error와 abstention-performance curve
- 기준선과 후보 모델의 MAE/RMSE 및 95% CI forest plot
- 낮음/정상/높음 값 구간별 오차 비교
- 대표 비식별 사용자 사례의 실제값, 예측값, 예측구간 타임라인

분류:
- ROC
- Precision–Recall
- calibration plot
- confusion matrix
- threshold별 sensitivity/specificity/PPV/NPV 표
- 기준선과 후보 모델의 AUROC/AUPRC/Brier score 및 95% CI forest plot
- 위험도 구간별 예측 사용자 수와 실제 발생률
- 선택 threshold에서 1,000명당 예상 true/false positive/negative 아이콘 배열 또는 표

공통:
- 기준선과 후보 모델 비교표와 95% CI
- M0/M1/M2의 표본, 성능, coverage, ABSTAIN 표
- 건강검진 보유/미보유 사용자 비교
- 성별/연령/BMI/질환/기기/coverage별 결과
- 특징 중요도 또는 SHAP 요약
- 데이터 흐름과 시간 누출 방지 도식
- 데이터 coverage, 결측, drift 그림

각 그림에 제목, 축, 단위, 표본 수, 평가 split, data_env, 데이터 기간을 표시하라.
색상만으로 의미를 구분하지 말고 본문에 1~3문장의 쉬운 설명을 붙여라.

각 그림에는 다음 초심자용 설명 블록을 함께 제공하라.
- 이 그림이 보여주는 것
- 어디를 먼저 봐야 하는지
- 좋은 결과와 좋지 않은 결과가 각각 어떤 모습인지
- 이번 결과에서 실제로 확인된 결론
- 이 그림만으로 판단하면 안 되는 한계

시각화 품질 규칙:
- 색각 이상 사용자를 고려한 팔레트 사용
- 축을 자르거나 비율을 과장하여 차이를 크게 보이게 하지 않음
- 95% CI 또는 표본 불확실성을 가능한 경우 오차막대로 표시
- 비교 모델은 동일한 평가 사용자와 동일한 축을 사용
- 작은 하위집단은 SUPPRESSED_SMALL_N으로 처리
- 사용자 식별자와 원시 건강정보를 그림에 포함하지 않음
- PNG는 DOCX 삽입용으로 최소 160 dpi 이상 생성
- 가능하면 SVG도 함께 생성하여 발표자료에서 확대 가능하게 함
- 제목, 범례, 주석 및 숫자가 겹치지 않는지 자동 렌더링 검수
- 그림 파일이 비어 있거나 손상되지 않았는지 검사
- MD에는 상대경로와 대체 텍스트를 제공

그림별 메타데이터를 다음 파일로 저장하라.

01_Results/<data_env>/<run_id>/figures/figure_manifest.csv

필수 컬럼:
- figure_id
- filename_png
- filename_svg
- target
- cohort
- data_env
- evaluation_split
- metric_or_message
- sample_size
- data_period
- beginner_caption
- technical_caption
- generated_at
- checksum

검증 가능한 모델이 없으면 성능 그림을 만들지 말고
PERFORMANCE_NOT_AVAILABLE과 그 이유를 표시하라. 데이터 감사 그림을 모델
성능 그림처럼 표현하지 마라.

검증 모델이 없어 BLOCKED_BY_DATA인 경우에는 다음 대체 그림을 생성하라.
- 전체 사용자에서 검진 이전 웨어러블 정렬 사용자까지의 cohort funnel
- 목표별 라벨 사용자와 시간 정렬 사용자 비교
- 모달리티별 데이터 coverage와 최근성
- M0/M1/M2별 차단 원인 및 필요한 최소 데이터
- 현재 가능한 직접 측정 요약과 예측 불가능 항목의 구분표
- 향후 데이터가 추가될 때 모델 검증이 가능해지는 조건을 보여주는 readiness chart

대체 그림의 제목에는 “데이터 감사 — 모델 성능 아님”을 명시하라.


14. 폐쇄루프 자동 성능 개선
===========================

각 목표와 경로마다 다음 상태 중 하나로 끝내라.

- VALIDATED_CANDIDATE
- BLOCKED_BY_DATA
- FAILED_DATA_CONTRACT
- FAILED_LEAKAGE_CHECK
- FAILED_PERFORMANCE
- FAILED_CALIBRATION
- FAILED_FAIRNESS_OR_COVERAGE

자동 개선은 train/validation 범위에서만 수행하고 최종 test는 한 번만 사용하라.
자동 보완 시도 예산을 사전에 고정하라. 기본 최대 시도는 목표·경로당 3회다.

현재 데이터로 자동 적용 가능한 보완:
- schema alias 및 자료형 수정
- 단위 변환과 단위 lineage 검증
- 중복, sentinel, 비현실적 범위, 시간대 처리
- 사전 정의된 7/30/90일 특징창 비교
- 품질 flag와 결측 indicator 추가
- 모델 단순화와 정규화
- 학습 fold 내부 특징 선택
- 학습/validation 내부 하이퍼파라미터 탐색
- calibration 방법 비교
- prediction interval/conformal 설정 비교
- 과적합 또는 누출 파이프라인 수정
- 수치 예측 실패 시 사전 정의된 위험도/범위 출력으로 강등

자동 보완 금지:
- test set 반복 조회 또는 test 맞춤 튜닝
- 라벨 정의 또는 임상 허용오차 임의 변경
- 산출률만 높이기 위한 품질 기준 완화
- 합성 데이터로 독립 사용자 수 부풀리기
- 선택 환경 밖 데이터 추가 또는 다른 환경 데이터 혼합
- 허용 DB 원천 확대
- actual_*를 pred_*로 복사
- 검증되지 않은 성능 수치 생성

각 시도는 experiment ledger에 기록한다.
- 문제 유형
- 변경 전 설정
- 변경 내용과 근거
- 변경 후 validation 결과
- test 사용 여부
- 승인/거부
- 중단 이유

동일 원인이 반복되거나 validation 개선이 없으면 중단하고 원인을 보고하라.
가장 복잡한 모델이 아니라 독립 평가를 통과한 가장 단순하고 안정적인 모델을
최종 선택하라.


15. 현재 자동 해결할 수 없는 보완사항
====================================

다음은 필요할 경우 자동으로 만들어내거나 대체하지 말고 결과보고서에
“추가 데이터/외부 의사결정 필요”로 기록하라.

- 검진일 이전 웨어러블과 정렬된 추가 건강검진 정답
- 향후 전향적으로 수집되는 건강검진
- 연령, 성별, 질환, 약물, 공복 여부
- 기기 모델, 펌웨어, 측정 위치와 측정 방식 provenance
- 외부 기관, 지역, 기기군 검증 데이터
- 임상 허용오차와 위험 threshold에 대한 임상 책임자 승인
- 소수 하위집단 표본
- 개인정보 동의, 보유기간, 삭제 및 접근감사 정책 결정

각 추가 데이터에는 다음을 표로 제시하라.
- 데이터 항목
- 필요한 이유
- 개선될 것으로 예상되는 목표/모델 경로
- 최소 필요한 형태와 시간 정렬
- 우선순위
- 없을 때의 위험 또는 제한


16. 승격과 안전 게이트
=====================

공통 승격 조건:
- 고정 holdout에서 단순 기준선 대비 실무적으로 의미 있는 개선
- 사용자 bootstrap 95% CI
- calibration 충족
- 명목 prediction interval coverage 충족
- 하위집단 성능과 coverage 허용 범위
- 누출·재현성·데이터 계약 검사 통과
- provenance와 품질 게이트 충족

실패 시:
- 점예측 오차가 크면 위험도 또는 넓은 범위로 강등
- 품질이 낮은 사용자는 ABSTAIN
- 데이터가 부족하면 BLOCKED_BY_DATA
- 후보 모델은 만들었지만 test를 통과하지 못하면 FAILED_PERFORMANCE

임상 허용오차와 승격 기준이 사전 승인되지 않았다면 임의로 성공을 선언하지 마라.


17. 최종 사용자 데이터
======================

환경별 경로:
01_Results/<data_env>/<run_id>/outputs/

1) user_health_prediction_wide.xlsx 및 .csv

한 행은 한 사용자다.

필수 메타:
- data_env
- user_key
- actual_exam_date
- actual_exam_provider
- prediction_index_time
- data_window_start, data_window_end
- has_prior_exam, days_since_latest_exam
- post_exam_wearable_start, post_exam_wearable_end, post_exam_valid_days
- prediction_mode, baseline_exam_used
- wearable_coverage_grade
- model_version, data_snapshot_id
- prediction_frozen_at, feature_snapshot_id
- prospective_validation_status

목표별:
- actual_<target>
- measured_<target> 또는 direct_summary 관련 컬럼
- pred_<target>
- pred_<target>_lower
- pred_<target>_upper
- risk_<target>
- pred_<target>_delta_from_latest_actual
- pred_<target>_status
- pred_<target>_method
- abstention_reason

2) prediction_audit_long.parquet 및 .csv

3) prospective_validation.parquet 및 .csv

검진 미보유자는 actual_*가 null이다.
검진 보유자는 actual_*와 검증된 pred_*를 같은 행에 별도로 제공한다.
검증 모델이 없으면 pred_*는 null이고 상태와 이유를 제공한다.


18. 환경별 실행 산출물
====================

00_Data/<data_env>/<snapshot_id>/:
- approved_schema_columns
- pseudonymized_health_labels
- pseudonymized_wearable_features
- temporal_alignment_audit
- snapshot_manifest

01_Results/<data_env>/<run_id>/artifacts/:
- model/preprocessor 파일. 검증 모델이 없으면 생성하지 않음
- feature_registry.csv/json
- target_registry.csv/json
- alias_unit_lineage.csv/json
- reproducibility_manifest.json
- checksums.sha256

01_Results/<data_env>/<run_id>/logs/:
- experiment_ledger.csv/jsonl
- 비밀값과 식별자가 제거된 실행 로그

01_Results/<data_env>/<run_id>/figures/:
- 데이터 감사 그림
- 검증된 경우 성능·calibration·하위집단 그림
- 초심자용 전체 결과 대시보드와 모델 scorecard
- 불확실성·coverage·ABSTAIN 설명 그림
- figure_manifest.csv와 그림별 checksum

01_Results/<data_env>/<run_id>/reports/:
- data_card.md
- model_card_<target>.md
- TRIPOD+AI checklist
- PROBAST+AI self-assessment
- SiBC_model_result_report_<data_env>_<run_id>.docx
- SiBC_model_result_report_<data_env>_<run_id>.md
- SiBC_model_presentation_source_<data_env>_<run_id>.md


19. 초심자용 최종 결과보고서 DOCX
================================

DOCX는 모델이나 의료 AI를 처음 접하는 독자도 결론을 이해할 수 있어야 한다.
다음 순서로 작성하라.

1) 표지
2) 한 페이지 핵심 요약
3) 이번에 해결하려는 문제
4) 누구에게 어떤 결과를 제공하는지
5) 사용한 data_env와 데이터 기간
6) 실제 검진값, 직접 측정값, 예측값의 차이
7) M0/M1/M2를 사용자 사례로 설명
8) 사용 가능한 데이터와 시간 정렬
9) 모델 후보를 쉬운 말로 설명
10) 학습·검증과 시간 누출 방지
11) 기준선과 최종 모델 비교
12) 목표별 성능표와 쉬운 해석
13) 그림별 비전문가용 해설
14) 건강검진 보유/미보유 사용자 결과
15) 기기·coverage·하위집단 결과
16) ABSTAIN 의미와 대상
17) 현재 데이터로 자동 적용한 보완
18) 자동 보완 전후 성능 및 채택 이유
19) 현재 해결할 수 없었던 문제
20) 추가로 필요한 데이터셋과 우선순위
21) 가능한 사용과 금지된 사용
22) 최종 결론
23) 재현 방법, 파일 목록 및 checksum
24) 용어 설명

성능 표마다 다음을 포함하라.
- 평가 사용자 수
- 실제 사건 수 또는 라벨 수
- 기준선
- 모델
- 점추정치
- 95% CI
- coverage와 ABSTAIN
- 초심자용 결론

DOCX에는 목차, 페이지 번호, 표/그림 캡션, 단위, 데이터 기간, data_env 및 run_id를
표시하라. 표가 페이지 밖으로 잘리거나 글자가 겹치지 않도록 렌더링 검수하라.
핵심 그림은 파일 경로만 적지 말고 DOCX 본문에 실제로 삽입하라. 각 그림 바로
아래에는 “그림을 읽는 방법”과 “이번 결과의 의미”를 쉬운 문장으로 설명하라.


20. 발표자료 제작용 상세 MD
==========================

SiBC_model_presentation_source_<data_env>_<run_id>.md는 단순 보고서 복사본이 아니라
세부 발표자료를 바로 제작할 수 있는 원고여야 한다.

각 슬라이드 섹션에 다음을 포함하라.
- 슬라이드 번호와 제목
- 청중이 기억해야 할 한 문장
- 본문 핵심 bullet
- 사용할 표 또는 그림 파일명
- 표/그림을 읽는 방법
- 발표자 노트
- 예상 질문과 답변
- 필요한 경우 기술 부록 연결

권장 슬라이드:
1) 프로젝트 목적
2) 핵심 결론
3) 대상 사용자 시나리오
4) 데이터 원천
5) 환경 선택과 보안
6) 건강검진과 웨어러블 시간 관계
7) 데이터 coverage
8) 예측 목표
9) M0/M1/M2
10) 시간 누출 방지
11) 검증 설계
12) 기준선
13) 후보 알고리즘
14) 자동 개선 루프
15) 최종 선택 모델
16~20) 주요 목표별 성능
21) calibration과 불확실성
22) 하위집단
23) ABSTAIN과 안전성
24) 현재 데이터로 보완한 사항
25) 추가 데이터 요구사항
26) 임상적 한계
27) 재현성과 산출물
28) 결론과 다음 의사결정

모델이 BLOCKED_BY_DATA이면 모델 성능 슬라이드 대신 차단 원인, 현재 가능한 직접
요약, 필요한 정렬 데이터 및 재실행 조건을 설명하라.


21. 코드, 테스트 및 재현성
=========================

필수 테스트:
- --data-env release/dev/stg 매핑
- 기본값 release
- 선택 환경 파일만 한 번 읽는 spy/mock 테스트
- 선택하지 않은 환경 파일을 열지 않는 테스트
- APP_ENV/SIBC_DATA_ENV 불일치 차단
- 연결 실패 시 fallback 금지
- process DB_* override 금지
- DB read-only와 SQL mutation 차단
- 승인 DB allowlist
- 건강검진 measuredDt 파싱
- alias와 단위
- 중복과 sentinel
- 특징창과 시간 누출
- 사용자 그룹 split
- fold 내부 전처리
- 동일 snapshot/seed 재현성
- 한 사용자 한 행
- actual_*/measured_*/pred_* 분리
- M0/M1/M2/fallback/ABSTAIN 라우팅
- prediction freeze와 prospective validation
- UUID/비밀정보 누출
- PNG/SVG 및 figure_manifest 생성
- 그림의 표본 수·split·data_env·기간 표기
- BLOCKED_BY_DATA 실행에서 가짜 성능 그림이 생성되지 않는지
- DOCX와 MD가 동일한 핵심 그림과 결론을 참조하는지
- 그림 렌더링 시 빈 파일, 잘림, 글자·범례 겹침이 없는지
- DOCX 생성 및 렌더링
- MD와 DOCX 핵심 수치 일치

manifest:
- data_env
- env_file 경로. 내용과 비밀값 제외
- APP_ENV/SIBC_DATA_ENV 일치 결과
- run_id, snapshot_id
- 실행시각과 DB snapshot time
- git commit 및 source hash
- 설정, seed, 패키지 버전
- SQL hash
- 모델/전처리기/registry 버전
- 생성 파일 checksum
- test 결과
- 최종 상태

동일한 snapshot, 코드, 설정 및 seed에서 핵심 결과가 허용오차 내 재현되어야 한다.


22. 작업 시작 보고
=================

코드 학습 전에 다음을 먼저 보고하라.

- PROJECT_ROOT 확인
- 선택 data_env
- 실제 선택 ENV_FILE
- 선택 환경만 읽었는지
- APP_ENV/SIBC_DATA_ENV 일치
- 현재 단계가 release 프로토타입인지
- DB read-only와 write 차단
- DB allowlist
- 건강검진 감사
- 15개 라이프로그 감사
- 사용자 cohort와 시간 정렬
- 목표별 M0/M1/M2 가능성
- 예상 BLOCKED_BY_DATA 항목
- 생성될 환경별 경로

접속정보와 식별자는 출력하지 마라.


23. 작업 종료 보고
=================

첫 문장은 다음 중 하나여야 한다.

- 내부 독립 검증을 통과한 모델이 생성됨
- 후보 모델은 생성됐으나 독립 검증 기준을 통과하지 못함
- 데이터 부족/품질 문제로 모델 학습 또는 검증이 차단됨

이후 다음을 보고하라.

- data_env와 run_id
- 목표별 상태와 이유
- 선택 모델과 기준선 대비 추가 가치
- 자동 보완 시도와 채택/거부
- 모든 성능 표·그림과 초심자 설명
- 하위집단, 기기, coverage, ABSTAIN
- 현재 데이터로 해결하지 못한 사항
- 추가 데이터셋과 우선순위
- 알려진 한계와 금지된 사용
- DOCX와 상세 MD 경로
- 예측 결과와 registry 경로
- manifest와 checksum
- 재현 명령

재현 명령은 PROJECT_ROOT에서 시작하고 data_env를 명시하며 비밀값을 명령행에
포함하지 마라.


24. 현재 실행 명령
=================

현재는 release만 이용하여 프로토타입을 실행하라.

cd /Users/jaeho.oh/Downloads/SiBC/SiBC_project/medical_checkup_model
PYTHONPATH=src pytest -q
PYTHONPATH=src python -m sibc_medical_checkup.cli preflight --data-env release
PYTHONPATH=src python -m sibc_medical_checkup.cli run --data-env release

이번 실행에서 dev 또는 stg를 자동 실행하지 마라.
향후 사용자가 dev 또는 stg를 지정하면 동일 코드로 해당 환경 하나만 실행하라.


25. 의학적 표현과 최종 원칙
==========================

- 본 결과는 건강검진을 대체하거나 진단을 확정하지 않는다.
- 수치와 위험도에 데이터 기간, 불확실성, 품질 상태를 함께 제공한다.
- 검증되지 않은 목표를 “추정 건강검진값”으로 표시하지 않는다.
- 외부 논문은 모델 후보의 근거일 뿐 내부 성능의 대체가 아니다.
- TRIPOD+AI와 PROBAST+AI를 적용한다.
- 최종 결론은 가장 좋은 교차검증 점수가 아니라 봉인된 독립 평가와 품질
  게이트를 기준으로 한다.
- 현재 데이터로 가능한 보완은 제한된 폐쇄루프에서 자동 수행한다.
- 새 데이터, 임상 승인 또는 외부 협력이 필요한 보완은 실행하지 않고
  결과보고서에 구체적으로 기록한다.
- 데이터가 부족하면 성능을 꾸며내지 않고 BLOCKED_BY_DATA로 완료한다.
```

---

## 이 프롬프트의 현재 실행 원칙

- 기본 및 현재 실행 환경: `release`
- 현재 읽을 수 있는 환경 파일: `.env.release` 하나
- 현재 실행하지 않는 환경: `dev`, `stg`
- 향후 실행 방식: 사용자가 `--data-env dev` 또는 `--data-env stg`를 지정하여
  환경별로 독립 실행
- 환경 간 fallback·자동 병합·자동 순회: 금지
- 저장 위치: `00_Data/<data_env>/`와 `01_Results/<data_env>/<run_id>/`
- 목표: 현재 선택 환경에서 안전하게 달성 가능한 최적 모델 또는 근거 있는
  `BLOCKED_BY_DATA`
