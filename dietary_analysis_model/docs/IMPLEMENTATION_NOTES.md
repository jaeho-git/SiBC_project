# 구현 메모 (dietary_analysis_model)

`SiBC_project/dietary_analysis_model` 기준. 환경 설정은 `uv sync --extra dev`, 실행은 `uv run …`.

loop-dev `sibc.meal`, `sibc.meal_food`, `sibc.user_master`를 끼니별·하루 단위로 집계하고, KDRIs 2025와 의료진이 쓰는 가이드라인으로
영양소를 판정하는 테이블 3개를 만듭니다. 현재 구현은 2026-10-21 방향 전환 전 구조이며, 설계 기준 문서
[system_design_20261022.md](system_design_20261022.md) §7에 따라 ①은 행동 층, ③은 습관 층(매일 기준일 baseline)의 전신으로 확장합니다.
②의 영양소별 가이드라인 판정과 끼니 고정 배분 판정은 의료진용으로 유지합니다.

## 테이블 (DB) 과 코드 (git)

| 위치 | 항목 | 내용 |
|---|---|---|
| **DB** | `sibc.dietary_analysis_meal` ① | 사용자 × 날짜 × 끼니(+`DAY_TOTAL`): 영양 합계 21개, 판정 프로필, 데이터 완전성 지표 |
| **DB** | `sibc.dietary_analysis_nutrient` ② | ① × 가이드라인 × 영양소 = 1행. 영양소별 가이드라인 판정(의료진용) |
| **DB** | `sibc.dietary_analysis_period` ③ | 기준일 × 사용자 × 끼니 × 기간(7/14/30/60/180) × 가이드라인 × 영양소 = 1행. 기간 baseline(습관 층의 전신). 알람 근거는 기준일 = 지난주 일요일 행 |
| git | `dietary_analysis/reference.py` | 가이드라인 13종, 영양소 23개, 판정 라벨·색, 끼니 배분 비율, 보관 정책, 규칙 버전 |
| git | `dietary_analysis/guidelines.py` | KDRIs 2025 성별·연령별 기준값, 타 가이드라인 기준, 기준 유형별 판정 구간 |
| git | `dietary_analysis/judgement.py` | 기준 선택, KDRIs 대체, 5단계/3단계 판정 |
| git | `dietary_analysis/rows.py` | ②③ 행 생성 |
| git | `dietary_analysis/refresh.py` | 매일 갱신 작업 (①은 SQL, ②③은 Python) |
| git | `sql/schema.sql` | 테이블 DDL |
| git | `tools/download_nutri_std.py`, `tools/extract_serving_rule.py`, `tools/build_food_reference.py` | 식약처 영양성분 참조 데이터 다운로드 → 1회 섭취참고량 규칙표 → 1인분 환산 참조 테이블 생성 |
| git | `data/food_code_classification.csv`, `data/processed_food_serving_rule.csv` | 식품코드 → 분류 접두어표, 가공식품 1회 섭취참고량 규칙표 |
| git | `tools/build_food_code_map.py` → `data/food_code_map.csv` | 앱 음식명 → 식약처 식품코드 매핑표 (등급·유형·플래그 우선순위로 후보 선택, `reviewed` 검수 플래그). `meal_food` 적재 시 참조 1인분 값을 가져오는 키 |
| `00_Data/` (git 제외) | `전국통합식품영양성분정보_전체_20260929.csv` | 식약처 API 전체 원본 |
| `01_Results/` (git 제외) | `food_nutrient_reference.csv`, `food_nutrient_reference_per_serving.csv`, `food_reference_profile.md` | 참조 테이블(100 기준 + 1인분), 1인분 환산 영양성분표, 프로파일 (원본에서 재생성) |
| git | `tools/build_knhanes_reference.py` → `data/knhanes_reference_dist.csv`, `data/knhanes_reference_model.json` | 국민건강영양조사 기본DB(SAS)에서 맥락 층 외부 참조(칸별 백분위, 회귀 표준화 계수) 생성. `uv sync --extra ref` 필요 |
| `00_Data/knhanes/` (git 제외) | `HN22/HN23/HN24 *.sas7bdat` | 국민건강영양조사 2022~2024 기본DB 원자료 |
| `01_Results/knhanes/` (git 제외) | `knhanes_person_2022_2024.csv` | 개인 단위 추출(검증용) |
| git | `tools/build_persona_food_pool.py` → `data/persona_food_pool_v1.csv`, `data/persona_params_v1.toml`, `data/persona_types_v1.csv` | 페르소나(합성 사용자) 생성기의 음식 풀·매개변수·유형표 ([persona_data_spec_20261027.md](persona_data_spec_20261027.md)) |
| git | `tools/build_persona_data.py`, `tools/check_persona_calibration.py`, `tests/test_persona_generator.py` | 페르소나 생성기(로컬 CSV 전용, DB 접속 없음), 보정·정합성 검사, 오프라인 테스트 |
| `01_Results/persona/` (git 제외) | `*.csv`, `load_local.sql`, `run_info.json` | 생성된 페르소나 데이터. 공유 DB에 적재하지 않음. `load_local.sql`은 로컬 PostgreSQL 전용 |
| git | `docs/guidelines.md` | 가이드라인 목록과 기준 (`python -m dietary_analysis.guideline_list`로 생성) |
| git | `docs/judgement_bands.md` | 판정 구간 문헌 근거 |

