# SiBC Clinical Validation Model 발표자료 원고

> 문서 상태: Concept Design + v0.1.0 기술 프로토타입 / 합성 기술 oracle 기준선 통과 / 운영 승인 전 / 임상 성능 미검증
> 기준일: 2026-08-06 (Asia/Seoul)
> 사용 주의: 본 원고의 지표 band와 상태 예시는 설명용이며, 승인된 산식·cutoff·실제 임상 성능을 의미하지 않는다.

## Slide 01. Clinical Layer 진단을 그대로 사용할 수 있는가

### 핵심 메시지
진단 후보 생성은 끝이 아니라 검증의 시작이다.

### 슬라이드 본문
- Clinical Diagnosis Engine의 출력은 아직 Diagnosis Candidate다.
- 필수 Evidence 누락, 시간 불일치, 배제 조건, Rule 버전 문제는 생성 단계 이후에도 남을 수 있다.
- 검증 없이 Profile·Behavior Layer로 전달하면 불확실성이 확정값처럼 전파될 수 있다.

### 시각화 제안
‘후보 생성 → 검증 Gate → 후속 사용’ 3단계 흐름도. 검증 전 후보에는 점선 테두리, 검증 후 출력에는 상태 배지를 표시.

### 발표자 노트
Clinical Layer가 기준을 사용했다는 사실만으로 결과의 후속 사용 적합성이 보장되지는 않습니다. 이 발표에서는 후보 생성 알고리즘 자체가 아니라 생성된 후보를 어떻게 검증할지에 집중합니다. 검증의 목적은 의료진을 대신하는 것이 아니라, 확인되지 않은 결과가 자동으로 다음 단계에 전달되는 경로를 통제하는 것입니다.

## Slide 02. 왜 별도 검증 Gate가 필요한가

### 핵심 메시지
생성 오류뿐 아니라 데이터·시간·버전·설명 오류까지 함께 막아야 한다.

### 슬라이드 본문
- 오래된 건강검진이 현재 상태처럼 사용될 수 있다.
- 설문·웨어러블·검진 Evidence가 서로 상충할 수 있다.
- 배제 조건이나 필수 기준 누락이 보조점수에 가려질 수 있다.
- 실행한 Rule과 설명 문구가 다르거나 버전을 추적하지 못할 수 있다.

### 시각화 제안
위험 카드 4개와 중앙의 ‘Clinical Validation Gate’ 방패 아이콘. 각 카드에서 Gate로 화살표 연결.

### 발표자 노트
후보가 그럴듯해 보이는 것과 검증 가능한 것은 다릅니다. 특히 시간 누수와 Rule 버전 문제는 결과 텍스트만 보고는 찾기 어렵습니다. Clinical Validation은 후보와 Evidence, 실행 trace를 함께 보면서 후속 사용을 허용하거나 차단합니다.

## Slide 03. Clinical Validation Model의 목적

### 핵심 메시지
진단기준 적용의 적절성과 후속 사용 가능성을 Rule-based로 판단한다.

### 슬라이드 본문
- 적용 가능성, 필수·보조 기준, Evidence 충분성·일관성을 점검한다.
- 데이터 품질, 시간 정합성, 배제·상충, 설명 추적성을 확인한다.
- 결과는 후보별 상태·지표·제한사항·전달 권한으로 반환한다.
- ‘신뢰’는 질병 확률이나 의료진의 확신도가 아니다.

### 시각화 제안
목적 정의를 중앙 인용문으로 배치하고 주변에 6개 검증 축을 원형으로 배열.

### 발표자 노트
이 모델은 새 진단을 만드는 모델이 아닙니다. 이미 만들어진 후보가 승인된 기준과 현재 Evidence에 비추어 사용 가능한지 평가합니다. 여기서 신뢰는 규칙 검증 결과의 사용 적합성을 뜻하며, 실제 질병 확률과는 구분해야 합니다.

## Slide 04. SiBC Workflow 내 위치

