"""Daily refresh of the three dietary analysis tables.

	set -a; source .env.dml; set +a
	python -m dietary_analysis.refresh                        # as_of = today (KST), all dates
	python -m dietary_analysis.refresh --from-date 2026-04-01 # rebuild ①/② for eaten_date >= date
	python -m dietary_analysis.refresh --as-of 2026-10-01     # backfill a period snapshot

Steps (one transaction, serialized by an advisory lock, no database objects created)
	1. ① sibc.dietary_analysis_meal: delete + rebuild from sibc.meal / meal_food / user_master
	   (② rows are removed by the cascade and rebuilt in step 2)
	2. ② sibc.dietary_analysis_nutrient: every guideline for every rebuilt ① row
	3. ③ sibc.dietary_analysis_period: snapshot for as_of, for users whose data for
	   as_of was recorded or edited (eaten_date = as_of or source_updated_at >= as_of)
	4. ③ retention: drop snapshots older than 180 days except Monday ones

Source rules for ①
- meal.status = COMPLETED rows become meal rows; SKIPPED rows are listed in the
  DAY_TOTAL row's skipped_meal_types.
- A meal referenced by another meal's edits_meal_id is superseded.
- Nutrient = sum(meal_food value x coalesce(serving_qty, 1)); a meal without
  meal_food rows contributes its own meal-level values.
- A total is kept when at least min_coverage of the items carry the value
  (flagged in incomplete_nutrients); below that it is NULL (판정불가).
- eaten_date = meal.ymd (local date recorded by the app).
"""

import argparse
import datetime as dt
import os
from collections import defaultdict
from decimal import Decimal

from .reference import (
	MEAL_SLOTS, NUTRIENT_COLUMNS, PERIOD_DAILY_RETENTION_DAYS, PERIOD_WEEKLY_KEEP_ISO_WEEKDAY, PERIOD_WINDOWS,
	RULE_VERSION,
)
from .rows import build_nutrient_rows, build_period_rows

KST = dt.timezone(dt.timedelta(hours=9))

_FOOD_VALUES = ", ".join(f"('{c}', f.{c})" for c in NUTRIENT_COLUMNS)
_MEAL_VALUES = ", ".join(f"('{c}', m.{c})" for c in NUTRIENT_COLUMNS)
_PIVOT = ",\n\t\t".join(f"max(val) filter (where nutrient = '{c}') as {c}" for c in NUTRIENT_COLUMNS)
_COLUMNS = ", ".join(NUTRIENT_COLUMNS)
_W_COLUMNS = ", ".join(f"w.{c}" for c in NUTRIENT_COLUMNS)
_COVERAGE = " + ".join(f"(w.{c} is not null)::int" for c in NUTRIENT_COLUMNS)
_SHARE_CASE = "case w.meal_type " + " ".join(
	f"when '{m}' then {s.energy_share}" for m, s in MEAL_SLOTS.items()) + " end"

