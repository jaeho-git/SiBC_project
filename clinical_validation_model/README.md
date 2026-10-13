# SiBC Clinical Validation Model

`clinical_validation_model`은 Clinical Diagnosis Engine이 생성한 진단 후보를
검증하는 **Clinical Layer 내부 독립 모듈**이다. 새로운 진단을 생성하거나 개인의
질병·위험·예후 확률을 추정하지 않는다.

```text
Clinical Layer
├── Clinical Diagnosis Engine       # diagnosis candidate 생성
└── Clinical Validation Model       # 근거·규칙·품질·충돌·설명 검증
    └── Validated Clinical Output   # 승인된 경우에만 후속 전달
```

## 현재 상태

| 항목 | 상태 |
|---|---|
| 단계 | Technical Prototype (synthetic scenario 기반) |
| 실제 임상 성능 | `BLOCKED_BY_REFERENCE_STANDARD` |
| 운영 데이터 연결 | `BLOCKED_BY_DB_ACCESS` (승인된 snapshot extraction 없음) |
| 운영 NANDA/Omaha Rule | 미포함 (fixture Rule만 포함) |

## 구현 범위

- YAML Rule schema, completeness/integrity audit, source/license/review 상태
- 필수 기준, 적용 가능성, 배제, 반대 근거, upstream validation, 시간 누수 hard gate
- 후보 단위 판정과 복수 후보 conflict/overlap 검증
- `clinical_validation_score`, 미보정 decision-stability index, CDEI 분리
- Profile/Behavior handoff gate
- 19개 시나리오·23개 후보의 deterministic synthetic technical oracle
- 의료 모델 release artifact의 checksum·mtime·row count·schema 읽기 전용 검증
- release 전용 환경, read-only DB scaffold, SQL allowlist/side-effect 차단
- baseline/previous-best/current/final-selected 집계 비교와 안전 우선 선택
- 12개 기술 그림의 PNG/SVG, figure manifest, 해석 MD/DOCX
- source 재검증, DLP scan, checksum 재검증 후 원자적 release 발행

운영 NANDA/Omaha Rule은 포함하지 않는다. Fixture Rule은 opaque test reference이며
`APPROVED_FOR_TEST`여도 Profile write와 Behavior Layer handoff가 항상 차단된다.

## 실행

```bash
cd clinical_validation_model    # 저장소 루트 기준
uv sync --extra test
uv run python -m sibc_clinical_validation.cli preflight
uv run pytest --cov=sibc_clinical_validation --cov-report=term
uv run python -m sibc_clinical_validation.cli run
```

기본값과 유일한 활성 데이터 환경은 `release`이며 기본 모드는 `artifact`다.
`dev`·`stg` 실행과 환경 fallback은 거부된다. Public manifest의 실행 모드는
`release_artifact`, `release_db`, `synthetic_fixture` 중 하나로 기록된다.

Artifact mode는 `medical_checkup_model`의 최신 pseudonymized release snapshot을
수정하지 않고 metadata와 무결성만 확인한다. DB mode는 TLS·read-only·repeatable
read 제어를 구현했지만 승인된 snapshot extraction이 없어 현재 연결을 시도하지
않고 `BLOCKED_BY_DB_ACCESS`를 반환한다.

## 합성 데이터 분리

```text
medical_checkup_model pseudonymized release artifacts (read-only)
                              +
00_Data/fixtures/synthetic_clinical_layer (synthetic Clinical Layer output)
                              ↓
                  Clinical Validation Model
```

필수 fixture 7개와 별도 synthetic evidence 파일을 제공한다. 모든 합성 row는
origin, synthetic flag, generator/rule version, scenario, 생성시각과 기술적
기대값을 가진다. `expected_*` oracle 필드는 domain object로 로딩되지 않아 판정
feature가 될 수 없다.

## 판정과 해석

지원 상태는 `VALIDATED`, `VALIDATED_WITH_LIMITATIONS`, `REVIEW_REQUIRED`,
`INSUFFICIENT_EVIDENCE`, `CONTRADICTED`, `NOT_APPLICABLE`, `ABSTAIN`이다.

- Clinical Validation Score는 rule 기준 충족 지수이며 확률이 아니다.
- Model Decision Confidence는 현재 `0.0`/`NOT_CALIBRATED`인 판정 안정성
  지수이며 진단확률이 아니다.
- CDEI는 traceability/explainability 지수이며 정확도가 아니다.
- 합성 Scenario accuracy는 실제 임상 정확도가 아니다.

실제 임상 성능은 독립 reference standard가 없어
`BLOCKED_BY_REFERENCE_STANDARD`로 유지한다.

## Release 결과

최종 run은 `01_Results/release/release_<timestamp>_<source-hash>/`에 원자적으로
발행되고 `01_Results/release/latest_run.json`이 이를 가리킨다. 결과에는 다음이
포함된다.

- candidate-level CSV/Parquet/JSONL, CDEI, conflict, data-quality, handoff 결과
- feature/rule/evidence/source registry와 reproducibility manifest
- model performance comparison CSV/Parquet/Markdown
- 필수 그림 12종 PNG/SVG와 figure manifest
- figure interpretation guide MD/DOCX
- automation cycle summary와 final model selection
- security scan, completion manifest, SHA-256 register

## 주요 경로

- `src/sibc_clinical_validation/`: 검증·평가·최적화·시각화 pipeline
- `rules/fixtures/test_rules.yaml`: 비임상 synthetic branch 테스트 규칙
- `00_Data/fixtures/synthetic_clinical_layer/`: deterministic fixtures
- `tests/`: unit/integration/release/security/leakage/reporting tests
- `docs/`: 구조, 계약, 문헌, 라이선스, blocker
- `01_Results/release/`: 로컬 release 결과(버전 관리 제외)

## 문서

| 문서 | 내용 |
|---|---|
| [MODEL_CARD.md](MODEL_CARD.md) | 모델 목적, 범위, 지표 해석과 한계 |
| [CHANGELOG.md](CHANGELOG.md) | 변경 이력 |
| [OPEN_ISSUES.md](OPEN_ISSUES.md) | 미해결 과제와 차단 사항 |
| `docs/architecture.md` | 전체 구조 |
| `docs/data_contract.md` | 입력과 출력 데이터 계약 |
| `docs/validation_plan.md` | 검증 계획 |
| `docs/BLOCKERS.md` | 차단 조건 상세 |
| `docs/DATA_SOURCE_INVENTORY.md`, `docs/LICENSE_AND_USAGE_REVIEW.md` | 데이터 원천과 라이선스 검토 |
| `docs/NANDA_RESEARCH_REGISTER.md`, `docs/OMAHA_RESEARCH_REGISTER.md` | NANDA/Omaha 문헌 조사 기록 |
| `docs/MEDICAL_CHECKUP_REUSE_ANALYSIS.md` | medical_checkup_model 재사용 분석 |

## 남은 차단 사항

- `BLOCKED_BY_CLINICAL_LAYER_CONTRACT`
- `BLOCKED_BY_SURVEY_SOURCE`
- `BLOCKED_BY_LICENSE` / `BLOCKED_BY_CLINICAL_REVIEW`
- `BLOCKED_BY_REFERENCE_STANDARD`
- 운영 conflict matrix, score acceptance 기준, downstream API 미승인

상세 내용은 [OPEN_ISSUES.md](OPEN_ISSUES.md)와 `docs/BLOCKERS.md`를 참조한다.