### 핵심 메시지
Clinical Validation은 별도 Layer가 아니라 Clinical Layer 내부의 최종 검증 모듈이다.

### 슬라이드 본문
- Clinical Diagnosis Engine: NANDA/Omaha 기반 Diagnosis Candidate 생성
- Clinical Validation Model: 후보의 Rule·Evidence·품질·시간·충돌 검증
- Clinical Layer 최종 출력: validation 결과와 downstream permission 포함
- 후속 소비자: User Profile 및 Behavior Layer

### 시각화 제안
Clinical Layer 컨테이너 안에 Diagnosis Engine과 Validation Model을 세로 배치하고, 외부에 사용자 데이터와 후속 Layer를 연결.

### 발표자 노트
Validation Model을 별도 Layer로 떼어내지 않는 이유는 Clinical Layer가 자기 출력의 검증 결과까지 책임져야 하기 때문입니다. 입력 Validation은 형식과 기본 품질을 보고, Clinical Validation은 특정 진단 후보를 Evidence가 지지하는지까지 봅니다. 두 검증은 서로 대체하지 않습니다.

## Slide 05. 검증 대상은 Diagnosis Candidate다

### 핵심 메시지
후보는 이름만이 아니라 Rule·Evidence·시간·추론 trace를 함께 가져야 한다.

### 슬라이드 본문
- 후보 식별자, taxonomy·판본, code reference
- applied_rule_ids, rule_version, rule_set_hash
- criteria_met / not_met / not_assessable
- source_evidence_ids, exclusions, contradictions
- index_datetime, observation_window, clinical_reasoning_trace

### 시각화 제안
Diagnosis Candidate 카드에 필드 그룹을 ‘식별·Rule·Evidence·시간·설명’ 다섯 영역으로 구분.

### 발표자 노트
v0.1.0에는 Python dataclass와 기술용 JSONL·CSV·Parquet 출력 계약이 있지만 실제 Clinical Layer와 합의된 production schema는 없습니다. 코드 필드와 목표 외부 계약의 이름, 자료형, 필수 여부, cardinality, null semantics를 별도로 확정해야 합니다. Rule 버전, 기준시점, Evidence 링크가 없으면 Validation Model이 추측해서 채우지 않고 제한이나 보류로 처리해야 합니다.

## Slide 06. 전체 검증 구조

### 핵심 메시지
9단계 검증은 후보별로 동일하게 실행되고 단계별 trace를 남긴다.

### 슬라이드 본문
- 1 적용 가능성 → 2 데이터 품질·시간 → 3 필수 기준
- 4 보조 Evidence → 5 배제·상충 → 6 복수 진단 충돌
- 7 Score·Confidence → 8 CDEI → 9 최종 상태·전달 결정
- 필수 기준과 중대한 배제 조건은 hard gate다.

### 시각화 제안
9개 번호 박스를 3×3 그리드로 배치하고 읽는 순서를 화살표로 표시.

### 발표자 노트
각 단계는 단순 점수 항목이 아니라 감사 가능한 검증 단위입니다. 앞 단계가 실패해도 가능한 범위에서 다른 문제를 기록하면 검토자가 전체 원인을 한 번에 확인할 수 있습니다. v0.1.0 코드에는 prototype 상태 우선순위가 있지만 의료전문가·기획·운영 승인을 받은 최종 정책은 아닙니다.

## Slide 07. Rule과 Evidence를 어떻게 검증하는가

### 핵심 메시지
필수 기준은 전부 평가하고, 보조 근거는 필수 기준을 대신하지 못한다.

### 슬라이드 본문
- 각 기준을 met·not_met·not_assessable로 명시한다.
- 필수 기준 누락·미평가·미충족은 hard gate로 처리한다.
- 보조 Evidence는 출처 다양성·방향 일치·독립성을 확인한다.
- NANDA와 Omaha Rule은 taxonomy별 판본·버전으로 분리한다.

### 시각화 제안
필수 기준 체크리스트와 보조 Evidence 저울을 나란히 배치. 필수 누락 시 빨간 Gate 표시.

