# SiBC Project

SiBC 서비스에 활용할 신규 데이터 분석 및 예측 모델을 개인적으로 개발·검증하기 위한 저장소입니다.

현재 이 저장소에서는 다음 네 모델을 관리합니다.

## Models

### 1. Medical Checkup Model

웨어러블 데이터를 기반으로 일부 건강검진 결과를 예측하고, 건강 상태 악화 탐지 및 적절한 건강검진·의료지원 연계를 지원하는 모델입니다.

경로:

```text
medical_checkup_model/
```

### 2. Lifestyle Change Model

웨어러블 및 생활 데이터를 기반으로 사용자의 활동, 수면 등 생활습관 변화를 감지하고, 장기적인 행동 변화 여부를 평가하기 위한 모델입니다.

경로:

```text
lifestyle_change_model/
```

### 3. Clinical Validation Model

Clinical Layer가 생성한 NANDA/Omaha 기반 진단 후보의 규칙, 근거 연결,
시간 정합성, 데이터 품질, 충돌 및 설명 가능성을 독립 검증하는 내부 모듈입니다.
현재 구현은 synthetic scenario 기반 기술 프로토타입이며 실제 임상 성능은
`BLOCKED_BY_REFERENCE_STANDARD`입니다.

경로:

```text
clinical_validation_model/
```

### 4. Dietary Analysis Model

푸드렌즈(FoodLens)에서 들어온 식사 기록 DB를 사용자별 식이분석이 가능한 데이터
테이블로 구축하고, 결정론적 규칙 엔진으로 영양소 섭취 수준을 5단계(부족, 약간부족,
적절, 약간과잉, 과잉)로 판정하는 모델입니다. 하나의 판정 결과를 사용자에게는 부족 및
과잉에 대한 안내로, 의료진에게는 기준과 데이터 출처가 명시된 판정 리포트로 제공합니다.

- 기본 기준은 KDRIs 2025이며, 의료진은 원하는 가이드라인(국내 임상학회 지침 등)을
  선택해 식이분석을 진행할 수 있습니다. 국외 기준은 참고로 병기합니다.
- 모든 판정에 기관, 지침명, 기준 연도, 데이터 출처(설문 추정 또는 기록 기반, 기록
  일수)를 표기합니다.
- 진단이나 처방이 아니라 의학적 판단의 근거 자료를 제공합니다.

현재 설계 확정 및 구현 착수 전 단계이며, 상세 내용은
`dietary_analysis_model/docs/HANDOVER_20261014.md`를 참조합니다.

경로:

```text
dietary_analysis_model/
```

## Repository Structure

```text
SiBC_project/
├── README.md
├── PROJECT_RULES.md
├── .gitignore
├── .env.example
├── .env.dev
├── .env.stg
├── .env.release
│
├── medical_checkup_model/
│   ├── README.md
│   ├── 00_Data/
│   ├── 01_Results/
│   ├── src/
│   ├── scripts/
│   └── docs/
├── clinical_validation_model/
│   ├── README.md
│   ├── 00_Data/
│   ├── 01_Results/
│   ├── configs/
│   ├── rules/
│   ├── src/
│   ├── tests/
│   └── docs/
├── dietary_analysis_model/
│   ├── README.md
│   ├── 00_Data/
│   ├── 01_Results/
│   └── docs/
│
└── lifestyle_change_model/
    ├── README.md
    ├── 00_Data/
    ├── 01_Results/
    ├── src/
    ├── scripts/
    └── docs/
```

## Folder Rules

| 폴더 | 용도 |
|---|---|
| `00_Data` | 원본 데이터, 중간 데이터, 모델 입력 데이터 |
| `01_Results` | 분석 결과, 예측 결과, 모델 파일, 그림, 보고서 |
| `src` | 재사용 가능한 핵심 로직과 함수 |
| `scripts` | 데이터 점검, 전처리, 학습, 평가, 보고서 생성 실행 파일 |
| `docs` | 데이터 정의, 모델 설계, 검증 기준, 의사결정 기록 |

## Environment Files

실행 환경은 다음 파일로 구분합니다.

```text
.env.dev
.env.stg
.env.release
```

환경 파일에는 DB 접속정보와 인증정보가 포함될 수 있으므로 Git에 업로드하지 않습니다.

Git에 포함되는 `.env.example`에는 변수명만 작성하고 실제 값은 넣지 않습니다.

## Git Rules

- `main`: 안정된 기준 버전
- `develop`: 통합 개발 브랜치
- `feature/*`: 기능별 작업 브랜치
- `fix/*`: 오류 수정 브랜치

예시:

```bash
git switch develop
git pull origin develop
git switch -c feature/medical-checkup-data-audit
```

작업 완료 후:

```bash
git status
git add .
git commit -m "feat: add medical checkup data audit"
git push -u origin feature/medical-checkup-data-audit
```

## Security Rules

다음 파일과 정보는 GitHub에 업로드하지 않습니다.

- `.env.dev`
- `.env.stg`
- `.env.release`
- DB 비밀번호 및 인증정보
- 실제 사용자 식별정보
- 원본 웨어러블 데이터
- 건강검진 원본 데이터
- 푸드렌즈 원본 식사 기록 및 CAN-Pro 추출 데이터
- 개인정보가 포함된 분석 결과
- 대용량 모델 파일 및 임시 산출물

## Current Status

| Model | Status |
|---|---|
| Medical Checkup Model | Prototype / 예측 파이프라인 구현 중 |
| Lifestyle Change Model | Planning / Initial Setup |
| Clinical Validation Model | Technical Prototype / Clinical Validation Blocked |
| Dietary Analysis Model | Design / 구현 착수 전 |

각 모델은 모델별 상태와 차단 조건에 맞춰 데이터 점검과 모델 설계를 순차적으로 진행합니다.