# Parameters: %(from_date)s (date or NULL), %(min_coverage)s (0..1), %(rule_version)s
SELECT_SQL = rf"""
with live_meal as (
	select m.*, to_date(m.ymd, 'YYYYMMDD') as eaten_date
	from sibc.meal m
	where m.status in ('COMPLETED', 'SKIPPED')
		and m.ymd ~ '^\d{{8}}$'
		and not exists (select 1 from sibc.meal e where e.edits_meal_id = m.meal_id)
		and (%(from_date)s::date is null or to_date(m.ymd, 'YYYYMMDD') >= %(from_date)s::date)
),
eaten_meal as (
	select * from live_meal where status = 'COMPLETED'
),
food as (
	select f.*, coalesce(f.serving_qty, 1) as qty
	from sibc.meal_food f
	join eaten_meal m on m.meal_id = f.meal_id
),
food_meta as (
	select meal_id, count(*) as food_cnt,
		array_agg(meal_food_id order by seq, meal_food_id) as food_ids,
		count(*) filter (where analysis_status is distinct from 'DONE') as unknown_cnt,
		max(updated_at) as food_updated_at
	from food group by meal_id
),
item_long as (
	select m.user_id, m.eaten_date, m.meal_type, v.nutrient, v.val * f.qty as val
	from food f
	join eaten_meal m on m.meal_id = f.meal_id
	cross join lateral (values {_FOOD_VALUES}) as v(nutrient, val)
	union all
	select m.user_id, m.eaten_date, m.meal_type, v.nutrient, v.val
	from eaten_meal m
	cross join lateral (values {_MEAL_VALUES}) as v(nutrient, val)
	where not exists (select 1 from food_meta fm where fm.meal_id = m.meal_id)
),
grp_long as (
	select l.user_id, l.eaten_date, k.meal_type, l.nutrient,
		count(*) as n_items, count(l.val) as n_known,
		case when count(l.val) > 0 and count(l.val) >= %(min_coverage)s * count(*) then sum(l.val) end as val
	from item_long l
	cross join lateral (values (l.meal_type), ('DAY_TOTAL')) as k(meal_type)
	group by l.user_id, l.eaten_date, k.meal_type, l.nutrient
),
wide as (
	select user_id, eaten_date, meal_type,
		{_PIVOT},
		coalesce(array_agg(nutrient order by nutrient) filter (where n_known < n_items), '{{}}') as incomplete_nutrients
	from grp_long
	group by user_id, eaten_date, meal_type
),
meal_meta as (
	select m.user_id, m.eaten_date, k.meal_type,
		array_agg(m.meal_id order by m.eaten_at, m.meal_id) as meal_ids,
		array_remove(array_agg(distinct m.input_type), null) as input_types,
		count(*) filter (where m.input_type in ('PHOTO', 'MIXED')) as photo_meal_cnt,
		count(*) filter (where m.input_type = 'MANUAL') as manual_meal_cnt,
		coalesce(sum(fm.unknown_cnt), 0) as unknown_food_cnt,
		max(greatest(m.updated_at, fm.food_updated_at)) as source_updated_at
	from eaten_meal m
	left join food_meta fm on fm.meal_id = m.meal_id
	cross join lateral (values (m.meal_type), ('DAY_TOTAL')) as k(meal_type)
	group by m.user_id, m.eaten_date, k.meal_type
),
grp_food as (
	select m.user_id, m.eaten_date, k.meal_type,
		coalesce(array_agg(fid order by fid) filter (where fid is not null), '{{}}') as food_ids
	from eaten_meal m
	left join food_meta fm on fm.meal_id = m.meal_id
	cross join lateral (values (m.meal_type), ('DAY_TOTAL')) as k(meal_type)
	left join lateral unnest(fm.food_ids) as fid on true
	group by m.user_id, m.eaten_date, k.meal_type
),
day_status as (
	select user_id, eaten_date,
		coalesce(array_agg(distinct meal_type) filter (where status = 'SKIPPED'), '{{}}') as skipped_meal_types,
		count(distinct meal_type) filter (where meal_type in ('BREAKFAST', 'LUNCH', 'DINNER')) as main_meals_recorded
	from live_meal
	group by user_id, eaten_date
)
select
	w.user_id, w.eaten_date, w.meal_type,
	case when w.meal_type = 'DAY_TOTAL' then 'DAY' else 'MEAL' end as row_level,
	g.meal_ids, gf.food_ids as meal_food_ids,
	cardinality(g.meal_ids) as meal_cnt, cardinality(gf.food_ids) as food_cnt,
	{_W_COLUMNS},
	{_SHARE_CASE} as energy_share,
	u.sex, u.age, u.weight as weight_kg, u.height as height_cm,
	(u.sex is not null and u.age is not null) as profile_complete,
	round(100.0 * ({_COVERAGE}) / {len(NUTRIENT_COLUMNS)}, 1) as nutrient_coverage_pct,
	w.incomplete_nutrients,
	g.input_types, g.photo_meal_cnt, g.manual_meal_cnt, g.unknown_food_cnt,
	case when w.meal_type = 'DAY_TOTAL' then ds.skipped_meal_types else '{{}}' end as skipped_meal_types,
	case when w.meal_type = 'DAY_TOTAL' then ds.main_meals_recorded end as main_meals_recorded,
	case when w.meal_type = 'DAY_TOTAL' then
		case when ds.main_meals_recorded = 3 then 'COMPLETE' else 'PARTIAL' end
	end as day_record_status,
	%(rule_version)s::varchar as rule_version,
	g.source_updated_at
from wide w
join meal_meta g using (user_id, eaten_date, meal_type)
join grp_food gf using (user_id, eaten_date, meal_type)
join day_status ds using (user_id, eaten_date)
left join sibc.user_master u on u.user_id = w.user_id
"""

