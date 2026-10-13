# SiBC Clinical Validation Model 발표 스크립트

> 기준일: 2026-08-06 (Asia/Seoul)  
> 예상 발표 시간: 약 18~20분  
> 문서 상태: Concept Design + v0.1.0 기술 프로토타입 / 운영 승인 전 / 임상 성능 미검증  
> 주의: 슬라이드의 정성 band와 상태 예시는 설명용이며 승인된 cutoff 또는 실제 임상 성능을 뜻하지 않습니다.

## Slide 01. Clinical Layer 진단을 그대로 사용할 수 있는가

Clinical Diagnosis Engine이 후보를 만들었다고 해서 후속 사용이 바로 허용되는 것은 아닙니다. 후보에는 필수 근거의 누락, 시간 불일치, 배제 조건, Rule 버전 문제처럼 생성 이후에야 드러나는 위험이 남을 수 있습니다. 이 발표에서 다루는 Clinical Validation Model은 새로운 진단을 만드는 모델이 아니라, 생성된 후보가 현재 근거와 승인된 기준에 비추어 사용 가능한지를 확인하는 Gate입니다. 핵심은 더 확신하는 것이 아니라, 확인되지 않은 결과가 Profile과 Behavior Layer로 확정값처럼 전달되는 경로를 통제하는 것입니다.

[Sources]
- /Users/jaeho.oh/.codex/attachments/a67460f1-2de4-4744-89c9-c49e149e2bb2/pasted-text.txt
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/README.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/MODEL_CARD.md

## Slide 02. 왜 별도 검증 Gate가 필요한가

후보가 그럴듯해 보이는 것과 검증 가능한 것은 다릅니다. 오래된 검진이 현재 상태처럼 사용되거나, 설문·웨어러블·검진이 서로 다른 방향을 가리킬 수 있습니다. 실행한 Rule과 설명 문구가 다르거나 어떤 판본을 사용했는지 추적하지 못하는 문제는 결과 텍스트만으로 발견하기 어렵습니다. 그래서 Gate는 후보만 보는 것이 아니라 Evidence, 기준시점, Rule provenance, 실행 trace를 함께 확인하고 사용·제한·검토·차단 중 하나로 경로를 결정합니다.

[Sources]
- /Users/jaeho.oh/.codex/attachments/a67460f1-2de4-4744-89c9-c49e149e2bb2/pasted-text.txt
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/MODEL_CARD.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/architecture.md

## Slide 03. Clinical Validation Model의 목적

이 모델의 목적은 진단을 다시 예측하는 것이 아니라, 이미 생성된 후보가 승인된 Rule과 적격 Evidence에 의해 추적 가능한지를 판단하는 것입니다. 적용 가능성, 필수·보조 기준, 데이터 품질, 시간 정합성, 배제와 상충, 설명 재현성을 분리해서 확인합니다. 결과는 후보별 상태와 세 가지 지표, 제한사항, 사람 검토 필요성, downstream permission으로 반환합니다. 여기서 ‘신뢰’는 질병 확률이나 의료진의 확신도가 아니라, 현재 Rule 검증 결과를 어디까지 사용할 수 있는지를 뜻합니다.

[Sources]
- /Users/jaeho.oh/.codex/attachments/a67460f1-2de4-4744-89c9-c49e149e2bb2/pasted-text.txt
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/README.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/MODEL_CARD.md

## Slide 04. SiBC Workflow 내 위치

Clinical Validation Model은 별도의 Workflow Layer가 아니라 Clinical Layer가 자기 출력을 검증하는 마지막 모듈입니다. Diagnosis Engine은 후보를 생성하고, Validation Model은 그 후보의 Rule·Evidence·품질·시간·충돌을 검증합니다. 입력 Validation이 형식과 기본 품질을 확인한다면, Clinical Validation은 특정 후보가 실제로 어떤 Evidence에 의해 지지되는지까지 확인합니다. 이 검증 결과와 명시적 전달 권한이 포함된 경우에만 Profile이나 Behavior Layer가 후속 처리를 검토할 수 있습니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/architecture.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/README.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/data_contract.md