뷰, jsonb, 가이드라인 지정 테이블은 없습니다. 병원·의료진·사용자에 따라 어떤 가이드라인을 보여줄지는 앱이 정하고,
DB에는 모든 사용자의 모든 가이드라인 결과가 미리 들어 있습니다.

## 설치 (1회, `sibc` 스키마 CREATE 권한 필요)

```bash
psql -v ON_ERROR_STOP=1 -f sql/schema.sql
```

갱신 작업을 `loop_dml`로 돌리려면 테이블 소유자가 권한을 부여합니다.

```sql
grant select, insert, delete on sibc.dietary_analysis_meal, sibc.dietary_analysis_nutrient, sibc.dietary_analysis_period to loop_dml;
```

## 갱신 (매일 1회, 스케줄링은 담당 개발자)

```bash
cd dietary_analysis_model
set -a; source ../.env.dml; set +a                       # SiBC_project 루트의 env 파일
uv run python -m dietary_analysis.refresh                          # ①② 전체 재계산 + 오늘(KST) 기준 ③ 스냅숏 + 보관 정리
uv run python -m dietary_analysis.refresh --from-date 2026-04-01   # ①②는 해당 날짜 이후만
uv run python -m dietary_analysis.refresh --as-of 2026-10-01       # 과거 기준일 ③ 스냅숏(백필)
```

| 옵션 | 기본값 | 의미 |
|---|---|---|
| `--from-date` | 없음(전체) | ①②에서 이 날짜 이후 행만 지우고 다시 계산 |
| `--as-of` | 오늘(Asia/Seoul) | ③ 기준일. 그날 기록이 생기거나 수정된 사용자만 스냅숏 생성 |
| `--min-coverage` | 0.8 | 값이 있는 음식 비율이 이 이상이면 합계, 미만이면 NULL(판정불가) |
| `--skip-period` | — | ③ 스냅숏과 보관 정리 생략 |

한 트랜잭션으로 실행되고 advisory lock으로 동시 실행을 막습니다. DB 객체는 만들지 않습니다.

## 가이드라인 행 규칙

- `guideline_code = 'KDRIs_2025'`: 모든 사용자, 영양소 23개 전부.
- 다른 가이드라인(`KSOLA_2022`, `WHO`, `US_DGA_2020_2025`, `US_DGA_2025_2030`, `US_AHA_ACC_2018`, `EU_ESC_EAS_2019`,
  `CN_CNS_DG_2022`, `CN_NHC_HYPERLIPIDEMIA_2023`, `CN_NHC_DIABETES_2023`, `CN_NHC_HYPERTENSION_2023`):
  **자체 수치 기준이 있는 영양소 행만** 저장. `KDA_2023`, `US_ADA_2026`는 수치 기준이 없어 행이 없습니다.
- 앱은 선택한 가이드라인 행이 없는 영양소에 KDRIs 행을 쓰고 "지표 누락 — KDRIs 2025 기준 적용"을 표시합니다.

```sql
-- [A] 의료진: 가이드라인 :G, 없는 영양소는 KDRIs 대체
select k.meal_type, k.nutrient_code,
       coalesce(g.intake_value, k.intake_value) as intake_value,
       coalesce(g.ref_value, k.ref_value)       as ref_value,
       coalesce(g.judgement_5, k.judgement_5)   as judgement_5,
       coalesce(g.color_hex, k.color_hex)       as color_hex,
       (g.nutrient_code is null)                as is_fallback
from sibc.dietary_analysis_nutrient k
left join sibc.dietary_analysis_nutrient g
  on (g.user_id, g.eaten_date, g.meal_type, g.nutrient_code) = (k.user_id, k.eaten_date, k.meal_type, k.nutrient_code)
 and g.guideline_code = :G
where k.user_id = :user_id and k.eaten_date = :date and k.guideline_code = 'KDRIs_2025';

-- [B] KDRIs 전체(기본): 탄·단·지 구성비는 nutrient_code in ('CARB_PCT','PROTEIN_PCT','FAT_PCT')
select * from sibc.dietary_analysis_nutrient
where user_id = :user_id and eaten_date = :date and guideline_code = 'KDRIs_2025';

-- [C] 끼니(x축) × 기간: 같은 대체 규칙을 ③에 적용
select * from sibc.dietary_analysis_period
where user_id = :user_id and as_of_date = :as_of and guideline_code = 'KDRIs_2025' and nutrient_code = 'FAT_PCT'
order by meal_type, window_days;
```

