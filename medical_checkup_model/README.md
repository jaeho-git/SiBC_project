# SiBC 웨어러블 → 건강검진 예측 모델

구축가이드 v1.3(`docs/SiBC_웨어러블_건강검진예측모델_구축가이드_20260901.md`)의
**통합 학습(joint training) 프레임** 구현입니다. 공공데이터(NHANES)와 자체
데이터를 처음부터 한 학습 테이블로 학습하고, 재학습 주기마다 자체 데이터
비중을 확대합니다. 검증은 처음부터 끝까지 자체 봉인 라벨로만 수행합니다.

## 구조

```
00_Data/
  public/          # 공공데이터 (git 제외; 로컬 다운로드)
    nhanes/        #   2011-2012(G), 2013-2014(H): DEMO/BPX/BMX/GLU/지질/MGX/PAXHR
    lifesnaps/     #   Zenodo rais_anonymized.zip (자기지도 사전학습용)
  processed/       # 통합 학습 테이블 (git 제외)
01_Results/        # 모델·리포트·model_registry.jsonl (git 제외)
configs/
  schema.yaml           # 스키마 앵커링: SiBC 수집 항목 기준 특징/목표 정의 (단일 진실)
  modeling_policy.yaml  # 평가·가중치·금지 규칙
src/sibc_checkup/
  env.py           # .env.release(.ddl 우선) 로더 — SiBC_project/ 상위 경로
  db.py            # read-only 세션 + SELECT 가드
  security.py      # user_id 가명화 (원본 ID 디스크 저장 금지)
  labels.py        # 검진 라벨: health_info_data[].measuredDt 기준, 별칭/단위 정규화
  features_own.py  # 자체 웨어러블 일별 특징 + 관측창(7/30/90) 전개 (시간 누출 금지)
  nhanes.py        # NHANES XPT -> 공공 행 (PAXHR 브리징: MIMS -> 일별 활동량)
  unified.py       # 통합 테이블: source 표시 + 가중치 상한 + 앵커링 검사
  train.py         # v1 baseline (HistGB) + 계보 기록
  cli.py           # build-table / train / all
tests/             # 앵커링·시간누출·가드 오프라인 테스트
```

## 실행

```bash
cd medical_checkup_model
uv sync                                     # 의존성 설치
uv run pytest -q                            # 오프라인 계약 테스트
bash scripts/download_public_data.sh        # NHANES + LifeSnaps 다운로드
uv run python -m sibc_checkup.cli build-table  # 통합 테이블 + 한국인 보정 기준
uv run python -m sibc_checkup.cli benchmark    # 알고리즘 파일럿 비교(항목별, 그룹 CV)
uv run python -m sibc_checkup.cli tune         # 승자(HistGBM) 항목별 하이퍼파라미터 튜닝
uv run python -m sibc_checkup.cli train        # 튜닝 파라미터로 통합 모델 학습
# 또는 build-table+benchmark+tune+train 일괄:
uv run python -m sibc_checkup.cli all
uv run python -m sibc_checkup.cli pretrain     # (선택) 자기지도 사전학습
```

## 모델 선택·튜닝 워크플로우 (파일럿 → 선택 → 튜닝)

`benchmark.py`가 항목별로 사용자 단위 그룹 교차검증(GroupKFold)으로 알고리즘을
비교한다. 성능 측정 대상을 둘로 분리한다:

- **Pilot A (공공 활동→검진, 약 1만 행)**: 알고리즘 계열 선택의 근거. 비교
  대상 = baseline_mean / elasticnet / random_forest / **hist_gbm** / mlp(딥러닝).
- **Pilot B (자체 M1 앵커→검진)**: 실제 자체 라벨에서 carry-forward(직전 검진값)
  대비 개선 검증.

2026-09-09 파일럿 결과: 10개 목표 전부 기준선 우세, **HistGradientBoosting이
5/10 최다 1위**(MLP은 신호 약한 ldl·중성지방에서만 근소 우위). → 주 알고리즘
HistGBM 선정. `tune.py`가 항목별 HistGBM 하이퍼파라미터를 그룹 CV 랜덤서치로
최적화해 `configs/best_params.json`에 저장하고, `train.py`가 이를 사용한다.