## Slide 05. 검증 대상은 Diagnosis Candidate다

검증 대상은 단순한 진단명 문자열이 아니라 구조화된 Diagnosis Candidate입니다. 후보에는 taxonomy와 판본, 적용 Rule과 해시, 기준별 충족 상태, Evidence linkage, 배제·상충, 기준시점과 관찰기간, 추론 trace가 함께 있어야 합니다. 현재 v0.1.0에는 기술용 dataclass와 출력 형식이 있지만 실제 Clinical Layer와 합의된 production schema는 없습니다. 따라서 필드명, 자료형, 필수 여부, cardinality와 null 의미를 정식 계약으로 확정해야 하며, Rule 버전이나 Evidence 링크가 없을 때 모델이 임의로 보완해서는 안 됩니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/data_contract.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/models.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/rule_schema.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/BLOCKERS.md

## Slide 06. 전체 검증 구조

검증은 적용 가능성부터 최종 전달 결정까지 아홉 단계로 실행됩니다. 데이터 품질과 시간, 필수 기준, 보조 Evidence, 배제와 상충, 후보 간 충돌을 차례로 확인한 뒤 Score·Confidence·CDEI와 상태를 산출합니다. 필수 기준, 중대한 배제, 미승인 Rule, 미래 정보 혼입 같은 조건은 평균 점수로 상쇄할 수 없는 hard gate입니다. 앞 단계에서 문제가 발견되더라도 가능한 범위의 나머지 검증을 수행해, 검토자가 전체 blocker와 trace를 한 번에 볼 수 있도록 합니다. 단, 현재 상태 우선순위는 prototype 정책이며 운영 승인된 최종 임상 정책은 아닙니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/configs/validation_policy.yaml
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/configs/scoring_policy.yaml
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/pipeline.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/validation.py

## Slide 07. Rule과 Evidence를 어떻게 검증하는가

각 기준은 충족, 미충족, 평가 불가의 세 상태로 명시적으로 평가합니다. 필수 기준이 누락되거나 평가할 수 없으면 보조 Evidence가 많아도 이를 대신해 통과시킬 수 없습니다. 같은 원천에서 파생된 여러 값도 독립된 근거처럼 중복 계산하지 않고 출처·방향·독립성을 확인해야 합니다. NANDA-I와 Omaha는 각각의 판본과 provenance를 유지하고 임의로 혼합하지 않습니다. 특히 NANDA-I 콘텐츠의 소프트웨어 사용은 정식 권한 범위를 확인해야 하며, Omaha의 공개 용어·코드 범위 역시 로컬 임상 규칙의 승인을 의미하지 않습니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/LICENSE_AND_USAGE_REVIEW.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/NANDA_RESEARCH_REGISTER.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/OMAHA_RESEARCH_REGISTER.md
- https://nanda.org/use-and-licensing/
- https://nanda.org/nanda-book/
- https://www.omahasystem.org/overview
- https://www.omahasystem.org/problemclassificationscheme

## Slide 08. Data Quality와 시간 정합성

좋은 값도 잘못된 시점이나 단위, 출처로 사용되면 잘못된 Evidence가 됩니다. 모든 Evidence는 기준시점 이전에 존재하고 허용된 observation window 안에 있어야 하며, 진단 이후의 데이터는 미래 정보 혼입으로 차단합니다. 건강검진은 적재 시각이 아니라 실제 측정시각을 사용해야 하고, 웨어러블은 착용·동기화·유효일과 파생 여부를 함께 확인해야 합니다. 특히 기록이 없다는 사실을 행동이 없었다는 의미로 바꾸어 해석해서는 안 됩니다. Clinical Validation은 값뿐 아니라 그 값이 생성된 과정까지 검증합니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/data_quality.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/evidence.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/DATA_SOURCE_INVENTORY.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/01_Results/dev/dev_20260806_171935665683_e912e6b/reports/leakage_audit.md

