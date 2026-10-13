# Codex 마스터 프롬프트
## SiBC Clinical Validation Model 구조 중심 발표자료 및 발표 스크립트 제작

당신은 복잡한 의료·데이터 시스템을 처음 접하는 이해관계자에게 정확하고 쉽게 설명하는 프레젠테이션 기획자이자 기술 아키텍처 분석가다.

아래의 구축 프롬프트, 현행 저장소 문서, 실제 구현 코드를 분석하여 **SiBC Clinical Validation Model의 목적과 구축 방식, 내부 구조, 동작 원리**를 설명하는 발표자료와 발표 스크립트를 작성하라.

이번 발표에서 중요한 것은 테스트 결과나 성능 수치가 아니다. 청중이 모델의 구조를 이해하고 다음 질문에 답할 수 있게 하는 것이 목적이다.

1. 이 모델은 왜 필요한가?
2. 무엇을 입력으로 받는가?
3. Rule과 Evidence는 어떻게 구조화되어 있는가?
4. 어떤 순서와 우선순위로 후보를 검증하는가?
5. 여러 후보의 충돌은 어떻게 처리하는가?
6. 어떤 구조의 결과를 반환하는가?
7. 이 구조가 어떻게 독립성·안전성·추적성을 확보하는가?

---

# 1. 작업 대상

## 1.1 구축 의도 확인용 원본 프롬프트

```text
/Users/jaeho.oh/.codex/attachments/98e255a5-199d-4ce5-a74f-ca0aa3d5761d/pasted-text.txt
```

## 1.2 실제 구현 저장소

```text
/Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model
```

## 1.3 발표자료 디자인 템플릿

```text
/Users/jaeho.oh/Downloads/SiBC/Result/SiBC_신뢰도평가모델_운영고도화로드맵_260723.pptx
```

템플릿이 존재하면 해당 PPTX의 마스터, 레이아웃, Pretendard 폰트, 색상, Confidential 표시, 푸터와 페이지 체계를 유지한다. 템플릿의 기존 신뢰도평가모델 문구나 결과 이미지는 내용 근거로 재사용하지 않는다.

---

# 2. 발표의 커뮤니케이션 목표

발표가 끝났을 때 모델을 처음 보는 제품·임상·데이터·개발 이해관계자가 다음 문장을 자신의 말로 설명할 수 있어야 한다.

> Clinical Validation Model은 학습형 진단 예측모델이 아니라, `DiagnosisCandidate + Versioned Rule + Evidence Snapshot`을 입력받아 후보 단위 안전 검증과 후보 집합 충돌 검증을 수행하고 `ValidatedClinicalOutput`을 반환하는 결정론적 Rule-based 검증 모듈이다.

발표의 중심 메시지는 다음과 같다.

> 후보, 규칙, 근거, 판정, 전달 권한을 서로 분리했기 때문에 검증의 독립성·추적성·재현성을 확보할 수 있다.

예상 발표 시간은 약 17~20분으로 하고, 제목과 목차를 포함해 정확히 17장으로 구성한다.

---

# 3. 사실 확인 우선순위

자료를 만들기 전에 실제 파일을 읽고 구현 구조를 확인한다. 자료 간 내용이 다르면 아래 순서를 따른다.

## 3.1 최우선: 실제 코드와 설정

```text
src/sibc_clinical_validation/models.py
src/sibc_clinical_validation/rule_schema.py
src/sibc_clinical_validation/evidence.py
src/sibc_clinical_validation/validation.py
src/sibc_clinical_validation/conflict_detection.py
src/sibc_clinical_validation/scoring.py
src/sibc_clinical_validation/confidence.py
src/sibc_clinical_validation/cdei.py
src/sibc_clinical_validation/behavior_handoff.py
src/sibc_clinical_validation/medical_adapter.py
src/sibc_clinical_validation/pipeline.py
src/sibc_clinical_validation/reporting.py
configs/validation_policy.yaml
configs/scoring_policy.yaml
configs/cdei_policy.yaml
configs/rule_policy.yaml
```

## 3.2 두 번째: 현행 설명 문서

```text
README.md
MODEL_CARD.md
docs/architecture.md
docs/data_contract.md
docs/validation_plan.md
docs/BLOCKERS.md
OPEN_ISSUES.md
```

