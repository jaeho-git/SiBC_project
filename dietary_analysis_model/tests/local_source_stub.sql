-- Local validation only (tests/local_source_stub.sql): source table stubs (subset of loop-dev.sibc columns)
-- plus synthetic data. Never run against loop-dev.
--
-- Synthetic users
--   A: M 45  - 2026-10-13 = the worked example (breakfast, lunch, afternoon snack, dinner)
--   B: F 34  - regular logger, micronutrients present
--   C: M, age NULL - profile gap
-- History: 2026-04-01 .. 2026-10-13, deterministic pseudo-random gaps.

drop schema if exists sibc cascade;
create schema sibc;

create table sibc.user_master (user_id uuid primary key, age integer, sex varchar, weight integer, height integer);

create table sibc.meal (
	meal_id uuid primary key, user_id uuid, ymd char(8), eaten_at timestamptz,
	meal_type varchar, input_type varchar, status varchar,
	energy_kcal numeric, carbohydrate_g numeric, protein_g numeric, fat_g numeric, sugar_g numeric,
	sodium_mg numeric, cholesterol_mg numeric, dietary_fiber_g numeric, saturated_fat_g numeric,
	trans_fat_g numeric, calcium_mg numeric, vitamin_a_ug numeric, vitamin_c_mg numeric,
	vitamin_d_ug numeric, vitamin_e_mg numeric, thiamin_mg numeric, riboflavin_mg numeric,
	niacin_mg numeric, potassium_mg numeric, iron_mg numeric, phosphorus_mg numeric,
	edits_meal_id uuid, created_at timestamptz, updated_at timestamptz
);

create table sibc.meal_food (
	meal_food_id uuid primary key, meal_id uuid, user_id uuid, eaten_at timestamptz, seq smallint,
	analysis_status varchar, serving_qty numeric,
	energy_kcal numeric, carbohydrate_g numeric, protein_g numeric, fat_g numeric, sugar_g numeric,
	sodium_mg numeric, cholesterol_mg numeric, dietary_fiber_g numeric, saturated_fat_g numeric,
	trans_fat_g numeric, calcium_mg numeric, vitamin_a_ug numeric, vitamin_c_mg numeric,
	vitamin_d_ug numeric, vitamin_e_mg numeric, thiamin_mg numeric, riboflavin_mg numeric,
	niacin_mg numeric, potassium_mg numeric, iron_mg numeric, phosphorus_mg numeric,
	created_at timestamptz, updated_at timestamptz
);

insert into sibc.user_master values
	('aaaaaaaa-0000-0000-0000-000000000001', 45, 'M', 72, 175),
	('bbbbbbbb-0000-0000-0000-000000000002', 34, 'F', 58, 162),
	('cccccccc-0000-0000-0000-000000000003', null, 'M', null, null);

-- Worked example: user A, 2026-10-13 (nutrients per serving)
create temp table ex(meal_no int, meal_type text, hh int, food_no int, qty numeric,
	kcal numeric, carb numeric, prot numeric, fat numeric, sugar numeric, na numeric, chol numeric,
	fiber numeric, sfa numeric, tfa numeric, ca numeric, vita numeric, vitc numeric, vitd numeric,
	vite numeric, thi numeric, ribo numeric, nia numeric, k numeric, fe numeric, p numeric);
insert into ex values
	-- breakfast: rice + soybean paste soup (micronutrients missing on the soup)
	(1, 'BREAKFAST', 7, 1, 1, 310, 68, 6, 1, 0, 5, 0, 1, 0.2, 0, 10, 0, 0, 0, 0.1, 0.05, 0.02, 1.2, 80, 0.5, 90),
	(1, 'BREAKFAST', 7, 2, 1, 210, 10, 16, 12, 3, 975, 20, 3, 2, 0, null, null, null, null, null, null, null, null, null, null, null),
	-- lunch: jjajangmyeon + sweet and sour pork
	(2, 'LUNCH', 12, 3, 1, 800, 120, 22, 25, 18, 1800, 30, 6, 6, 0.3, null, null, null, null, null, null, null, null, null, null, null),
	(2, 'LUNCH', 12, 4, 1, 550, 60, 20, 25, 20, 800, 60, 1, 7, 0.4, null, null, null, null, null, null, null, null, null, null, null),
	-- afternoon snack: yogurt
	(3, 'AFTERNOON_SNACK', 15, 5, 1, 180, 28, 3, 6.5, 22, 90, 15, 0, 4, 0.1, 120, 40, 1, 0.1, 0.1, 0.03, 0.15, 0.1, 150, 0.1, 100),
	-- dinner: grilled fish + rice + kimchi (kimchi 2 servings)
	(4, 'DINNER', 19, 6, 1, 250, 0, 30, 14, 0, 450, 70, 0, 3, 0, null, null, null, null, null, null, null, null, null, null, null),
	(4, 'DINNER', 19, 7, 1, 310, 68, 6, 1, 0, 5, 0, 1, 0.2, 0, 10, 0, 0, 0, 0.1, 0.05, 0.02, 1.2, 80, 0.5, 90),
	(4, 'DINNER', 19, 8, 2, 80, 13.5, 1, 2.5, 3, 497.5, 0, 2, 0.3, 0, null, null, null, null, null, null, null, null, null, null, null);

