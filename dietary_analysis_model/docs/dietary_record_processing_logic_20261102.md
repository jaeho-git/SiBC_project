# 식이 기록 처리 로직 — 끼니 입력 1건이 식이분석 데이터가 되는 순서 (2026-11-02)

독자: 식이분석 데이터 생성을 구현하는 개발자. 사용자 A가 사진을 찍거나 음식명을 직접 입력한 순간부터, 그 끼니가 `meal`·`meal_food` 행이 되고, 행동 층·습관 층 결과 값으로 이어지는 **처리 순서와 규칙**을 적는다.
근거는 설계 문서 [system_design_20261022.md](system_design_20261022.md) §3.2·§3.3·§3.5·§3.7.5·§4, 완전성 규칙 초안 [completeness_rules_draft_20261026.md](completeness_rules_draft_20261026.md), 방향 규칙 초안 [direction_rules_draft_20261026.md](direction_rules_draft_20261026.md)이다.
페르소나 생성기 [persona_data_spec_20261027.md](persona_data_spec_20261027.md)의 관측 층은 이 문서의 1~4단계를 그대로 구현한 것이며, 두 문서가 어긋나면 이 문서를 고치고 생성기를 따라 맞춘다(§8 대응표).

규칙 버전: `record_logic.2026.11.02-draft`. "초안"으로 표시한 수치는 평가로 확정한다.

---

## 0. 핵심 요약

### 목적

사용자가 사진을 찍거나 음식명을 입력한 끼니 1건이 어떤 순서로 `meal`·`meal_food` 행이 되고, 식이분석의 행동 층·습관 층 결과 값으로 이어지는지를 개발자가 그대로 구현할 수 있는 수준으로 적는다. 페르소나 데이터는 같은 규칙으로 만들어졌으므로, 구현이 끝나면 페르소나 데이터로 수용 기준(§9)을 바로 확인할 수 있다.

### 핵심 결론

> 끼니 1건은 **즉시 경로**(음식 식별 → 1인분 영양 환산 → 끼니 행 확정 → 하루 누적 → 행동 층 결과 값 1행)와 **매일 배치 경로**(하루 확정 → 습관 층 기준일 행 → 웨어러블 결합·재계산)로 나뉜다. 푸드렌즈는 실시간이고 웨어러블은 중앙값 4.4일 늦게 도착하므로 두 경로를 분리한다. 음식 영양은 참조 1인분 값 × 인분 수(0.5 단위, 0.5~3.0)로 계산하고, 매핑에 실패한 음식은 0이 아니라 NULL로 둔다. 끼니의 `ymd`는 섭취 시각의 KST 날짜이며 자정 이후 섭취는 다음 날이다. 끼니 영양 합계는 항상 음식 합과 같아야 하고, 수정은 원본을 남긴 채 새 행으로 잇는다.

### 결정 사항

| 결정 항목 | 결론 | 근거 강도 | 핵심 근거 |
|---|---|---|---|
| 처리 경로 | 즉시 경로(5~6단계)와 매일 배치(7~9단계) 분리 | 강함 | 웨어러블 수신 지연 중앙값 4.4일, 90백분위 23.5일(설계 §3.7, data_check §1.3) |
| 영양 산출 | 참조 1인분 × 인분 수. 매핑 실패는 UNKNOWN·NULL | 강함 | 참조 공란과 실측 0의 구분(food_reference §2), LLM 추정값 원천은 미결(설계 §9) |
| 인분 수 | 0.5 단위, 0.5~3.0 | 중간 | 2026-11-02 결정. 상한 초과는 항목을 나눠 입력 |
| 날짜 귀속 | 섭취 시각의 KST 날짜. 자정 이후는 다음 날, 야식은 플래그 | 강함 | 설계 §3.6 시간 정렬 결정 |
| 수정·중복 | 원본 유지 + `edits_meal_id` 연결, 같은 끼니 유형은 합산 | 중간 | 완전성 규칙 §1.1 |
| 판정 범위 | 과잉은 불완전한 날에도, 부족은 완전한 날에만 | 강함 | 설계 §3.3 |
| 재계산 | 최근 35일 기준일 행을 매일 다시 만듦 | 강함 | 웨어러블 baseline과 동일(data_check §1.1) |