## 3.3 세 번째: 구축 의도

첨부된 마스터 프롬프트는 설계 의도와 구축 원칙을 확인하는 자료로 사용한다. 마스터 프롬프트의 권장 구조와 현행 코드가 다르면, **현행 구현을 본문에 표시하고 설계 의도는 향후 확장 또는 배경으로 구분**한다.

---

# 4. 발표 범위

## 4.1 반드시 포함할 내용

- 모델의 목적과 해결하려는 문제
- 학습형 예측모델이 아닌 결정론적 Rule-based 검증 엔진이라는 정체성
- SiBC 안에서의 최소한의 위치와 책임 경계
- 기존 `medical_checkup_model`에서 참고·재사용한 환경·보안·read-only·보고 패턴과 새로 구현한 검증 코어의 구분
- 계약 기반 입력 구조
- `DiagnosisCandidate`, `CriterionAssessment`, `EvidenceItem`, `EvidenceLink`의 역할
- Rule Registry와 version·status·provenance·integrity 구조
- Evidence와 Criterion의 연결 구조
- 데이터 품질·시간 정합성·upstream eligibility 검증
- 후보 단위 `ClinicalValidationEngine`의 판단 순서
- Hard gate와 상태 우선순위
- 복수 후보의 공존·중복·상호배제 검사
- Status, Clinical Validation Score, Decision Confidence, CDEI의 역할 분리
- `ValidatedClinicalOutput`의 출력 계약
- Profile write와 Behavior handoff permission 구조
- release-only 실행, read-only artifact, 결정론적 replay, privacy scan, checksum, atomic publication의 구조적 의미
- 운영 adapter·Rule pack·Evidence provider·정책 파일 등 안전한 확장 지점

## 4.2 본문에서 제외할 내용

다음 내용은 현재 발표의 핵심이 아니므로 본문과 결론에서 제외한다.

- 자동화 테스트 통과 건수
- 합성 시나리오 수와 후보 수
- technical oracle 일치율
- 상태별 결과 분포
- 모델 성능 비교표
- baseline 대비 개선 수치
- 정확도·민감도·특이도·AUROC 등 성능 지표
- 현재 run 결과, release run ID, 산출물 파일 수
- 성숙도 점수나 진행률 막대
- 결과 중심의 로드맵
- 특정 후보의 평가 결과를 성능 사례처럼 제시하는 내용

Status code는 **결과 수치가 아니라 출력 계약과 판정 구조를 설명하기 위해서만** 사용한다.

현재의 blocker나 미승인 상태는 구조적 경계를 설명하는 데 반드시 필요한 경우에만 슬라이드 하단 또는 발표자 노트에서 짧게 언급한다. 별도의 “현재 결과와 한계” 슬라이드는 만들지 않는다.

---

# 5. 기술적 정확성 규칙

다음 규칙을 반드시 지킨다.

1. 모델을 진단 생성 모델, 머신러닝 모델, 질병확률 모델로 설명하지 않는다.
2. 모델의 정확한 유형은 **deterministic rule-engine technical prototype**으로 표현한다.
3. Clinical Diagnosis Engine의 내부 후보 생성 로직이 구현되어 있다고 주장하지 않는다.
4. 실제 production Clinical Layer API가 존재한다고 표현하지 않는다. 현재 입력 계약은 mock adapter contract임을 구분한다.
5. NANDA/Omaha 운영 Rule이 구현 또는 승인되었다고 표현하지 않는다.
6. Reliability Model 또는 Cross-Validation 점수가 Clinical Validation Score에 결합된다고 설명하지 않는다.
7. `VALIDATED`를 확정 진단 또는 임상적 정답으로 표현하지 않는다.
8. Clinical Validation Score는 Rule 기준 충족 정도이며 확률이 아니다.
9. Decision Confidence는 진단확률이 아니라 판정 안정성 메타데이터다.
10. CDEI는 설명·추적 가능성이지 정확도가 아니다.
11. Status, Score, Confidence, CDEI를 하나의 종합 점수로 합치지 않는다.
12. 높은 점수가 hard gate 실패를 상쇄한다고 설명하지 않는다.
13. 현재 핵심 후보 판정은 `validation.py`의 `ClinicalValidationEngine`에 구현되어 있다. 별도의 운영 `rule_engine.py`가 존재하는 것처럼 설명하지 않는다.
14. `data_quality.py`는 보조 helper이고, main path의 품질·시간 검사는 `validation.py`에 구현되어 있음을 필요 시 구현 매핑에 반영한다.
15. 실제 pseudonymized medical artifact는 현재 prototype에서 원시 값 결합이 아니라 read-only metadata·무결성 확인 대상으로 사용된다는 점을 구분한다.
16. synthetic fixture의 `expected_*` 필드는 domain object에 들어가지 않으며 판정 feature로 사용되지 않는 구조를 결과가 아닌 leakage 방지 설계로 설명한다.
17. 기술 gate 통과와 Profile/Behavior 전달 허용은 별개의 판단임을 명확히 한다.
18. 실제 코드에 없는 클래스·모듈·API·연결 관계를 만들지 않는다.