insert into sibc.meal (meal_id, user_id, ymd, eaten_at, meal_type, input_type, status, created_at, updated_at)
select distinct
	('aaaaaaaa-1013-0000-0000-00000000000' || meal_no)::uuid,
	'aaaaaaaa-0000-0000-0000-000000000001'::uuid, '20261013',
	('2026-10-13 ' || hh || ':00:00+09')::timestamptz, meal_type, 'MANUAL', 'COMPLETED',
	('2026-10-13 ' || hh || ':05:00+09')::timestamptz, ('2026-10-13 ' || hh || ':05:00+09')::timestamptz
from ex;

insert into sibc.meal_food
select ('aaaaaaaa-1013-0000-0001-00000000000' || food_no)::uuid,
	('aaaaaaaa-1013-0000-0000-00000000000' || meal_no)::uuid,
	'aaaaaaaa-0000-0000-0000-000000000001'::uuid,
	('2026-10-13 ' || hh || ':00:00+09')::timestamptz, food_no, 'DONE', qty,
	kcal, carb, prot, fat, sugar, na, chol, fiber, sfa, tfa, ca, vita, vitc, vitd, vite, thi, ribo, nia, k, fe, p,
	now(), now()
from ex;

-- Generated history for A/B/C. hashtext() gives deterministic variation.
with days as (
	select d::date as day from generate_series('2026-04-01'::date, '2026-10-12'::date, interval '1 day') d
), slots(meal_type, hh, base_kcal) as (values
	('BREAKFAST', 8, 450), ('MORNING_SNACK', 10, 150), ('LUNCH', 12, 750),
	('AFTERNOON_SNACK', 15, 200), ('DINNER', 19, 700), ('LATE_NIGHT_SNACK', 22, 300)
), users(user_id, tag, log_rate, micro) as (values
	('aaaaaaaa-0000-0000-0000-000000000001'::uuid, 'A', 55, false),
	('bbbbbbbb-0000-0000-0000-000000000002'::uuid, 'B', 85, true),
	('cccccccc-0000-0000-0000-000000000003'::uuid, 'C', 40, false)
), plan as (
	select u.user_id, u.tag, u.micro, d.day, s.meal_type, s.hh, s.base_kcal,
		abs(hashtext(u.tag || d.day::text || s.meal_type)) % 100 as r
	from users u cross join days d cross join slots s
	where abs(hashtext(u.tag || d.day::text)) % 100 < u.log_rate
), chosen as (
	select *, md5(tag || day::text || meal_type) as h
	from plan
	where (meal_type in ('BREAKFAST', 'LUNCH', 'DINNER') and r < 90)
		or (meal_type = 'AFTERNOON_SNACK' and r < 45)
		or (meal_type = 'MORNING_SNACK' and r < 20)
		or (meal_type = 'LATE_NIGHT_SNACK' and r < 12)
)
insert into sibc.meal (meal_id, user_id, ymd, eaten_at, meal_type, input_type, status, created_at, updated_at)
select
	(substr(h, 1, 8) || '-' || substr(h, 9, 4) || '-' || substr(h, 13, 4) || '-' || substr(h, 17, 4) || '-' || substr(h, 21, 12))::uuid,
	user_id, to_char(day, 'YYYYMMDD'), (day + make_interval(hours => hh)) at time zone 'Asia/Seoul',
	meal_type, 'MANUAL',
	case when meal_type = 'BREAKFAST' and r < 8 then 'SKIPPED' else 'COMPLETED' end,
	now(), now()
from chosen;

-- 1~3 foods per completed meal
insert into sibc.meal_food
select
	(substr(h2, 1, 8) || '-' || substr(h2, 9, 4) || '-' || substr(h2, 13, 4) || '-' || substr(h2, 17, 4) || '-' || substr(h2, 21, 12))::uuid,
	m.meal_id, m.user_id, m.eaten_at, k, 'DONE',
	case when abs(hashtext(h2)) % 10 = 0 then 1.5 else 1 end,
	kcal, kcal * cp / 400, kcal * pp / 400, kcal * fp / 900, kcal * cp / 400 * 0.18,
	kcal * 1.9, kcal * 0.12, kcal * 0.006, kcal * fp / 900 * 0.33, kcal * fp / 900 * 0.01,
	case when micro then kcal * 0.35 end, case when micro then kcal * 0.4 end,
	case when micro then kcal * 0.05 end, case when micro then kcal * 0.002 end,
	case when micro then kcal * 0.005 end, case when micro then kcal * 0.0006 end,
	case when micro then kcal * 0.0007 end, case when micro then kcal * 0.006 end,
	case when micro then kcal * 1.3 end, case when micro then kcal * 0.005 end,
	case when micro then kcal * 0.5 end,
	now(), now()