## 판정 규칙 요약

- 기준 유형 5가지(필요추정량, 평균필요량·권장섭취량, 충분섭취량, 상한형, 에너지적정비율)별 구간. 근거는 `docs/judgement_bands.md`.
- 설계 파라미터 3개(충분섭취량 × 0.5, 상한 × 1.4, 적정비율 ± 5%p)는 기준 보완 후 확정할 초안 (`rule_version` = `...-draft`).
- 끼니 판정은 하루 절대량 기준 × 배분 비율(아침 25%, 점심·저녁 30%, 간식 5%). 비율 기준은 그대로. 이 고정 배분 판정은 의료진용으로만 유지하고, 사용자 알람 근거는 하루 누적·남은 섭취 허용량으로 판단한다(설계 §3.3).
- 색: 과잉 `#EB5757`, 부족 `#F2C94C`, 적절 `#27AE60`, 판정불가 `#BDBDBD`. 5단계 라벨: 부족·약간부족·적절·약간과잉·과잉.
- 하루 단위 판정(②)은 참고, 7일 이상 평균(③)이 공식 판정. ③의 `sufficiency = LOW`는 기록일이 기간의 50% 미만.
- 성별·연령이 없으면 판정불가(0). KDRIs 기준값은 6세 이상.

## 데이터 완전성 지표

| 위치 | 컬럼 |
|---|---|
| ① | `nutrient_coverage_pct`, `incomplete_nutrients`, `input_types`, `photo_meal_cnt`, `manual_meal_cnt`, `unknown_food_cnt`, `skipped_meal_types`, `main_meals_recorded`, `day_record_status`, `profile_complete` |
| ② | `is_incomplete`, `judgement_5 = 0`(판정불가) |
| ③ | `valid_days`, `slot_days`, `record_days`, `record_coverage_pct`, `sufficiency`, `window_exceeds_history` |

## 테스트

```bash
uv run pytest -q
```

`tests/local_source_stub.sql`은 원천과 같은 구조의 합성 데이터입니다. 로컬 DB에서만 실행하세요.

## 참조 데이터 재생성

```bash
export DATAGO_KEY=<공공데이터포털 인증키>
uv run python tools/download_nutri_std.py --out 00_Data/전국통합식품영양성분정보_전체_YYYYMMDD.csv
uv run python tools/extract_serving_rule.py --xls <가공식품 .xls> --out data/processed_food_serving_rule.csv   # xls 갱신 시에만
uv run python tools/build_food_reference.py --full 00_Data/전국통합식품영양성분정보_전체_YYYYMMDD.csv --out-dir 01_Results
uv run python tools/build_food_code_map.py --names data/food_names_dev.txt --reference 01_Results/food_nutrient_reference.csv --out data/food_code_map.csv --existing data/food_code_map.csv
```

## 외부 참조 분포 재생성 (국민건강영양조사)

```bash
uv sync --extra dev --extra ref
uv run python tools/build_knhanes_reference.py \
  --sas 00_Data/knhanes/HN22/hn22_all.sas7bdat 00_Data/knhanes/HN23/hn23_all.sas7bdat 00_Data/knhanes/HN24/hn24_all.sas7bdat \
  --out-person 01_Results/knhanes/knhanes_person_2022_2024.csv \
  --out-dist data/knhanes_reference_dist.csv --out-model data/knhanes_reference_model.json
```

상세는 `docs/knhanes_reference.md`.

## 페르소나 데이터 (합성, 로컬 전용)

```bash
cd dietary_analysis_model
python tools/build_persona_food_pool.py                 # 1인분 환산표에서 음식 풀 재생성 (01_Results 참조 테이블 필요)
python tools/build_persona_data.py                      # 01_Results/persona/ 에 CSV 생성. 지시가 있을 때만 실행
python tools/build_persona_data.py --codes P01,E01 --max-per-type 2 --out /path/to/tmp   # 소규모 시험
python tools/check_persona_calibration.py               # 보정 목표 32개·정합성 검사 (실패 시 종료 코드 1)
uv run --extra dev pytest tests/test_persona_generator.py
```

생성기는 DB에 접속하지 않으며, 생성 데이터는 loop-dev·release DB에 적재하지 않는다. 로컬 PostgreSQL에서 식이분석 코드를 돌려 볼 때만 `01_Results/persona/load_local.sql`을 로컬 DB에 실행한다.
