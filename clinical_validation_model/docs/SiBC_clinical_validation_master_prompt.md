# Codex 마스터 프롬프트
## SiBC Clinical Validation Model 자동 구축 및 고도화

당신은 SiBC 프로젝트의 데이터사이언스·소프트웨어 구현 담당 Codex Agent다.

작업 대상 Git 저장소:

```text
/Users/jaeho.oh/Downloads/SiBC/SiBC_project
```

주 작업 폴더:

```text
/Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model
```

현재 Git branch는 `develop`이다. 작업 전 Git 상태를 확인하고 사용자의 기존 변경사항을 보호하라.

---

# 1. 최종 목표

`clinical_validation_model`을 구축하라.

이 모델은 시스템 Workflow에서 별도의 외부 Layer로 노출하지 않고, **Clinical Layer 내부의 독립 검증 모듈**로 동작한다.

Clinical Layer는 내부적으로 다음 두 단계로 구성한다.

```text
Clinical Layer
├── Clinical Diagnosis Engine
│   └── NANDA/Omaha 기반 진단 후보 생성
└── Clinical Validation Model
    └── 생성된 진단 후보의 근거·규칙·품질·충돌·설명 가능성 검증
```

Clinical Validation Model은 Clinical Diagnosis Engine이 생성한 진단 후보에 대해 다음을 Rule-based로 독립 검증한다.

- 진단 기준 적용 가능성
- 필수 진단 조건 충족 여부
- 보조 근거 충분성
- 사용자 데이터와 진단 기준 간 연결 적절성
- 배제 조건 및 반대 근거
- 진단 간 충돌 및 대체 진단 가능성
- 데이터 품질과 시간 정합성
- 설명 가능성과 판정 재현성
- Behavior Layer 전달 가능 여부

이 모델은 사용자를 새롭게 진단하는 모델이 아니라, **Clinical Layer 내부에서 Clinical Diagnosis Engine의 결과를 검증하는 독립 Validation Module**이다.

시스템 외부 Workflow에서는 진단 생성과 검증을 모두 `Clinical Layer`로 묶어 표현한다. 다만 코드, 규칙, 테스트, 로그 및 판정 책임은 분리하여 검증 독립성을 유지한다.

다음 자동화 사이클을 실제 코드로 구현하라.

```text
프로젝트 분석
→ 데이터 구조 조사
→ NANDA/Omaha 문헌조사
→ Rule schema 설계
→ Baseline 구현
→ 테스트
→ 결과 및 실패 사례 분석
→ 개선사항 도출
→ 안전한 자동 수정
→ 회귀검증
→ 개선 전후 비교
→ 개선안 채택 또는 원복
→ 최종 보고서 생성
```

자동화는 모델을 한 번 구현하는 것으로 끝나지 않는다. 결과를 반복 분석하고 안전하게 보완하여 기술적 완성도, 안정성, 설명 가능성 및 검증 가능성을 높여야 한다.

## 1.1 SiBC Workflow 내 위치

시스템 Workflow는 다음과 같이 해석한다.

```text
User Data
    ↓
Cross-Validation Layer
    ↓
Clinical Layer
    ├── Clinical Diagnosis Engine
    └── Clinical Validation Model
    ↓
Validated Clinical Output
    ↓
Static User Profile / Dynamic User Profile
    ↓
Behavior Layer 및 후속 Agent
```

중요 원칙:

- `Clinical Validation Model`을 Workflow 도식의 별도 Layer로 추가하지 않는다.
- 외부 시스템 계약에서는 `Clinical Layer`가 진단 생성과 진단 검증을 모두 책임진다.
- 내부 구현에서는 진단 생성 엔진과 검증 모듈을 분리하여 독립성·추적성·시험 가능성을 유지한다.
- 검증이 완료되지 않은 진단 후보는 Clinical Layer의 최종 출력으로 승격하지 않는다.
- Profile과 Behavior Layer에는 원칙적으로 검증 상태가 포함된 Clinical Layer 최종 출력만 전달한다.

---

# 2. 기존 모델과의 관계

## 2.1 Reliability Model과 완전 분리

Clinical Validation Model과 기존 Reliability Model을 결합하지 마라.

```text
Reliability Model
- Behavior Layer의 루틴 답변 신뢰도 평가
- 공식 scope는 exercise only
- 기존 score, confidence, final decision 체계 유지

Clinical Validation Model
- Clinical Layer의 NANDA/Omaha 기반 진단 후보 검증
- 진단 기준, 근거 충분성, 충돌, 배제 조건, 설명 가능성 평가
- 별도의 score, confidence, status, CDEI 산출
```

금지:

- Reliability 결과를 Clinical Validation Score에 결합
- Reliability score를 진단 검증 근거로 사용
- Reliability Model 코드나 공식 scope 변경
- 두 모델의 confidence를 같은 의미로 해석
- 두 모델의 판정을 하나로 합산

---

## 2.2 Cross-Validation Layer와의 관계

Cross-Validation Layer는 Clinical Layer 진입 전에 사용자 입력 또는 루틴 관련 응답의 신뢰도와 사용 가능성을 평가한다.

Clinical Validation Model은 이를 다시 수행하지 않는다.

역할 분리:

```text
Cross-Validation Layer
- 사용자 입력의 신뢰성·일관성·사용 가능성 평가
- 입력별 validation status와 provenance 제공
- 기존 Reliability Model의 공식 scope는 exercise only

Clinical Validation Model
- Clinical Diagnosis Engine이 해당 입력을 어떻게 사용해 진단 후보를 생성했는지 검증
- 진단 기준 충족, Evidence 연결, 배제·충돌, 시간 정합성, CDEI 평가
```

Clinical Validation Model은 Cross-Validation 결과를 다음과 같이 취급한다.

- upstream validation metadata
- evidence eligibility flag
- provenance
- limitation
- missing/contradictory input indicator

금지:

- Cross-Validation 또는 Reliability 점수를 Clinical Validation Score에 합산
- Cross-Validation 판정을 임상진단의 정답으로 사용
- Clinical Validation Model이 사용자 입력 신뢰도를 다시 독자적으로 산출
- upstream에서 제외된 데이터를 근거 없이 다시 포함

Cross-Validation 결과가 없거나 불충분하면 다음 중 적절한 상태를 사용한다.

```text
REVIEW_REQUIRED
INSUFFICIENT_EVIDENCE
BLOCKED_BY_UPSTREAM_VALIDATION
```

# 3. 프로젝트 구조 원칙

현재 저장소의 `medical_checkup_model` 구조와 실행 방식을 우선 분석하라.

```text
medical_checkup_model/
├── 00_Data/
├── 01_Results/
├── configs/
├── docs/
├── scripts/
├── sql/
├── src/
├── tests/
├── pyproject.toml
├── requirements-lock.txt
└── README.md
```

`clinical_validation_model`은 가능한 한 `medical_checkup_model`과 유사한 프로젝트 구조, 실행 방식, 환경설정, 결과물 관리 및 문서화 방식을 사용하되 기능은 독립적으로 구현하라.

---

# 4. 반드시 먼저 분석할 코드

다음 경로를 우선 조사하라.

```text
/Users/jaeho.oh/Downloads/SiBC/SiBC_project/medical_checkup_model
```

중점 분석 대상:

```text
src/sibc_medical_checkup/env.py
src/sibc_medical_checkup/config.py
src/sibc_medical_checkup/db.py
src/sibc_medical_checkup/queries.py
src/sibc_medical_checkup/sql_guard.py
src/sibc_medical_checkup/security.py
src/sibc_medical_checkup/transform.py
src/sibc_medical_checkup/pipeline.py
src/sibc_medical_checkup/reporting.py
src/sibc_medical_checkup/xlsx_export.py
configs/modeling_policy.yaml
configs/prototype.yaml
sql/
tests/
```

확인할 내용:

- `.env` 탐색과 환경 선택
- 환경변수와 Secret masking
- DB connection과 read-only 보호
- SQL allowlist/guard와 parameterization
- cohort 및 temporal alignment
- 건강검진·웨어러블 데이터 추출
- pseudonymization과 raw identifier 제거
- 데이터 정규화, 단위 변환, timestamp, 중복·결측 처리
- wearable summary 및 temporal cohort 생성
- schema와 data quality 처리
- run ID, artifacts, figures, logs, outputs, reports
- `latest_run.json`, checksum, reproducibility manifest, experiment ledger
- 테스트 naming 및 release integration 방식

---

# 5. 코드 재사용 원칙

데이터 접근과 처리 코드는 다음 우선순위로 재사용하라.

```text
1. 기존 코드 직접 import
2. adapter 또는 wrapper
3. 안전한 공통 모듈 추출
4. 제한적 복제
5. 신규 구현
```

우선 재사용 후보:

- env/config loading
- DB connection
- SQL guard와 read-only query
- 건강검진 query
- temporal cohort
- wearable summary
- pseudonymization
- schema validation
- normalization, unit, timestamp
- reporting
- reproducibility manifest
- checksum
- experiment ledger
- release output structure

제약:

- `medical_checkup_model` 동작을 임의 변경하지 않는다.
- 가능하면 `clinical_validation_model` 내부 adapter에서 호출한다.
- 예측 또는 training 로직은 재사용하지 않는다.
- 건강검진 예측 결과를 진단 근거로 사용하지 않는다.
- 데이터 추출·정규화·품질검사 코드만 우선 재사용한다.
- `pred`, `risk`, prediction output을 actual/measured로 해석하지 않는다.

---

# 6. 권장 폴더 구조

```text
clinical_validation_model/
├── 00_Data/
│   ├── dev/
│   ├── stg/
│   ├── release/
│   └── fixtures/
├── 01_Results/
│   ├── dev/
│   ├── stg/
│   └── release/
├── configs/
│   ├── validation_policy.yaml
│   ├── scoring_policy.yaml
│   ├── cdei_policy.yaml
│   ├── rule_policy.yaml
│   └── prototype.yaml
├── docs/
│   ├── SiBC_clinical_validation_master_prompt.md
│   ├── SiBC_clinical_validation_project_context.md
│   ├── architecture.md
│   ├── data_contract.md
│   ├── validation_plan.md
│   ├── NANDA_RESEARCH_REGISTER.md
│   ├── OMAHA_RESEARCH_REGISTER.md
│   ├── LICENSE_AND_USAGE_REVIEW.md
│   └── CLINICAL_RULE_CANDIDATES.md
├── scripts/
│   ├── run_prototype.sh
│   ├── run_validation.sh
│   ├── run_optimization.sh
│   ├── run_regression.sh
│   └── build_result_report.py
├── sql/
│   ├── clinical_validation_health_check.sql
│   ├── clinical_validation_wearable.sql
│   ├── clinical_validation_temporal_cohort.sql
│   └── clinical_validation_data_quality.sql
├── src/
│   └── sibc_clinical_validation/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── env.py
│       ├── db.py
│       ├── queries.py
│       ├── sql_guard.py
│       ├── security.py
│       ├── transform.py
│       ├── pipeline.py
│       ├── data_quality.py
│       ├── evidence.py
│       ├── rule_schema.py
│       ├── rule_engine.py
│       ├── validation.py
│       ├── scoring.py
│       ├── confidence.py
│       ├── cdei.py
│       ├── explainability.py
│       ├── conflict_detection.py
│       ├── behavior_handoff.py
│       ├── evaluation.py
│       ├── optimization.py
│       ├── reporting.py
│       └── research.py
├── rules/
│   ├── nanda/
│   ├── omaha/
│   ├── internal/
│   └── fixtures/
├── tests/
│   ├── test_env_and_config.py
│   ├── test_sql_guard.py
│   ├── test_transform.py
│   ├── test_data_quality.py
│   ├── test_rule_schema.py
│   ├── test_rule_engine.py
│   ├── test_scoring.py
│   ├── test_confidence.py
│   ├── test_cdei.py
│   ├── test_conflict_detection.py
│   ├── test_temporal_leakage.py
│   ├── test_user_leakage.py
│   ├── test_output_and_reporting.py
│   ├── test_release_integration.py
│   └── test_optimization_pipeline.py
├── pyproject.toml
├── requirements-lock.txt
├── README.md
├── MODEL_CARD.md
├── CHANGELOG.md
└── OPEN_ISSUES.md
```

실제 `medical_checkup_model` convention과 충돌하면 기존 convention을 우선하라. 불필요하게 복잡하게 만들지 마라.

---

# 7. 환경과 DB

환경 파일은 프로젝트에 다음과 같이 존재할 수 있다.

```text
.env.release
.env.dev
.env.stg
```

그러나 **이번 작업의 실행·평가·고도화·결과 저장은 release 환경에 대해서만 수행한다.**

```text
ACTIVE_ENVIRONMENT = release
ENV_FILE = .env.release
```

`dev` 및 `stg` 환경은 경로 존재 여부와 코드 호환성만 조사할 수 있으며, 데이터 조회·모델 실행·성능 평가·결과 생성에 사용하지 않는다. 환경 fallback도 금지한다. `.env.release` 또는 release artifact 접근이 실패하면 dev/stg로 전환하지 말고 `BLOCKED_BY_RELEASE_ACCESS`로 중단한다.

기존 `medical_checkup_model`의 env loading 방식을 재사용하되 release profile을 명시적으로 고정하고, 모든 실행 결과의 `environment` 필드는 `release`여야 한다.

DB 안전 원칙:

- read-only
- INSERT/UPDATE/DELETE/ALTER/DROP/CREATE 금지
- release DB write 금지
- 전체 dump 금지
- 최소 컬럼·최소 cohort 조회
- query/cohort limit 지원
- 환경 데이터 혼합 금지
- 환경명을 feature로 사용 금지
- connection string과 `.env` 내용 출력 금지
- Secret 로그·exception 출력 금지
- `.env` Git 추가 금지

접속 실패:

```text
BLOCKED_BY_DB_ACCESS
BLOCKED_BY_RELEASE_ACCESS
```

---

# 8. 건강검진 데이터

기존 release artifacts를 분석하고 재사용하라.

```text
medical_checkup_model/00_Data/release/*/
├── approved_schema_columns.csv
├── latest_actual_pseudonymized.parquet
├── temporal_cohort_pseudonymized.parquet
└── wearable_summary_pseudonymized.parquet
```

두 실행 모드를 지원하라.

```text
Artifact mode
- pseudonymized parquet 재사용
- 기본 개발 모드

DB mode
- DB에서 read-only 신규 snapshot 생성
```

건강검진 임상 시점은 실제 측정일을 사용한다. 가능한 경우:

```text
health_info_data[].measuredDt
```

적재일, 수정일, ETL일, 실행일, 결과 생성일을 임상 측정시점으로 사용하지 마라.

