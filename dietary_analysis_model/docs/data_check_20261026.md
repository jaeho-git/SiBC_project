# 데이터 확인 결과 — 웨어러블 baseline DB와 production 식이 원천 (2026-10-26)

작업 순서 2단계(설계 §8.2)의 데이터 확인 결과다. 코드는 `ichms-sibc-ontology-be/reliable_model/baseline_pipeline`
(README, `config/baseline_metrics.yaml`, `raw_sql.py`, `steps.py`, `runner.py`, `sql/create_baseline_tables.sql`)과
설계보고서 `SiBC_웨어러블_Baseline테이블_설계보고_20260831.docx`를 읽었고, DB는 release(`invites_loop`)와 개발(`loop-dev`)을
읽기 전용 집계 쿼리로 확인했다. 개별 사용자 행은 조회하지 않았다.

---

## 1. 웨어러블 baseline DB

### 1.1 위치와 구조

| 항목 | 내용 |
|---|---|
| DB / 스키마 | **release DB `invites_loop`**, 스키마 `sibc`. 개발 DB(loop-dev)에는 baseline 테이블이 없다 |
| 원천 | `discovery.disc_lifelog_user_*` 13개 테이블(걸음·활동·심박·열량·수면·SpO2·체성분·혈압·악력·meal) |
| 테이블 | `baseline_lifelog_hourly`(사용자×지표×날짜×시), `baseline_lifelog_outlier_point`, `baseline_lifelog_daily`(사용자×지표×날짜), `baseline_lifelog_window`(사용자×지표×기준일×창) |
| 창 길이 | 원래 7 / 14 / 30 / 180일. **2026-10-26에 60일 창을 추가**해 식이분석과 같은 7/14/30/60/180으로 통일(`config/baseline_metrics.yaml` windows 수정, window 층 2025-12-18~2026-10-26 전체 재계산) |
| 기준일 | `baseline_date`, 사용자 최초 데이터일부터 **매일** 1행. 이력이 창보다 짧으면 보유 이력 전체로 계산하고 `n_days_covered`에 실측 일수 기록 |
| 하루 경계 | `Asia/Seoul` 00시~24시(`(ts AT TIME ZONE 'Asia/Seoul')::date`). 수면·활동처럼 자정을 넘는 세션은 **시작일 귀속** |
| 과거 기준일 재계산 | **한다.** nightly가 최근 35일(소급 동기화 4주 + 1주)을 DELETE 후 INSERT로 통째 재계산. 35일보다 오래된 행은 확정 스냅샷으로 불변 |
| 착용 시간 열 | **없다.** 측정이 있는 날만 행이 생기고 미착용일은 행이 없음. 착용 시간 대리 지표로 심박 `n_records` 사용 가능 |
| 지표 | 29종. 소모 열량은 `total_kcal_burned`, `active_kcal_burned`(원천 `disc_lifelog_user_calories`, 일 합계), 운동 열량 `activity_kcal`. 체중 `weight_kg`, `bmi`(원천 `body_info`). 식이 4종(`intake_kcal` 등, 원천 `disc_lifelog_user_meal` jsonb × percent) |
| 계산 시각 | 모든 행에 `run_id`, `computed_at` |

### 1.2 적재 상태 (2026-10-26 조회)

| 항목 | 값 |
|---|---|
| 마지막 실행 | `baseline_nightly_20260831_150703`(8/31) 이후 멈춰 있었음. **2026-10-26에 2026-08-01~10-26 구간 backfill을 수동 실행해 복구**(`baseline_backfill_20261026_112014`, 29지표 × 3개월 청크 87건 모두 성공, 권한 skip 없음). 매일 실행할 스케줄은 아직 없음 |
| window 행 | backfill 후 7일 601,061 / 14일 720,495 / 30일 898,586 / 180일 1,430,002행, 기준일 2025-12-18 ~ 2026-10-26 |
| daily 행 | 212,711행 |
| `total_kcal_burned` | 2026-07-01 ~ 2026-10-26, 325명(backfill 후). calories 원천 권한이 늦게 부여되어 7월부터만 있음 |
| `weight_kg` | 455명, 2026-02-20 ~ 2026-10-26 (backfill 후) |
| `heartrate_bpm` 일별 측정 수 | 10백분위 141, 중앙값 850, 90백분위 1,280건/일 |

### 1.3 원천 수신 지연 (calories, 2026-07-01 이후, `ins_dt − measured_dt`)

| 중앙값 | 90백분위 | 99백분위 | 최대 |
|---|---|---|---|
| 4.4일 | 23.5일 | 28.6일 | 30.0일 |