**Pilot C (자기지도 임베딩 기여, 2026-09-09)**: `ssl_emb__0..15`(자기지도
인코더 임베딩)를 통합 테이블 특징으로 투입. 시간 누출 방지를 위해 검진일
이전 웨어러블 관측창이 있는 own 행에만 부여(현재 14행, 공공행 0). 그 14행
LeaveOneOut 비교 결과 임베딩 추가가 오히려 성능을 악화(weight 7.54→8.79,
bmi 2.14→2.40; 14행에 16차원 추가 → 과적합). **결론: 임베딩 표 특징 투입은
현재 이득 없음**. 인프라(스키마 등록·누출 방지 병합·Pilot C)는 서빙 준비
상태로 유지하되, `train.py`가 유효값 20개 미만 특징을 자동 제외하므로 현재
학습에는 미반영(무해). 임베딩의 이득은 웨어러블 라벨 축적 시 실현된다.

원칙: 봉인 테스트로 알고리즘·파라미터를 고르지 않는다(선택은 CV로만). 항목별
최적 알고리즘·파라미터가 다를 수 있으므로 항목 단위로 비교·튜닝한다.

DB 접속은 상위 `SiBC_project/.env.release`를 자동 로드합니다
(`.env.release.ddl`이 있으면 우선). 세션은 read-only이며 SELECT만 실행됩니다.

## 원칙 (요약)

- 시간 기준은 `health_info_data[].measuredDt`. 검진일 이전 특징만 사용.
- 입력 특징·예측 목표는 `configs/schema.yaml`(SiBC 수집 항목)로 고정 —
  공공 전용 변수는 통합 테이블에 들어올 수 없고, 위반 시 빌드가 실패한다.
- 평가 세트에 공공데이터 행 금지. NHANES 내부 홀드아웃 수치는 개발 참고용
  (public-internal)으로만 기록하며 성능으로 보고하지 않는다.
