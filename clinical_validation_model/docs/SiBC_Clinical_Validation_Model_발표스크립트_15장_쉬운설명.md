# SiBC Clinical Validation Model 발표 스크립트 — 15장 쉬운 설명

> 기준일: 2026-08-07  
> 예상 발표 시간: 약 12~15분  
> 상태: Concept Design + v0.1.0 기술 프로토타입 / 운영 승인 전 / 임상 성능 미검증

## Slide 01. SiBC Clinical Validation Model

오늘은 Clinical Validation Model을 처음 보시는 분도 이해할 수 있도록 핵심만 설명드리겠습니다. 이 모델은 새로운 진단을 만드는 모델이 아니라, 이미 나온 진단 후보를 한 번 더 안전하게 확인하는 모델입니다. 발표의 핵심은 하나입니다. 근거가 부족하거나 서로 충돌할 때 자동으로 통과시키지 않고 멈출 수 있어야 한다는 것입니다.

[Sources]
- /Users/jaeho.oh/.codex/attachments/39de3905-4237-447b-b550-0d292a207279/pasted-text.txt
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/README.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/MODEL_CARD.md

## Slide 02. 오늘 볼 내용

발표는 세 가지 질문으로 구성했습니다. 첫째, 왜 진단 후보를 다시 검증해야 하는지 보겠습니다. 둘째, 어떤 기준으로 확인하고 어떤 순서로 검증하는지 설명하겠습니다. 마지막으로 결과를 어떻게 읽는지, 현재 어디까지 검증됐고 다음에 무엇이 필요한지 말씀드리겠습니다.

[Sources]
- /Users/jaeho.oh/.codex/attachments/39de3905-4237-447b-b550-0d292a207279/pasted-text.txt

## Slide 03. 한눈에 보는 Clinical Validation

진단 후보는 아직 확정된 진단이 아니라 검토가 필요한 결과입니다. 모델은 이 후보에 필요한 근거가 있는지, 자료의 시점이 맞는지, 반대되는 정보가 있는지, 판단 이유를 설명할 수 있는지 확인합니다. 그다음 사용 가능, 제한 사용, 사람 검토, 사용 보류 중 하나로 결과를 정리합니다. 여기서 Gate는 이런 조건을 확인한 뒤 통과 여부를 결정하는 안전 관문입니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/README.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/MODEL_CARD.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/validation_plan.md

## Slide 04. 왜 검증이 필요한가

후보가 그럴듯해 보여도 네 가지 위험이 남을 수 있습니다. 필수 근거가 빠질 수 있고, 너무 오래됐거나 판단 뒤에 생긴 값이 섞일 수 있습니다. 설문과 검진처럼 서로 다른 자료가 반대 방향을 가리키거나 어떤 규칙과 버전을 사용했는지 설명하지 못할 수도 있습니다. 검증 모델은 이런 후보를 자동으로 확정값처럼 사용하지 않고, 문제와 이유를 드러내는 역할을 합니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/MODEL_CARD.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/validation_plan.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/configs/validation_policy.yaml

## Slide 05. 먼저 알아둘 네 가지 용어

Candidate는 시스템이 제안한 진단 후보이고, Evidence는 그 후보를 지지하거나 반박하는 근거 자료입니다. Rule은 무엇을 어떤 방식으로 확인할지 정한 기준입니다. Gate는 조건을 만족하면 통과시키고, 그렇지 않으면 제한하거나 멈추는 안전 관문입니다. 마지막으로 Status는 이 검증을 거친 뒤 정해지는 결과 상태입니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/README.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/data_contract.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/validation_plan.md

## Slide 06. 네 가지 질문만 기억하면 된다

검증 구조가 복잡해 보여도 네 가지 질문만 기억하면 됩니다. 필요한 근거가 충분한지, 그 근거의 시점이 맞는지, 반대되거나 적용하면 안 되는 근거가 있는지 확인합니다. 마지막으로 어떤 기준과 이유로 판단했는지를 다시 설명할 수 있어야 합니다. 이 네 질문을 후보마다 같은 방식으로 적용하는 것이 모델의 기본 원리입니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/evidence.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/data_quality.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/conflict_detection.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/explainability.py

## Slide 07. 검증은 다섯 단계로 진행된다

첫 단계에서는 어떤 후보를 검토하는지 확인합니다. 다음으로 필수 근거와 참고 근거를 확인하고, 자료의 품질과 시점이 적절한지 봅니다. 이후 상충이나 배제 조건 같은 위험을 확인합니다. 마지막으로 상태를 정하고, 왜 그런 결과가 나왔는지 이유를 기록합니다. 이 기록이 있어야 나중에 같은 판단을 다시 확인할 수 있습니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/pipeline.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/validation.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/configs/validation_policy.yaml

## Slide 08. 필수 조건과 참고 근거는 다르다

필수 조건은 반드시 확인돼야 하는 조건이고, 참고 근거는 판단을 더 잘할 수 있도록 돕는 자료입니다. 참고 근거가 아무리 많아도 빠진 필수 조건을 대신할 수는 없습니다. Hard gate는 이런 필수 조건이 실패했을 때 다른 점수가 높더라도 통과를 막는 장치입니다. 그래서 필수 조건이 없거나 충족되지 않으면 제한이나 보류로 처리합니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/configs/validation_policy.yaml
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/configs/scoring_policy.yaml
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/validation.py

## Slide 09. 좋은 데이터는 값·출처·시점이 맞아야 한다