---

# 6. 설명 및 시각화 원칙

- 쉬운 한국어를 먼저 쓰고 실제 기술 명칭은 괄호 또는 작은 구현 매핑 영역에 표시한다.
- 각 슬라이드는 하나의 핵심 메시지만 전달한다.
- 슬라이드 제목은 단순 명사보다 발표자가 말할 수 있는 결론형 문장으로 작성한다.
- 구조를 설명하는 발표이므로 결과 차트보다 흐름도, 객체 관계도, 계층도, 결정 트리, 출력 envelope를 사용한다.
- 구조도에는 한 방향의 읽기 흐름을 사용하고 연결선이 상자나 글자를 통과하지 않게 한다.
- 한 슬라이드에 코드 전문이나 JSON 전문을 넣지 않는다. 구조를 이해하는 데 필요한 필드 그룹만 보여준다.
- 클래스명·파일명은 본문을 방해하지 않도록 하단의 `구현 매핑` 영역에 작게 표시한다.
- 처음 나오는 용어는 슬라이드 하단에서 한 문장으로 설명한다.
- 약어는 처음 등장할 때 풀어 쓴다.
- 슬라이드 본문은 최대 3~5개 핵심 요소로 제한한다.
- 발표자 노트에는 본문보다 자세한 설명과 실제 파일 경로 근거를 제공한다.

---

# 7. 17장 발표자료 구성

## Slide 01. SiBC Clinical Validation Model 구조와 동작 원리

**핵심 메시지:** 진단 후보를 규칙과 근거로 독립 검증하는 내부 모듈이다.

화면 구성:

```text
Diagnosis Candidate
        ↓
Clinical Validation Model
        ↓
Validated Clinical Output
```

- 부제: `목적 · 입력 계약 · 검증 구조 · 출력 구조`
- 상태나 성능 수치는 넣지 않는다.
- 용어: Diagnosis Candidate는 아직 확정되지 않은 검토 대상이다.

추천 시각화: 입력–검증–출력의 단순 3단 구조.

## Slide 02. 목적에서 출력까지 네 단계로 설명합니다

**핵심 메시지:** 목적과 경계에서 시작해 내부 구조와 실행 구조까지 순서대로 본다.

목차:

1. 목적과 책임 경계
2. 구축 원칙과 전체 아키텍처
3. 입력·Rule·Evidence·판정 구조
4. 출력·실행 안전·확장 지점

추천 시각화: 네 구간의 학습 흐름.

## Slide 03. 이 모델의 목적은 후보를 다시 검증하는 것입니다

**핵심 메시지:** 후보 생성과 후보 검증은 다른 책임이다.

하는 일:

- 후보가 올바른 Rule과 연결됐는지 확인
- 필요한 Evidence가 충분하고 적절한지 확인
- 품질·시점·배제·상충을 확인
- 결과와 제한사항, 전달 가능 범위를 남김

하지 않는 일:

- 새로운 진단 후보 생성
- 질병·진단·위험 확률 예측
- 의료전문가의 판단 대체

추천 시각화: `하는 일 / 하지 않는 일` 대조.

용어: Rule-based는 학습된 확률이 아니라 명시적으로 관리되는 규칙으로 판정한다는 뜻이다.

## Slide 04. 시스템 안에서는 한 Layer, 내부 책임은 분리합니다

**핵심 메시지:** 외부 Workflow에서는 Clinical Layer에 포함되지만 내부적으로는 후보 생성 엔진과 독립된 검증 모듈이다.

