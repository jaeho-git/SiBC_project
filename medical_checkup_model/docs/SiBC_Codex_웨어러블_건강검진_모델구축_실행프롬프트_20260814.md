# SiBC 자율형 웨어러블–건강검진 예측 모델 구축 실행 프롬프트

## 사용 방법

아래 프롬프트 전체를 Codex에 전달한다. 이 프롬프트는 **실제 모델 구축 작업**을 지시하지만, 데이터·시간 정렬·독립 검증 조건을 충족하지 못하면 임의의 예측값이나 성능 수치를 만들지 않고 `BLOCKED_BY_DATA`로 안전하게 종료하도록 설계돼 있다.

모델 구축 전에 다음 기준 문서를 반드시 읽는다.

- `docs/SiBC_웨어러블_건강검진_예측_모델구축계획_20260814.md`
- `docs/SiBC_웨어러블_건강검진_예측_프로젝트_컨텍스트.md`
- 기존 프로젝트의 `README.md`, `configs/`, `sql/`, `src/`, `tests/`

---

```text
당신은 임상 예측 모델, 웨어러블 시계열 분석, 데이터 엔지니어링, MLOps,
통계 검증, 보안 및 초심자용 기술 보고를 담당하는 수석 ML 엔지니어다.

0. 작업 목표와 우선순위
=========================

SiBC의 목표는 예측 기준시점 이전에 수집된 웨어러블/라이프로그로 건강검진 관련
현재 상태를 추정하는 것이다. 대상은 다음 두 종류를 모두 포함한다.

- M0: 건강검진 이력이 없거나 사용하지 않는 사용자에게 웨어러블만으로 예측
- M1/M2: 과거 건강검진이 있는 사용자에게 과거 실제값과 이후 웨어러블을 이용해
  현재 절대값 또는 변화량을 예측

이번 작업의 성공은 ‘무조건 예측 모델을 생성하는 것’이 아니다. 데이터 계약,
시간 정렬, 최소 표본, 독립 검증을 통과했을 때에만 모델·예측·성능을 생성하고,
그렇지 않으면 근거 있는 BLOCKED_BY_DATA 보고서와 다음 데이터 요구사항을
완성하는 것이다.

실제 건강검진값(actual_*), 웨어러블 직접 측정 요약(measured_*), 모델 예측(pred_*)은
절대로 혼용하거나 서로 덮어쓰지 마라. 직접 측정 요약은 모델 예측이 아니다.

1. 고정 프로젝트 경로와 기존 구조
===================================

PROJECT_ROOT는 반드시 다음 경로다.

/Users/jaeho.oh/Downloads/SiBC/SiBC_project/medical_checkup_model

모든 탐색, 코드 작성, 테스트, 실행, 산출물 저장은 PROJECT_ROOT에서 수행하라.
먼저 기존 저장소 구조와 변경 사항을 읽고, 기존 사용자 파일을 삭제·초기화·덮어쓰지
말고 확장 가능한 방식으로 작업하라. Git commit/push는 사용자가 명시적으로
요청한 경우에만 수행한다.

기존 구조를 유지한다.

medical_checkup_model/
├── 00_Data/<data_env>/<snapshot_id>/
├── 01_Results/<data_env>/<run_id>/
│   ├── artifacts/
│   ├── outputs/
│   ├── reports/
│   ├── figures/
│   └── logs/
├── configs/
├── docs/
├── scripts/
├── sql/
├── src/sibc_medical_checkup/
└── tests/

새로운 최상위 data/, output/, report/, artifact/, log/ 폴더를 만들지 마라.
가명 스냅샷은 00_Data/, 실행 결과는 반드시
01_Results/<data_env>/<run_id>/ 아래에 둔다.

2. 환경 선택과 보안
====================

환경 파일의 고정 상위 경로는 다음과 같다.

/Users/jaeho.oh/Downloads/SiBC/SiBC_project

허용된 매핑만 사용한다.

- release → .env.release
- dev     → .env.dev
- stg     → .env.stg

CLI 인자는 --data-env이며 허용값은 release, dev, stg다. 기본값은 release다.
이번 최초 모델 구축은 release만 사용한다. dev 또는 stg를 읽거나 접근하거나
fallback으로 사용하지 마라. 향후 사용자가 명시적으로 요청할 때만 한 번에 하나씩
실행한다.

선택한 환경 파일을 한 번만 읽고, APP_ENV 및 SIBC_DATA_ENV가 선택값과 일치하는지
DB 접속 전에 확인하라. 실패하면 FAILED_ENV_IDENTITY로 중단하라. 선택하지 않은
.env 파일의 존재·내용·접속 가능 여부도 확인하지 마라.

DB는 읽기 전용 세션으로만 접속한다. 다음을 모두 준수하라.

- default_transaction_read_only=on을 확인한다.
- SELECT/WITH 기반의 승인된 SQL allowlist만 사용한다.
- INSERT, UPDATE, DELETE, MERGE, DDL, COPY, CALL, write-back을 금지한다.
- DB 비밀번호, 호스트, 접속 문자열, 원본 user_id, 원시 건강검진 JSON을 화면,
  로그, 산출물, Git에 출력하지 않는다.
- 원본 사용자 ID는 메모리에서 HMAC 가명키로 변환한 뒤에만 디스크에 저장한다.
- 실행 종료 전 산출물의 비밀정보·식별자 누출 검사를 수행한다.

3. 건강검진 정답과 시간 원칙
==============================

건강검진 정답의 유일한 논리 원천은 다음이다.

discovery.disc_medical_user_info.user_health_sn.health_info_data

사용자 연결이 필요할 때는 disc_medical_user_info.user_health_sn에서 참조한
disc_health_user_info.user_health_sn을 통해 health_info_data를 읽는다. 다른
건강검진 원천을 비교·병합·대조·정답으로 사용하지 마라.

건강검진의 임상 측정일은 health_info_data[].measuredDt만 사용한다.
ins_dt, upd_dt, 적재 시각은 계보 확인에는 사용 가능하지만 임상 정답시각으로
사용하면 안 된다.

시간 누출 방지 규칙:

- 라벨 시점 T의 특징은 반드시 T 이전에 끝나야 한다.
- feature_end <= label_time 검사를 코드·테스트·manifest에 기록한다.
- T 이후 웨어러블을 T의 건강검진 정답에 사용하면 즉시 실패시킨다.
- 과거 검진값은 M1/M2에서 T 이전 입력으로 사용할 수 있지만, 성능 평가는
  T 이후의 새로운 건강검진 정답으로만 한다.

4. 허용된 lifelog와 *_sn 연결
==============================

모든 아래 16개 테이블을 데이터 감사 및 특징 후보에 포함하되, 실제 특징 사용은
시간·품질·출처 검사를 통과한 값에 한정한다.

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

중요한 연결 규칙:

- 측정 테이블의 user_lifelog_sn은 disc_lifelog_user_info.user_lifelog_sn을 통해
  사용자·플랫폼·기기·시간대 정보와 연결한다.
- sleep_detail.user_sleep_sn은 sleep.user_sleep_sn을 통해 sleep과 연결한다.
- oxygen_saturation.user_sleep_sn은 선택적 수면 연결이다. 값이 채워진 경우
  수면 세션 존재 여부와 최종 사용자 일치 여부를 검사한다.
- user_lifelog_sn 값만 같다고 사용자 동일성을 가정하지 말고, 상위 user_info의
  사용자 키로 최종 검증한다.
- lifelog_raw_data, inbody_data, meal_data, device JSON은 키·형태·결측률·버전이
  문서화되기 전에는 블랙박스 특징으로 통째로 넣지 마라.

food와 meal은 현재 스키마상 실제 섭취 임상시각이 확인되지 않았다. ins_dt/upd_dt를
식사 발생 시각으로 간주하지 말고, 실제 event time과 입력/연동 출처가 검증되기
전까지 시간 정렬 건강검진 모델의 특징에서 제외하라.

5. Samsung Health Data SDK 통합 범위
=====================================

다음 파일의 01_통합 매트릭스를 기준으로 한다.

/Users/jaeho.oh/Downloads/Samsung_SDK_취득가능데이터_통합활용전략_20260731_검토수정본.xlsx

Samsung / Health Data SDK 열이 ○ 또는 △인 항목만 취득 가능 후보로 다룬다.
✕, -, 빈칸, Sensor SDK 단독 항목은 이 작업의 Data SDK 통합 범위에서 제외한다.

Data SDK 후보 19개:

걸음수, 활동/칼로리, 운동 세션, 운동 GPS 경로, 일상 심박수, 부정맥/AFib 알림,
혈압, SpO₂, 피부/체온, 수면(총/세션), 수면 단계, 수면 점수, 수면무호흡,
체중·체성분, 혈당, 식이(영양), 물, VO2max, 에너지/준비도 점수.

Data SDK 레코드가 discovery DB에 실제로 존재하는지 매 실행에서 스키마·행수·최신
이벤트시각·사용자 수·권한/기기/설정 조건을 감사하라. 존재하지 않는 타입을
만들어 내거나 현재 lifelog 테이블에 있다고 가정하지 마라.

우선 통합 가치가 높은 데이터는 운동 세션, VO2max, 활동/칼로리 실제 집계값,
실제 섭취시각이 있는 Nutrition, 수면 단계, 그리고 혈압·체성분·혈당의 기기/
측정방법/출처 메타데이터다.

AFib 알림과 수면무호흡은 일반 건강검진 수치 회귀의 기본 입력으로 사용하지 말고,
진단 대체가 아닌 안전 플래그·의료진 확인 경로로 분리하라. 수면 점수와 에너지
점수는 원천 심박·수면·활동 특징만 쓴 모델과 같은 독립 평가 세트에서 추가 가치가
입증될 때에만 보조 특징으로 채택하라.

6. 데이터 감사와 스냅샷
=========================

실제 학습 전에 아래 항목을 data card, feature registry, lineage registry에 기록하라.

- 16개 소스별 행 수, 가명 사용자 수, 최소/최대 event time, 최근 적재시각
- 주요 수치 컬럼의 단위·결측·이상값·sentinel·중복 의심률
- activity_type, heartrate_se_cd, sleep_stage, measured_meal_status 등 코드값과
  공식 코드북 존재 여부
- bloodpressure의 data_origin, recording_method, device JSON 완결성
- bodyfat.inbody_data의 키·기기 모델·단위·측정조건
- food/meal의 실제 발생시각 유무와 적재시각 분리
- source_system, source_record_id, measurement_method, origin_device,
  app_version, algorithm_version, is_user_entered, is_external_device,
  is_derived, quality_flag의 수집 가능성
- 건강검진 라벨별 사용자 수와 M0/M1/M2 시간 정렬 사용자 수

스냅샷에는 원시 user_id와 원시 health_info_data JSON을 저장하지 말고, 가명키와
필요 최소의 정규화 값·계보·품질 지표만 저장하라.

7. 목표, 특징, 모델 경로
==========================

초기 회귀 목표는 다음 10개다.

- sbp, dbp, weight, bmi, waist
- fasting_glucose, triglyceride, hdl_cholesterol, ldl_cholesterol,
  total_cholesterol

대사위험과 간기능 위험은 임상 정의·임계값·사건 수가 사전 승인된 경우에만
분류 목표로 추가한다. AST, ALT, GGT, 혈색소, eGFR, 크레아티닌, 요단백 등은
현재 웨어러블과의 생물학적 연결·교란요인·정답 표본을 별도 검토한 뒤 연구 후보로
유지하라.

기본 관측창은 T 직전 7일, 30일, 90일이며 데이터가 충분할 때 180일도 비교한다.
각 창에서 수준(평균/중앙값/분위수), 변동성(SD/IQR), 추세(시간 대비 기울기),
최근 변화(7일 대 이전 23일), 규칙성(시간 표준편차), 유효일 수, 결측·출처 비율을
계산하라. 관측일 수가 적으면 수준·변동성·추세를 산출하지 말고 결측/ABSTAIN
정책을 적용하라.

M0: T 이전 웨어러블만 사용하여 T 이후 최초 건강검진을 예측한다.
M1: 이전 검진값 E0, E0 이후 T까지의 웨어러블, 경과시간으로 다음 검진 절대값을
    예측한다. E0 유지(carry-forward)와 M0를 모두 이겨야 한다.
M2: 이전 검진값 E0와 E0~E1 사이 웨어러블로 E1-E0 변화량을 예측한다. 변화 없음
    기준선을 이겨야 한다.

8. 모델 후보와 제한된 자동 보완
==================================

회귀의 기준선은 인구 중앙값, 최근 직접 측정값, M1의 이전 검진값 유지다.
후보는 Elastic Net과 Histogram Gradient Boosting이다.

분류의 기준선은 유병률/사전 승인된 단순 규칙이며, 후보는 보정된 Logistic
Regression과 보정된 Histogram Gradient Boosting이다.

‘최적 모델’은 교차검증 점수만 최대인 모델이 아니다. 봉인된 독립 평가에서 기준선
대비 개선, calibration, 예측구간, coverage, ABSTAIN 비율, 하위집단 안정성,
재현성, 모델 단순성을 함께 만족하는 모델이다.

폐쇄루프 품질관리에서 허용되는 자동 보완:

- 스키마/형식 오류 수정
- 단위 또는 별칭 매핑 수정과 계보 기록
- 문서화된 sentinel/불가능값 제거
- 사전 정의 특징 창 비교
- 특징 축소 또는 모델 단순화
- 학습·검증 내부에서만 하이퍼파라미터 조정
- calibration 또는 예측구간 방법 비교

다음은 금지한다.

- 봉인 독립 평가를 반복 확인하며 튜닝
- 라벨 정의·임상 허용오차·품질 gate를 성능 때문에 완화
- 실제 정답 부족을 합성 성능·대리 라벨·actual 복사로 대체
- 환경 간 데이터 병합
- 승인 범위 밖 데이터 사용
- actual_*를 pred_*로 복사

보완 예산과 변경 사유를 target/route별 experiment ledger에 기록하라.

9. 검증과 승격 규칙
=====================

사용자 단위 분리와 시간 순서 분리를 함께 적용하라. 동일 사용자가 학습과 독립
평가 양쪽에 존재하면 안 된다. 모델·특징 선택 과정에서는 봉인된 독립 평가를
사용하지 마라.

초기 최소 gate:

- 학습 사용자 100명 이상
- 독립 평가 사용자 30명 이상
- 분류는 양성·음성 사건 각각 30건 이상
- 목표별 라벨과 정답 이전 웨어러블 coverage 조건 충족

회귀 지표와 의미:

- MAE = 평균 |실제값-예측값|. 원래 단위의 평균 오차이며 작을수록 좋다.
- RMSE = 제곱오차 평균의 제곱근. 큰 오차에 더 민감하며 작을수록 좋다.
- R² = 평균 예측 대비 설명된 분산 비율. 클수록 좋고 음수도 가능하다.
- Bias = 평균(예측-실제). 0에 가까울수록 전체 과대/과소 예측이 작다.
- Calibration slope/intercept = 예측 분포의 과도한 압축/확산과 평균 편향을 본다.
- PICP = 선언한 예측구간이 실제값을 포함한 비율. 예를 들어 90% 구간이면 약 90%에
  가까운지 본다.

분류 지표와 의미:

- AUROC: 양성/음성의 순위 구분력. 불균형 상황에서 단독 사용 금지.
- AUPRC: 양성 사례 탐지 성능. 유병률과 함께 보고.
- Brier score = 평균(예측확률-실제라벨)^2. 확률의 정확도와 보정을 함께 본다.
- Calibration plot: 예측 확률 구간별 실제 발생률. 위험확률 제공의 필수 근거.
- 민감도/특이도/PPV/NPV: 사전 승인된 임계값에서만 계산.

모든 목표에 대해 기준선 대비 표, bootstrap 95% CI, 기기·성별·연령·수집량·출처별
하위집단 성능, coverage 및 ABSTAIN 비율을 보고하라. 표본이 부족하면 성능 지표를
계산하지 말고 성능 미산출 사유를 보고하라.

10. 결과물, 그림, 문서
========================

각 실행은 01_Results/<data_env>/<run_id>/에 다음을 생성하라.

artifacts/
- reproducibility_manifest.json
- feature_registry.csv/json
- target_registry.csv/json
- target_alias_unit_lineage.csv/json
- data-quality and checksums artifacts

outputs/
- user_health_prediction_wide.csv 및 XLSX
- prediction_audit_long.csv/parquet
- prospective_validation.csv/parquet (가능한 경우)

reports/
- data_card.md
- target별 model_card_<target>.md
- performance_unavailable.md 또는 검증된 성능 보고서
- 초심자용 결과보고서 MD와 DOCX
- TRIPOD+AI checklist 및 편향/적용성 자체 점검

figures/
- 데이터 퍼널, source coverage, 시간 정렬, coverage/ABSTAIN 그림
- 검증이 통과한 뒤에만 실제-예측 산점도, 잔차/오차 분포, 기준선 비교,
  calibration, 예측구간 포함률, ROC/PR, 하위집단 성능 그림

초심자용 보고서는 ‘데이터 감사 그림’과 ‘모델 성능 그림’을 명확히 구분하고,
현재 모델이 없는 경우 성능이 없는 이유를 첫 페이지에 표시하라.

DOCX 결과보고서를 만들 때는 본문, 제목, 표, 머리말, 꼬리말을 Pretendard 글꼴과
검은색 글씨로 통일하라. 표의 가독성을 점검하고 페이지 렌더링으로 잘림/겹침을
검증하라.

최종 사용자 파일의 한 행은 사용자 한 명이며 다음을 구분한다.

- actual_* 및 actual_*_measured_dt: 최신 실제 건강검진값과 검진일
- measured_* 및 source: 최근 웨어러블 직접 측정 요약과 출처
- pred_*, pred_*_lower, pred_*_upper: 독립 검증 후에만 채우는 예측과 구간
- prediction_route, coverage_grade, abstain_reason, data_provenance_summary

11. 테스트와 완료 보고
=======================

구현·수정 후에는 최소한 다음을 실행하라.

cd /Users/jaeho.oh/Downloads/SiBC/SiBC_project/medical_checkup_model
PYTHONPATH=src pytest -q
PYTHONPATH=src python -m sibc_medical_checkup.cli preflight --data-env release
PYTHONPATH=src python -m sibc_medical_checkup.cli run --data-env release

환경을 선택하지 않은 경우 dev/stg 명령을 실행하지 마라. 실패한 테스트나 데이터
gate는 숨기지 말고 원인·영향·수정 여부를 기록하라.

최종 응답은 다음 순서로 작성하라.

1. 결론: 검증된 모델 생성 여부 또는 BLOCKED_BY_DATA 여부
2. 근거: 데이터 범위, run ID, 표본 수, 시간 정렬, target별 상태
3. 변경 파일: 생성/수정 파일과 역할
4. 검증: 실행한 테스트, 품질 검사, 성능 지표 또는 미산출 사유
5. 결과 위치: 주요 CSV/XLSX/MD/DOCX/그림 경로
6. 제한사항과 다음 의사결정: 추가 데이터·임상 승인·다음 검진 연결 필요사항

어떤 경우에도 건강검진·진단·치료 판단을 대체한다고 주장하지 마라.
```
