"""Offline tests: reference data, judgement bands, long-format row builders, SQL shape."""

import datetime as dt
import re
from pathlib import Path

import pytest

from dietary_analysis import guidelines, judgement, refresh, rows
from dietary_analysis.guidelines import Thresholds
from dietary_analysis.reference import (
	DEFAULT_GUIDELINE, GUIDELINES, MEAL_SLOTS, NUTRIENT_COLUMNS, NUTRIENTS, SELECTABLE_GUIDELINES,
)

USER = "aaaaaaaa-0000-0000-0000-000000000001"
DAY = dt.date(2026, 10, 13)


def _row(meal_type, sex="M", age=45, **values):
	row = {c: None for c in NUTRIENT_COLUMNS}
	row.update(user_id=USER, eaten_date=values.pop("eaten_date", DAY), meal_type=meal_type,
		row_level="DAY" if meal_type == "DAY_TOTAL" else "MEAL", sex=sex, age=age,
		incomplete_nutrients=values.pop("incomplete", []))
	row.update(values)
	return row


# Worked example: user A (M 45) on 2026-10-13
EXAMPLE = [
	_row("BREAKFAST", energy_kcal=520, carbohydrate_g=78, protein_g=22, fat_g=13, sodium_mg=980),
	_row("LUNCH", energy_kcal=1350, carbohydrate_g=180, protein_g=42, fat_g=50, sodium_mg=2600, saturated_fat_g=13),
	_row("AFTERNOON_SNACK", energy_kcal=180, carbohydrate_g=28, protein_g=3, fat_g=6.5, sodium_mg=90, calcium_mg=120),
	_row("DINNER", energy_kcal=720, carbohydrate_g=95, protein_g=38, fat_g=20, sodium_mg=1450),
	_row("DAY_TOTAL", energy_kcal=2770, carbohydrate_g=381, protein_g=105, fat_g=89.5, sodium_mg=5120,
		incomplete=["calcium_mg"]),
]


def _pick(records, guideline, nutrient, meal_type=None):
	return next(r for r in records if r["guideline_code"] == guideline and r["nutrient_code"] == nutrient
		and (meal_type is None or r["meal_type"] == meal_type))


# --- reference data ----------------------------------------------------------

def test_default_guideline_is_selectable_and_unique():
	assert DEFAULT_GUIDELINE in SELECTABLE_GUIDELINES
	assert {"KSSO_OBESITY", "KDCA_HTN_DIET"}.isdisjoint(SELECTABLE_GUIDELINES)


def test_every_criterion_references_known_codes_and_has_values():
	for c in guidelines.CRITERIA:
		assert c.guideline in GUIDELINES and c.nutrient in NUTRIENTS
		if c.numeric:
			t = c.thresholds()
			assert any(x is not None for x in (t.deficient, t.low, t.high, t.excess)), c


def test_kdris_band_tables_have_one_value_per_band():
	for nutrient, _kind, _sex, fields, _note in guidelines._KDRIS_BY_BAND:
		for name, values in fields.items():
			assert len(values) == len(guidelines._KDRIS_BANDS), (nutrient, name)


def test_criteria_keys_are_unique():
	keys = [(c.guideline, c.nutrient, c.sex, c.age_min) for c in guidelines.CRITERIA]
	assert len(keys) == len(set(keys))


def test_every_collected_nutrient_is_judged_under_kdris():
	"""Each source nutrient column has a KDRIs criterion directly or via its energy-% counterpart."""
	judged_columns = {NUTRIENTS[c].column for c in rows.JUDGED if judgement.applies(DEFAULT_GUIDELINE, c)}
	assert judged_columns == set(NUTRIENT_COLUMNS)


def test_meal_shares_cover_every_meal_type():
	assert MEAL_SLOTS["DAY_TOTAL"].energy_share == 1.0
	main = sum(s.energy_share for s in MEAL_SLOTS.values() if s.main_meal)
	assert main == pytest.approx(0.85)


# --- judgement bands (docs/judgement_bands.md) --------------------------------

def _kdris(nutrient, sex="M", age=45):
	return judgement.resolve(DEFAULT_GUIDELINE, nutrient, sex, age).criterion