### 발표자 노트
많은 보조 Evidence가 있어도 필수 기준이 확인되지 않으면 통과시켜서는 안 됩니다. 같은 원천에서 파생된 여러 값도 독립 근거처럼 중복 계산하지 않습니다. 구체적인 기준 내용은 승인된 공식 자료와 라이선스 범위 안에서만 Rule로 구축해야 합니다.

## Slide 08. Data Quality와 시간 정합성

### 핵심 메시지
좋은 값도 잘못된 시점·단위·출처로 쓰이면 잘못된 Evidence가 된다.

### 슬라이드 본문
- 필수 필드, 자료형, 단위, 중복, provenance를 확인한다.
- Evidence는 index_datetime 이전이고 허용 observation_window 안에 있어야 한다.
- 웨어러블 착용·sync·유효일과 파생 여부를 함께 본다.
- 건강검진 측정시점은 measuredDt를 사용하고 적재시각으로 대체하지 않는다.

### 시각화 제안
기준시점 이전 observation window 타임라인. 오래된 값과 미래 값은 범위 밖에 빨간색으로 표시.

### 발표자 노트
시간 정합성은 Clinical Validation의 핵심 안전장치입니다. 진단 이후의 데이터가 들어가면 미래 정보 혼입이 됩니다. 또한 웨어러블 기록이 없다는 사실을 행동 부재로 해석하면 안 되며, 데이터 생성과정을 함께 봐야 합니다.

## Slide 09. 배제·상충 조건

### 핵심 메시지
반대 근거와 배제 조건은 별도 Gate로 드러내야 한다.

### 슬라이드 본문
- exclusion과 contradiction을 분리해 기록한다.
- 설문·검진·웨어러블 간 방향 불일치를 표시한다.
- 미승인 Rule, edition 혼합, version mismatch를 자동 통과시키지 않는다.
- 설명 문구와 실제 실행 trace의 불일치도 검증한다.

### 시각화 제안
후보 중앙 카드에 찬성 Evidence와 반대 Evidence가 양쪽에서 들어오고, exclusion은 차단 바 형태로 표시.

### 발표자 노트
배제 조건은 단순 감점이 아니라 통과 여부를 바꿀 수 있는 Gate입니다. 상충은 어느 출처가 맞다고 임의로 선택하지 않고 유형과 영향, 검토 필요성을 기록합니다. Rule 버전이 불명확한 경우도 임상 근거 부족과 별개의 거버넌스 문제로 다뤄야 합니다.

## Slide 10. 복수 진단을 어떻게 검증하는가

### 핵심 메시지
사용자별 한 상태가 아니라 후보별 상태를 산출한 뒤 후보 간 충돌을 확인한다.

### 슬라이드 본문
- 여러 NANDA 후보, 여러 Omaha problem 후보가 동시에 존재할 수 있다.
- 각 후보를 독립 검증한 뒤 공존·상호배타 관계를 확인한다.
- 공유 Evidence는 후보-기준-Evidence의 다대다 linkage로 남긴다.
- NANDA와 Omaha 기준을 임의로 합쳐 새로운 Rule을 만들지 않는다.

### 시각화 제안
한 사용자에서 3개 후보로 분기된 뒤 각각 다른 status badge를 받고, 마지막에 conflict matrix를 통과하는 흐름.

### 발표자 노트
후보 A는 VALIDATED이고 후보 B는 근거 부족일 수 있습니다. 이를 사용자 단일 점수로 평균내면 중요한 차이를 잃습니다. 상호배타 관계는 의료전문가가 승인한 conflict matrix가 있을 때만 자동 판정해야 합니다.

## Slide 11. Clinical Validation Score

### 핵심 메시지
진단기준 충족 정도를 요약하지만 질병 확률은 아니다.

### 슬라이드 본문
- 적용 가능성, 필수·보조 기준, Evidence 충분성·일관성
- 시간 정합성, 데이터 품질, 진단 특이성, Rule coverage
- 공식 산식·가중치·결측 처리·cutoff는 미승인
- hard gate 실패를 높은 점수로 상쇄할 수 없음

