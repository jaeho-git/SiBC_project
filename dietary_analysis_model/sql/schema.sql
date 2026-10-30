-- =============================================================================
-- dietary_analysis_model / sql/schema.sql       Target: loop-dev.sibc (PostgreSQL 16)
--
-- Three tables, filled daily by `python -m dietary_analysis.refresh`.
--   ① sibc.dietary_analysis_meal      user x date x meal_type (+DAY_TOTAL): nutrient totals, profile, completeness
--   ② sibc.dietary_analysis_nutrient  ① x guideline x nutrient: judgement  -> 그림 A (의료진), 그림 B (사용자)
--   ③ sibc.dietary_analysis_period    as_of x user x meal_type x window x guideline x nutrient -> 그림 C
-- One ②/③ row = one chart bar. Guidelines, criteria, bands, colors, and meal
-- shares live in git (dietary_analysis/reference.py, guidelines.py).
--
-- Guideline rows: KDRIs_2025 has every judged nutrient for every user. Other
-- guidelines have rows only for nutrients they define themselves; for the rest
-- the app uses the KDRIs_2025 row and shows "지표 누락 - KDRIs 2025 기준 적용".
-- =============================================================================

create table if not exists sibc.dietary_analysis_meal (
	user_id               uuid        not null,
	eaten_date            date        not null,
	meal_type             varchar(30) not null,          -- BREAKFAST, MORNING_SNACK, LUNCH, AFTERNOON_SNACK, DINNER, LATE_NIGHT_SNACK, SNACK, DAY_TOTAL
	row_level             varchar(4)  not null check (row_level in ('MEAL', 'DAY')),
	-- source records aggregated into this row
	meal_ids              uuid[]      not null,
	meal_food_ids         uuid[]      not null,
	meal_cnt              smallint    not null,
	food_cnt              smallint    not null,
	-- nutrient totals = sum(meal_food value x serving_qty); NULL when < 80% of foods carry the value
	energy_kcal           numeric(10,2),
	carbohydrate_g        numeric(10,2),
	protein_g             numeric(10,2),
	fat_g                 numeric(10,2),
	sugar_g               numeric(10,2),
	dietary_fiber_g       numeric(10,2),
	saturated_fat_g       numeric(10,2),
	trans_fat_g           numeric(10,2),
	cholesterol_mg        numeric(10,2),
	sodium_mg             numeric(10,2),
	potassium_mg          numeric(10,2),
	calcium_mg            numeric(10,2),
	phosphorus_mg         numeric(10,2),
	iron_mg               numeric(10,2),
	vitamin_a_ug          numeric(10,2),
	vitamin_c_mg          numeric(10,2),
	vitamin_d_ug          numeric(10,2),
	vitamin_e_mg          numeric(10,2),
	thiamin_mg            numeric(10,2),
	riboflavin_mg         numeric(10,2),
	niacin_mg             numeric(10,2),
	energy_share          numeric(5,4),                  -- meal share of daily amount references (DAY_TOTAL = 1)
	-- profile used for the judgement (user_master at refresh time)
	sex                   varchar(1),
	age                   integer,
	weight_kg             numeric(6,2),
	height_cm             numeric(6,2),
	profile_complete      boolean     not null,          -- sex and age present
	-- data completeness
	nutrient_coverage_pct numeric(5,1),                  -- non-null nutrient columns / 21
	incomplete_nutrients  text[]      not null default '{}',  -- nutrient columns with a missing food value (possible underestimate)
	input_types           text[]      not null default '{}',  -- distinct meal.input_type (MANUAL / PHOTO / MIXED)
	photo_meal_cnt        smallint    not null default 0,
	manual_meal_cnt       smallint    not null default 0,
	unknown_food_cnt      smallint    not null default 0,  -- meal_food.analysis_status <> DONE
	skipped_meal_types    text[]      not null default '{}',  -- DAY rows: meals recorded as SKIPPED
	main_meals_recorded   smallint,                      -- DAY rows: breakfast/lunch/dinner eaten or skipped (0-3)
	day_record_status     varchar(8),                    -- DAY rows: COMPLETE / PARTIAL
	rule_version          varchar(40) not null,
	source_updated_at     timestamptz,
	refreshed_at          timestamptz not null default now(),
	primary key (user_id, eaten_date, meal_type)
);
create index if not exists dietary_analysis_meal_date_idx on sibc.dietary_analysis_meal (eaten_date);
comment on table sibc.dietary_analysis_meal is
	'① 식이분석 끼니·하루 요약. 사용자 x 날짜 x 끼니(간식 포함) + 하루 합계(DAY_TOTAL). 영양 합계, 판정 프로필, 데이터 완전성 지표.';

