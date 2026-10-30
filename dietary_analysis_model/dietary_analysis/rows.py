"""Long-format rows for sibc.dietary_analysis_nutrient (②) and sibc.dietary_analysis_period (③).

One row = one chart bar. Pure builders: dietary_analysis_meal rows (①) in, table
rows out. Every selectable guideline is precomputed for every user: KDRIs 2025
for all judged nutrients, other guidelines only for the nutrients they have their
own numeric criterion for. The app picks guideline_code at read time and falls
back to the KDRIs row when a guideline has no row for a nutrient (지표 누락).
"""

import datetime as dt
from collections.abc import Sequence

from .judgement import applies, evaluate
from .reference import (
	DEFAULT_GUIDELINE, MEAL_SLOTS, NUTRIENTS, PERIOD_MIN_RECORD_SHARE, PERIOD_WINDOWS, SELECTABLE_GUIDELINES,
)

JUDGED: tuple[str, ...] = tuple(code for code, n in NUTRIENTS.items() if n.judged)


# -----------------------------------------------------------------------------
# Intake values from a ① row
# -----------------------------------------------------------------------------

def energy_basis(row: dict) -> float | None:
	"""Denominator of energy ratios: recorded energy, else 4/4/9 macro energy."""
	if row.get("energy_kcal") is not None:
		return row["energy_kcal"]
	macros = (row.get("carbohydrate_g"), row.get("protein_g"), row.get("fat_g"))
	if any(v is None for v in macros):
		return None
	return macros[0] * 4 + macros[1] * 4 + macros[2] * 9


def intake_value(row: dict, nutrient: str) -> float | None:
	n = NUTRIENTS[nutrient]
	value = row.get(n.column)
	if n.kind == "AMOUNT" or value is None:
		return value
	basis = energy_basis(row)
	return 100 * value * n.kcal_per_g / basis if basis else None


def _meal_share(meal_type: str) -> float | None:
	slot = MEAL_SLOTS.get(meal_type)
	return slot.energy_share if slot else None


def _r(x, digits=2):
	return None if x is None else round(x, digits)


def _judgement_columns(rec: dict) -> dict:
	return {
		"ref_kind": rec["ref_kind"], "ref_value": rec["primary_ref_value"], "ref_label": rec["primary_ref_label"],
		"range_low": rec["range_low"], "range_high": rec["range_high"], "pct_of_ref": rec["pct_of_primary_ref"],
		"judgement_5": rec["judgement_5"], "label_5": rec["label_5"],
		"judgement_3": rec["judgement_3"], "label_3": rec["label_3"], "color_hex": rec["color_hex_3"],
	}


def _guideline_records(values: dict[str, float | None], sex, age, share: float | None):
	"""Yield (guideline, nutrient, evaluate() record) for every stored combination."""
	for code in JUDGED:
		if applies(DEFAULT_GUIDELINE, code):
			yield DEFAULT_GUIDELINE, code, evaluate(values[code], code, DEFAULT_GUIDELINE, sex, age, share)
	for guideline in SELECTABLE_GUIDELINES:
		if guideline == DEFAULT_GUIDELINE:
			continue
		for code in JUDGED:
			rec = evaluate(values[code], code, guideline, sex, age, share)
			if rec["applied_guideline_code"] == guideline:      # own numeric criterion only
				yield guideline, code, rec


# -----------------------------------------------------------------------------
# ② nutrient rows
# -----------------------------------------------------------------------------

def build_nutrient_rows(meal_row: dict) -> list[dict]:
	"""② rows for one ① row (all guidelines)."""
	share = _meal_share(meal_row["meal_type"]) if meal_row["row_level"] == "MEAL" else 1.0
	values = {code: intake_value(meal_row, code) for code in JUDGED}
	incomplete = set(meal_row.get("incomplete_nutrients") or [])
	out = []
	for guideline, code, rec in _guideline_records(values, meal_row.get("sex"), meal_row.get("age"), share):
		n = NUTRIENTS[code]
		out.append({
			"user_id": meal_row["user_id"], "eaten_date": meal_row["eaten_date"],
			"meal_type": meal_row["meal_type"], "guideline_code": guideline, "nutrient_code": code,
			"intake_value": _r(values[code]), "unit": n.unit, "value_kind": n.kind,
			**_judgement_columns(rec),
			"is_incomplete": n.column in incomplete,
		})
	return out


# -----------------------------------------------------------------------------
# ③ period rows
# -----------------------------------------------------------------------------

def _period_values(rows: Sequence[dict]) -> tuple[dict[str, float | None], dict[str, int]]:
	"""Averages over slot days (energy ratios as ratio of sums) and days with a value."""
	values: dict[str, float | None] = {}
	valid: dict[str, int] = {}
	for code in JUDGED:
		n = NUTRIENTS[code]
		if n.kind == "AMOUNT":
			xs = [r[n.column] for r in rows if r.get(n.column) is not None]
			values[code] = sum(xs) / len(xs) if xs else None
			valid[code] = len(xs)
		else:
			pairs = [(r[n.column] * n.kcal_per_g, energy_basis(r)) for r in rows if r.get(n.column) is not None]
			pairs = [(num, den) for num, den in pairs if den]
			den = sum(d for _, d in pairs)
			values[code] = 100 * sum(num for num, _ in pairs) / den if den else None
			valid[code] = len(pairs)
	return values, valid


def build_period_rows(meal_rows: Sequence[dict], as_of: dt.date, sex, age,
		history_start: dt.date | None = None, windows: Sequence[int] = PERIOD_WINDOWS) -> list[dict]:
	"""③ rows for one user and one as_of date: meal_type x window x guideline x nutrient."""
	if history_start is None:
		history_start = min((r["eaten_date"] for r in meal_rows if r["row_level"] == "DAY"), default=as_of)
	out = []
	for window in windows:
		start = as_of - dt.timedelta(days=window - 1)
		in_window = [r for r in meal_rows if start <= r["eaten_date"] <= as_of]
		record_days = sum(1 for r in in_window if r["row_level"] == "DAY")
		if record_days == 0:
			continue
		coverage = round(100 * record_days / window, 1)
		sufficiency = "LOW" if record_days < PERIOD_MIN_RECORD_SHARE * window else "OK"
		by_slot: dict[str, list[dict]] = {}
		for r in in_window:
			by_slot.setdefault(r["meal_type"], []).append(r)
		for meal_type, slot_rows in by_slot.items():
			share = _meal_share(meal_type)
			values, valid = _period_values(slot_rows)
			for guideline, code, rec in _guideline_records(values, sex, age, share):
				n = NUTRIENTS[code]
				out.append({
					"as_of_date": as_of, "user_id": slot_rows[0]["user_id"], "meal_type": meal_type,
					"window_days": window, "guideline_code": guideline, "nutrient_code": code,
					"window_start": start, "energy_share": share,
					"avg_value": _r(values[code]), "unit": n.unit, "value_kind": n.kind,
					"valid_days": valid[code], "slot_days": len(slot_rows), "record_days": record_days,
					"record_coverage_pct": coverage, "sufficiency": sufficiency,
					"window_exceeds_history": start < history_start,
					**_judgement_columns(rec),
				})
	return out