정확한 값도 언제, 어디서, 어떤 방식으로 측정됐는지가 틀리면 올바른 근거가 아닙니다. 판단 이후에 생긴 자료는 미래 정보를 미리 본 것과 같기 때문에 제외해야 합니다. 너무 오래된 자료는 현재 상태를 설명하기 어려우므로 제한사항을 표시합니다. 또한 기록이 없다는 사실을 실제 행동이 없었다는 의미로 바꾸어 해석해서는 안 됩니다. 관찰 기간은 근거로 인정하는 시간 범위를 뜻합니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/data_quality.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/evidence.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/DATA_SOURCE_INVENTORY.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/01_Results/dev/dev_20260806_171935665683_e912e6b/reports/leakage_audit.md

## Slide 10. 결과는 세 가지 관점으로 읽는다

첫 번째는 기준을 얼마나 충족했는지를 보는 Validation Score입니다. 두 번째는 현재 자료에서 판단이 얼마나 안정적인지를 보는 Decision Confidence입니다. 세 번째 CDEI는 어떤 근거와 기준으로 판단했는지 설명하고 다시 추적할 수 있는 정도를 나타냅니다. Score는 질병 확률이 아니고 Confidence도 후보가 맞을 확률이 아닙니다. 세 지표는 서로 다른 질문에 답하므로 하나의 종합 점수로 합치지 않습니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/scoring.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/confidence.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/cdei.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/MODEL_CARD.md

## Slide 11. 최종 결과는 네 가지 상태로 정리한다

결과는 쉬운 말로 사용 가능, 제한 사용, 사람 검토, 사용 보류로 정리할 수 있습니다. 사용 가능은 현재 Rule 검증을 통과했다는 뜻이고, 제한 사용은 반드시 제한사항을 함께 봐야 합니다. 사람 검토는 충돌이나 불명확한 부분을 사람이 확인해야 하는 상태입니다. 근거 부족, 상충, 적용 불가, 판단 불가 상태는 자동 사용을 보류합니다. 중요한 점은 사용 가능이 확정 진단을 뜻하지 않는다는 것입니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/configs/validation_policy.yaml
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/models.py
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/src/sibc_clinical_validation/validation.py

## Slide 12. 세 사례를 보면 결과가 더 쉽게 보인다

A는 필수 조건이 충족되고 자료 품질과 시점도 양호하며 상충이 없어 사용 가능으로 볼 수 있습니다. B는 필수 조건은 충족했지만 참고 근거가 일부 부족해 제한사항을 붙입니다. C는 겉보기 점수가 높더라도 자료가 충돌하거나 Rule 버전이 불명확해 사람이 확인해야 합니다. 따라서 점수 하나만 보고 후보를 통과시키지 않습니다. 이 사례들은 설명용이며 승인된 실제 cutoff를 뜻하지 않습니다.

[Sources]
- /Users/jaeho.oh/.codex/attachments/39de3905-4237-447b-b550-0d292a207279/pasted-text.txt
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/MODEL_CARD.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/configs/validation_policy.yaml

## Slide 13. 현재 확인된 범위와 한계

현재 저장소에서 자동화 테스트 99개를 다시 실행해 99개 모두 통과했습니다. 합성 검증은 19개 시험 시나리오의 23개 후보가 기대 결과와 모두 일치했습니다. 이는 프로그램의 검증 단계와 안전 분기가 설계대로 동작한다는 기술 기준선입니다. 실제 환자에서 얼마나 정확한지는 아직 확인하지 않았고, 독립적인 전문가 비교 기준도 마련되지 않았습니다. 따라서 기술 통과를 임상 검증 완료로 표현해서는 안 됩니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/tests
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/01_Results/dev/dev_20260806_171935665683_e912e6b/reports/validation_report.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/01_Results/dev/dev_20260806_171935665683_e912e6b/reports/run_summary.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/01_Results/dev/dev_20260806_171935665683_e912e6b/reports/performance_unavailable.md

## Slide 14. 다음은 전문가 기준과 실제 자료 검증이다

다음 단계에서는 먼저 사용할 Rule의 공식 출처와 판본, 사용 권한을 정하고 전문가 승인을 받아야 합니다. 그다음 실제 사용 환경을 대표하는 사례와 독립적인 전문가 비교 기준을 만듭니다. Reference standard는 모델 결과를 보지 않은 전문가들이 별도로 합의한 비교 기준입니다. 이 기준이 생긴 뒤에 실제 성능을 측정하고, 점수의 의미와 승인 기준을 정할 수 있습니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/validation_plan.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/BLOCKERS.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/LICENSE_AND_USAGE_REVIEW.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/CLINICAL_RULE_CANDIDATES.md

## Slide 15. 멈출 줄 아는 검증 모델

Clinical Validation Model의 가치는 높은 숫자를 만드는 데 있지 않습니다. 필요한 근거가 있는지, 시점이 맞는지, 반대되는 정보가 있는지 확인하고 불명확하면 멈추는 데 있습니다. 멈춤은 실패가 아니라 잘못된 자동 사용을 막는 의도된 안전 동작입니다. 현재 확인된 것은 기술 기준선이며, 실제 임상 성능과 운영 승인은 앞으로의 검증 과제입니다.

[Sources]
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/README.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/MODEL_CARD.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/BLOCKERS.md
- /Users/jaeho.oh/Downloads/SiBC/SiBC_project/clinical_validation_model/docs/validation_plan.md