표현 범위:

```text
Cross-Validation metadata
        ↓
Clinical Diagnosis Engine
        ↓ DiagnosisCandidate
Clinical Validation Model
        ↓ ValidatedClinicalOutput
Profile / Behavior
```

- Clinical Validation Model을 별도의 외부 Workflow Layer로 그리지 않는다.
- Reliability/Cross-Validation의 score를 합산하지 않는다.
- Clinical Diagnosis Engine의 내부 생성 알고리즘은 설명하지 않는다.

추천 시각화: 최소한의 시스템 경계도.

용어: Upstream은 모델 앞 단계에서 전달되는 입력과 메타데이터를 뜻한다.

## Slide 05. 검증 코어는 독립적으로 만들고 안전 기반은 재사용했습니다

**핵심 메시지:** 기존 데이터 접근·보안·발행 패턴과 Clinical Validation 고유 로직을 분리하여 구축했다.

왼쪽 — 참고·재사용·adapter 영역:

- 환경과 설정 관리
- release artifact read-only 접근
- DB·SQL 안전 장치
- 개인정보 보호와 reporting 패턴

오른쪽 — 신규 검증 코어:

- 입력 domain contract
- Rule Registry와 무결성 검사
- Evidence linkage와 candidate validation
- conflict, CDEI, handoff gate

직접 import, adapter, 독립 구현 여부는 실제 코드를 확인해 정확히 표기한다.

추천 시각화: `공통 안전 기반 / 독립 검증 코어` 2열 구조.

용어: Adapter는 다른 시스템의 데이터를 현재 모델 계약에 맞게 연결하는 경계 모듈이다.

## Slide 06. 다섯 가지 원칙이 전체 구조를 결정했습니다

**핵심 메시지:** 구조는 기능보다 안전성과 추적성을 먼저 고려해 설계되었다.

다섯 원칙:

1. 동일 입력에는 동일 결과 — Deterministic
2. 입력 객체와 책임을 명확히 분리 — Contract-based
3. Rule과 정책을 version으로 관리 — Governed Rule
4. 필수 안전 조건을 점수보다 먼저 적용 — Hard gate first
5. 불명확하면 멈추고 이유를 남김 — Fail-safe and traceable

추천 시각화: 다섯 설계 원칙의 연결 구조.

용어: Fail-safe는 불확실할 때 자동 통과보다 중단·검토를 선택하는 방식이다.

## Slide 07. 모델은 여섯 개의 구조 블록으로 동작합니다

**핵심 메시지:** 입력 계약부터 전달 Gate까지 단계별 책임이 분리되어 있다.

전체 구조:

```text
1. Input Contract
        ↓
2. Rule Registry & Policies
        ↓
3. Evidence–Criterion Linkage
        ↓
4. Candidate Validation Engine
        ↓
5. Candidate-set Conflict Check
        ↓
6. Output Contract & Handoff Gate
```

하단 구현 매핑:

```text
models.py · rule_schema.py · evidence.py · validation.py
conflict_detection.py · reporting.py · behavior_handoff.py
```

추천 시각화: 여섯 블록의 메인 아키텍처 흐름도.

## Slide 08. 입력은 네 객체로 나누어 받습니다

**핵심 메시지:** 후보, 기준 판정, 근거, 연결 관계를 분리해 서로 교차검증할 수 있게 했다.

핵심 객체:

- `DiagnosisCandidate`: 후보 ID, taxonomy, 적용 Rule, 기준시점, 관찰기간, reasoning trace
- `CriterionAssessment`: 기준의 역할과 `MET / NOT_MET / NOT_ASSESSABLE` 상태
- `EvidenceItem`: 출처·단위·측정시각·품질·eligibility·provenance
- `EvidenceLink`: 어느 Evidence가 어느 Candidate의 어떤 Criterion에 연결되는지 표현

중요 설명:

- 후보가 주장한 기준 요약을 정답으로 신뢰하지 않는다.
- Evidence metadata와 연결 관계를 분리한다.
- 현재 계약은 production API가 아니라 mock adapter contract다.

추천 시각화: 네 객체의 관계도.

용어: Observation Window는 해당 판단에서 근거로 인정하는 시간 범위다.