소모 열량은 측정일로부터 **중앙값 4~5일, 10%는 3주 이상** 늦게 서버에 들어온다. 최대 30일은 플랫폼 소급 범위로 보인다.
이 분포는 설계 §3.7의 "전주 기반" 결정을 뒷받침하고, 동시에 **월요일에 계산한 지난주 일요일 행은 절반 이상의 사용자에서 소모 데이터가 비어 있음**을 뜻한다.
따라서 최근 기준일 행 재계산(설계 §3.7.6)은 필수이고, 알람 근거 행의 창 상태가 주 중반 이후에 "완전"으로 바뀌는 사용자가 많을 것이다.

---

## 2. production 식이 원천

> **2026-10-26 결정으로 이 절의 결론은 바뀌었다.** 식이분석은 release DB의 `user_diet_intake`를 쓰지 않고, loop-dev의 `sibc.meal`·`sibc.meal_food`·`sibc.meal_food_master`를 원천으로 한다. 아래 2.1~2.2는 조회 사실의 기록으로만 남기며, 설계 반영은 §2.3을 따른다.

### 2.1 조회 사실 (참고용)

개발 DB(loop-dev)의 `sibc.meal` / `sibc.meal_food`(끼니·음식 분리)는 **release DB에 없다.** release DB의 식이 테이블은 다음과 같다.

| 테이블 | 행 수 | 사용자 | 기간 | 구조 |
|---|---|---|---|---|
| `sibc.user_diet_intake` | 56,024 | 353 | 2026-01-05 ~ 2026-10-26 | **끼니 1건 = 1행.** `eaten_at`, `ymd`, `meal_type`(BREAKFAST/LUNCH/DINNER/SNACK), `food_name_raw`, `food_names`(배열, 중앙값 5개, 최대 26개), `total_gram`, `intake_percent`, 영양소 22열(개발 DB의 21종 + `vitamin_e_mg`) |
| `sibc.user_diet_analysis` | 56,024 | 353 | 같음 | `eat_date`, `meal_data`(jsonb), `one_line_summary`, `ai_analysis`, `next_meal_tips` |
| `sibc.target_calorie` | 705 | — | — | `target_daily_calorie`, `calorie_calculation_basis`(jsonb), 식이 주의사항 |

월별 끼니 기록은 2026-05 이후 월 6,000~8,600건, 사용자 140~230명이다. `intake_percent`가 100이 아닌 행이 38%(21,408행)다.

### 2.2 설계에 미치는 영향

- **끼니·하루 집계의 입력 구조가 바뀐다.** 끼니 합계는 이미 행에 있으므로 Σ(음식 × 인분) 계산이 필요 없고, 하루 누적은 `user_id × ymd` 합계다. `intake_percent`가 이미 반영된 값인지 확인해야 한다(baseline의 meal 지표는 `nutrition × percent/100`으로 보정하고 있어, 원천 jsonb는 보정 전 값일 가능성이 있음).
- **음식별 기여도**(설계 §3.2 2단계)는 `user_diet_intake`만으로는 불가능하다. `user_diet_analysis.meal_data`(jsonb)에 음식별 영양 값이 있는지 확인이 필요하다.
- **참조 데이터 매핑의 키는 `food_names` 배열의 음식명**이다. 개발 DB `meal_food.food_name`(111종)은 표본일 뿐이므로, 매핑표 2차는 `user_diet_intake.food_names`의 distinct 값(production)으로 만든다.
- **vitamin E**는 production에 있다. 참조 데이터(식약처)에 없는 유일한 영양소였으므로, production 값의 출처(LLM 추정)를 확인하고 판정 대상에 넣을지 정한다.
- `target_calorie`는 앱이 이미 쓰는 사용자별 목표 열량이다. 방향 층의 "사용자 목표" 논의와 직접 관련되므로 `calorie_calculation_basis`의 산출 근거를 확인해 우리 기준 층과의 관계(덮어쓰지 않음)를 정한다.
- 식이분석 테이블(`dietary_analysis_*`)은 현재 loop-dev에만 있다. 운영 적용 시 release DB에 같은 구조를 만들고 `user_diet_intake`를 읽어야 한다.

---

### 2.3 결정 후 식이 원천 (loop-dev)