from sibc.meal m
join (values ('A', false), ('B', true), ('C', false)) as uu(tag, micro)
	on left(m.user_id::text, 1) = lower(uu.tag)
cross join lateral generate_series(1, 1 + abs(hashtext(m.meal_id::text)) % 3) k
cross join lateral (select md5(m.meal_id::text || k) as h2) hh
cross join lateral (
	select
		round((case m.meal_type when 'BREAKFAST' then 450 when 'LUNCH' then 750 when 'DINNER' then 700
			when 'AFTERNOON_SNACK' then 200 when 'MORNING_SNACK' then 150 else 300 end)
			* (0.7 + (abs(hashtext(h2)) % 60) / 100.0) / (1 + abs(hashtext(m.meal_id::text)) % 3)) as kcal,
		48 + abs(hashtext(h2 || 'c')) % 22 as cp,
		10 + abs(hashtext(h2 || 'p')) % 12 as pp
) b
cross join lateral (select greatest(100 - b.cp - b.pp, 5) as fp) f
where m.status = 'COMPLETED' and m.ymd <> '20261013';

-- Edge cases
-- (1) duplicate LUNCH record on the same day for user B
insert into sibc.meal (meal_id, user_id, ymd, eaten_at, meal_type, input_type, status, created_at, updated_at)
values ('bbbbbbbb-dddd-0000-0000-000000000001', 'bbbbbbbb-0000-0000-0000-000000000002', '20261010',
	'2026-10-10 13:30:00+09', 'LUNCH', 'MANUAL', 'COMPLETED', now(), now());
insert into sibc.meal_food (meal_food_id, meal_id, user_id, eaten_at, seq, analysis_status, serving_qty,
	energy_kcal, carbohydrate_g, protein_g, fat_g, sugar_g, sodium_mg, cholesterol_mg, dietary_fiber_g,
	saturated_fat_g, trans_fat_g, calcium_mg, vitamin_a_ug, vitamin_c_mg, vitamin_d_ug, vitamin_e_mg,
	thiamin_mg, riboflavin_mg, niacin_mg, potassium_mg, iron_mg, phosphorus_mg, created_at, updated_at)
values ('bbbbbbbb-dddd-0000-0001-000000000001', 'bbbbbbbb-dddd-0000-0000-000000000001',
	'bbbbbbbb-0000-0000-0000-000000000002', '2026-10-10 13:30:00+09', 1, 'DONE', 1,
	250, 40, 5, 8, 20, 120, 10, 1, 3, 0, 80, 30, 5, 0.5, 1, 0.1, 0.2, 1, 200, 0.5, 100, now(), now());
-- (2) completed meal without meal_food rows: meal-level values are used
insert into sibc.meal (meal_id, user_id, ymd, eaten_at, meal_type, input_type, status,
	energy_kcal, carbohydrate_g, protein_g, fat_g, sugar_g, sodium_mg, cholesterol_mg, dietary_fiber_g,
	saturated_fat_g, trans_fat_g, created_at, updated_at)
values ('bbbbbbbb-dddd-0000-0000-000000000002', 'bbbbbbbb-0000-0000-0000-000000000002', '20261011',
	'2026-10-11 22:30:00+09', 'SNACK', 'PHOTO', 'COMPLETED', 120, 15, 2, 6, 10, 60, 5, 0.5, 2, 0, now(), now());
-- (3) edited meal: the original (old) is superseded by the edit (new)
insert into sibc.meal (meal_id, user_id, ymd, eaten_at, meal_type, input_type, status,
	energy_kcal, carbohydrate_g, protein_g, fat_g, created_at, updated_at)
values
	('cccccccc-dddd-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000003', '20261012',
	 '2026-10-12 21:00:00+09', 'LATE_NIGHT_SNACK', 'MANUAL', 'COMPLETED', 999, 100, 10, 50, now(), now());
insert into sibc.meal (meal_id, user_id, ymd, eaten_at, meal_type, input_type, status,
	energy_kcal, carbohydrate_g, protein_g, fat_g, sugar_g, sodium_mg, cholesterol_mg, dietary_fiber_g,
	saturated_fat_g, trans_fat_g, edits_meal_id, created_at, updated_at)
values
	('cccccccc-dddd-0000-0000-000000000002', 'cccccccc-0000-0000-0000-000000000003', '20261012',
	 '2026-10-12 21:00:00+09', 'LATE_NIGHT_SNACK', 'MANUAL', 'COMPLETED', 300, 40, 8, 12, 15, 300, 20, 1, 4, 0,
	 'cccccccc-dddd-0000-0000-000000000001', now(), now());