### 시각화 제안
구성요소 레이더가 아니라 9개 구성 블록과 하단의 ‘Not a probability’ 경고 라벨.

### 발표자 노트
이 점수는 기준 충족을 요약하는 내부 지표입니다. 질병 존재 확률이나 위험확률로 표현하면 안 됩니다. 승인된 reference standard가 없으므로 현재 숫자 cutoff를 정하거나 진단별로 threshold를 조정해서는 안 됩니다.

## Slide 12. Model Decision Confidence

### 핵심 메시지
후보가 맞을 확률이 아니라 현재 Validation Decision의 안정성이다.

### 슬라이드 본문
- 현재 입력과 Rule 상태에서 판정이 얼마나 명확한지 평가한다.
- 경계값·출처 충돌·버전 불명확이면 낮아질 수 있다.
- 미보정 상태는 rule_decision_stability_index로 표시한다.
- model_decision_confidence: 0.0과 calibration_status: NOT_CALIBRATED를 함께 제공한다.

### 시각화 제안
같은 Score라도 안정·불안정한 두 판정 사례를 비교하는 2열 카드.

### 발표자 노트
Confidence라는 단어가 확률로 오해되기 쉽습니다. 그래서 보정 전에는 stability index로 이름을 바꾸고 NOT_CALIBRATED를 명시하는 것이 안전합니다. 실제 전문가 reference와 calibration을 거치기 전에는 0.8 같은 숫자를 의료적 확신으로 해석할 수 없습니다.

## Slide 13. CDEI

### 핵심 메시지
판정의 적절성이 아니라 설명·추적 가능성을 평가한다.

### 슬라이드 본문
- Rule·source·Evidence linkage와 시간 사용을 추적한다.
- 기준별 결과, 충돌, 제한사항을 투명하게 공개한다.
- 동일 입력·Rule로 재현 가능한지 확인한다.
- 높은 CDEI가 높은 Clinical Validation Score를 뜻하지 않는다.

### 시각화 제안
Score·Confidence·CDEI를 서로 겹치지 않는 세 원으로 표현하고 각 질문을 안에 배치.

### 발표자 노트
CDEI는 Clinical Diagnostic Explainability Index의 약자입니다. 현재 SiBC 제안 지표이며 공인 임상 표준으로 확인된 것은 아닙니다. 잘못된 후보라는 판단도 근거를 완전하게 추적하면 CDEI가 높을 수 있습니다.

## Slide 14. Validation Status

### 핵심 메시지
상태는 후보의 검증 결과와 후속 사용 가능성을 함께 요약한다.

### 슬라이드 본문
- VALIDATED / VALIDATED_WITH_LIMITATIONS
- REVIEW_REQUIRED / INSUFFICIENT_EVIDENCE
- CONTRADICTED / NOT_APPLICABLE / ABSTAIN
- 상태마다 reason code, limitation, reviewer requirement가 필요하다.

### 시각화 제안
7개 status badge를 ‘사용 가능·제한·검토·차단’ 4개 영역에 배치한 상태 맵.

### 발표자 노트
VALIDATED는 확정 임상진단이 아니라 Rule 검증 통과를 뜻합니다. REVIEW_REQUIRED는 충돌이나 경계 문제를 사람이 풀어야 하는 상태이고, INSUFFICIENT_EVIDENCE는 필요한 근거가 부족한 상태입니다. ABSTAIN은 안전한 자동 결정을 내릴 수 없을 때 사용하는 포괄적 보류입니다.

## Slide 15. 결과 해석 예시

### 핵심 메시지
세 지표와 상태를 함께 봐야 하며 점수 하나로 통과시키지 않는다.

### 슬라이드 본문
- A: VALIDATED — 필수 기준·품질·시간·trace 양호
- B: VALIDATED_WITH_LIMITATIONS — 필수 통과, 보조 Evidence 일부 누락
- C: REVIEW_REQUIRED — Score가 높아도 충돌·버전 문제로 Confidence 낮음
- 높음·중간 등 표시는 설명용이며 운영 cutoff가 아님