## Slide 09. Rule은 기준뿐 아니라 출처와 완전성까지 관리합니다

**핵심 메시지:** Rule은 단순 조건문이 아니라 version·출처·승인·무결성을 가진 관리 대상이다.

Rule의 여섯 영역:

1. Identity — Rule ID, taxonomy, diagnosis reference, version, status
2. Criteria — applicability, required, supporting, exclusion, contradiction
3. Time — index time, lookback, freshness
4. Measurement — 허용 source, unit, quality
5. Conflict & Decision — 상호배제 Rule, hard gate, review 조건
6. Governance — source, license, clinical review, completeness/integrity audit

Rule Registry는 다음을 검사한다.

- taxonomy·version·status 정합성
- 필수 provenance 누락
- 기준 중복과 required/exclusion 충돌
- 원본 대비 누락·수정·요소 수 불일치

추천 시각화: YAML Rule의 계층형 해부도.

용어: Provenance는 Rule이나 Evidence가 어디에서 왔고 어떤 version인지 설명하는 이력이다.

## Slide 10. Evidence는 값보다 연결과 맥락을 함께 검증합니다

**핵심 메시지:** 근거가 존재하는지만 보지 않고 후보–기준–근거 연결이 서로 일치하는지 확인한다.

교차검사 구조:

```text
DiagnosisCandidate
  └─ source_evidence_ids
          ↕ 집합 일치
CriterionAssessment
  └─ criterion_id · feature_id · evidence_ids
          ↕ 연결 일치
EvidenceItem / EvidenceLink
  └─ source · unit · timestamp · quality · eligibility
```

확인 항목:

- Candidate가 선언한 근거 집합과 실제 근거 집합
- Criterion ID·role·feature와 Rule 정의
- Evidence → Criterion → Feature 연결
- Evidence code에서 유도한 상태와 Criterion 상태
- 필수 Criterion에 eligible Evidence가 실제 연결됐는지 여부

추천 시각화: Candidate → Criterion ← Evidence linkage 관계도.

용어: Eligibility는 해당 근거가 현재 판정에 사용 가능한 상태인지 나타낸다.

## Slide 11. 품질과 시간은 별도의 안전 관문입니다

**핵심 메시지:** 정확해 보이는 값도 출처·단위·시점·품질이 맞지 않으면 사용하지 않는다.

검사 구조:

```text
Source / Unit
      ↓
Upstream eligibility / Quality
      ↓
measured_datetime ≤ index_datetime
      ↓
Freshness / Observation Window
```

설명할 위험:

- 미래 근거 사용 — temporal leakage
- 너무 오래된 근거 — stale evidence
- 허용되지 않은 source 또는 unit
- 품질 부족 또는 upstream 제외 근거
- 필수 근거 연결 누락

추천 시각화: 데이터가 여러 안전 필터를 통과하는 흐름.

용어: Temporal leakage는 판단시점 이후의 정보를 과거 판단에 사용하는 오류다.

## Slide 12. 상태는 점수가 아니라 Hard gate 순서로 결정됩니다

**핵심 메시지:** 필수 안전 조건을 먼저 판정하고, 점수는 그 결정을 대체하지 않는다.

판정 우선순위:

```text
Rule 없음·version/무결성/승인/upstream 실패
→ ABSTAIN

적용 불가
→ NOT_APPLICABLE

적용 가능성 또는 필수 근거 평가 부족
→ INSUFFICIENT_EVIDENCE

연결·미래 정보·허용 source/unit 실패
→ ABSTAIN

시간·품질 검토 필요
→ REVIEW_REQUIRED

필수 기준 실패·배제·반대 근거
→ CONTRADICTED

필수 관문 통과 + 보조 근거 일부 부족
→ VALIDATED_WITH_LIMITATIONS

모든 관문 통과
→ VALIDATED
```

후속 재검사:

- 설명 trace가 실제 실행과 다르면 `ABSTAIN`으로 전환 가능
- 후보 집합 상호배제 충돌이 있으면 `REVIEW_REQUIRED`로 전환 가능

추천 시각화: 위에서 아래로 내려가는 결정 트리.

용어: Status precedence는 여러 조건이 동시에 있을 때 어떤 판정을 먼저 적용하는지 정한 우선순위다.

## Slide 13. 복수 후보는 개별 검증 후 집합으로 다시 봅니다