def test_energy_bands_follow_knhanes_and_khei():
	t = _kdris("ENERGY_KCAL").thresholds()        # EER 2,500
	assert (t.deficient, t.low, t.high, t.excess) == (1500, 1875, 3125, 3500)
	assert [judgement.judge(v, t) for v in (1400, 1600, 2770, 3300, 3600)] == [1, 2, 3, 4, 5]


def test_ear_rni_bands_have_no_slight_excess():
	t = _kdris("CALCIUM_MG").thresholds()         # EAR 650 / RNI 800 / UL 2,500
	assert (t.deficient, t.low, t.high, t.excess) == (650, 800, 2500, 2500)
	assert [judgement.judge(v, t) for v in (600, 700, 1500, 2400, 2600)] == [1, 2, 3, 3, 5]


def test_ai_bands():
	t = _kdris("DIETARY_FIBER_G").thresholds()    # AI 30, no UL
	assert (t.deficient, t.low, t.high, t.excess) == (15, 30, None, None)
	assert [judgement.judge(v, t) for v in (10, 20, 40, 100)] == [1, 2, 3, 3]


def test_upper_bands_use_single_excess_ratio():
	na = _kdris("SODIUM_MG").thresholds()         # AI 1,500 / CDRR 2,300
	assert (na.low, na.high, na.excess) == (1500, 2300, pytest.approx(3220))
	sfa = _kdris("SAT_FAT_PCT").thresholds()      # 7%
	assert (sfa.high, sfa.excess) == (7, pytest.approx(9.8))
	assert judgement.judge(9.0, sfa) == 4 and judgement.judge(10.5, sfa) == 5


def test_range_pct_bands_use_five_point_margin():
	t = _kdris("FAT_PCT").thresholds()            # 15~30%
	assert (t.deficient, t.low, t.high, t.excess) == (10, 15, 30, 35)
	assert [judgement.judge(v, t) for v in (8, 12, 25, 33, 40)] == [1, 2, 3, 4, 5]


def test_judge_scales_daily_amount_reference_to_meal():
	t = _kdris("SODIUM_MG").thresholds()
	assert judgement.judge(600, t, scale=0.30) == 3
	assert judgement.judge(2600, t, scale=0.30) == 5


def test_resolve_uses_sex_and_age_band():
	assert judgement.resolve(DEFAULT_GUIDELINE, "SAT_FAT_PCT", "M", 17).criterion.upper == 8
	assert judgement.resolve(DEFAULT_GUIDELINE, "SAT_FAT_PCT", "M", 45).criterion.upper == 7
	assert judgement.resolve(DEFAULT_GUIDELINE, "SODIUM_MG", "F", 80).criterion.upper == 1800
	assert judgement.resolve(DEFAULT_GUIDELINE, "CHOLESTEROL_MG", "M", 17).criterion is None
	assert judgement.resolve(DEFAULT_GUIDELINE, "ENERGY_KCAL", None, None).criterion is None


# --- ② nutrient rows ---------------------------------------------------------

def test_nutrient_rows_worked_example_kdris():
	out = rows.build_nutrient_rows(EXAMPLE[4])             # DAY_TOTAL
	kdris = [r for r in out if r["guideline_code"] == DEFAULT_GUIDELINE]
	assert len(kdris) == 23
	energy = _pick(out, DEFAULT_GUIDELINE, "ENERGY_KCAL")
	assert (energy["ref_value"], energy["pct_of_ref"], energy["label_5"]) == (2500, 110.8, "적절")
	sodium = _pick(out, DEFAULT_GUIDELINE, "SODIUM_MG")
	assert (sodium["ref_label"], sodium["judgement_5"], sodium["color_hex"]) == ("만성질환위험감소섭취량", 5, "#EB5757")
	calcium = _pick(out, DEFAULT_GUIDELINE, "CALCIUM_MG")
	assert calcium["judgement_5"] == 0 and calcium["is_incomplete"] and calcium["label_3"] == "판정불가"
	assert set(refresh.NUTRIENT_COLUMNS_OUT) <= set(out[0])