### 시각화 제안
A/B/C 3개 결과 카드에 status와 세 지표의 정성 band를 표시.

### 발표자 노트
사례 C가 특히 중요합니다. 필수 기준을 충족해 Validation Score가 높더라도 Rule 버전이 불명확하거나 Evidence가 상충하면 Decision Confidence는 낮을 수 있습니다. 이런 후보를 점수만 보고 통과시키지 않는 것이 검증 Gate의 역할입니다.

## Slide 16. Profile 및 Behavior Layer Gate

### 핵심 메시지
후속 Layer는 score를 해석하지 않고 명시적 permission과 제한사항을 사용한다.

### 슬라이드 본문
- VALIDATED: 권고안상 Profile·Behavior 전달 가능
- VALIDATED_WITH_LIMITATIONS: 제한사항과 승인된 범위 안에서만
- REVIEW_REQUIRED·INSUFFICIENT·CONTRADICTED·NOT_APPLICABLE·ABSTAIN: 원칙적으로 Behavior 전달 금지
- 기술용 handoff 필드는 구현됐으나 production API는 미확정

### 시각화 제안
Status별 Profile/Behavior 통과 여부를 녹색·노란색·빨간색 Gate로 표시한 매트릭스.

### 발표자 노트
후속 Layer가 임의로 점수를 해석하면 같은 결과가 시스템마다 다르게 쓰일 수 있습니다. 프로토타입은 profile_write_allowed와 behavior_handoff_allowed를 명시하며 test-only Rule에서는 모두 차단합니다. 실제 Profile·Behavior API와 운영 승인 계약은 아직 없습니다.

## Slide 17. Synthetic Dataset 기반 구축

### 핵심 메시지
19개 합성 시나리오와 23개 후보로 기술 동작을 검증하되 임상 성능과 분리한다.

### 슬라이드 본문
- Candidate·Criteria·Evidence·link·expected oracle을 결정론적 fixture로 분리한다.
- 19개 시나리오·23개 후보가 누락·배제·상충·시간누수·버전·설명 오류를 포함한다.
- expected_* 필드는 allowlist domain object에 들어가지 않아 판정 feature가 될 수 없다.
- 건강검진 release artifact는 수정 없이 metadata·integrity만 감사한다.
- 합성 결과는 실제 임상 성능을 증명하지 못한다.

### 시각화 제안
read-only artifact fingerprint와 Synthetic Candidate·Evidence가 분리돼 기술 oracle로 들어가는 구조도.

### 발표자 노트
현재 실제 Clinical Layer output이 없기 때문에 합성 후보와 Evidence로 기술 경로를 검증합니다. 기대 판정은 엔진 입력에서 차단하고 별도 oracle 비교에만 사용합니다. 이 기준선은 분기와 Gate, trace, 재현성을 시험하지만 임상 정답이 아닙니다.

## Slide 18. 현재 가능한 것과 불가능한 것

### 핵심 메시지
자동화·합성 기술 기준선은 통과했지만 임상 검증과 운영 전달은 여전히 차단돼 있다.

### 슬라이드 본문
- TECHNICAL_PROTOTYPE: IMPLEMENTED
- AUTOMATED_TEST_SUITE: PASSED_LOCAL_77
- SYNTHETIC_TECHNICAL_ORACLE: PASSED_23_OF_23
- CURRENT_SOURCE_ARTIFACT_RUN: PASSED
- OPERATIONAL_HANDOFF: BLOCKED
- CLINICAL_VALIDATION: BLOCKED_BY_REFERENCE_STANDARD
- REAL_WORLD_PERFORMANCE: NOT_AVAILABLE
- 건강검진 예측은 별도로 BLOCKED_BY_DATA

### 시각화 제안
검증 성숙도 계단. 구현·자동화 test·합성 oracle은 통과, production 통합·임상·운영에는 차단 배지를 표시.

