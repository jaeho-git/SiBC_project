# SiBC Project

SiBC 서비스에 활용할 신규 데이터 분석 및 예측 모델을 개인적으로 개발·검증하기 위한 저장소입니다.

현재 이 저장소에서는 다음 두 모델을 관리합니다.

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
- 개인정보가 포함된 분석 결과
- 대용량 모델 파일 및 임시 산출물

## Current Status

| Model | Status |
|---|---|
| Medical Checkup Model | Planning / Initial Setup |
| Lifestyle Change Model | Planning / Initial Setup |

두 모델은 현재 처음 시작하는 단계이며, 데이터 점검과 모델 설계를 순차적으로 진행할 예정입니다.