### 범위와 경계

| 구분 | 누가 만드는가 | 이 문서에서의 위치 |
|---|---|---|
| 끼니 입력(사진·수동·내 음식·결식 표시·수정) | 앱(푸드렌즈) | 1단계 입력 이벤트. 이 문서는 입력의 **형식과 의미**만 정의한다 |
| `meal`, `meal_food` 행 | 앱 백엔드 | 2~4단계. 음식 식별 → 1인분 영양 환산 → 끼니 행 확정의 규칙 |
| 하루 누적·완전성, 행동 층 결과 값 | 식이분석 | 5~6단계. 끼니 1건마다 즉시 |
| 하루 확정, 습관 층 기준일 행, 웨어러블 결합, 재계산 | 식이분석 | 7~9단계. 매일 배치 |
| 결론·알람 | 앱 | 범위 밖. 식이분석은 결과 값과 판단 기준만 낸다(설계 §0) |

끼니 1건이 들어오면 5~6단계는 **즉시**(수 초 안) 끝나야 하고, 7~9단계는 하루 한 번이면 된다.

---

## 1. 전체 흐름

```text
[사용자 A]  사진 촬영 / 음식명 입력 / 내 음식 선택 / 결식 표시 / 기존 끼니 수정
    │ 1단계 입력 이벤트
    │   idempotency_key, eaten_at, meal_type, 음식 목록·인분 수, 입력 유형
    ▼
[앱 백엔드]
    2단계 음식 식별   음식명 정규화 → 식품코드 매핑(EXACT → BASE → PREFIX)
                      → 실패 시 UNKNOWN
    3단계 영양 환산   참조 1인분 영양 × 인분 수(0.5 단위) → meal_food 1행/음식
    4단계 끼니 확정   Σ음식 → meal 1행, ymd = eaten_at의 KST 날짜,
                      상태(COMPLETED/SKIPPED/DRAFT), 수정 연결
    │ 끼니 확정 이벤트 (meal_id)
    ▼
[식이분석 · 즉시]
    5단계 하루 누적   오늘 기록 끼니, 예정 끼니, 하루 분류(잠정),
                      야식·운동 후 플래그
    6단계 행동 층     결과 값 1행: 하루 기준량, 남은 허용량, 트리거,
                      방향, 판정, 기여도, 근거 주 상태, 신뢰도
    │
    ▼ (다음 날 00시 KST 이후 / 매일 새벽)
[식이분석 · 배치]
    7단계 하루 확정   하루 분류 확정, 식이 유효일 결정
    8단계 습관 층     기준일 행 7/14/30/60/180일: 평균·판정·유효일·
                      기록률·창 상태·추세 (최근 35일 재계산)
    9단계 웨어러블    유효일(심박 n_records ≥ 480), 동시 유효일,
                      에너지 지수, 창 상태 갱신
    │
    ▼
[앱]  결과 값 + 판단 기준(조건표·방향 규칙·판정 구간) 대조 → 결론·알람
```

---

## 2. 1단계 — 입력 이벤트

끼니 1건은 하나의 이벤트로 들어온다. 사진·수동·내 음식은 **같은 이벤트 형식**이고 `input_type`만 다르다.