`medical_checkup_model`의 건강검진 예측은 계속 `BLOCKED_BY_DATA`로 유지한다.

금지:

- 검증된 미래 검진 예측 주장
- 개인별 위험확률 주장
- prospective performance나 accuracy 주장
- 개인별 의료진단 생성
- `pred_*`/`risk_*`를 진단 근거로 사용

Clinical Validation Model은 실제 측정값 또는 검증된 파생값만 Evidence로 사용한다.

---

# 9. 웨어러블 데이터

`medical_checkup_model`이 사용하는 웨어러블 데이터와 처리 코드를 재사용한다.

후보 항목:

- steps
- active minutes
- exercise duration
- sedentary duration
- heart rate
- resting heart rate
- HRV
- sleep duration
- sleep regularity
- energy expenditure
- body weight
- oxygen saturation
- wear time
- valid day count
- sync delay

실제 존재하는 필드만 사용하라.

필수 품질정보:

- 관찰기간
- 착용시간과 유효일 수
- non-wear
- 기기 변경
- 권한·동기화 상태
- source application
- algorithm version
- timezone
- 중복 event
- manual input 여부

`steps = 0`을 실제 활동 없음으로 자동 해석하지 마라. 미착용, 배터리, 권한, sync 실패, 데이터 미수집, 기기 변경을 먼저 구분하라.

품질 부족 시:

```text
NOT_ASSESSABLE
INSUFFICIENT_EVIDENCE
REVIEW_REQUIRED
```

---

# 10. 설문조사 데이터

설문 source는 아직 확정되지 않았다. adapter와 schema만 구현하라. 파일·테이블·경로를 추측하지 마라.

```python
class SurveyEvidenceProvider:
    def load_responses(
        self,
        subject_key: str,
        index_datetime: datetime
    ):
        ...
```

지원 schema:

```text
survey_id
survey_version
question_id
question_reference
coded_response
response_datetime
recall_period
scoring_rule_version
completion_status
missing_reason
proxy_response
provenance
quality_flags
```

필수 설문이 없을 때:

```text
BLOCKED_BY_SURVEY_SOURCE
INSUFFICIENT_EVIDENCE
NOT_ASSESSABLE
```

건강검진·웨어러블 파이프라인은 설문 없이도 실행 가능하게 한다.

---

# 11. Clinical Layer 입력 계약

프로젝트에서 실제 Clinical Layer output schema를 검색하라.

우선 확인:

```text
diagnosis_id
taxonomy
diagnosis_code
diagnosis_name
diagnosis_status
applied_rule_ids
rule_version
input_feature_ids
evidence_ids
criteria_met
criteria_not_met
criteria_not_assessable
exclusion_check
contradiction_check
clinical_layer_score
clinical_layer_confidence
index_datetime
observation_window
generation_timestamp
clinical_layer_version
```

없다면 adapter interface와 mock schema를 정의하되 운영 schema라고 주장하지 마라.

```text
BLOCKED_BY_CLINICAL_LAYER_CONTRACT
BLOCKED_BY_UPSTREAM_VALIDATION
```

Synthetic output은 테스트 전용이다.

Clinical Layer 내부 계약은 최소 두 단계로 분리한다.

```text
DiagnosisCandidate
- Clinical Diagnosis Engine의 중간 결과
- 아직 profile 또는 Behavior Layer에 사용 불가

ValidatedClinicalOutput
- Clinical Validation Model의 검증 결과가 결합된 Clinical Layer 최종 결과
- validation status와 handoff permission 포함
```

권장 필드:

```text
diagnosis_candidate_id
diagnosis_payload
applied_rule_ids
source_evidence_ids
upstream_validation_refs
clinical_validation_status
clinical_validation_score
model_decision_confidence
cdei_score
limitations
human_review_required
profile_write_allowed
behavior_handoff_allowed
validation_run_id
validation_model_version
```

---

# 12. NANDA 및 Omaha 문헌조사

공식 자료와 신뢰할 수 있는 문헌을 조사하여 Rule 후보를 구조화하라.

우선순위:

```text
1. NANDA International 공식 자료
2. Omaha System 공식 자료
3. 공식 출판물·사용자 문서
4. 공신력 있는 전문기관
5. peer-reviewed 논문
6. 체계적 문헌고찰
7. 검증 연구
```

블로그, 출처 불명 요약, 생성형 AI 답변, 비공식 번역, 무단 복제 자료, 출처 불명 표를 운영 Rule 근거로 사용하지 마라.

각 source 기록:

```text
source_id
title
authors_or_organization
publication_year
edition
source_type
official_status
url_or_identifier
accessed_at
applicable_population
clinical_context
evidence_level
license_status
allowed_use
extracted_claims
limitations
review_status
```

생성 문서:

```text
docs/NANDA_RESEARCH_REGISTER.md
docs/OMAHA_RESEARCH_REGISTER.md
docs/LICENSE_AND_USAGE_REVIEW.md
docs/CLINICAL_RULE_CANDIDATES.md
```

## 12.1 NANDA

- 공식 판본과 version 확인
- 상업적 소프트웨어 이용 권한 확인
- 전체 진단명·정의·특성·관련요인 무단 복제 금지
- 비공식 출처 Rule 추출 금지
- 라이선스·Clinical review 전 운영 Rule 활성화 금지
- 승인 전 `RESEARCH_ONLY`

상태:

```text
RESEARCH_ONLY
LICENSE_REVIEW_REQUIRED
CLINICAL_REVIEW_REQUIRED
APPROVED_FOR_TEST
APPROVED_FOR_OPERATION
REJECTED
```

차단:

```text
BLOCKED_BY_LICENSE
BLOCKED_BY_RULE_DEFINITION
BLOCKED_BY_CLINICAL_REVIEW
```

## 12.2 Omaha

공식 구조를 조사한다.

```text
Problem Classification Scheme
Intervention Scheme
Problem Rating Scale for Outcomes
```

초기에는 Problem Classification Scheme을 우선한다.

- problem/domain/modifier
- individual/family/community
- health promotion/potential/actual
- signs and symptoms
- risk factors
- rating scales
- 공식 code/definition
- 사용조건

공식 Omaha 구조와 SiBC operational rule을 분리하고 공식 구조를 임의 변경하지 마라.

---

# 13. Threshold 분리

모든 기준은 다음 네 계층으로 분리한다.

```text
Source Threshold
Normalized Threshold
Clinical Interpretation
SiBC Operational Threshold
```

금지:

- 문헌 threshold를 자동 운영 기준으로 사용
- 여러 출처를 임의 평균
- 건강검진 reference range를 NANDA/Omaha 기준으로 자동 변환
- 성능 향상을 위해 임상기준 변경
- 웨어러블 기준을 공식 임상기준으로 오인
- 테스트 통과율을 위해 기준 완화

승인 전:

```text
DRAFT
REVIEW_REQUIRED
BLOCKED_BY_CLINICAL_APPROVAL
```

---

# 14. Rule schema

Rule은 YAML 또는 JSON으로 관리한다.