def test_nutrient_rows_other_guidelines_only_own_criteria():
	out = rows.build_nutrient_rows(EXAMPLE[1])             # LUNCH, share 0.30
	by_guideline = {}
	for r in out:
		by_guideline.setdefault(r["guideline_code"], set()).add(r["nutrient_code"])
	assert by_guideline["KSOLA_2022"] == {"FAT_PCT", "SAT_FAT_PCT", "CHOLESTEROL_MG"}
	assert by_guideline["WHO"] == {"SODIUM_MG"}
	assert by_guideline["US_AHA_ACC_2018"] == {"SAT_FAT_PCT"}
	assert "KDA_2023" not in by_guideline and "US_ADA_2026" not in by_guideline   # qualitative only
	who = _pick(out, "WHO", "SODIUM_MG")
	assert who["ref_value"] == 600 and who["judgement_5"] == 5                   # 2,000 x 0.30, 2,600 > 840
	ksola = _pick(out, "KSOLA_2022", "SAT_FAT_PCT")
	assert ksola["intake_value"] == 8.67 and ksola["range_high"] == 7 and ksola["label_5"] == "약간과잉"


def test_nutrient_rows_missing_profile_is_unjudged_but_kept():
	out = rows.build_nutrient_rows(_row("DAY_TOTAL", sex=None, age=None, energy_kcal=2000, sodium_mg=3000))
	assert {r["guideline_code"] for r in out} == {DEFAULT_GUIDELINE}
	assert {r["judgement_5"] for r in out} == {0}
	assert _pick(out, DEFAULT_GUIDELINE, "SODIUM_MG")["intake_value"] == 3000


# --- ③ period rows -------------------------------------------------------------

def test_period_rows_windows_ratio_of_sums_and_flags():
	meals = []
	for i in range(10):
		day = DAY - dt.timedelta(days=i)
		kcal, fat = (1000, 40) if i % 2 else (500, 10)
		meals.append(_row("LUNCH", eaten_date=day, energy_kcal=kcal, fat_g=fat, sodium_mg=1000))
		meals.append(_row("DAY_TOTAL", eaten_date=day, energy_kcal=kcal, fat_g=fat, sodium_mg=1000))
	out = rows.build_period_rows(meals, DAY, "M", 45)
	fat7 = next(r for r in out if r["meal_type"] == "LUNCH" and r["window_days"] == 7
		and r["guideline_code"] == DEFAULT_GUIDELINE and r["nutrient_code"] == "FAT_PCT")
	# days 0..6: four 500 kcal days (10 g) and three 1000 kcal days (40 g)
	assert fat7["avg_value"] == round(100 * (4 * 90 + 3 * 360) / (4 * 500 + 3 * 1000), 2)
	assert fat7["record_days"] == 7 and fat7["sufficiency"] == "OK" and fat7["valid_days"] == 7
	na30 = next(r for r in out if r["meal_type"] == "LUNCH" and r["window_days"] == 30
		and r["guideline_code"] == DEFAULT_GUIDELINE and r["nutrient_code"] == "SODIUM_MG")
	assert na30["sufficiency"] == "LOW" and na30["window_exceeds_history"]
	assert na30["ref_value"] == 690 and na30["judgement_5"] == 5                 # 1,000 > 690 x 1.4 = 966
	assert {r["window_days"] for r in out} == {7, 14, 30, 60, 180}
	assert {r["guideline_code"] for r in out} >= {DEFAULT_GUIDELINE, "WHO", "KSOLA_2022"}
	assert set(refresh.PERIOD_COLUMNS_OUT) <= set(out[0])


# --- SQL ------------------------------------------------------------------------

def test_refresh_sql_uses_only_named_parameters():
	stray = re.findall(r"%(?!\(from_date\)s|\(min_coverage\)s|\(rule_version\)s)", refresh.INSERT_MEAL_SQL)
	assert stray == []
	assert "create " not in refresh.INSERT_MEAL_SQL.lower()
	for column in NUTRIENT_COLUMNS:
		assert f"as {column}" in refresh.SELECT_SQL or f"w.{column}" in refresh.SELECT_SQL


def test_schema_declares_every_column_the_refresh_writes():
	schema = (Path(__file__).resolve().parents[1] / "sql" / "schema.sql").read_text()
	for column in refresh.NUTRIENT_COLUMNS_OUT + refresh.PERIOD_COLUMNS_OUT:
		assert re.search(rf"^\t{column}\s", schema, re.M), column
	for column in NUTRIENT_COLUMNS + ("energy_share", "weight_kg", "profile_complete", "nutrient_coverage_pct",
			"rule_version"):
		assert re.search(rf"^\t{column}\s", schema, re.M), column
	assert "create or replace view" not in schema and "jsonb" not in schema