| 필드 | 형식 | 규칙 |
|---|---|---|
| `idempotency_key` | 문자열 | 같은 키의 재전송은 같은 `meal_id`로 귀결(중복 생성 금지). `meal.idempotency_key` 열에 저장 |
| `user_id` | uuid | |
| `eaten_at` | timestamptz | **섭취 시각.** 사용자가 고르지 않으면 촬영·입력 시각을 쓰되 `provided_at`과 구분해 둔다 |
| `provided_at`, `provided_timezone` | timestamptz, 문자열 | 기록 시각과 사용자 시간대(`Asia/Seoul`) |
| `meal_type` | BREAKFAST / MORNING_SNACK / LUNCH / AFTERNOON_SNACK / DINNER / LATE_NIGHT_SNACK / SNACK | 사용자 선택 우선. 없으면 §4.2 시각 규칙으로 보정. `UNKNOWN`은 저장하지 않고 보정한다(미결 #4) |
| `input_type` | PHOTO / MANUAL / MIXED | 사진 인식 결과를 손으로 고치면 MIXED |
| `items[]` | 음식 목록 | 각 항목: `food_name`(앱 표시명), `serving_qty`(0.5 단위, 0.5~3.0, 기본 1.0), `source`(PHOTO / MANUAL / MY_FOOD), 사진 인식 시 `estimated_amount_g`(있을 때만) |
| `status` | COMPLETED / SKIPPED / DRAFT | 결식 표시는 `items`가 비고 `status = SKIPPED`인 이벤트다. DRAFT는 사진만 올리고 확정하지 않은 상태 |
| `edits_meal_id` | uuid, 선택 | 기존 끼니를 고친 이벤트면 원본 `meal_id`. 원본은 지우지 않는다(§4.4) |

인분 수 규칙: 사용자가 입력하는 값은 0.5 단위이고 하한 0.5, 상한 3.0이다(2026-11-02 결정). 상한을 넘는 양은 같은 음식을 두 항목으로 나눠 입력한다.

---

## 3. 2~3단계 — 음식 식별과 영양 환산 (`meal_food` 1행/음식)

### 3.1 음식명 정규화

```python
def normalize(food_name: str) -> str:
    s = unicodedata.normalize("NFC", food_name)
    s = re.sub(r"\s+", "", s)              # 공백 제거
    s = re.sub(r"[()\[\]【】]", "", s)        # 괄호 제거(괄호 안 내용은 유지)
    return s.strip()
```

`food_name`은 사용자가 본 이름 그대로, `food_name_norm`은 위 결과를 저장한다. 매핑과 통계는 항상 `food_name_norm`으로 한다.

### 3.2 식품코드 매핑 (설계 §3.2 1단계, food_reference.md §8)

순서대로 처음 성공하는 규칙을 쓴다. 결과는 `meal_food_master`의 식품코드 1개다.

| 순서 | 규칙 | 설명 |
|---|---|---|
| 1 | 내 음식(MY_FOOD) | 사용자가 저장한 음식은 그 음식에 묶인 식품코드·1인분 값 |
| 2 | 매핑표 EXACT | `food_name_norm` = 매핑표 `food_name_norm` (검수 `reviewed = Y` 우선) |
| 3 | 매핑표 BASE | 조리법·수식어를 뗀 기본명 일치(예: "된장국한그릇" → "된장국") |
| 4 | 마스터 직접 | `meal_food_master.representative_name_norm` 또는 `primary_name_norm` 일치 |
| 5 | PREFIX | 앞부분 일치 후보가 하나뿐이고 열량 분산이 작을 때만 |
| 6 | 실패 | `analysis_status = UNKNOWN`, 영양소 21열 **NULL**(0이 아님). 음식명은 그대로 보존해 매핑표 2차의 입력으로 쓴다 |

같은 이름이 여러 코드에 걸리면 등급(FULL > CORE > PARTIAL) → 유형(음식 > 가공식품 > 원재료) → 1인분 출처(고시표 > 식품중량 > 포장) 순으로 고른다.

### 3.3 1인분 영양 환산

```python
def nutrients_for(item, ref) -> dict | None:
    # ref: 식품코드의 1인분 환산 영양값(21열). 마스터가 100 g/100 ml 기준이면 1인분 환산표로 먼저 바꾼다.
    if ref is None:
        return None                                   # UNKNOWN: 영양소 전부 NULL
    out = {}
    for col in NUTRIENT_COLUMNS:                     # energy_kcal … niacin_mg (21열)
        v = ref[col]
        out[col] = None if v is None else round(v * item.serving_qty, 3)   # 참조에 없는 값은 NULL 유지(비타민 E 등)
    return out
```

- 참조에 공란인 영양소는 **NULL로 둔다.** 0으로 바꾸면 "실측 0"과 구분이 안 된다(food_reference §2).
- `estimated_amount_g` = 1인분 중량(g) × 인분 수. 1인분 단위가 ml인 음식은 비워 둔다. 사진 인식이 g 추정을 주면 그 값을 우선하고 인분 수는 `추정 g / 1인분 g`를 0.5 단위로 반올림한다.
- 음식 행 하나에 `seq`(끼니 안 순번), `source`, `analysis_status`(DONE / UNKNOWN), `created_at`을 채운다.

---

## 4. 4단계 — 끼니 행 확정 (`meal` 1행/끼니)

### 4.1 날짜 귀속

```python
KST = ZoneInfo("Asia/Seoul")
ymd = eaten_at.astimezone(KST).strftime("%Y%m%d")     # 하루 경계 00시~24시 KST (설계 §3.6)
```

자정 이후 새벽 섭취는 **다음 날 `ymd`**다. 하루를 뒤로 밀지 않는다. 늦은 식사는 날짜가 아니라 §4.2 플래그로 표현한다.

### 4.2 끼니 유형 보정과 야식 플래그

사용자가 `meal_type`을 고르면 그대로 쓴다. 비어 있거나 UNKNOWN이면 KST 시각으로 보정한다(초안).

| KST 시각 | 보정 유형 |
|---|---|
| 05:00~10:29 | BREAKFAST |
| 10:30~11:29 | MORNING_SNACK |
| 11:30~14:29 | LUNCH |
| 14:30~16:59 | AFTERNOON_SNACK |
| 17:00~20:59 | DINNER |
| 21:00~04:59 | LATE_NIGHT_SNACK |

야식 플래그(행동 층 열)는 유형과 별개로 **`eaten_at`이 21:00 이후 또는 00:00~04:00이면 참**이다. 저녁(DINNER)이 21시 넘어 기록돼도 플래그는 선다.

### 4.3 영양 합계와 상태

```python
foods = [f for f in meal_foods if f.analysis_status == "DONE"]
for col in NUTRIENT_COLUMNS:
    vals = [f[col] for f in foods if f[col] is not None]
    meal[col] = round(sum(vals), 3) if vals else None   # DONE 음식이 하나도 없으면 NULL(0 아님)
```

| `status` | 영양소 열 | `meal_food` | 하루 집계에서 |
|---|---|---|---|
| COMPLETED | Σ DONE 음식 | 1행 이상 | 포함 |
| SKIPPED | 모두 NULL | 없음 | **결식 표시**로 처리(기록된 주요 끼니 수에는 넣지 않고, 결식 끼니 수에 넣음) |
| DRAFT | 모두 NULL | 없음 | 제외. 24시간 안에 확정되지 않으면 보관 규칙에 따라 정리 |

**불변 조건:** `meal`의 영양소 = 같은 끼니 `meal_food`(DONE)의 합. 어긋난 행은 만들지 않고, 음식이 바뀌면 끼니 합을 다시 계산한다.

### 4.4 수정·중복·삭제

- **수정:** 새 `meal` 행을 만들고 `edits_meal_id`에 원본을 넣는다. 원본은 남긴다. 집계는 **수정 사슬의 마지막 행만** 쓴다(원본과 중간 수정본은 제외).
- **중복:** 같은 날 같은 `meal_type`에 여러 COMPLETED 행이 있으면 **합산**한다(끼니 단위 = `user_id × ymd × meal_type` 합계, 완전성 규칙 §1.1). 사진을 두 번 올린 경우는 앱이 `idempotency_key`로 막는다.
- **삭제:** 물리 삭제 대신 `status`를 DELETED로 바꾸는 것을 권한다(미결 #5). 삭제된 행은 집계에서 제외하고 행동 층 결과 값을 다시 계산한다.

### 4.5 기록 지연

`created_at − eaten_at`은 기록 지연이다. 지연이 24시간을 넘는 끼니는 하루 확정(7단계) 뒤에 들어오므로 **해당 날짜의 하루 분류와 습관 층 행을 재계산 대상에 올린다**(§8.3).

---

## 5. 5단계 — 하루 누적과 완전성(잠정, 끼니 1건마다)

끼니 확정 이벤트를 받으면 그 사용자·그 `ymd`의 상태를 다시 계산한다.

```python
def day_state(user_id, ymd, now_kst):
    meals = latest_versions(meal.where(user_id, ymd, status in ("COMPLETED", "SKIPPED")))   # 수정 사슬 마지막, DRAFT 제외
    recorded_main = {m.meal_type for m in meals if m.meal_type in MAIN and m.status == "COMPLETED"}
    skipped_main  = {m.meal_type for m in meals if m.meal_type in MAIN and m.status == "SKIPPED"}
    pending_main  = {t for t in MAIN if t not in recorded_main | skipped_main and now_kst < slot_end(t)}  # 아직 오지 않은 끼니 = 예정
    cumulative    = sum_nutrients(m for m in meals if m.status == "COMPLETED")
    n_snacks      = count(m for m in meals if m.meal_type not in MAIN and m.status == "COMPLETED")
    late_night    = any(is_late_night(m.eaten_at) for m in meals)
    day_class     = classify(recorded_main, skipped_main, pending_main)
    return ...
```

하루 분류(완전성 규칙 §1.2). 끼니 시점에는 `pending_main`이 있으므로 **잠정**이고, 7단계에서 확정한다.

| 분류 | 조건 |
|---|---|
| 완전 | 기록 주요 끼니 = 3 |
| 결식 포함 완전 | 기록 + 결식 표시 = 3 |
| 불완전 | 기록 주요 끼니 1~2 (예정 끼니가 남아 있으면 "진행 중"으로 표시) |
| 미기록 | 기록 주요 끼니 0 (간식만 있어도 미기록) |

운동 후 2시간 플래그: 웨어러블 운동 세션(`activity_*`) 종료 시각이 있고 `eaten_at`이 그 뒤 2시간 안이면 참. 세션 데이터는 늦게 오므로 즉시 경로에서는 "있으면 세움", 9단계 재계산에서 채운다.

---

## 6. 6단계 — 행동 층 결과 값 (끼니 1건 = 1행, 설계 §4)

### 6.1 하루 섭취 기준량

```python
def daily_reference_kcal(user, habit_state):
    if habit_state.ready_for_personal:          # 창 상태 "완전"인 주가 4주 이상(설계 §3.7.6)
        return habit_state.mean_expenditure_4w  # 개인 소모 기준
    return KDRIS_EER[user.sex][age_band(user.age)]   # 기본: KDRIs 2025 필요추정량
```

영양소별 기준은 `KDRIs_2025`(기본) 또는 의료진 지정 가이드라인을 쓴다(가이드라인 13종, `dietary_analysis/guidelines.py`).

### 6.2 남은 끼니 예상과 남은 허용량

```python
share = personal_meal_share(user) or {"BREAKFAST": 0.30, "LUNCH": 0.38, "DINNER": 0.32}   # 개인 패턴 없으면 집단 평균(운영 집계)
expected_rest = sum(share[t] for t in pending_main) * daily_reference_kcal      # 예정 끼니의 예상 섭취
remaining_allowance = daily_reference_kcal - cumulative.energy_kcal - expected_rest
```

### 6.3 트리거(설계 §3.7.5)

```python
usual = personal_mean_kcal(user, meal_type)  or share[meal_type] * daily_reference_kcal
meal_ratio = this_meal.energy_kcal / usual                       # "평소 같은 끼니 대비 배수"
trigger_over  = meal_ratio >= 1.3 or cumulative.energy_kcal > daily_reference_kcal      # 초안 배수 1.3
trigger_under = meal_ratio <= 0.7 and day_class in ("완전", "결식 포함 완전")           # 부족 트리거는 완전한 날만
offset = this_week_cumulative_to_now(user) < last_week_cumulative_same_point(user) * 0.9  # 상쇄(초안 10 %)
```

### 6.4 방향과 판정

- 방향: 방향 규칙 초안 §4의 결정 순서(의료진 가이드라인 → BMI → 체중 추세 → 지수 추세 → 유지). 체중은 `user_master`의 현재 값, 체중 추세는 9단계 결과를 읽는다. 결과에 방향·강도·근거 코드·신뢰도 등급을 함께 쓴다.
- 판정: **과잉은 불완전한 날에도** 낸다(기록된 것만으로 이미 초과면 초과). **부족은 완전한 날에만** 낸다(설계 §3.3). 그 외는 보류.
- 근거 주 상태: 기준일 = 지난주 일요일인 7일 창 행(8단계)의 창 상태(완전 / 섭취만 / 비교 불가)와 조절 상태를 그대로 옮겨 적는다. 없으면 "비교 불가".
- 기여도 상위 음식: 이 끼니 음식 중 열량(및 판정 영양소) 기여 상위 3개(`meal_food_id`, 비중).
- 집단 백분위: 습관 층 창 평균이 있을 때만(8단계 값 참조), 참조 버전 함께.

### 6.5 결과 행 열 (설계 §4 행동 층)

`user_id, meal_id, ymd, meal_type, eaten_at, cumulative_*(21열), daily_reference_kcal, reference_basis(KDRIS/PERSONAL), remaining_allowance_kcal, expected_rest_kcal, pending_main_count, day_class(잠정), direction, direction_code, judgement(줄임/유지/채움/보류), top_foods(json), late_night_flag, post_exercise_flag, basis_sunday, basis_window_state, meal_ratio, trigger_type(OVER/UNDER/NONE), offset_flag, weekly_trigger_count(같은 유형 누적), percentile, reference_version, rule_version, computed_at, readiness, confidence`

같은 `meal_id`가 다시 들어오면(수정·재계산) 행을 **덮어쓴다**(끼니 1건 = 1행 유지). 이전 값은 `computed_at`으로만 구분한다.

---

## 7. 7~9단계 — 매일 배치

### 7.1 하루 확정 (7단계)

다음 날 00:00 KST 이후(초안: 03:00 실행) 전날의 하루 분류를 확정한다. `pending_main`은 더 이상 없으므로 미기록 끼니는 **미기록**(결식 표시가 없으면 불확실)으로 남는다. 식이 유효일 = 완전 또는 결식 포함 완전(불완전은 가중 0, 초안).

### 7.2 습관 층 기준일 행 (8단계)

매일 그날을 기준일로 7/14/30/60/180일 창 행을 만든다(설계 §3.2 5단계).

| 열 | 계산 |
|---|---|
| 식이 유효일, 기록률 | 창 안 유효일 수, 유효일 / 창 길이 |
| 섭취 평균(21열), 끼니 배분, 결식·야식 빈도, 주중·주말 평균 | 유효일 평균 |
| 영양소 판정 | 평균값에 판정 구간 적용(`judgement_bands.md`) |
| 창 상태 | 완전성 규칙 §3 표(식이·웨어러블·동시 유효일 최소치) |
| 전주 대비 변화, 추세 | 전주 vs 전전주, 7일 vs 14·30일 평균. 임계 ±5 %(초안) → 점진적 초과 / 점진적 감소 / 유지 / 보류 |
| 방향·조절 상태 | 방향 규칙표 + 조건표(설계 §3.7.4) |
| 계산 시각, 기준 버전, 준비 상태, 신뢰도 | |

알람 근거는 **기준일 = 지난주 일요일** 행이다. 이번 주 내내 같은 행을 쓰고 월요일에 한 주 옮긴다.

### 7.3 재계산 범위

매일 **최근 35일**의 기준일 행을 지우고 다시 만든다(웨어러블 baseline과 동일). 늦게 들어온 끼니(§4.5)와 웨어러블(§7.4)이 이 구간 안이면 자동으로 반영된다. 35일보다 오래된 행은 불변 스냅숏이다. 근거 레코드에는 계산 시각과 당시 창 상태를 남겨 "월요일에는 섭취만, 목요일에는 완전"이 됐음을 추적할 수 있게 한다.

### 7.4 웨어러블 결합 (9단계)

```python
valid_wear_day = exists(heartrate_bpm row, n_records >= 480) and exists(total_kcal_burned row)   # 완전성 규칙 §2, 초안 480
both_valid     = diet_valid_day & valid_wear_day
energy_index   = mean(intake_kcal[d] - total_kcal_burned[d] for d in both_valid)   # 창 상태 "완전"에서만
```

미착용일은 행이 없으므로 0으로 읽지 않는다. 부분 착용일(`n_records < 480`)은 소모를 쓰지 않는다. 결합 뒤 창 상태를 다시 정하고 6단계의 `basis_window_state`가 참조하는 지난주 일요일 행을 갱신한다.

---

## 8. 페르소나 생성기와의 대응

페르소나 데이터는 "진실 층"(실제 사용자가 먹은 것)을 난수로 만든 뒤, **이 문서의 1~4단계를 관측 층으로 그대로 적용**해 만든 것이다. 실제 운영에서는 진실 층이 사용자 자신이고 1~4단계는 앱·식이분석 코드가 수행한다. 따라서 생성기로 만든 `meal`·`meal_food`와 실제 앱이 만드는 행은 같은 규칙을 만족해야 한다.

| 이 문서 | 생성기(`tools/build_persona_data.py`) | 비고 |
|---|---|---|
| §2 입력 이벤트 | `simulate()`의 하루 루프에서 끼니별 `emit_meal()` 호출 | `input_type` PHOTO 60 / MANUAL 30 / MIXED 10 % |
| §3.1 정규화 | 음식 풀의 `food_name_norm`, 이름 변형 30 %는 공백 제거 규칙만 적용 | 매핑표 2차 연결률 시험용 |
| §3.2 매핑 실패 | `analysis_status = UNKNOWN` 3 %, 영양소 NULL | 실제 비율은 운영에서 측정 |
| §3.3 환산 | `compose()`: 참조 1인분 × `serving_qty`(0.5 단위, 0.5~3.0) | 끼니 목표 열량에 맞춰 품목 수 조정 |
| §4.1 날짜 귀속 | `ymd = eaten_at(KST).date`, 자정 이후 야식은 다음 날 | 테스트 E10 |
| §4.2 야식 | 21시 이후·00~04시, `LATE_NIGHT_SNACK` | 운영 비율 11 % 보정 |
| §4.3 합계·상태 | `meal` = Σ DONE 음식, SKIPPED·DRAFT는 NULL | 정합성 검사 항목 |
| §4.4 수정·중복 | A9 유형: `edits_meal_id`, 같은 끼니 2행, DRAFT | 테스트 P20 |
| §4.5 기록 지연 | `created_at − eaten_at` 70 / 25 / 5 % | |
| §5~§7 | 생성하지 않음. **구현 대상**이며 페르소나 데이터가 입력 | 정답표 `persona_truth_daily`로 복원력 평가 |
| §7.4 수신 지연 | `persona_truth_daily.burn_available_from` | 테스트는 계산일 이전 도착 행만 보이게 걸러 재계산을 재현 |

---

## 9. 수용 기준 (경계 페르소나 → 기대 결과)

구현이 끝나면 페르소나 데이터(`01_Results/persona/`, 로컬)로 아래를 확인한다. 각 행은 명세 §7.2의 경계 페르소나다.

| 페르소나 | 입력 상황 | 기대 결과 |
|---|---|---|
| E01 | 7일 창 식이 유효일 4일 / 3일 교대 | 창 상태 섭취만 / 비교 불가 교대 |
| E02 | 식이 4·웨어러블 4·동시 3 / 2 교대 | 완전 / 섭취만 교대 |
| E03 | 전주 지수 +160 / +140 kcal | 균형 밖 / 균형 안 |
| E04 | 전주 대비 +5.5 % / +4.5 % | 점진적 초과 / 유지 |
| E05 | 과잉 → 더 과잉 | 식이조절 긴급 |
| E06 | 과잉 → 유지 범위 | 개선 확인(긍정) |
| E07 | 나트륨만 2주 과잉 → 해소 | 영양소 단위 조절 성립 → 해소 |
| E08 | 아침 SKIPPED + 점심·저녁 | 결식 포함 완전, 부족 판정 가능 |
| E09 | 아침·점심 2끼로 기준 초과 | 불완전한 날이지만 과잉 판정 |
| E10 | 23:30 야식 + 00:40 야식 | 00:40은 다음 날 ymd, 둘 다 야식 플래그 |
| E11a/b | 체중 +0.9 / +1.1 kg, 측정 3 / 2일 | 안정·측정 충족 / 증가·측정 미달(UNKNOWN) |
| E12a/b | BMI 24.9 / 25.3 | 경계 표시, 보수적 방향 / 줄임 |
| E13 | 지난주 소모가 월 2일 → 목 5일 도착 | 월요일 계산 섭취만 → 목요일 재계산 완전 |
| E14 | 전주 과잉, 이번 주 누적 15 % 낮음 | 줄임 근거 보류(상쇄) |
| E15 | 저체중 + 당뇨 가이드라인 | 가이드라인 최우선, 열량은 채움 |
| E16 | 키·체중 NULL | 신뢰도 낮음, 방향 보류 |
| E17 | 완전 주 4주 연속 | 5주째 개인 기준 전환 |
| E18 | 추석 주만 과잉 | 명절 주 표시(규칙 미정이면 표시만) |
| P11 | 저녁 누락, 진실은 과잉 | 관측 정상·부족 판정 없음(불완전), 진실 대비 과소보고 탐지 양성 |
| P20 | 중복·수정·DRAFT | 수정 사슬 마지막만, 같은 끼니 합산, DRAFT 제외 |

---

## 10. 미결 사항

| # | 항목 | 현재 | 결정 필요 |
|---|---|---|---|
| 1 | `SKIPPED`의 의미 | loop-dev `meal.status`에 존재(15행). 이 문서는 결식 표시로 해석 | 앱 쪽 확인 |
| 2 | 섭취량 진실 원천 | 이 문서는 참조 1인분 × 인분을 기준으로, 매핑 실패는 NULL | LLM 추정값을 별도 열로 보존할지(설계 §9) |
| 3 | 5~6단계 실행 구조 | 끼니 확정 이벤트 → 즉시 계산을 전제 | 이벤트 처리 / 짧은 주기 배치 / 앱 내 계산 중 선택 |
| 4 | `meal_type` 미지정·UNKNOWN | §4.2 시각 보정 표(초안) | 경계 시각 확정 |
| 5 | 삭제 | 논리 삭제 권고 | 상태값 추가 여부 |
| 6 | 트리거 배수 1.3·상쇄 10 % | 초안 | 평가 1차로 확정 |
| 7 | 매핑 PREFIX 규칙 | 보류 2건(food_reference) | 매핑표 2차와 함께 |

---

## 11. 변경 이력

| 날짜 | 내용 |
|---|---|
| 2026-11-02 | 초안. 입력 이벤트 → 음식 식별·환산 → 끼니 행 → 하루 누적 → 행동 층 → 하루 확정 → 습관 층 → 웨어러블 결합의 9단계, 페르소나 생성기 대응표, 경계 페르소나 수용 기준 20건, 미결 7건 |