## Slide 09. 배제·상충 조건

찬성 Evidence만 모으면 후보는 쉽게 그럴듯해집니다. 그래서 exclusion과 contradiction은 일반 감점 항목이 아니라 별도의 Gate와 reason code로 드러내야 합니다. 출처 간 방향이 다를 때 모델이 어느 한쪽을 임의로 정답으로 선택하지 않고, 충돌 유형과 영향, 사람 검토 필요성을 기록합니다. 미승인 Rule, 판본 혼합, version mismatch도 임상 근거 부족과 구분되는 거버넌스 blocker입니다. 설명 문구가 실제 실행 trace와 다르면 결과가 맞아 보이더라도 검증 가능한 출력으로 볼 수 없습니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/configs/rule_policy.yaml
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/conflict_detection.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/explainability.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/CLINICAL_RULE_CANDIDATES.md

## Slide 10. 복수 진단을 어떻게 검증하는가

한 사용자에게 여러 NANDA 또는 Omaha 후보가 동시에 존재할 수 있기 때문에 사용자 단위의 한 점수로 요약해서는 안 됩니다. 먼저 후보마다 독립적인 Validation Status를 산출하고, 그다음 후보 간 공존·중복·상호배타 관계를 확인합니다. 공유 Evidence는 후보–기준–Evidence의 다대다 linkage로 남겨 어떤 근거가 어디에 사용됐는지 추적할 수 있어야 합니다. 후보 A가 통과하고 후보 B가 근거 부족일 수 있다는 차이를 평균내면 중요한 안전 신호가 사라집니다. 자동 conflict 판정은 의료전문가가 승인한 versioned matrix가 있을 때만 허용해야 합니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/conflict_detection.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/configs/validation_policy.yaml
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/data_contract.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/BLOCKERS.md

## Slide 11. Clinical Validation Score

Clinical Validation Score는 적용 가능성, 필수·보조 기준, Evidence 충분성, 시간과 품질 등을 요약하는 Rule 충족 지수입니다. 질병이 존재할 확률이나 개인 위험확률은 아닙니다. 더 중요한 것은 hard gate가 실패하면 높은 구성요소 점수로 이를 상쇄하지 않는다는 점입니다. 현재 repository에는 prototype 가중치가 있지만 공식 산식, 결측 처리, 진단별 cutoff, 운영 acceptance 기준은 승인되지 않았습니다. 따라서 지금 단계에서 80점 이상이면 안전하다는 식의 threshold를 제시해서는 안 됩니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/configs/scoring_policy.yaml
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/scoring.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/MODEL_CARD.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/validation_plan.md

## Slide 12. Model Decision Confidence

Model Decision Confidence는 후보가 맞을 확률이 아니라, 현재 입력과 Rule 상태에서 Validation Decision이 얼마나 안정적인지를 나타냅니다. 경계값에 가깝거나 Evidence가 충돌하고 Rule 버전이 불명확하면 판정 안정성은 낮아질 수 있습니다. 확률로 오해되는 것을 막기 위해 prototype은 이를 `rule_decision_stability_index`로 구분하며, 보정 전 confidence 값은 0.0, 상태는 `NOT_CALIBRATED`로 제공합니다. 전문가 reference와 calibration이 없는 상태에서 0.8 같은 숫자를 의료적 확신으로 표현하는 것은 허용되지 않습니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/confidence.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/MODEL_CARD.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/01_Results/dev/dev_20260806_171935665683_e912e6b/artifacts/reproducibility_manifest.json

## Slide 13. CDEI