INSERT_MEAL_SQL = f"""
insert into sibc.dietary_analysis_meal (
	user_id, eaten_date, meal_type, row_level, meal_ids, meal_food_ids, meal_cnt, food_cnt,
	{_COLUMNS},
	energy_share, sex, age, weight_kg, height_cm, profile_complete,
	nutrient_coverage_pct, incomplete_nutrients, input_types, photo_meal_cnt, manual_meal_cnt, unknown_food_cnt,
	skipped_meal_types, main_meals_recorded, day_record_status, rule_version, source_updated_at
)
{SELECT_SQL}
"""

DELETE_MEAL_SQL = """
delete from sibc.dietary_analysis_meal
where %(from_date)s::date is null or eaten_date >= %(from_date)s::date
"""

_MEAL_READ_COLUMNS = ("user_id", "eaten_date", "meal_type", "row_level", *NUTRIENT_COLUMNS,
	"sex", "age", "incomplete_nutrients")

NUTRIENT_COLUMNS_OUT = ("user_id", "eaten_date", "meal_type", "guideline_code", "nutrient_code",
	"intake_value", "unit", "value_kind", "ref_kind", "ref_value", "ref_label", "range_low", "range_high",
	"pct_of_ref", "judgement_5", "label_5", "judgement_3", "label_3", "color_hex", "is_incomplete")

PERIOD_COLUMNS_OUT = ("as_of_date", "user_id", "meal_type", "window_days", "guideline_code", "nutrient_code",
	"window_start", "energy_share", "avg_value", "unit", "value_kind", "valid_days", "slot_days", "record_days",
	"record_coverage_pct", "sufficiency", "window_exceeds_history", "ref_kind", "ref_value", "ref_label",
	"range_low", "range_high", "pct_of_ref", "judgement_5", "label_5", "judgement_3", "label_3", "color_hex")


def _plain(value):
	return float(value) if isinstance(value, Decimal) else value


def _fetch_dicts(cur, sql: str, params=None) -> list[dict]:
	cur.execute(sql, params)
	names = [d[0] for d in cur.description]
	return [{k: _plain(v) for k, v in zip(names, r)} for r in cur.fetchall()]


def _insert_rows(cur, table: str, columns: tuple[str, ...], rows: list[dict]) -> int:
	from psycopg2.extras import execute_values

	if not rows:
		return 0
	values = [tuple(r[c] for c in columns) for r in rows]
	execute_values(cur, f"insert into {table} ({', '.join(columns)}) values %s", values, page_size=1000)
	return len(rows)


def _refresh_nutrient(cur, from_date: dt.date | None) -> int:
	meals = _fetch_dicts(cur,
		f"select {', '.join(_MEAL_READ_COLUMNS)} from sibc.dietary_analysis_meal "
		"where %(from_date)s::date is null or eaten_date >= %(from_date)s::date "
		"order by user_id, eaten_date", {"from_date": from_date})
	rows = []
	for m in meals:
		rows.extend(build_nutrient_rows(m))
	return _insert_rows(cur, "sibc.dietary_analysis_nutrient", NUTRIENT_COLUMNS_OUT, rows)