create table if not exists sibc.dietary_analysis_nutrient (
	user_id               uuid        not null,
	eaten_date            date        not null,
	meal_type             varchar(30) not null,
	guideline_code        varchar(40) not null,          -- KDRIs_2025 (all nutrients) or another guideline (own criteria only)
	nutrient_code         varchar(40) not null,          -- 23 codes: ENERGY_KCAL, CARB_PCT, ... (dietary_analysis/reference.py)
	intake_value          numeric(12,2),                 -- amount in `unit`, or % of energy
	unit                  varchar(12) not null,
	value_kind            varchar(12) not null,          -- AMOUNT / ENERGY_PCT
	-- reference applied (daily reference x energy_share for a meal)
	ref_kind              varchar(12),                   -- EER / EAR_RNI / AI / AI_CDRR / UPPER / RANGE_PCT / RANGE_ABS
	ref_value             numeric(12,2),                 -- 적정섭취수준 shown next to the intake
	ref_label             varchar(30),                   -- 필요추정량 / 권장섭취량 / 충분섭취량 / 만성질환위험감소섭취량 / 상한 기준 / 적정비율
	range_low             numeric(12,2),
	range_high            numeric(12,2),
	pct_of_ref            numeric(7,1),
	-- judgement: 0 판정불가, 1 부족, 2 약간부족, 3 적절, 4 약간과잉, 5 과잉
	judgement_5           smallint    not null check (judgement_5 between 0 and 5),
	label_5               varchar(8)  not null,
	judgement_3           varchar(10) not null,          -- DEFICIENT / ADEQUATE / EXCESS / UNKNOWN
	label_3               varchar(8)  not null,
	color_hex             char(7)     not null,          -- 과잉 #EB5757, 부족 #F2C94C, 적절 #27AE60, 판정불가 #BDBDBD
	is_incomplete         boolean     not null,          -- a food lacked this value (possible underestimate)
	primary key (user_id, eaten_date, meal_type, guideline_code, nutrient_code),
	foreign key (user_id, eaten_date, meal_type) references sibc.dietary_analysis_meal on delete cascade
);
create index if not exists dietary_analysis_nutrient_date_idx on sibc.dietary_analysis_nutrient (eaten_date);
comment on table sibc.dietary_analysis_nutrient is
	'② 영양소 판정 (1행 = 막대 1개). 사용자 앱: guideline_code = KDRIs_2025. 의료진: 병원이 정한 코드로 조회하고 '
	'행이 없는 영양소는 KDRIs_2025 행 사용(지표 누락 표시). 하루 단위 판정은 참고용, 공식 판정은 ③(7일 이상 평균).';

create table if not exists sibc.dietary_analysis_period (
	as_of_date            date        not null,
	user_id               uuid        not null,
	meal_type             varchar(30) not null,
	window_days           smallint    not null check (window_days in (7, 14, 30, 60, 180)),
	guideline_code        varchar(40) not null,
	nutrient_code         varchar(40) not null,
	window_start          date        not null,
	energy_share          numeric(5,4),
	avg_value             numeric(12,2),                 -- mean over days the meal was eaten (energy % = ratio of sums)
	unit                  varchar(12) not null,
	value_kind            varchar(12) not null,
	-- data completeness
	valid_days            integer     not null,          -- slot days with a value for this nutrient
	slot_days             integer     not null,          -- days the meal_type was eaten in the window
	record_days           integer     not null,          -- days with any eaten meal in the window
	record_coverage_pct   numeric(5,1) not null,         -- record_days / window_days
	sufficiency           varchar(3)  not null,          -- OK / LOW (< 50% coverage: 참고용)
	window_exceeds_history boolean    not null,          -- window starts before the user's first record
	-- reference and judgement (same columns as ②)
	ref_kind              varchar(12),
	ref_value             numeric(12,2),
	ref_label             varchar(30),
	range_low             numeric(12,2),
	range_high            numeric(12,2),
	pct_of_ref            numeric(7,1),
	judgement_5           smallint    not null check (judgement_5 between 0 and 5),
	label_5               varchar(8)  not null,
	judgement_3           varchar(10) not null,
	label_3               varchar(8)  not null,
	color_hex             char(7)     not null,
	primary key (as_of_date, user_id, meal_type, window_days, guideline_code, nutrient_code)
);
create index if not exists dietary_analysis_period_user_idx on sibc.dietary_analysis_period (user_id, as_of_date);
comment on table sibc.dietary_analysis_period is
	'③ 기간 패턴 (1행 = 막대 1개). 기준일 이전 7/14/30/60/180일 끼니별 평균과 판정. '
	'최근 180일은 기준일마다, 그 이전은 월요일 기준일만 보관. 그날 기록이 생기거나 수정된 사용자만 스냅숏 생성.';

-- Grants for the daily job when it runs as loop_dml (run as table owner):
-- grant select, insert, delete on sibc.dietary_analysis_meal, sibc.dietary_analysis_nutrient,
--   sibc.dietary_analysis_period to loop_dml;