CDEI는 판정이 맞는지를 평가하는 정확도 지표가 아니라, 그 판정을 얼마나 설명하고 추적할 수 있는지를 평가합니다. 어떤 Rule과 source를 사용했는지, Evidence가 어떤 기준에 연결됐는지, 시간과 충돌을 어떻게 처리했는지, 동일 입력에서 재현 가능한지를 확인합니다. 따라서 잘못된 후보라고 판단한 결과도 그 근거가 완전하게 추적되면 CDEI가 높을 수 있습니다. 반대로 Validation Score가 높아도 trace가 불완전하면 CDEI는 낮아야 합니다. CDEI는 현재 SiBC 제안 지표이며 공인 임상 표준으로 확인된 지표는 아닙니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/configs/cdei_policy.yaml
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/cdei.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/01_Results/dev/dev_20260806_171935665683_e912e6b/reports/cdei_validation.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/MODEL_CARD.md

## Slide 14. Validation Status

상태는 후보의 검증 결과와 후속 사용 가능성을 함께 요약합니다. `VALIDATED`는 확정 임상진단이 아니라 Rule 검증을 통과했다는 뜻이고, `VALIDATED_WITH_LIMITATIONS`는 제한사항을 반드시 함께 전달해야 하는 상태입니다. `REVIEW_REQUIRED`는 사람이 충돌이나 경계 문제를 해결해야 하며, `INSUFFICIENT_EVIDENCE`는 필요한 근거가 부족한 상태입니다. `CONTRADICTED`, `NOT_APPLICABLE`, `ABSTAIN`은 자동 전달을 허용하지 않는 차단 또는 보류 상태입니다. 모든 상태에는 reason code, limitation, reviewer requirement가 함께 있어야 합니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/configs/validation_policy.yaml
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/models.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/validation.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/README.md

## Slide 15. 결과 해석 예시

세 사례의 차이는 한 점수만으로는 보이지 않습니다. A는 필수 기준과 시간, 품질, trace가 모두 양호해 `VALIDATED`가 될 수 있습니다. B는 필수 기준은 통과했지만 보조 Evidence 일부가 부족해 제한사항을 동반한 상태입니다. C가 가장 중요한 사례로, Validation Score가 높더라도 Rule 버전이 불명확하거나 Evidence가 상충하면 Decision Confidence가 낮고 사람 검토가 필요합니다. 이 예시의 높음·중간 band는 설명용일 뿐, 승인된 cutoff나 실제 임상 성능을 뜻하지 않습니다.

[Sources]
- /Users/jaeho.oh/.codex/attachments/a67460f1-2de4-4744-89c9-c49e149e2bb2/pasted-text.txt
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/MODEL_CARD.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/configs/validation_policy.yaml
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/configs/scoring_policy.yaml

## Slide 16. Profile 및 Behavior Layer Gate

후속 Layer가 점수를 각자 해석하면 같은 후보가 시스템마다 다르게 사용될 수 있습니다. 그래서 출력에는 `profile_write_allowed`와 `behavior_handoff_allowed`를 명시하고 제한사항과 차단 이유도 함께 전달합니다. Prototype 정책상 test-only Rule은 상태가 좋아 보이더라도 Profile write와 Behavior handoff가 모두 차단됩니다. `REVIEW_REQUIRED`, `INSUFFICIENT_EVIDENCE`, `CONTRADICTED`, `NOT_APPLICABLE`, `ABSTAIN` 역시 원칙적으로 Behavior 전달 대상이 아닙니다. 기술용 필드는 구현됐지만 실제 Profile·Behavior production API와 운영 승인 계약은 아직 없습니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/behavior_handoff.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/data_contract.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/01_Results/dev/dev_20260806_171935665683_e912e6b/outputs/behavior_handoff.csv
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/BLOCKERS.md

## Slide 17. Synthetic Dataset 기반 구축