**핵심 메시지:** 사람 전체를 하나의 평균값으로 만들지 않고 후보별 결과를 보존한 채 관계를 다시 확인한다.

처리 순서:

1. Candidate A·B·C를 각각 독립 검증
2. 같은 case의 후보를 candidate set으로 그룹화
3. 공존, 일부 평가 가능, taxonomy 간 중복, 상호배제를 구분
4. 상호배제 충돌은 사람 검토로 전환하고 전달을 차단

후보 집합 상태 예:

- `COEXISTENT`
- `PARTIALLY_ASSESSABLE`
- `CROSS_TAXONOMY_OVERLAP_DISCLOSED`
- `MUTUALLY_EXCLUSIVE_CANDIDATES`

추천 시각화: 후보 A·B·C와 candidate-set conflict check의 관계도.

용어: Mutual exclusion은 두 후보를 동시에 확정 상태로 사용할 수 없는 관계다.

## Slide 14. 판정과 세 가지 지표는 서로 다른 구조입니다

**핵심 메시지:** Status가 사용 결정을 나타내고, Score·Confidence·CDEI는 서로 다른 설명 정보를 제공한다.

네 출력 요소:

- `Validation Status`: 실제 후보 검증 결정
- `Clinical Validation Score`: Rule 기준 충족 정도
- `Decision Confidence`: 현재 판정의 안정성 메타데이터
- `CDEI`: 설명과 추적 가능성

반드시 설명할 원칙:

- 네 요소를 합산하지 않는다.
- Score와 Confidence를 확률로 해석하지 않는다.
- CDEI가 높다고 후보가 더 정확한 것은 아니다.
- Hard gate 실패는 높은 Score로 상쇄할 수 없다.

CDEI는 세부 항목을 다음 네 묶음으로 쉽게 설명한다.

1. Rule과 source 추적
2. Criterion과 Evidence 연결
3. 충돌·제한사항의 투명성
4. 설명 충실도와 판정 재현성

추천 시각화: 서로 독립된 네 출력 블록.

용어: CDEI는 `Clinical Diagnostic Explainability Index`의 약자로 설명·추적성 지표다.

## Slide 15. 출력은 결과값이 아니라 사용 가능한 계약으로 반환됩니다

**핵심 메시지:** 최종 출력은 판정뿐 아니라 이유·제한·검토·전달 권한을 함께 가진다.

`ValidatedClinicalOutput`의 구조:

- 실행 정보 — model, version, run, environment, index time
- 진단 참조 — taxonomy, opaque reference, Rule ID/version/status
- 판정 — status, score, hard gate, confidence metadata
- 설명 — CDEI, met/not met/not assessable, exclusion, contradiction
- 품질과 제한 — issues, limitations, blockers
- 후보 집합 — conflict, completeness, review flag
- 사람 검토 — required와 reason
- 사용 권한 — Profile write와 Behavior handoff
- 추적성 — snapshot, feature version, source IDs, decision fingerprint

Handoff 조건은 별도로 설명한다.

```text
검증 상태 허용
AND Rule이 운영 승인됨
AND reference standard가 승인됨
→ Profile / Behavior 전달 허용
```

추천 시각화: JSON envelope를 필드 그룹으로 단순화한 출력 구조도.

용어: Decision fingerprint는 동일 입력·Rule·판정을 다시 확인하기 위한 식별용 해시다.

## Slide 16. 검증 엔진 바깥에도 안전한 실행 구조가 있습니다

**핵심 메시지:** 결정론적 검증 코어를 release-only 실행·무결성·개인정보 보호·원자적 발행 구조가 감싼다.

실행 파이프라인:

1. Release preflight와 실행 mode 확인
2. upstream artifact read-only fingerprint
3. fixture·contract·Rule Registry 무결성 확인
4. 후보별 검증과 candidate-set 검사
5. 동일 입력 deterministic replay
6. source artifact 재검증
7. privacy scan과 checksum 등록·검증
8. staging directory에서 atomic publication

구조적 안전 장치:

- release 외 환경 실행과 fallback 차단
- DB·SQL read-only 원칙
- 실제 source artifact 불변성 확인
- 민감정보와 Secret 출력 차단
- code·Rule·policy·runtime version 기록