```yaml
rule_id: CLV-RULE-0001
taxonomy: OMAHA
diagnosis_code: null
diagnosis_name_reference: null
rule_version: 0.1.0
status: RESEARCH_ONLY

applicability:
  population: []
  required_context: []
  exclusions: []

required_evidence: []
supporting_evidence: []
related_factors: []
risk_factors: []
contradictory_evidence: []
exclusion_criteria: []

temporal_requirements:
  index_time_field: index_datetime
  lookback_window: null
  freshness_limit: null

measurement_requirements:
  allowed_sources: []
  allowed_units: []
  minimum_quality: null

conflicts:
  mutually_exclusive_rules: []
  review_rules: []

decision:
  hard_gates: []
  allowed_statuses: []
  human_review_conditions: []

provenance:
  source_ids: []
  source_version: null
  license_status: UNKNOWN
  clinical_review_status: NOT_REVIEWED
```

검사:

- source/rule version/taxonomy/license/clinical review 누락
- 단위·시간범위 누락
- 내부 상충
- required/exclusion 중복
- 승인되지 않은 Rule 활성화
- hard gate 희석
- 미연결 데이터 필드
- 존재하지 않는 feature reference

---

# 15. 판정 상태

```text
VALIDATED
VALIDATED_WITH_LIMITATIONS
REVIEW_REQUIRED
INSUFFICIENT_EVIDENCE
CONTRADICTED
NOT_APPLICABLE
ABSTAIN
```

차단:

```text
BLOCKED_BY_DATA
BLOCKED_BY_SURVEY_SOURCE
BLOCKED_BY_DB_ACCESS
BLOCKED_BY_RELEASE_ACCESS
BLOCKED_BY_LICENSE
BLOCKED_BY_RULE_DEFINITION
BLOCKED_BY_REFERENCE_STANDARD
BLOCKED_BY_CLINICAL_REVIEW
BLOCKED_BY_CLINICAL_APPROVAL
BLOCKED_BY_CLINICAL_LAYER_CONTRACT
BLOCKED_BY_UPSTREAM_VALIDATION
```

필수 기준과 배제 조건은 hard gate다.

```text
IF rule is not approved
    → ABSTAIN or BLOCKED
ELSE IF applicability is false
    → NOT_APPLICABLE
ELSE IF required evidence is missing
    → INSUFFICIENT_EVIDENCE
ELSE IF data quality is inadequate
    → REVIEW_REQUIRED or ABSTAIN
ELSE IF exclusion is triggered
    → CONTRADICTED
ELSE IF required criteria are satisfied and no material contradiction exists
    → VALIDATED
ELSE IF supported but material limitations remain
    → VALIDATED_WITH_LIMITATIONS
ELSE
    → REVIEW_REQUIRED or ABSTAIN
```

---

# 16. 정량지표

구현:

```text
clinical_validation_score
model_decision_confidence
applicability_score
required_criteria_score
supporting_criteria_score
evidence_sufficiency_score
evidence_consistency_score
temporal_alignment_score
data_quality_score
diagnostic_specificity_score
rule_coverage_score
```

`clinical_validation_score`는 진단 기준 충족 정도이며 질병·진단·위험·예후 확률이 아니다. 필수 실패와 배제 조건을 가중평균으로 보상하지 마라.

`model_decision_confidence`는 최종 validation decision의 안정성과 명확성이다. 진단확률, 질병확률, 개인 위험도, 예후확률이 아니다.

구성 후보:

```text
rule_determinacy
data_coverage
data_quality
temporal_alignment
conflict_uncertainty
boundary_uncertainty
source_certainty
rule_version_certainty
```

미보정 시:

```json
{
  "model_decision_confidence": 0.0,
  "confidence_type": "rule_decision_stability_index",
  "calibration_status": "NOT_CALIBRATED"
}
```

---

# 17. CDEI

```text
CDEI = Clinical Diagnostic Explainability Index
```

CDEI는 진단 정확도나 확률이 아니다.

구성:

```text
rule_traceability
source_traceability
evidence_linkage
temporal_explainability
criterion_transparency
conflict_transparency
limitation_disclosure
decision_reproducibility
narrative_faithfulness
groundedness
```

상태:

```text
COMPLETE
PARTIAL
INSUFFICIENT_TRACEABILITY
UNFAITHFUL_EXPLANATION
NOT_ASSESSABLE
```

반드시 별도로 유지:

```text
clinical_validation_score
model_decision_confidence
cdei_score
```

---

# 18. 용어 분리

절대 혼용하지 마라.

```text
actual
measured
derived
pred
risk
score
probability
confidence
status
```

예:

```text
measured_sbp
derived_bmi
clinical_validation_score
model_decision_confidence
```

---

# 19. Leakage 방지

모든 실행에 `index_datetime`을 둔다.

```text
measured_datetime <= index_datetime
wearable_event_datetime <= index_datetime
survey_response_datetime <= index_datetime
```

금지:

- 진단 이후 데이터 사용
- Behavior 개입 후 데이터를 과거 진단 근거로 사용
- 동일 사용자의 split 중복
- 반복측정치를 독립 사용자처럼 분할
- dev/stg/release 혼합
- 환경명을 feature로 사용
- 기기/기관이 판정을 대체
- Clinical Layer 결과를 reference standard로 사용
- Validation 결과를 Clinical Layer 정답으로 사용

snapshot 기록:

```text
environment
snapshot_id
index_datetime
subject_split_id
query_version
feature_version
rule_version
code_version
```

---

# 20. 데이터 품질 Gate

```text
Schema
→ Type
→ Unit
→ Range
→ Duplicate
→ Timestamp
→ Provenance
→ Wearable Availability
→ Observation Window
→ Clinical Appropriateness
```

품질 차원:

```text
completeness
validity
accuracy
consistency
timeliness
uniqueness
integrity
provenance
representativeness
stability
availability
clinical_appropriateness
```

Evidence 상태:

```text
USED
EXCLUDED
DOWN_WEIGHTED
NOT_ASSESSABLE
REVIEW_REQUIRED
```

낮은 품질 데이터를 정상값으로 위장하지 마라.

---

# 21. 실행 모드

```text
Release Artifact mode
- medical_checkup_model/00_Data/release의 pseudonymized artifact 사용
- 이번 작업의 기본·우선 실행 모드

Release DB mode
- .env.release를 이용한 read-only 조회
- release artifact로 충족되지 않는 데이터 계약 확인이 필요할 때만 사용

Synthetic Fixture mode
- 실제 release Evidence를 변경하지 않고, 존재하지 않는 Clinical Layer 결과만 합성
- Rule/CDEI/leakage/conflict/회귀시험에 사용
```

`dev`와 `stg` 실행모드는 이번 작업에서 비활성화한다.

---

# 22. 결과 디렉터리

```text
clinical_validation_model/01_Results/release/
└── release_YYYYMMDD_HHMMSS_<short_commit>/
    ├── artifacts/
    ├── figures/
    ├── logs/
    ├── outputs/
    └── reports/
```

artifacts:

```text
checksums.sha256
feature_registry.csv/json
rule_registry.csv/json
evidence_registry.csv/json
reproducibility_manifest.json
report_context.json
source_register.json
data_lineage.json
```

logs:

```text
experiment_ledger.csv/jsonl
failure_ledger.csv
optimization_ledger.jsonl
```

outputs:

```text
clinical_validation_long.csv/parquet
clinical_validation_summary.csv/parquet
cdei_results.csv/parquet
rule_conflicts.csv
data_quality_issues.csv
behavior_handoff.csv
```

reports:

```text
run_summary.md
data_card.md
data_profile.json
model_card.md
validation_report.md
failure_analysis.md
improvement_report.md
model_performance_comparison.md
figure_interpretation_guide.md
figure_interpretation_guide.docx
automation_cycle_summary.md
final_model_selection.md
leakage_audit.md
cdei_validation.md
performance_unavailable.md
```