현재 실제 Clinical Layer production output이 없기 때문에 합성 Candidate와 Evidence로 기술 경로를 검증합니다. Fixture는 19개 시나리오와 23개 후보로 구성되고, 누락·배제·상충·미래 정보·버전 오류·설명 불일치 같은 분기를 포함합니다. 기대 결과인 `expected_*` 필드는 allowlist 기반 domain object에 들어가지 않아 모델 판정 feature로 사용될 수 없습니다. 건강검진 release artifact는 내용을 수정하지 않고 실행 전후 fingerprint와 integrity만 확인합니다. 이 기준선은 Rule 엔진과 Gate, trace, 재현성을 검증하지만 실제 환자에서의 임상 정답이나 성능을 증명하지 않습니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/synthetic.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/00_Data/fixtures/synthetic_clinical_layer/synthetic_generation_manifest.json
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/validation_plan.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/01_Results/dev/dev_20260806_171935665683_e912e6b/artifacts/reproducibility_manifest.json

## Slide 18. 현재 가능한 것과 불가능한 것

현재 확인된 성과와 아직 주장할 수 없는 범위를 분리해서 보겠습니다. 현재 저장소에서 로컬 자동화 테스트 97개를 다시 실행해 모두 통과했고, 최신 artifact-mode run은 19개 시나리오와 23개 후보에서 기술 oracle 23건 모두 일치했습니다. source mutation check도 통과했으며, 보안 스캔은 텍스트 파일 35개에서 finding 0건을 기록하고 최신 run은 37개 checksum 파일을 관리합니다. 그러나 임상 성능은 `BLOCKED_BY_REFERENCE_STANDARD`, 운영 handoff는 `BLOCKED`, 실제 sensitivity·specificity·PPV·NPV·calibration은 `NOT_AVAILABLE`입니다. 따라서 기술 기준선 통과를 임상 검증 완료로 표현해서는 안 됩니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/tests
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/01_Results/dev/latest_run.json
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/01_Results/dev/dev_20260806_171935665683_e912e6b/reports/run_summary.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/01_Results/dev/dev_20260806_171935665683_e912e6b/reports/validation_report.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/01_Results/dev/dev_20260806_171935665683_e912e6b/artifacts/security_scan.json
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/01_Results/dev/dev_20260806_171935665683_e912e6b/reports/performance_unavailable.md

## Slide 19. 향후 단계

다음 단계에서 가장 먼저 필요한 것은 새로운 점수가 아니라 production 입력·출력 계약입니다. 실제 Clinical Layer output과 Candidate·Evidence schema, 데이터 품질과 read-only snapshot 계약을 먼저 확정해야 합니다. 이후 Rule의 공식 출처, 판본, 라이선스, 로컬 mapping과 conflict matrix를 분리해 version registry로 관리해야 합니다. 현재 합성 oracle, 시간 누수, 보안, source mutation 기준은 CI 회귀 기준으로 고정할 수 있습니다. 마지막으로 독립된 전문가 reference standard와 blinded adjudication을 구축한 뒤 임상 검증, Confidence calibration, cutoff 승인, 운영 handoff 승인의 순서로 진행해야 합니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/BLOCKERS.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/validation_plan.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/LICENSE_AND_USAGE_REVIEW.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/CLINICAL_RULE_CANDIDATES.md
- https://nanda.org/use-and-licensing/
- https://www.omahasystem.org/overview

## Slide 20. 결론: 검증은 ‘더 확신하는 모델’이 아니라 ‘멈출 줄 아는 Gate’다

Clinical Validation Model의 핵심은 더 높은 숫자를 만드는 데 있지 않습니다. 후보별로 어떤 Rule과 Evidence가 사용됐는지, 기준시점이 맞는지, 무엇이 상충하거나 빠졌는지를 확인하고 안전한 사용 범위를 명시하는 것이 목적입니다. 필수 기준은 hard gate로 유지하고, Validation Score·Decision Confidence·CDEI는 서로 다른 질문에 답하는 지표로 분리해야 합니다. 불명확하면 `REVIEW_REQUIRED` 또는 `ABSTAIN`하고 자동 전달을 차단해야 합니다. 현재 결과는 목표 구조와 기술 prototype의 근거이며, production output·승인 Rule·독립 reference standard가 확보되기 전에는 임상 성능이나 운영 승인을 의미하지 않습니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/README.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/MODEL_CARD.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/BLOCKERS.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/validation_plan.md