### 발표자 노트
v0.1.0은 77개 로컬 자동화 test를 통과하고 19개 합성 시나리오의 23개 후보를 기술 oracle과 비교합니다. 최신 artifact-mode run은 현재 source hash와 일치하고 source mutation check도 통과했지만, 결과는 기록된 합성 fixture와 artifact metadata 범위에 한정됩니다. sensitivity, specificity, PPV, NPV, calibration과 개인별 신뢰성은 여전히 주장할 수 없습니다.

## Slide 19. 향후 단계

### 핵심 메시지
통과한 합성 기준선을 고정하고 production 계약·Rule 거버넌스·전문가 임상 검증으로 이동한다.

### 슬라이드 본문
- 실제 Clinical Layer output과 정식 Candidate/Evidence schema 확보
- 승인된 실제 data snapshot·품질 metadata·read-only query 통합
- 승인된 NANDA/Omaha Rule, 판본·라이선스·version registry 구축
- 합성 oracle·보안·시간누수 회귀 기준을 CI와 source hash로 고정
- 전문가 reference standard와 adjudication protocol 구축
- 임상 검증·Confidence calibration·cutoff 승인·운영 승인

### 시각화 제안
5단계 로드맵. 각 단계의 완료 조건과 승인 주체 아이콘을 함께 표시.

### 발표자 노트
가장 먼저 필요한 것은 모델 점수가 아니라 production 입력·출력 계약과 데이터 품질 계약입니다. 다음으로 Rule의 출처와 판본, 라이선스를 고정하고 합성 oracle을 회귀 기준으로 관리해야 합니다. 실제 성능과 cutoff는 독립된 전문가 reference standard가 생긴 뒤에만 논의할 수 있습니다.

## Slide 20. 결론: 검증은 ‘더 확신하는 모델’이 아니라 ‘멈출 줄 아는 Gate’다

### 핵심 메시지
후보별 근거·시간·충돌·설명을 검증하고 안전한 사용 범위를 명시하는 것이 핵심이다.

### 슬라이드 본문
- 진단 후보 생성과 후속 사용 사이에 독립된 검증 책임을 둔다.
- 필수 기준 hard gate, 후보별 status, 세 지표 분리를 유지한다.
- 불명확하면 REVIEW_REQUIRED 또는 ABSTAIN하고 자동 전달을 차단한다.
- production output·승인 Rule·전문가 기준 확보 전에는 임상 성능을 주장하지 않는다.

### 시각화 제안
최종 한 장 요약: Candidate → Validation Gate → ①사용 ②제한 사용 ③검토 ④차단의 네 갈래.

### 발표자 노트
Clinical Validation Model의 핵심은 더 높은 숫자를 만드는 것이 아닙니다. 무엇이 없거나 충돌할 때 멈출지를 명시하고, 그 이유를 재현 가능하게 남기는 것입니다. 현재 문서는 이 목표 구조의 기획 기준이며 구현과 운영 승인을 뜻하지 않습니다.

## 제작 시 공통 주의사항

- `VALIDATED`를 확정 임상진단, 질병 확률 또는 의료진의 확신도로 표현하지 않는다.
- Clinical Validation Score, Model Decision Confidence, CDEI를 하나의 점수로 합치지 않는다.
- 자동화 test와 합성 기술 oracle 통과를 임상 검증과 구분하고, 임상 검증은 `BLOCKED_BY_REFERENCE_STANDARD`, 운영 handoff는 `BLOCKED`, 실제 운영 성능은 `NOT_AVAILABLE`로 표시한다.
- 건강검진 예측의 `BLOCKED_BY_DATA` 상태와 actual·measured·derived·pred·risk 구분을 유지한다.
- NANDA 상세 기준을 슬라이드에 복제하지 않고 판본·라이선스·Rule governance만 설명한다.
- 원시 건강정보, 사용자 식별자, DB 접속정보 또는 Secret을 포함하지 않는다.