환경별 `latest_run.json` 관리.

---

# 23. 성능 비교, 시각화 및 해석 산출물

Clinical Validation Model은 예측 모델이 아니므로 단순 accuracy 하나로 성능을 평가하지 않는다. 기술적 정확성, 안전성, 설명 가능성, 재현성, 효율성을 구분하고 각 자동 개선 cycle을 동일한 release snapshot과 Scenario Matrix에서 비교한다.

## 23.1 비교 대상

```text
baseline
previous_best
current_candidate
final_selected
```

각 버전은 `model_version`, `code_commit`, `rule_version`, `feature_version`, `synthetic_generator_version`, `release_snapshot_id`, `run_id`를 기록한다. 동일 release snapshot, 동일 Scenario Matrix, 동일 Rule set이 아닌 결과는 직접 비교하지 않는다.

## 23.2 핵심 성능 지표

### Rule 및 판정 정확성

```text
overall_scenario_accuracy
status_exact_match_rate
required_gate_accuracy
exclusion_gate_accuracy
contradiction_detection_rate
conflict_detection_rate
not_applicable_detection_rate
insufficient_evidence_detection_rate
abstain_decision_accuracy
profile_handoff_gate_accuracy
behavior_handoff_gate_accuracy
```

### 안전성

```text
unsafe_pass_rate
false_validated_rate
missed_exclusion_rate
missed_contradiction_rate
missed_future_leakage_rate
unapproved_rule_activation_rate
source_data_mutation_count
sensitive_data_exposure_count
```

`unsafe_pass_rate`, `unapproved_rule_activation_rate`, `source_data_mutation_count`, `sensitive_data_exposure_count`의 목표값은 0이다.

### Score 및 상태 일관성

```text
score_status_consistency_rate
hard_gate_score_violation_count
score_monotonicity_pass_rate
boundary_stability_rate
multi_diagnosis_consistency_rate
```

### Model Decision Confidence

```text
confidence_ordering_accuracy
confidence_error_separation
high_confidence_error_rate
confidence_stability_rate
confidence_calibration_status
```

전문가 reference standard가 없으므로 실제 임상 calibration을 주장하지 않는다. 현재는 정답·오답 synthetic scenario 간 confidence 분리와 판정 안정성만 평가한다.

### CDEI 및 설명 가능성

```text
cdei_component_completeness
evidence_trace_completeness
rule_trace_completeness
limitation_disclosure_rate
conflict_disclosure_rate
narrative_faithfulness_rate
groundedness_pass_rate
reproducibility_trace_rate
```

### 데이터 품질 및 Coverage

```text
evidence_coverage_rate
required_evidence_assessable_rate
data_quality_gate_accuracy
temporal_alignment_pass_rate
wearable_availability_classification_accuracy
rule_coverage_rate
scenario_coverage_rate
```

### 재현성 및 효율성

```text
deterministic_replay_rate
regression_pass_rate
test_pass_rate
branch_coverage
runtime_seconds
peak_memory_mb
throughput_candidates_per_second
```

## 23.3 해석 원칙

- 합성 Scenario 기반 accuracy를 실제 임상 정확도로 표현하지 않는다.
- Score와 confidence를 probability로 표현하지 않는다.
- `VALIDATED` 비율이 높다고 좋은 모델로 판단하지 않는다.
- `ABSTAIN` 비율을 무조건 낮추지 않는다.
- 안전성 저하를 동반한 성능 향상은 채택하지 않는다.
- reference standard가 없으면 sensitivity, specificity, PPV, NPV, AUROC를 산출하거나 주장하지 않는다.
- 계산할 수 없는 지표는 0으로 채우지 말고 `NOT_AVAILABLE` 또는 `BLOCKED_BY_REFERENCE_STANDARD`로 표시한다.

## 23.4 필수 비교 파일

```text
01_Results/release/<run_id>/outputs/model_performance_comparison.csv
01_Results/release/<run_id>/outputs/model_performance_comparison.parquet
01_Results/release/<run_id>/reports/model_performance_comparison.md
```

비교표 필수 열:

```text
metric_group
metric_name
baseline_value
previous_best_value
current_candidate_value
final_selected_value
absolute_change_vs_baseline
relative_change_vs_baseline
acceptance_direction
acceptance_status
interpretation
limitation
```

## 23.5 필수 그림 자료

각 그림은 PNG와 SVG 두 형식으로 생성한다.

```text
figures/01_validation_workflow.png/.svg
figures/02_scenario_matrix_coverage.png/.svg
figures/03_status_distribution_comparison.png/.svg
figures/04_confusion_matrix_status.png/.svg
figures/05_safety_gate_performance.png/.svg
figures/06_component_metric_comparison.png/.svg
figures/07_confidence_correctness_relationship.png/.svg
figures/08_cdei_component_profile.png/.svg
figures/09_data_quality_and_coverage.png/.svg
figures/10_multi_diagnosis_outcomes.png/.svg
figures/11_baseline_vs_final_improvement.png/.svg
figures/12_runtime_and_reproducibility.png/.svg
```

각 그림의 목적:

1. 실제 release Evidence와 합성 Clinical Layer 결과가 모델에 연결되는 구조
2. 정상·오류·경계·복수진단 Scenario coverage
3. baseline과 개선 모델의 Validation Status 분포 비교
4. expected status와 actual status 비교
5. unsafe pass, missed exclusion, leakage 탐지 등 안전성
6. 데이터 품질·Evidence·Rule·CDEI 하위 지표 비교
7. 올바른 판정과 오류 판정의 confidence 분포
8. CDEI 하위 구성요소 결과
9. 데이터 가용성, 평가 가능성, 결측 및 wearable 상태
10. 공존·충돌·부분 평가 가능 진단 세트 결과
11. baseline 대비 final selected 개선 요약
12. 실행시간, 처리량, deterministic replay 결과

## 23.6 그림 작성 원칙

- 제목만 보고 목적을 이해할 수 있어야 한다.
- 축 이름, 단위, 범례를 명확히 표시한다.
- 약어는 그림 또는 캡션에서 풀어쓴다.
- 색상에만 의존하지 않고 label과 패턴을 함께 사용한다.
- 3D 차트와 장식용 차트를 사용하지 않는다.
- 각 캡션에 `Synthetic scenario-based technical evaluation`임을 표시한다.
- 데이터가 없으면 빈 그래프를 만들지 말고 `NOT_AVAILABLE` 사유를 보고한다.
- 원시 식별자와 원시 건강정보를 표시하지 않는다.

## 23.7 그림 해석 파일

```text
01_Results/release/<run_id>/reports/figure_interpretation_guide.md
01_Results/release/<run_id>/reports/figure_interpretation_guide.docx
```

각 그림마다 다음을 작성한다.

```text
그림 번호와 제목
- 그림의 목적
- 무엇을 비교하는지
- 핵심 관찰 결과
- 좋은 결과의 방향
- 주의해서 해석할 부분
- 모델 개선에 주는 시사점
- 현재 데이터 및 검증의 한계
```

수치 개선의 원인을 추측하지 말고 failure analysis와 변경 이력으로 확인되는 내용만 작성한다.

## 23.8 그림 추적성

```text
figures/figure_manifest.csv
figures/figure_manifest.json
```

필수 항목:

```text
figure_id
file_name
title
purpose
source_output_files
metric_names
model_versions_compared
release_snapshot_id
synthetic_scenario_version
generated_at
interpretation_section
limitations
```