추천 시각화: 검증 코어를 둘러싼 8단계 실행 sequence.

용어: Atomic publication은 모든 검사가 끝난 완전한 결과만 한 번에 최종 위치로 전환하는 발행 방식이다.

## Slide 17. 고정된 검증 코어에 승인된 구성요소를 연결합니다

**핵심 메시지:** 향후 확장은 입력 adapter와 Rule·Evidence·Policy를 교체하되 검증 순서와 안전 관문을 유지하는 방식이다.

고정할 코어:

- 입력 계약 분리
- Rule 무결성 검사
- Evidence linkage
- Hard gate와 상태 우선순위
- candidate-set conflict check
- trace·provenance·permission 출력

안전한 확장 지점:

- 실제 Clinical Layer adapter
- 승인된 operational Rule pack
- 새로운 Evidence provider
- versioned validation/scoring/CDEI policy
- 승인된 downstream contract

마지막 결론:

> 후보·규칙·근거·판정·사용 권한을 분리한 구조가 검증의 독립성, 추적성, 재현성을 만든다.

추천 시각화: 중앙의 고정 Validation Core와 주변의 교체 가능한 extension port.

---

# 8. 발표 스크립트 작성 지침

- 17장 전체 발표 스크립트를 별도 Markdown 파일로 작성한다.
- 슬라이드당 약 45~70초 분량으로 작성한다.
- 슬라이드 본문을 그대로 읽지 말고 “왜 이렇게 구조화했는가”를 중심으로 설명한다.
- 처음 나오는 기술용어는 즉시 쉬운 말로 풀어 설명한다.
- 실제 클래스명과 파일명은 발표 흐름을 방해하지 않도록 필요한 경우에만 언급한다.
- 테스트 건수, 성능 결과, 시나리오 결과는 말하지 않는다.
- 현재 구현과 설계 의도를 구분한다.
- 각 슬라이드 발표자 노트 마지막에는 아래 형식의 근거를 포함한다.

```text
[Sources]
- /absolute/path/to/source.py
- /absolute/path/to/source.md
```

- 실제 코드 근거가 있는 내용은 가능한 한 코드 파일을 우선 인용한다.
- 단순한 설계 의도는 첨부 마스터 프롬프트를 인용한다.

---

# 9. 산출물 요구사항

최종적으로 다음 파일을 생성한다.

1. 구조 중심 발표자료 PPTX
2. 17장 전체 발표 스크립트 Markdown
3. 필요 시 슬라이드 원고 Markdown

권장 파일명:

```text
SiBC_Clinical_Validation_Model_구조중심_발표자료.pptx
SiBC_Clinical_Validation_Model_구조중심_발표스크립트.md
SiBC_Clinical_Validation_Model_구조중심_발표자료_원고.md
```

저장 위치:

```text
/Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/
```

---

# 10. 최종 품질검사

완료 전에 다음을 확인한다.

- 정확히 17장인가?
- 제목과 목차가 포함되었는가?
- 모델의 목적에서 시작해 입력–Rule–Evidence–판정–출력으로 흐름이 이어지는가?
- 결과 수치와 성능 차트가 제거되었는가?
- Clinical Diagnosis Engine의 미구현 내부 로직을 추측하지 않았는가?
- 현행 코드를 설계 의도보다 우선했는가?
- 입력 계약이 mock adapter contract임을 구분했는가?
- `validation.py`의 실제 상태 우선순위를 정확히 반영했는가?
- 후보 단위 검증과 후보 집합 검증을 구분했는가?
- Status, Score, Confidence, CDEI를 분리했는가?
- 기술 gate와 downstream permission을 분리했는가?
- 각 용어가 처음 등장할 때 설명되었는가?
- 클래스명과 파일명이 본문을 과도하게 복잡하게 만들지 않는가?
- 모든 발표자 노트에 `[Sources]`가 포함되었는가?
- 텍스트 잘림, 겹침, 너무 작은 글씨가 없는가?
- 템플릿의 로고·색상·폰트·푸터·페이지 체계를 유지했는가?

최종 보고는 다음 형식으로 간단히 작성한다.

```text
완료 결과
- 생성한 파일
- 슬라이드 수
- 구조 중심으로 변경한 핵심 사항
- 제외한 결과 중심 내용
- 검수 결과
```