| 테이블 | 내용 (2026-10-26 조회) |
|---|---|
| `sibc.meal` | 끼니 1행. `meal_type` 7종(BREAKFAST, MORNING_SNACK, LUNCH, AFTERNOON_SNACK, DINNER, LATE_NIGHT_SNACK, SNACK), `eaten_at`, `input_type`, `status`, 영양소 합계 29열(vitamin E, 티아민·리보플라빈·니아신·칼륨·철·인 포함). 104행, 17명, 2026-09-03 ~ 10-26 |
| `sibc.meal_food` | 음식 1행. `food_name`, `food_name_norm`, `serving_qty`, `source`(MANUAL/MY_FOOD/PHOTO), `analysis_status`(DONE/UNKNOWN), `estimated_amount_g`, 영양소 29열. 184행, 음식명 111종 |
| `sibc.meal_food_master` | 기준 식품 마스터 21,172행. `source_code` KR_MFDS 19,398(식약처) + 97(농진청 국가표준식품성분표) + CN_CFCD 1,677(중국). `serving_basis` 100g/100ml, `food_weight_g` 보유 13,743행, 대·중·소·세 분류, `primary_name_norm`/`representative_name_norm`, `norm_version`. 비타민 A 등 일부 영양소는 전부 NULL |
| 연결률 | `meal_food.food_name_norm` ↔ 마스터 `representative_name_norm` 74/184, `primary_name_norm` 61/184 |

**설계에 미치는 영향.** 끼니·음식 분리 구조이므로 기존 집계 코드(Σ 음식 × 인분)와 음식별 기여도가 그대로 성립한다. 참조 데이터 표준화 결과(1인분 환산표, 매핑표)는 `meal_food_master`와 같은 식약처 코드 체계이므로, 매핑표의 목적지는 이 마스터 테이블이 된다. 마스터는 100 g/100 ml 기준이라 1인분 환산 열(또는 별도 환산표)이 필요하다. 웨어러블 baseline은 release DB에 있으므로 두 DB 사이의 결합 경로(같은 DB로 복제 또는 읽기 연결)가 결정 사항으로 남는다.

## 3. 체중·키

| DB | 사용자 | 키·체중 보유 | 갱신 이력 |
|---|---|---|---|
| release `user_master` | 704 | 704 / 704 | 없음. `updated_at`이 전 행 2026-10-26으로 동일(행 일괄 갱신), 체중 변경 시각이 아님 |
| loop-dev `user_master` | 52 | 52 / 52 | 없음 |
| 체중계 연동(baseline `weight_kg`) | 346명 (2026-08-31 기준), 원천 `body_info` 3,231 lifelog 계정 | 측정일별 값 있음 |

체중 추세는 baseline `weight_kg`로만 가능하고, 연동이 없는 사용자는 가입 시 체중으로 BMI만 쓴다. `user_profiles_log`(사용자×일자, `health_profile` jsonb)에 체중 이력이 있을 가능성이 있어 확인 대상이다.

---

## 4. 설계 §9 확인 사항의 처리

| 확인 사항 | 결과 |
|---|---|
| baseline DB 위치·열·기준일·하루 경계 | 확인 완료(§1.1). 하루 경계 00~24시 KST로 식이와 일치 |
| 과거 기준일 행 재계산 여부 | 한다(최근 35일). 식이 baseline도 같은 35일 재계산 규칙을 쓰면 됨 |
| 착용 시간 열 | 없음. 심박 `n_records` 대리 지표로 대체(완전성 규칙 초안 §2) |
| 늦게 동기화된 데이터의 측정 시각 보존 | **보존된다.** 원천에 `measured_dt`(측정)와 `ins_dt`(수신)가 따로 있고 baseline은 `measured_dt`로 귀속. 중복은 원천 PK와 DELETE+INSERT 재계산으로 처리 |
| 끼니 기록 시점 전송에 시계 동기화분 포함 여부 | 데이터로는 판단 불가. 다만 수신 지연 분포(§1.3)가 중앙값 4.4일이므로 "앱 사용 시점에 당일 데이터가 서버에 있다"고 가정할 수 없음. 전주 기반 + 재계산 설계로 흡수 |
| 체중 수집 주기 | `user_master`는 이력 없음. 체중계 연동 사용자(약 절반)만 추세 가능 |

---

## 5. 새로 생긴 확인 사항

1. (종료) baseline nightly: 10/26 수동 복구, 새벽 자동 실행은 과장님이 처리.
2. (종료) `user_diet_intake` 관련 항목은 2026-10-26 결정으로 불필요.
3. `target_calorie.calorie_calculation_basis`의 산출 방식과 우리 기준 층(KDRIs·개인 소모량)의 관계 (loop-dev에도 같은 테이블 존재).
4. `user_profiles_log.health_profile`에 체중 이력이 있는지.
5. (결정) 두 DB를 모두 읽되 저장은 loop-dev. 방식은 6단계에서 확정.
6. (완료) 식이분석 60일 창 유지, 웨어러블 baseline에 60일 창 추가. 이후 nightly는 yaml 설정대로 5개 창을 계산함.
7. `meal_food_master`의 1인분 환산 열 추가 여부와 `meal_food.food_name_norm` 연결률 개선(매핑표 2차).