---

# 23. 자동 구축·고도화 파이프라인

## Phase 0. Preflight

- Git status/branch/uncommitted changes
- Python environment
- `.env.release`
- release profile 강제 여부
- dev/stg fallback 비활성화
- `medical_checkup_model`
- release artifact/output
- Secret masking
- release read-only DB

## Phase 1. Discovery

생성:

```text
docs/PROJECT_DISCOVERY_REPORT.md
docs/DATA_SOURCE_INVENTORY.md
docs/MEDICAL_CHECKUP_REUSE_ANALYSIS.md
docs/BLOCKERS.md
```

## Phase 2. Data reuse

분석·adapter 연결:

```text
env.py
config.py
db.py
queries.py
sql_guard.py
security.py
transform.py
pipeline.py
reporting.py
```

## Phase 3. Research

NANDA/Omaha 공식자료와 peer-reviewed literature 조사. 라이선스·임상검토 구분.

## Phase 4. Schema

```text
ClinicalCase
ClinicalLayerDiagnosis
EvidenceItem
DiagnosisRule
ValidationResult
CDEIResult
BehaviorHandoff
```

## Phase 5. Baseline

- synthetic fixture
- Omaha 후보 우선
- NANDA research-only/schema
- 건강검진·웨어러블 artifact
- survey placeholder

## Phase 6. Testing

- 필수 충족/누락
- 배제/반대/충돌
- 경계값
- 설문 source 없음
- 웨어러블 미착용/sync 실패
- 오래된 검진
- 단위 불일치
- 미래 데이터
- user/environment leakage
- 미승인 Rule/source 누락
- 설명-실행 불일치
- 재현성
- Secret masking
- SQL write 차단

## Phase 7. Evaluation

기술적 검증:

```text
schema pass rate
rule execution correctness
hard gate correctness
conflict detection correctness
leakage test pass rate
deterministic reproducibility
evidence trace completeness
CDEI faithfulness
runtime
memory
test coverage
```

임상 검증은 전문가 reference standard, 승인 Rule, adjudication, 충분한 사례, intended use가 있을 때만 수행한다.

없으면:

```text
CLINICAL_VALIDATION_STATUS = BLOCKED_BY_REFERENCE_STANDARD
```

## Phase 8. Failure analysis

```text
DATA_SCHEMA_ERROR
DATA_QUALITY_ERROR
TEMPORAL_ERROR
RULE_DEFINITION_ERROR
RULE_CONFLICT
SCORING_ERROR
CONFIDENCE_ERROR
CDEI_ERROR
EXPLANATION_FAITHFULNESS_ERROR
LICENSING_BLOCK
CLINICAL_REVIEW_BLOCK
SURVEY_SOURCE_BLOCK
DB_ACCESS_BLOCK
IMPLEMENTATION_BUG
TEST_DEFECT
```

## Phase 9. 자동 개선 및 최적화

자동화의 핵심은 한 번의 baseline 실행이 아니라, release Evidence와 합성 Clinical Layer Dataset으로 반복 평가·보완하고 안전성 제약 아래 최적 후보를 선택하는 것이다.

```text
baseline/current best 고정
→ 후보 개선안 생성
→ candidate 실행
→ 전체 Scenario Matrix 평가
→ 안전성 Gate 확인
→ 성능·CDEI·재현성 비교
→ 개선안 채택 또는 폐기
→ 실패 사례를 다음 cycle에 반영
```

자동 수정 허용:

- 코드 버그와 schema validation
- 예외·timestamp·unit·duplicate 처리
- deterministic ordering
- Evidence linkage 검증
- conflict detection 구현 오류
- score/status 일관성 오류
- confidence 안정성 계산 오류
- CDEI trace와 faithfulness
- 테스트·Scenario coverage
- 실행 성능 병목
- logging/secret masking
- 보고서·그림·해석 파일 생성 오류
- 비임상적 config와 pipeline orchestration

자동 수정 금지:

- NANDA/Omaha 공식 정의
- 필수·배제·상충 기준
- 임상 threshold
- intended use
- 전문가 검토·escalation 기준
- 라이선스 콘텐츠
- reference label 또는 expected oracle를 결과에 맞춰 변경
- 임상 acceptance criteria
- 실제 release Evidence 값

후보 선택 우선순위:

```text
1. source data 불변성
2. secret/privacy 안전성
3. unsafe pass 및 hard-gate 오류 최소화
4. leakage 및 미승인 Rule 활성화 0 유지
5. status exact match와 conflict/exclusion 탐지 개선
6. CDEI faithfulness와 trace completeness 개선
7. confidence 오류 분리와 안정성 개선
8. 재현성 유지
9. runtime 및 memory 개선
```

하위 우선순위 개선이 상위 우선순위를 악화시키면 후보를 채택하지 않는다. 기본 최대 10 cycle로 시작하며 연속 2 cycle 동안 유의미한 개선이 없으면 종료한다. safety regression이 발생하면 해당 후보를 즉시 폐기한다.

## Phase 10. Regression, Benchmark and Visualization

각 후보 개선 후 다음을 모두 실행한다.

```text
unit
integration
regression
boundary
conflict
multi-diagnosis
leakage
CDEI
confidence stability
source data checksum
secret scan
SQL guard
static/type checks
performance benchmark
figure generation
figure interpretation validation
```

채택 조건:

- source artifact 변경 없음
- safety/hard gate/leakage/secret/regression 악화 없음
- unsafe pass 증가 없음
- expected oracle 변경 없음
- status exact match, conflict/exclusion detection, CDEI 중 하나 이상 개선되거나 효율이 개선됨
- 다른 핵심 technical metric은 허용 범위 내 유지
- 재현성 유지
- scope/임상 Rule 무단 변경 없음
- 모든 필수 그림과 해석 파일 생성 성공

악화 시 이번 자동 개선 변경만 원복한다. baseline, previous best, candidate, final selected 결과를 동일한 비교표와 그림으로 저장한다.

## Phase 11. 종료 및 최종 선택

다음 중 하나이면 종료한다.

- release 기술 acceptance criteria 충족
- 연속 2 cycle 실질 개선 없음
- 최대 cycle 도달
- 남은 이슈가 임상·라이선스 승인 대상
- 설문 source/reference standard 부족
- 모든 신규 후보가 safety regression 유발
- release 접근 차단
- 사용자 또는 전문가 검토 필요

종료 후 baseline, previous best, final selected를 비교하고 최종 선택 근거, 성능표, 필수 그림 12종, 그림 해석 MD/DOCX, cycle별 변경·성과·폐기 사유를 생성한다. 결과는 실제 임상 성능이 아니라 release 기반 기술·합성 시나리오 성능임을 명확히 표시한다.

---

# 24. Clinical Layer 최종 출력과 Profile 반영

Clinical Validation Model의 결과는 별도 Workflow Layer의 출력이 아니라 Clinical Layer 최종 출력의 일부로 포함한다.

## 24.1 Profile 반영 원칙

다음과 같이 처리한다.