def _refresh_period(cur, as_of: dt.date) -> tuple[int, int]:
	"""Snapshot for users whose as_of data was recorded or edited. Returns (users, rows)."""
	cur.execute("select distinct user_id::text from sibc.dietary_analysis_meal "
		"where eaten_date = %(d)s or source_updated_at >= (%(d)s::date::timestamp at time zone 'Asia/Seoul')",
		{"d": as_of})
	user_ids = sorted(r[0] for r in cur.fetchall())
	if not user_ids:
		return 0, 0
	cur.execute("delete from sibc.dietary_analysis_period where as_of_date = %s and user_id = any(%s::uuid[])",
		(as_of, user_ids))
	start = as_of - dt.timedelta(days=max(PERIOD_WINDOWS) - 1)
	meals = _fetch_dicts(cur,
		f"select {', '.join(_MEAL_READ_COLUMNS)} from sibc.dietary_analysis_meal "
		"where user_id = any(%s::uuid[]) and eaten_date between %s and %s order by user_id, eaten_date",
		(user_ids, start, as_of))
	history = {r["user_id"]: r["first_day"] for r in _fetch_dicts(cur,
		"select user_id::text as user_id, min(eaten_date) as first_day from sibc.dietary_analysis_meal "
		"where user_id = any(%s::uuid[]) and row_level = 'DAY' group by user_id", (user_ids,))}
	profiles = {r["user_id"]: (r["sex"], r["age"]) for r in _fetch_dicts(cur,
		"select user_id::text as user_id, sex, age from sibc.user_master where user_id = any(%s::uuid[])", (user_ids,))}
	by_user: dict[str, list[dict]] = defaultdict(list)
	for m in meals:
		by_user[str(m["user_id"])].append(m)
	rows = []
	for uid, user_meals in by_user.items():
		sex, age = profiles.get(uid, (None, None))
		rows.extend(build_period_rows(user_meals, as_of, sex, age, history_start=history.get(uid)))
	return len(by_user), _insert_rows(cur, "sibc.dietary_analysis_period", PERIOD_COLUMNS_OUT, rows)


def _apply_period_retention(cur, as_of: dt.date) -> int:
	cur.execute("delete from sibc.dietary_analysis_period "
		"where as_of_date < %s and extract(isodow from as_of_date) <> %s",
		(as_of - dt.timedelta(days=PERIOD_DAILY_RETENTION_DAYS), PERIOD_WEEKLY_KEEP_ISO_WEEKDAY))
	return cur.rowcount


def refresh(conn, from_date: dt.date | None = None, min_coverage: float = 0.8,
		as_of: dt.date | None = None, skip_period: bool = False) -> dict[str, int]:
	as_of = as_of or dt.datetime.now(KST).date()
	params = {"from_date": from_date, "min_coverage": min_coverage, "rule_version": RULE_VERSION}
	result: dict[str, int] = {}
	with conn:
		with conn.cursor() as cur:
			cur.execute("select pg_advisory_xact_lock(hashtext('sibc.dietary_analysis.refresh'))")
			cur.execute(DELETE_MEAL_SQL, params)
			result["meal_deleted"] = cur.rowcount
			cur.execute(INSERT_MEAL_SQL, params)
			result["meal_inserted"] = cur.rowcount
			result["nutrient_inserted"] = _refresh_nutrient(cur, from_date)
			if not skip_period:
				result["period_users"], result["period_inserted"] = _refresh_period(cur, as_of)
				result["period_pruned"] = _apply_period_retention(cur, as_of)
	return result


def connect_from_env():
	"""Connection from DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD (e.g. .env.dml)."""
	import psycopg2

	return psycopg2.connect(
		host=os.environ["DB_HOST"],
		port=os.environ.get("DB_PORT", "5432"),
		dbname=os.environ["DB_NAME"],
		user=os.environ.get("DB_USER") or os.environ["DB_USERNAME"],
		password=os.environ["DB_PASSWORD"],
	)


def main() -> None:
	parser = argparse.ArgumentParser(description="Refresh sibc.dietary_analysis_* tables")
	parser.add_argument("--from-date", type=dt.date.fromisoformat, default=None,
		help="rebuild ①/② only for eaten_date >= this date (default: all dates)")
	parser.add_argument("--as-of", type=dt.date.fromisoformat, default=None,
		help="period snapshot date (default: today in Asia/Seoul)")
	parser.add_argument("--min-coverage", type=float, default=0.8,
		help="minimum share of foods carrying a nutrient value to keep the total (default 0.8)")
	parser.add_argument("--skip-period", action="store_true", help="do not write a period snapshot")
	args = parser.parse_args()
	conn = connect_from_env()
	try:
		result = refresh(conn, args.from_date, args.min_coverage, args.as_of, args.skip_period)
	finally:
		conn.close()
	print(", ".join(f"{k}={v}" for k, v in result.items()))


if __name__ == "__main__":
	main()