- 버전별 공공/자체 구성은 `01_Results/model_registry.jsonl`에 기록한다.
- 합성(페르소나) 데이터로 학습·평가하지 않는다.
- 원본 user_id·원시 검진 JSON을 디스크에 저장하지 않는다 (가명키 사용).
- git에는 코드만 올린다 (00_Data/*, 01_Results/*는 .gitignore로 제외).

## 데이터 소스와 "최신 데이터" 판단 (2026-09-02)

통합 학습 테이블의 공공 행은 두 소스에서 온다.

| 소스 | 행 수 | 웨어러블 특징 | 사용 연도 | 최신성 판단 |
|---|---|---|---|---|
| KNHANES (한국) | 592 | 분단위 걸음(PAXSTEP)·강도(PAXINTEN) 집계 | 활동+검진 2014-2017 | 가속도계(PAM)는 2014-2017만 존재 — 그것이 최신 |
| NHANES (미국) | 9,981 | 손목 가속도 MIMS·악력 | 2011-2014 | 손목 가속도·악력은 2011-2014 사이클만 공개 — 그것이 최신 |
| own (SiBC) | 1,506 | 실제 수집 웨어러블 전체 | 진행 중 | 항상 최신 실기기 |

**"오래된 데이터라도 되는가"에 대한 판단**: 웨어러블+검진을 쌍으로 가진
공개 데이터의 가속도계는 KNHANES 2014-2017, NHANES 2011-2014가 각 조사의
**마지막(=최신) 수집분**이다. 더 최신 공개 데이터는 존재하지 않는다(그래서
접근 불가한 All of Us/UK Biobank가 대안 후보였다). 반면 **검진값 분포**는
KNHANES 2010-2024 전 연도 포맷이 동일해, 최신(2019-2024)을 한국인 보정
기준으로 사용한다. 기기 해상도 세대차는 ① 출처 표시 변수(domain indicator)와
② 재학습을 통한 자체(최신 기기) 데이터로의 중심 이동으로 흡수한다. 공공 행은
'활동량→검진값'의 거친 관계만 가르치면 되고, 미세 해상도는 자체 데이터가
담당한다.

## 트랙 1 — M1 개인화 모델 (자체 데이터로 학습·봉인 검증, 2026-09-09)

`m1.py` (`cli train-m1`). 입력 = 직전 검진값(앵커)·경과일·추세(직전-직전값,
연간 기울기)·다른 항목 직전값·인구통계·(있으면) 웨어러블 관측창 → 다음 검진값.

절차: 항목별 M1 행 선별 → 사용자 20% 봉인 분리(마지막 1회 평가 전용) →
학습 사용자 내 GroupKFold(5)로 elasticnet/hist_gbm/random_forest 비교 →
**승격 규칙**(사전 규정, 봉인셋 미참조): carry-forward 대비 CV MAE ≥3% 개선
AND 과반 폴드 승리 AND 표본 정책(학습 ≥100명, 봉인 ≥30명) → `MODEL`,
아니면 `CARRY_FORWARD`. CV 잔차 10/90% 분위수로 예측구간, 봉인셋 PICP 검증.
ABSTAIN: 앵커 없음 또는 앵커 3년 초과. 산출: `01_Results/m1/<ver>/`,
`configs/m1_serving_rules.json`(항목별 서빙 분기), 레지스트리.

m1_v1 결과(자체 봉인셋, 실제 성능):

| 항목 | 경로 | 봉인 MAE (모델 vs 직전값) | R² | 비고 |
|---|---|---|---|---|
| 수축기혈압 | MODEL(elasticnet) | 8.78 vs 10.83 | 0.31 | 5/5 폴드 승 |
| 이완기혈압 | MODEL(elasticnet) | 7.16 vs 8.07 | 0.24 | 5/5 |
| 공복혈당 | MODEL(random_forest) | 12.71 vs 15.17 | 0.12 | 5/5 |
| 체중·BMI·허리 | CARRY_FORWARD | 직전값 R² 0.94/0.90 | — | 직전값이 이미 최선 |
| 지질 4항목 | CARRY_FORWARD | — | — | 반복 지질검진 사용자 62명뿐(정책 미달) |

교훈: 지질은 CV상 승격 가능해 보였으나(HDL 4/5) 봉인셋 R²가 -1.4로 뒤집힘 —
표본 정책 게이트가 소표본 착시를 정확히 차단. 지질 M1은 반복 지질 라벨 축적
후 재시도.

**m1_v2 — 예측구간 보수화**: 경로별 잔차 구간(MODEL은 OOF 잔차, CARRY_FORWARD는
직전값 잔차)을 각각 산출하고 명목 커버리지를 85%(7.5/92.5 분위수)로 상향.
봉인셋 PICP(실제 서빙 경로 기준): sbp 0.86, dbp 0.80(←0.75), 혈당 0.80(←0.72),
체중/BMI 0.93, 허리 0.85 — 정책 충족 항목 전부 ≥0.80 달성.

### 고도화 6단계 (2026-09-10, `m1_v3`)

| # | 방향 | 모듈 | 결과 |
|---|---|---|---|
| 1 | 약한 지도(웨어러블 측정값 대리 라벨) | `proxy.py` | 대리 풀 확인(혈압 1,995측정/199명, 체중 2,141/174명). **부정적 발견**: 일 단위 심박·수면·걸음 요약→측정 혈압 R²≈0(평균 기준선 수준, 직전 측정 CF 8.5가 우세). 체중은 R² 0.37. 혈압 대리학습은 야간심박·HRV 등 고해상도 특징이 선행돼야 함. 측정↔검진 보정: 체중 as-is MAE 2.95, 혈압 slope 0.69~0.82(n=10) |
| 2 | 임계값 분류·변화 방향 | `clinical.py` | **분류 4문제 전부 봉인셋에서 '직전 상태' 기준선 우세**: 고혈압 AUROC 0.82(vs 0.77), 공복혈당≥100 0.82(vs 0.77), 비만 0.96(vs 0.86), 복부비만 0.955(vs 0.86). 고TG는 양성 8건 정책 차단. 방향(3분류): 혈압 0.48 vs 다수 0.30(악화 재현 0.64), 혈당 0.575 vs 0.425 유효; 체중·BMI·허리는 '항상 유지' 못 이김 |
| 3 | 분위수 회귀+컨포멀(CQR) | `m1.py` | 상수/CQR 중 커버리지(≥0.80) 우선·같으면 좁은 쪽 채택. 공복혈당 PICP 0.77→0.82(CQR, 사용자별 가변 폭 13~106), 허리 CQR(더 좁음), 나머지 상수 유지 |
| 4 | 교차특징 모델(지질 구제) | `m1.py` MODEL_CROSS | 자기 지질 앵커 없이 BMI·혈압·혈당 앵커+demo로 학습 → 62명→약 310명(정책 충족), 모집단 평균 대비 ≥3% 개선으로 4항목 승격(봉인 R² 0.07~0.21). **하이브리드**: 신선한 자기 앵커 있으면 CF, 없으면 교차 모델 → 지질 ABSTAIN ~208명→1명 |
| 5 | 혼합효과(경험적 베이즈 축소) | `m1.py` EBShrinkageRegressor | 7개 항목에서 최적 후보로 선택. 이완기 봉인 MAE 7.16→6.96, 공복혈당 12.71→12.10(R² 0.12→0.17), 체중 1.94(<CF 2.00, CV 3% 미달로 CF 유지) |
| 6 | 활동량 브리징(분포 정합) | `unified._add_activity_bridge` | `activity_pct__w7__median`: NHANES MIMS→내부 백분위, 자체·KNHANES 걸음→KNHANES ECDF(성별 층화). NHANES가 forward 전이 특징 공간에 합류. forward 12명이라 게이트 BLOCKED(참고: 체중 7.58→7.40, 혈당 10.2→8.6) |

### 후속 3단계 (2026-09-10)

- **고해상도 심박 특징** (`features_own.SQL_DAILY_HR`, 단일 패스): 야간(00~05시)
  중앙값·최저, 야간 연속차 RMS(RMSSD 대리), 일 SD, p90, 기기 휴지기 심박
  (코드 20301202). 일별 특징은 당일 캐시(`00_Data/processed/daily_features_<date>.parquet`)
  로 DB 재조회를 막는다. **혈압 대리학습 재시도 결과 R² 여전히 ≈0**(수축기 봉인 0.05)
  → 심박 파생 일 단위 특징으로는 혈압 복원 불가(2회 확인). 체중 R² 0.41.
- **임상 플래그·방향 서빙** (`clinical._persist` → `configs/clinical_rules.json`,
  `serve._clinical_outputs`): 봉인셋에서 기준선을 이긴 문제만 서빙 게이트 통과 —
  플래그 4개(고혈압·공복혈당장애·비만·복부비만), 방향은 혈압·혈당만. 산출 컬럼
  `flag_<문제>_prob/flag_<문제>`, `direction_<항목>/…_worsen_prob`.
- **문서 반영**: 구축가이드 md 11장(구현·검증 결과), 보고서 docx 11장 —
  `scripts/append_report_section.py`(기존 서식 템플릿 복제, 멱등 삽입) +
  `scripts/report_section_11.json`.

### M1 서빙 (`serve.py`, `cli serve-m1 [--index-time YYYY-MM-DD] [--no-wearable]`)

사용자당 1행, 구축가이드 5.8 스키마: `actual_*`(최근 실제 검진값+검진일),
`measured_*`(웨어러블 30일 직접 측정 요약), `pred_*`/`_lower`/`_upper`(경로
적용 예측+85% 구간), `route_*`(MODEL/CARRY_FORWARD/ABSTAIN), `abstain_reason_*`,
`coverage_grade`(30일 걸음 유효일: A≥21/B≥10/C≥1/none). 기준일 이전 검진·
웨어러블만 사용(누출 없음), 가명키만 출력. 산출 `01_Results/serving/`.
2026-09-09 실행: 394명 — sbp MODEL 323/ABSTAIN 71(앵커 3년 초과 37, 검진 없음 34),
체중 등 CARRY_FORWARD 357, 지질은 ABSTAIN ~208(지질 검진 없음/오래됨). 구간·
양수 위반 0건. 주의: 서빙의 `anchor_days_since`(최근 검진→오늘)는 학습 분포
(연속 검진 간격 ~1년)와 다를 수 있어 직전 검진 직후 예측은 직전값에 수렴.

### 트랙 2 자동 평가 (`m0_forward_eval.py`, `cli eval-m0-forward`)

자체 forward 쌍(검진일 이전 웨어러블 관측창 보유 행)에서 **공공 행만으로 학습한**
M0를 평가(통합 모델은 own 행이 학습에 섞여 누출이므로 사용 금지). 특징은 공공·
forward 양쪽 커버리지 ≥5% 교집합. 게이트: forward 사용자 ≥30 전에는
`BLOCKED_BY_DATA`(지표는 참고용). 실행마다 `01_Results/m0_forward_eval.jsonl`에
append → 라벨 유입 추적. 2026-09-09: forward 15행/12명 → BLOCKED. 참고 지표
(n=6~15): 체중 7.6 vs 공공평균 14.0, BMI 2.6 vs 5.1, 허리 10.8 vs 16.5로
demo·걸음·악력만으로도 일부 신호 전이; sbp·혈당은 n<8이라 판단 불가.
**식별된 구조적 문제**: 공유 특징이 demo·걸음(w7, KNHANES 유래)·악력뿐 —
NHANES 가속도(MIMS)→자체 걸음 브리징이 미구현이라 NHANES 활동 특징이 자체
사용자에 전이되지 못함. M0 성능 상한을 올리려면 브리징 층 구현이 선행 과제.

## 현재 상태 (2026-09-02)

- v1.2는 공공 지배 버전. 공공 행 = NHANES 9,981 + KNHANES(한국인) 592,
  자체 1,506. 출처 표시 변수(src_own/knhanes/nhanes)를 모델 특징으로 투입,
  KNHANES는 도메인 정합 가중치 3.0(nhanes=1). 10개 목표 전부 공공 내부
  홀드아웃에서 평균 기준선 우세(개발 참고용, 성능 주장 아님).
- KNHANES 통합: `src/sibc_checkup/knhanes.py`. 2014-2017 PAM(분단위 걸음·강도)
  → 개인 일별 요약 → 검진값(ID 연결) → 한국인 공공 행. 검진값 보정 기준
  분포는 `00_Data/processed/korean_calibration_reference.parquet`
  (성별×연령대×항목, 2019-2024).
- demo 특징: demo_sex=release `ichms.auth_user_profile`(99.9%),
  demo_age=iccoli `tb_user_personal_info.birth`(service=iccoli, 98.7%).
- 자기지도 사전학습 v0(`cli pretrain`): SiBC 5채널 14일 창 마스킹 복원,
  자체 + LifeSnaps. 산출 `01_Results/pretrain/`.
- env 안전장치: DB_NAME이 release(invites_loop)가 아닌 파일은 스킵,
  `DB_HOST` 해석 실패 시 `DB_HOST_PUBLIC` 폴백.
- KNHANES 다운로드: 로그인 불필요, 동의 팝업(성명·소속·이메일)만 통과.
  파일은 `00_Data/public/knhanes/`(zip + `ex_*/` 추출 SAS). 모두 git 제외.
- 알고리즘 파일럿·튜닝 완료(2026-09-09): HistGBM 선정, 항목별 튜닝 →
  `configs/best_params.json`. v1.3은 튜닝 파라미터로 학습. 개선폭이 작아
  (기본값이 이미 최적 근처) 현재 병목은 하이퍼파라미터가 아니라 신호·자체
  라벨 양임이 확인됨. 산출: `01_Results/benchmark/benchmark_report.json`.
- 자체 M1 경로(직전 검진 앵커)가 현재 가장 강한 예측력. 항목별로 모델이
  carry-forward를 이기는 것(혈압·공복혈당·HDL·중성지방)과 지지 않는 것
  (체중·BMI·콜레스테롤)이 갈림 → 서빙 규칙에 항목별로 반영 예정.
- NHIS 개인단위 파일은 data.go.kr에서 삭제(2026-09-09 확인) — 생략. KNHANES가
  한국인 보정 담당. 다음: ssl_emb_* 통합 테이블 투입, 한국인 보정층 서빙 적용.

### 발표자료 (`scripts/build_result_deck.js`, 2026-09-11)

식이분석 리서치 발표자료 템플릿 포맷(16:9, Pretendard, 진청 커버·흰 본문·파란
핵심 박스·Confidential 배지·푸터)에 맞춘 결과 발표자료 12장. 실행:
`NODE_PATH=<pptxgenjs 설치 경로> node scripts/build_result_deck.js` → Downloads에
`SiBC_건강검진예측모델_구축검증결과_발표자료_<date>.pptx`. 차트는 네이티브
(pptxgenjs addChart). 유의성 수치는 `scripts/significance.py` →
`01_Results/significance.json`(사용자 클러스터 부트스트랩 B=2,000).

### 모델 분석 보고서 — 실사용 준비도 감사 (2026-09-17)

`scripts/audit_model.py` → `01_Results/model_audit.json`, `scripts/build_analysis_report_docx.js`
→ `Downloads/SiBC_건강검진예측모델_분석보고서_20260917.docx`. 핵심: 서빙 M1의 웨어러블 특징
0개(정답지 15건), 고위험 영역 과소예측(SBP≥140 −13, 혈당≥126 −36) → 회귀값 단독 병원안내 금지·
플래그 병행, 시드 3종 승격 안정, 한국인 보정 서빙 미적용·드리프트 감시 없음. 보완 순위 1~9.

**보고서 v2 (2026-09-17, 푸드렌즈 RAG 보고서 템플릿 포맷 + 시각화)**: `scripts/make_analysis_charts.py`
(`uv run --with matplotlib`, 차트 A~F 1400×800 → `scripts/report_assets/`) →
`scripts/build_analysis_report_v2_docx.js`(NODE_PATH=node_modules; A4·Pretendard·표지/EXEC SUMMARY/
PART/장·진청 표·파란 강조상자·전폭 차트·푸터 페이지번호). 렌더 QA: LibreOffice 격리 프로필 + pypdf 분할 + qlmanage.

### 분석 보고서 v3 (2026-09-17, 표 선·용어·추적성 수정)
- `scripts/build_analysis_report_v3_docx.js` → 동일 파일명 `Downloads/SiBC_건강검진예측모델_분석보고서_20260917.docx` 덮어씀 (13p, validate PASS, Word·LibreOffice 렌더링 확인).
- 표: 셀별 `tcBorders`/`tcMar` 제거, 표 단위 `tblBorders`(D1D5DB sz4)+`tblCellMar`(80/100)만 사용 → 뷰어별 선 어긋남 방지. 6장 표의 빈 첫 셀 제거(항목명 반복).
- 용어: '봉인 테스트/봉인셋' → '최종 검증(따로 떼어 둔 사용자 59명)', '승격' → '채택', '시드 3종' → '분할 3회 반복', '퍼뮤테이션 중요도' → '입력 의존도 분석', '드리프트' → '성능 저하', 'τ' → '변화 기준폭', '서빙' → '서비스 산출(서빙)'. 1장 용어표에 채택 규칙·95% 신뢰구간·서비스 산출 추가.
- 추적성: EXEC SUMMARY 각 결론에 '→ n장, 그림 k' 참조, '보고서 구성' 표(PART/장/질문/근거 그림), 각 장 첫머리 '요점' 한 줄(파란 좌측선), 그림 번호 1~6을 읽는 순서로 재부여(차트 PNG 제목도 동일), 11장 과제에 '(결함 n)' 표기, 12장 요청에 '(11장 순위 n)' 표기.
- 배치: 4·5장은 그림을 표 앞에 두어 그림이 다음 페이지로 밀리며 생기던 빈 반 페이지 제거.

### 분석 보고서 v3.1 (2026-09-17, 필수 내용 위주 축약 → 10p)
- 같은 스크립트(`build_analysis_report_v3_docx.js`)·같은 파일명. 제거: 준비도 매트릭스 그림(3장 표와 중복), 7장 입력 의존도 표(본문 한 문단으로), 6장 남녀 행, 5장 고중성지방 행(본문 언급), 부록(근거 파일·한계 고지를 끝 한 줄로), 10장 과제 9→8행. 9장·10장 병합(갖춰진 것=한 문단, 빠진 것=결함 표) → 장 번호 1~11, 그림 1~5로 재부여(차트 제목 동일).
- 레이아웃 교훈: 콜아웃 뒤 빈 스페이서 문단이 PART pageBreakBefore 직전에 오면 빈 페이지 생성 → 스페이서 제거하고 다음 요소의 spacing.before로 대체. 그림은 표 앞 배치 + 필요 시 540~600pt 폭으로 축소해 표 행 낙오 방지.

## 2026-09-17 재구축 + M2 고도화 (커밋 1920810 이후 작업, 미커밋)
- 데이터 현황: `scripts/data_status.py` → `01_Results/data_status_<date>.json`. 비교 기준은 날짜가 아니라 '이전 데이터셋(직전 모델이 학습한 데이터, 이후 미최신화)' 대 '현재 데이터셋(2026-09-17 조회)'. 웨어러블 469→493명, 검진 394→420명(1,606건), '착용 뒤 검진' 정답지 13→15명(게이트 30 미달).
- 재구축: 통합 v1.4, 개인화 m1_v4, 플래그 재학습. `scripts/significance.py`·`audit_model.py`는 버전 하드코딩 제거(서빙 규칙의 version, 최신 v* 폴더 자동 선택). 이전 결과는 `01_Results/snapshots/2026-09-10_before_rebuild/`.
- M2(`src/sibc_checkup/m2.py`, 규칙 `configs/m2_rules.json`, 산출 `01_Results/m2/`):
  - 진단: 예측값 기준 기울기 0.88~0.99, 예측 상위 10% 간극 ±3 이내 → 고위험 과소예측은 평균 회귀(재보정 무효). 개인 내 변동 기반 오차 하한 수축기 7.7 / 이완기 5.5.
  - 안내 기준점(민감도 0.85 사전 고정): 고혈압 놓침 21/23 → 2/23(기준점 0.066, 안내 대상 47%, PPV 21%), 3단계 등급(low/caution/high).
  - 측정값 융합(±180일 쌍, 반복 5겹 CV): 혈압 REJECT, 체중 PROVISIONAL(2.41→2.03), 이력 없음 체중 ADOPT(2.16kg)·수축기 ADOPT(참고, 11.3).
  - 시간 순서 검증(2025-01-01 분할): 수축기·이완기 통과, 혈당 경계. 음성 실험: 방문 이력·타 혈액 항목 입력 추가 ≤1.2%.
  - 서빙: `serve_m2()` → `01_Results/serving/m2_predictions_<date>.parquet` (495명 = 검진 보유 420 + 웨어러블만 75).
- 보고서: `scripts/make_upgrade_charts.py`(그림 5종, `scripts/upgrade_assets/`) + `scripts/build_upgrade_report_docx.js` → `Downloads/SiBC_건강검진예측모델_고도화결과보고서_20260917.docx` (11p). 테스트 32개.
- 고도화 결과 보고서 v2(경영진 보고용 간결판, 7p): `scripts/build_upgrade_report_v2_docx.js`. 2쪽에 결론 1문단 + 핵심 수치 카드 4개 + 결과 요약표 + 결정 필요 사항. 본문 6장, 그림 4개(차트 PNG 내부 제목에서 그림 번호 제거 — 번호는 문서 캡션이 관리). 표지 설명 문구 삭제.
- 결과 보고서(첫 보고용, 7p): `scripts/make_result_charts.py`(그림 5종, `scripts/result_assets/`) + `scripts/build_result_report_docx.js` → `Downloads/SiBC_건강검진예측모델_결과보고서_20260918.docx`. 과거 데이터셋·이전 모델 비교, '재구축/고도화 전후' 표현 없음. 구성: 핵심 요약 → 모델 개요·데이터 → 수치 예측 → 고위험 안내 → 웨어러블 측정값 활용 → 활용 수준·산출 범위 → 제한·보완.

## 2026-09-18 임상 가이드라인 기반 판정 (미커밋)
- `configs/clinical_guidelines.yaml`: 출처(sources: 학회 4곳+국가검진, PMID/DOI/PMCID/URL) · 항목별·출처별 구간 · 기본 3단계(default_tiers, 출처 간 상이 시 가장 이른 경계) · 기저질환별 조절 목표(disease_profiles) · 분류기 대상(model_flags). 수치는 2026-09-18 원문 확인분만(PMC 전문, KSoLA 5판 PDF, 법령정보센터 별표 4 별첨 PDF). 의료진 승인 전 초안.
- `src/sibc_checkup/guideline.py`: grade_value / grade_bp / bp_stage / stage_by_source / grade_prediction(구간 상한 반영) / goal_status. `clinical.THRESHOLDS`는 yaml에서 생성(15문제: 8개 학습·채택, 지질 7개 BLOCKED_BY_POLICY).
- `m2.tier_validation`·`combine_tier`: 최종 3단계 = 수치 판정(예측+상한)과 확률 판정의 나쁜 쪽. 검증: 실제 위험 174건 중 정상 판정 0건(직전 단계 그대로는 16건). 단 혈압 '주의' 65%, 위험→위험 17%.
- `serve_m2`: tier_pred_*/tier_actual_*/stage_pred_* 컬럼 추가(495명, 전원 기본 기준; DB에 진단명 구조화 필드 없음 — discovery 복약·문진 테이블만 존재).
- 보고서: `scripts/build_result_report_v2_docx.js`(js-yaml로 참고문헌 자동 생성) → `Downloads/SiBC_건강검진예측모델_결과보고서_20260918.docx` (12p: 본문 8p + 부록 A-1~A-6). 테스트 38개.

## 2026-09-18 수치 예측 전용 재구축 (최종 방향, 미커밋)
- 방향 정정: 모델은 항목별 **예측 수치**만 산출. 정상/주의/위험 판정·기준 초과 플래그·안내·변화 방향은 후단 **판단 Agent** 담당 → 모델 산출물에서 제거.
- `src/sibc_checkup/predict.py` + CLI `predict`: `01_Results/predictions/predictions_long_<date>.parquet|csv`(사용자×항목 4,950행) / `predictions_wide_<date>`; 필드 = value/lower/upper(85%)/route/evidence_level(A·B·C)/abstain_reason/basis_*(직전 검진값·경과일, 웨어러블 측정 중앙값·횟수·기간)/model_version. 명세: `configs/prediction_output_schema.json` v1.0.
- `serve.serve_all(include_clinical=False)` 기본, `m2.run(include_judgment=False)` 기본. clinical.py·guideline.py·m2.referral/tier_validation·configs/clinical_guidelines.yaml 은 판단 Agent 측 참고용 자산으로만 보존(모델 산출 경로에서 미사용).
- 보고서: `scripts/make_prediction_charts.py`(P1~P5) + `scripts/build_result_report_v3_docx.js` → `Downloads/SiBC_건강검진예측모델_결과보고서_20260918.docx` (8p: 요약·개요·수치 성능+구간·출력 명세·웨어러블 활용·제한). 테스트 40개.

## 2026-09-18 실측·예측 분리 재구축 (최종 방향 v2, 미커밋)
- 사용자 지적: 혈압계·체중계로 잰 값을 입력에 넣어 같은 항목을 '예측'했다고 부르는 것은 오류. 예측 = 다른 데이터로만 추정한 값.
- `predict.py` v2: kind=MEASURED(DEVICE/DEVICE_DERIVED: 혈압계·체중계 180일 중앙값, BMI는 체중계×직전 검진 신장비) / PREDICTED(method=HISTORY[M1, 검증됨, 웨어러블 미사용] · HISTORY_WEARABLE[통합 v1.4: 앵커+7일 걸음·활동량 백분위·활동시간·악력, REFERENCE_ONLY] · WEARABLE_ONLY[이력 없음, UNVALIDATED]). `joint_inputs_are_clean()`로 예측 입력에 같은 항목 측정값 없음을 강제. 서빙 시 활동량 백분위는 `_add_activity_pct`(KNHANES 걸음 ECDF). 명세 v2.0.
- 근거: `scripts/wearable_contribution.py` → `01_Results/wearable_contribution.json`. 공공 홀드아웃 2,115건 절제: 활동 신호 기여 혈압·혈당·지질 ≤1%, 체중 +9.0%(악력 포함), BMI +5.5%, 허리 +7.4%. 자체 대리(심박·수면·걸음→혈압계) R² 0.05/0.09. 착용 뒤 검진 15명 → 자체 검증 불가.
- 산출(2026-09-18): 518명(검진 보유 420 + 웨어러블만 98). 실측 혈압 400·체중 357·BMI 286명, 이력 예측 338~417명, 이력+웨어러블 243명, 웨어러블만 33명. 실측 대 예측 참고 일치도: 수축기 HISTORY 10.17 / +웨어러블 9.47 mmHg.
- 보고서: `scripts/make_v2_charts.py`(Q1~Q4) + `scripts/build_result_report_v4_docx.js` → 같은 파일명 (7p). 이전 v3(수치 전용, FUSION/M0_MEASURED 경로)은 폐기 — 측정값 통과를 예측으로 표기한 오류. 테스트 42개.