```text
VALIDATED
→ Static/Dynamic User Profile 반영 가능
→ Behavior Layer 전달 가능

VALIDATED_WITH_LIMITATIONS
→ 제한사항과 적용 범위를 함께 Profile에 반영 가능
→ 허용 범위 내 Behavior Layer 전달 가능

REVIEW_REQUIRED
→ 후보 상태로 보관 가능
→ 기본적으로 Profile 확정값 반영 및 Behavior 전달 금지

INSUFFICIENT_EVIDENCE
→ 확정 진단으로 Profile 반영 금지
→ 추가 데이터 필요

CONTRADICTED
→ Profile 및 Behavior 전달 금지

NOT_APPLICABLE
→ Profile 및 Behavior 전달 금지

ABSTAIN
→ 자동 확정 중지
```

Profile에는 원시 근거를 저장하지 말고 최소한의 검증 메타데이터만 저장한다.

권장 메타데이터:

```text
validated_diagnosis_reference
clinical_validation_status
clinical_validation_score
model_decision_confidence
cdei_score
rule_version
validation_datetime
limitations
human_review_required
behavior_handoff_allowed
```

## 24.2 핵심 Gate

Clinical Diagnosis Engine의 진단 후보를 바로 Profile 또는 Behavior Layer에 전달하지 마라.

반드시 다음 순서를 따른다.

```text
Diagnosis Candidate
→ Clinical Validation Model
→ Validated Clinical Output
→ Profile / Behavior Layer
```

# 25. 출력 계약

최소 포함:

```json
{
  "model_name": "clinical_validation_model",
  "model_version": "0.1.0",
  "run_id": "masked-run-id",
  "environment": "release",
  "execution_mode": "release_artifact",
  "index_datetime": "ISO-8601",
  "diagnosis": {
    "taxonomy": "OMAHA",
    "diagnosis_reference": "approved-reference",
    "rule_id": "CLV-RULE-0001",
    "rule_version": "0.1.0",
    "rule_status": "RESEARCH_ONLY"
  },
  "validation_result": {
    "status": "ABSTAIN",
    "clinical_validation_score": null,
    "model_decision_confidence": null,
    "confidence_type": "rule_decision_stability_index",
    "calibration_status": "NOT_CALIBRATED"
  },
  "cdei": {
    "cdei_score": null,
    "cdei_status": "NOT_ASSESSABLE",
    "components": {},
    "missing_elements": []
  },
  "criteria": {
    "met": [],
    "not_met": [],
    "not_assessable": [],
    "exclusions_triggered": [],
    "contradictions": []
  },
  "data_quality": {
    "status": "REVIEW_REQUIRED",
    "issues": []
  },
  "limitations": [],
  "blockers": [],
  "human_review": {
    "required": true,
    "reason": "RULE_NOT_APPROVED"
  },
  "behavior_layer_handoff": {
    "allowed": false,
    "mode": "BLOCKED",
    "reason": "CLINICAL_REVIEW_REQUIRED"
  },
  "provenance": {
    "data_snapshot_id": "masked",
    "query_version": null,
    "feature_version": null,
    "rule_source_ids": [],
    "medical_checkup_artifact_source": null
  }
}
```

---

# 26. 보안 및 개인정보

출력 금지:

```text
이름
전화번호
이메일
주민등록번호
원시 사용자 ID
원시 건강정보 행
DB 비밀번호/host
access token
connection string
.env 내용
```

사용 가능:

```text
pseudonymized subject key
aggregate statistics
masked examples
synthetic fixture
minimum necessary fields
```

예외에도 원시 row를 출력하지 마라.

---

# 27. 최초 실행 지시

1. Git 상태와 기존 변경 보호
2. `PROJECT_RULES.md`, 루트 `README.md` 확인
3. `medical_checkup_model` 구조·실행 분석
4. env/DB/SQL guard/security/query/transform/pipeline/reporting 분석
5. 건강검진·웨어러블 재사용 코드 정리
6. release pseudonymized artifact schema 분석
7. `clinical_validation_model`을 유사 구조로 생성
8. `.env.release` 로딩 방식을 재사용하고 release 환경을 강제로 고정
9. dev/stg fallback을 비활성화
10. Release Artifact mode를 우선 사용하고 Release DB mode는 read-only로 제한
10. survey placeholder
11. Clinical Layer contract 검색 또는 adapter schema
12. NANDA/Omaha 공식자료와 peer-reviewed 문헌조사
13. 라이선스·사용조건 문서화
14. Rule schema와 source registry
15. synthetic baseline Rule Engine
16. 건강검진·웨어러블 Evidence 연결
17. score/confidence/CDEI 분리 구현
18. hard gate/conflict/data quality
20. baseline 성능과 안전성 지표 산출
21. 필수 그림과 초기 해석 파일 생성
22. 테스트 실행
23. 실패 분석
24. 자동 수정 가능한 항목만 반복 보완
25. 각 cycle마다 전체 회귀시험과 baseline/previous best 비교
26. 안전성 우선순위에 따라 최적 모델 선택
27. final selected 모델의 성능 비교표와 그림 12종 생성
28. 그림 해석 MD 및 DOCX 생성
29. 임상·라이선스·데이터 blocker 유지
30. release run directory에만 저장
31. 최종 보고:

```text
결론
근거
변경·권고
검증
제한사항
```

확인 불가 사항을 추측하지 말고 다음 상태를 사용하라.

```text
ABSTAIN
REVIEW_REQUIRED
BLOCKED_BY_DATA
BLOCKED_BY_SURVEY_SOURCE
BLOCKED_BY_DB_ACCESS
BLOCKED_BY_RELEASE_ACCESS
BLOCKED_BY_LICENSE
BLOCKED_BY_RULE_DEFINITION
BLOCKED_BY_REFERENCE_STANDARD
BLOCKED_BY_CLINICAL_REVIEW
BLOCKED_BY_CLINICAL_APPROVAL
BLOCKED_BY_CLINICAL_LAYER_CONTRACT
BLOCKED_BY_UPSTREAM_VALIDATION
```

근거 없는 임상기준, 검증되지 않은 성능, 개인별 진단 또는 위험확률을 생성하지 마라.

# 추가 요구사항: 실제 데이터 보존 및 Synthetic Clinical Layer Dataset

## 핵심 원칙

현재 존재하는 건강검진 및 웨어러블 데이터는 원본 그대로 사용하고 절대 변경하지 않는다. 실제 데이터는 read-only reference로만 연결한다.

현재 존재하지 않는 Clinical Layer 결과만 별도의 합성 데이터셋으로 생성한다. 합성 대상은 다음과 같다.

- diagnosis candidates
- applied NANDA/Omaha rule references
- evidence-to-criterion linkage
- criteria met / not met / not assessable
- exclusion and contradiction results
- clinical reasoning trace
- index datetime and observation window
- candidate priority, coexistence, overlap, mutual exclusion

실제 데이터와 합성 Clinical Layer 결과는 반드시 물리적·논리적으로 분리한다.

```text
Actual/Pseudonymized Evidence Dataset
        +
Synthetic Clinical Layer Output Dataset
        ↓
Clinical Validation Model
```

## 실제 데이터 변경 금지

다음을 금지한다.

- 실제 건강검진 또는 웨어러블 값 변경
- 실제 timestamp 이동
- 실제 결측값 임의 보완
- 실제 데이터에 noise 추가 후 measured/actual로 저장
- 기존 medical_checkup_model artifact 덮어쓰기
- 합성값을 actual/measured로 표기
- 실제 사용자에게 임의 진단을 운영 결과처럼 저장

실행 전후 source artifact checksum, row count, schema, modified time을 비교한다. 변경이 감지되면 즉시 중단하고 `BLOCKED_BY_SOURCE_DATA_MUTATION`으로 기록한다.

## Synthetic Clinical Layer Dataset 구조

다음 파일을 생성한다.

```text
00_Data/fixtures/synthetic_clinical_layer/
├── diagnosis_candidates.parquet
├── diagnosis_candidate_evidence_links.parquet
├── diagnosis_candidate_criteria.parquet
├── diagnosis_candidate_conflicts.parquet
├── scenario_manifest.csv
├── expected_validation_results.csv
└── synthetic_generation_manifest.json
```

모든 합성 결과에는 다음 필드를 포함한다.

```text
data_origin = SYNTHETIC_CLINICAL_LAYER_OUTPUT
is_synthetic = true
generator_version
scenario_id
source_rule_ids
source_versions
generation_timestamp
expected_validation_result
intended_test_purpose
```

최소 schema는 다음을 포함한다.

```text
scenario_id
synthetic_case_id
diagnosis_candidate_id
taxonomy
diagnosis_code_reference
diagnosis_name_reference
diagnosis_type
candidate_status
applied_rule_ids
applied_rule_version
source_evidence_ids
criteria_met
criteria_not_met
criteria_not_assessable
exclusions_detected
contradictions_detected
related_factors_detected
risk_factors_detected
signs_symptoms_detected
index_datetime
observation_window
clinical_reasoning_trace
candidate_priority
coexisting_diagnosis_ids
mutually_exclusive_diagnosis_ids
expected_validation_status
expected_profile_write_allowed
expected_behavior_handoff_allowed
is_synthetic
generator_version
```

## 복수 진단 시나리오

하나의 사용자 또는 하나의 시점에 하나의 진단만 존재한다고 가정하지 않는다. 다음을 지원한다.

- 복수 NANDA 진단 후보
- 복수 Omaha problem 후보
- NANDA와 Omaha 후보의 동시 존재
- 공존 가능한 진단
- 상호 배타적인 진단
- 상위·하위 또는 중복 개념 진단
- actual/potential/health-promotion 등 서로 다른 상태
- 동일 Evidence가 여러 진단 기준에 사용되는 경우
- 진단별로 다른 관찰기간이 필요한 경우
- 일부 진단만 검증 가능하고 나머지는 INSUFFICIENT_EVIDENCE인 경우

각 diagnosis candidate별로 독립 validation result를 생성한다. 필요 시 후보 집합 전체에 대해 `candidate_set_conflict_status`, `candidate_set_completeness`, `candidate_set_review_required`를 산출한다.

## NANDA/Omaha 기준 완전성 보존

합성 데이터는 공식·허용 가능한 출처에서 구조화한 테스트용 Rule 전체를 기반으로 생성한다.

다음을 금지한다.

- 필수 기준 삭제
- defining characteristics 일부만 선택하고 전체 기준처럼 표현
- exclusion criteria 누락
- temporal requirement 누락
- applicability/population 조건 누락
- source 기준 임의 완화·강화
- 서로 다른 판본 혼합
- NANDA와 Omaha 요소를 하나의 비공식 Rule로 합성
- 시나리오에 맞추기 위한 threshold 변경
- 테스트 통과율을 높이기 위한 기준 변경

각 Rule에 대해 다음 completeness audit를 수행한다.

```text
source_rule_element_count
implemented_rule_element_count
omitted_elements
modified_elements
version_alignment_status
license_status
clinical_review_status
```

누락 또는 변경이 발견되면 해당 Rule을 실행하지 않고 `BLOCKED_BY_RULE_INTEGRITY`로 기록한다.

NANDA의 라이선스 대상 상세 콘텐츠는 권한 없이 저장소에 복제하지 않는다. 필요한 경우 code/reference/placeholder 및 승인된 테스트 범위로 제한한다.

## 필수 Scenario Matrix

최소 다음 시나리오를 생성한다.

```text
POSITIVE_CONTROL
NEGATIVE_CONTROL
MISSING_REQUIRED_EVIDENCE
PARTIAL_SUPPORT
EXCLUSION_TRIGGERED
CONTRADICTORY_EVIDENCE
NOT_APPLICABLE
BOUNDARY_VALUE
STALE_EVIDENCE
FUTURE_EVIDENCE_LEAKAGE
INVALID_EVIDENCE_LINK
UNAPPROVED_RULE
RULE_VERSION_MISMATCH
MULTIPLE_COHERENT_DIAGNOSES
MULTIPLE_CONFLICTING_DIAGNOSES
NANDA_OMAHA_CROSS_TAXONOMY_OVERLAP
PARTIALLY_ASSESSABLE_DIAGNOSIS_SET
EXPLANATION_TRACE_MISMATCH
UPSTREAM_VALIDATION_FAILURE
```

각 시나리오에는 `expected_status`, score/confidence/CDEI constraints, exclusion/conflict result, human review, profile write, behavior handoff 기대값을 기록한다.

## 생성 절차

```text
공식·허용 가능한 Source 조사
→ Rule candidate 구조화
→ license 및 clinical review 상태 확인
→ Rule completeness audit
→ 테스트 가능한 Rule 선정
→ base scenario 생성
→ 한 번에 하나의 조건을 통제하여 mutation
→ 복수 진단 조합 생성
→ expected validation oracle 기록
→ schema/rule integrity 검사
→ Clinical Validation Model 실행
→ 실제 결과와 expected result 비교
```

`expected validation oracle`은 기술적 기대 판정일 뿐 실제 임상 정답이 아니다.

## 결과 해석 제한

합성 데이터 기반으로 주장 가능한 범위는 다음과 같다.

```text
TECHNICAL_VALIDATION
SYNTHETIC_SCENARIO_VALIDATION
RULE_ENGINE_CORRECTNESS
SCHEMA_CORRECTNESS
GATE_BEHAVIOR
CDEI_TRACEABILITY
```

다음은 주장하지 않는다.

```text
REAL_WORLD_CLINICAL_PERFORMANCE
DIAGNOSTIC_ACCURACY
SENSITIVITY
SPECIFICITY
PPV
NPV
CLINICAL_CALIBRATION
INDIVIDUAL_DIAGNOSIS_VALIDITY
```

실제 임상 검증 상태는 `BLOCKED_BY_REFERENCE_STANDARD`로 유지한다.

---


---

# 추가 요구사항: 최종 Release 보고 패키지

최종 선택된 release run에는 다음 파일이 모두 존재해야 한다.

```text
01_Results/release/latest_run.json
01_Results/release/<run_id>/outputs/model_performance_comparison.csv
01_Results/release/<run_id>/outputs/model_performance_comparison.parquet
01_Results/release/<run_id>/figures/figure_manifest.csv
01_Results/release/<run_id>/figures/figure_manifest.json
01_Results/release/<run_id>/reports/model_performance_comparison.md
01_Results/release/<run_id>/reports/figure_interpretation_guide.md
01_Results/release/<run_id>/reports/figure_interpretation_guide.docx
01_Results/release/<run_id>/reports/automation_cycle_summary.md
01_Results/release/<run_id>/reports/final_model_selection.md
```

최종 보고는 다음을 구분한다.

```text
Release data technical results
Synthetic scenario validation results
Unavailable clinical performance
Remaining blockers
```

`최적 모델`은 현재 release snapshot과 합성 Scenario Matrix에서 정의된 안전성·기술 정확성·설명 가능성·재현성 기준에 따라 선택된 최적 후보를 의미한다. 실제 임상 최적성이나 개인별 진단 신뢰성을 의미하지 않는다.
