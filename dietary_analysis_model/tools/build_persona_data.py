"""Persona data generator (docs/persona_data_spec_20261027.md).

Writes LOCAL CSV files only. This tool never opens a database connection: it does not import
psycopg2, read .env files, or know any host. Output goes to 01_Results/persona/ (git-ignored)
unless --out says otherwise. Loading the files anywhere is a separate, manual step and the
shared databases (loop-dev, release) are off limits for persona data.

Usage:
	python tools/build_persona_data.py                       # full set, default seed
	python tools/build_persona_data.py --codes P01,E01 --max-per-type 2 --out /tmp/x
	python tools/build_persona_data.py --scale 0.5           # multiply every type's n

Inputs (all tracked in git):
	data/persona_params_v1.toml      parameters and calibration targets
	data/persona_types_v1.csv        persona types (axes, profile ranges, n, overrides JSON)
	data/persona_food_pool_v1.csv    per-serving foods from the MFDS reference
	data/knhanes_reference_model.json  expected daily energy (KNHANES_2022_2024_v1 regression)

Outputs (CSV, UTF-8, header row, empty field = NULL):
	user_master, meal, meal_food, baseline_lifelog_daily, persona_manifest, persona_truth_daily,
	load_local.sql (DDL + \\copy for a LOCAL PostgreSQL only), run_info.json
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import random
import tomllib
import uuid
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KST = dt.timezone(dt.timedelta(hours=9))
NS = uuid.uuid5(uuid.NAMESPACE_URL, "sibc-dietary-analysis/persona")
MAIN = ("BREAKFAST", "LUNCH", "DINNER")
NUTRIENTS = (
	"energy_kcal", "carbohydrate_g", "protein_g", "fat_g", "sugar_g", "dietary_fiber_g",
	"saturated_fat_g", "trans_fat_g", "cholesterol_mg", "sodium_mg", "potassium_mg", "calcium_mg",
	"phosphorus_mg", "iron_mg", "vitamin_a_ug", "vitamin_c_mg", "vitamin_d_ug", "vitamin_e_mg",
	"thiamin_mg", "riboflavin_mg", "niacin_mg",
)
# Production BMI medians by sex × age band (2026-10-27, release user_master aggregate). Used only
# to centre the BMI draw when a type's range is wide (non-recorder types).
BMI_MEDIAN = {
	("F", "19-29"): 22.7, ("M", "19-29"): 23.8, ("F", "30-49"): 22.5, ("M", "30-49"): 25.2,
	("F", "50-64"): 23.4, ("M", "50-64"): 25.8, ("F", "65-74"): 24.3, ("M", "65-74"): 24.5,
	("F", "75+"): 23.6, ("M", "75+"): 25.3,
}

USER_MASTER_COLS = ("user_id", "user_nm", "age", "sex", "weight", "height", "joined_dt", "created_at", "updated_at")
MEAL_COLS = ("meal_id", "user_id", "ymd", "eaten_at", "meal_type", "input_type", "status", *NUTRIENTS,
	"edits_meal_id", "created_at", "updated_at", "provided_at", "provided_timezone")
MEAL_FOOD_COLS = ("meal_food_id", "meal_id", "user_id", "eaten_at", "seq", "food_name", "food_name_norm",
	"analysis_status", "serving_qty", "source", "estimated_amount_g", *NUTRIENTS, "created_at", "updated_at")
BASELINE_COLS = ("user_id", "metric_code", "measure_date", "value", "value_min", "value_max", "value_stddev",
	"value_p25", "value_p75", "n_records", "n_excluded", "ref_median", "ref_p25", "ref_p75", "outlier_flag",
	"deviation_score", "run_id", "computed_at")
MANIFEST_COLS = ("user_id", "persona_code", "persona_name", "instance_no", "axis_a_recording", "axis_b_value",
	"axis_c_observation", "axis_w_wearable", "axis_s_scale", "guideline_code", "arrival_profile", "deterministic",
	"sex", "age", "height_cm", "weight_kg_start", "bmi_start", "pal", "bmr_kcal", "expected_kcal",
	"true_intake_factor", "trend_pct_per_week", "weekend_factor", "snack_share", "late_night_rate",
	"underreport_factor", "snack_drop_rate", "wear_rate", "partial_rate", "device_bias",
	"scale_measure_prob", "start_date", "end_date", "gap_start", "gap_end", "overrides", "seed")
TRUTH_COLS = ("user_id", "date", "week_index", "week_rel", "true_intake_kcal", "true_carb_g", "true_protein_g",
	"true_fat_g", "true_sodium_mg", "true_expenditure_kcal", "true_weight_kg", "skipped_meals", "n_snacks",
	"late_night", "exercise_end_at", "recorded_day", "recorded_kcal", "recorded_main_meals", "wear", "partial",
	"burn_available_from", "scale_measured", "weight_available_from")


# ----------------------------------------------------------------------------- helpers

def fmt(v, nd=3):
	if v is None:
		return ""
	if isinstance(v, bool):
		return "true" if v else "false"
	if isinstance(v, float):
		if math.isnan(v):
			return ""
		s = f"{v:.{nd}f}" if nd is not None else repr(v)
		return s.rstrip("0").rstrip(".") if "." in s else s
	if isinstance(v, (dt.datetime, dt.date)):
		return v.isoformat()
	return str(v)


def det_uuid(*parts) -> str:
	return str(uuid.uuid5(NS, ":".join(str(p) for p in parts)))


def lognormal_params(median: float, p90: float) -> tuple[float, float]:
	sigma = math.log(p90 / median) / 1.2815516
	return math.log(median), sigma


def mifflin(sex: str, weight: float, height: float, age: int) -> float:
	base = 10 * weight + 6.25 * height - 5 * age
	return base + 5 if sex == "M" else base - 161


def parse_mix(spec: str) -> list[tuple[str, float]]:
	"""'W0' -> [('W0',1)] ; 'W0:0.5|W1:0.5' -> weighted list."""
	out = []
	for part in spec.split("|"):
		if ":" in part:
			k, w = part.split(":")
			out.append((k.strip(), float(w)))
		else:
			out.append((part.strip(), 1.0))
	return out


# ----------------------------------------------------------------------------- inputs

@dataclass
class Food:
	code: str
	name: str
	norm: str
	slot: str
	serving_qty: float
	serving_unit: str
	nut: dict[str, float | None]

	@property
	def kcal(self) -> float:
		return self.nut["energy_kcal"] or 0.0

	def density(self, col: str, per: float = 1.0) -> float:
		v = self.nut.get(col)
		return (v or 0.0) * per / self.kcal if self.kcal else 0.0


class Pool:
	def __init__(self, path: Path):
		self.by_slot: dict[str, list[Food]] = {}
		with path.open(encoding="utf-8", newline="") as f:
			for r in csv.DictReader(f):
				nut = {c: (float(r[c]) if r.get(c, "") not in ("", None) else None) for c in NUTRIENTS}
				food = Food(r["food_code"], r["food_name"], r["food_name_norm"], r["slot"], float(r["serving_qty"]),
					r["serving_unit"], nut)
				self.by_slot.setdefault(food.slot, []).append(food)
		for slot in ("STAPLE", "NOODLE", "SOUP", "SIDE", "KIMCHI", "BREAD", "DRINK", "DAIRY"):
			if not self.by_slot.get(slot):
				raise SystemExit(f"food pool has no rows for slot {slot}: {path}")

	def pick(self, rng: random.Random, slot: str, bias: str | None) -> Food:
		foods = self.by_slot[slot]
		if not bias:
			return rng.choice(foods)
		weights = []
		for f in foods:
			w = 1.0
			if bias == "sodium" and f.density("sodium_mg") > 3.0:
				w *= 4.0
			elif bias == "satfat" and f.density("saturated_fat_g", 9) > 0.10:
				w *= 4.0
			elif bias == "sugar" and f.density("sugar_g", 4) > 0.30:
				w *= 4.0
			elif bias == "lowprotein":
				w /= 1.0 + 6.0 * f.density("protein_g", 4)
			weights.append(w)
		return rng.choices(foods, weights=weights, k=1)[0]


class Energy:
	"""Expected daily energy from the KNHANES regression (KNHANES_2022_2024_v1)."""

	def __init__(self, path: Path):
		m = json.loads(path.read_text(encoding="utf-8"))["models"]["ENERGY_KCAL"]
		self.c = m["coefficients"]

	def expected(self, sex: str, age: int, height: float, weight: float, weekend: float) -> float:
		c = self.c
		x = (c["intercept"] + c["female"] * (1 if sex == "F" else 0) + c["age"] * age + c["age2_per100"] * age * age / 100
			+ c["height_cm"] * height + c["weight_kg"] * weight + c["weekend"] * weekend)
		return math.exp(x)


@dataclass
class PersonaType:
	code: str
	name: str
	sex: str
	age_band: str
	bmi_lo: float
	bmi_hi: float
	axis_a: str
	axis_b: str
	axis_c: str
	axis_w: str
	axis_s: str
	guideline: str
	arrival: str
	n: int
	overrides: dict = field(default_factory=dict)


def load_types(path: Path) -> list[PersonaType]:
	out = []
	with path.open(encoding="utf-8", newline="") as f:
		for r in csv.DictReader(f):
			ov = json.loads(r["overrides"]) if r["overrides"].strip() else {}
			out.append(PersonaType(r["code"], r["name"], r["sex"], r["age_band"], float(r["bmi_lo"]), float(r["bmi_hi"]),
				r["axis_a"], r["axis_b"], r["axis_c"], r["axis_w"], r["axis_s"], r["guideline"], r["arrival"],
				int(r["n"]), ov))
	return out


# ----------------------------------------------------------------------------- simulation

@dataclass
class Profile:
	user_id: str
	code: str
	name: str
	instance: int
	sex: str
	age: int
	height: float
	weight0: float
	pal: float
	bmr: float
	expected_wd: float
	expected_we: float
	axis_a: str
	axis_b: str
	axis_c: str
	axis_w: str
	axis_s: str
	guideline: str
	arrival: str
	det: bool
	intake_factor: float
	report_factor: float
	snack_drop: float
	wear_owner: bool
	wear_rate: float
	partial_rate: float
	device_bias: float
	scale_owner: bool
	scale_prob: float
	ov: dict
	gap: tuple[int, int] | None = None       # week indexes [start, end)
	dropout_week: int | None = None
	start_week: int = 0
	null_body: bool = False
	exercise_weekdays: tuple[int, ...] = ()
	late_night_rate: float = 0.0
	weekend_factor: float = 1.0
	trend_pct: float = 0.0
	snack_share: float = 0.0


class Generator:
	def __init__(self, params: dict, pool: Pool, energy: Energy, seed: int, out: Path, run_id: str):
		self.p = params
		self.pool = pool
		self.energy = energy
		self.seed = seed
		self.out = out
		self.run_id = run_id
		self.start: dt.date = params["period"]["start"]
		self.end: dt.date = params["period"]["end"]
		self.today: dt.date = params["period"]["today"]
		self.n_weeks = ((self.end - self.start).days + 1) // 7
		self.computed_at = dt.datetime.combine(self.today, dt.time(3, 0), tzinfo=KST)
		self.user_seq = 0
		self.files = {}
		self.writers = {}
		self.counts = {}

	# ---- output plumbing
	def open(self):
		self.out.mkdir(parents=True, exist_ok=True)
		for name, cols in (("user_master", USER_MASTER_COLS), ("meal", MEAL_COLS), ("meal_food", MEAL_FOOD_COLS),
				("baseline_lifelog_daily", BASELINE_COLS), ("persona_manifest", MANIFEST_COLS),
				("persona_truth_daily", TRUTH_COLS)):
			f = (self.out / f"{name}.csv").open("w", encoding="utf-8", newline="")
			w = csv.writer(f)
			w.writerow(cols)
			self.files[name] = f
			self.writers[name] = (w, cols)
			self.counts[name] = 0

	def close(self):
		for f in self.files.values():
			f.close()

	def emit(self, table: str, row: dict):
		w, cols = self.writers[table]
		w.writerow([fmt(row.get(c)) for c in cols])
		self.counts[table] += 1

	# ---- week helpers
	def week_index(self, d: dt.date) -> int:
		return (d - self.start).days // 7

	def week_rel(self, d: dt.date) -> int:
		return self.week_index(d) - self.n_weeks

	# ---- profile
	def make_profile(self, t: PersonaType, i: int, rng: random.Random) -> Profile:
		p = self.p
		ov = t.overrides
		det = bool(ov.get("deterministic", False))
		lo, hi = p["profile"]["age_band_range"][t.age_band]
		age = rng.randint(lo, hi)
		elderly = age >= 65
		hmean = p["profile"]["height_mean"][t.sex] + (p["profile"]["height_elderly_offset"] if elderly else 0.0)
		height = max(145.0, min(190.0, rng.gauss(hmean, p["profile"]["height_sd"])))
		if t.bmi_hi - t.bmi_lo > 3.0:
			med = BMI_MEDIAN[(t.sex, t.age_band)]
			bmi = min(t.bmi_hi, max(t.bmi_lo, rng.gauss(med, 3.0)))
		else:
			bmi = rng.uniform(t.bmi_lo, t.bmi_hi)
		weight = bmi * (height / 100) ** 2
		prof_ov = ov.get("profile", {})
		if "height_cm" in prof_ov:
			height = float(prof_ov["height_cm"])
		if "weight_kg" in prof_ov:
			weight = float(prof_ov["weight_kg"])
		b = p["axis_b"][t.axis_b]
		active = bool(b.get("active", False))
		pal_base = p["expenditure"]["pal_active"] if active else (
			p["expenditure"]["pal_elderly"] if elderly else p["expenditure"]["pal_adult"])
		pal = pal_base if det else rng.gauss(pal_base, p["expenditure"]["pal_sd"])
		bmr = mifflin(t.sex, weight, height, age)
		f_lo, f_hi = b["factor"]
		intake_factor = float(ov.get("intake_factor", rng.uniform(f_lo, f_hi)))
		c = p["axis_c"][t.axis_c]
		r_lo, r_hi = c["report_factor"]
		report_factor = 1.0 if det else rng.uniform(r_lo, r_hi)
		snack_drop = 0.0 if det else c["snack_drop"]
		axis_w = rng.choices([k for k, _ in parse_mix(t.axis_w)], weights=[w for _, w in parse_mix(t.axis_w)], k=1)[0]
		axis_s = rng.choices([k for k, _ in parse_mix(t.axis_s)], weights=[w for _, w in parse_mix(t.axis_s)], k=1)[0]
		w = p["axis_w"][axis_w]
		s = p["axis_s"][axis_s]
		wear_rate = float(ov.get("wear_rate", w.get("wear_rate", 0.0)))
		partial_rate = float(ov.get("partial_rate", w.get("partial_rate", 0.0)))
		bias_range = 0.0 if det else p["expenditure"]["device_bias_range"]
		device_bias = 1.0 + rng.uniform(-bias_range, bias_range)
		arrival = t.arrival or ("ios" if rng.random() < p["wearable"]["ios_share"] else "android")
		self.user_seq += 1
		user_id = p["meta"]["user_id_prefix"] + f"{self.user_seq:012d}"
		prof = Profile(user_id, t.code, t.name, i, t.sex, age, height, weight, pal, bmr,
			self.energy.expected(t.sex, age, height, weight, 0.0), self.energy.expected(t.sex, age, height, weight, 1.0),
			t.axis_a, t.axis_b, t.axis_c, axis_w, axis_s, t.guideline, arrival, det, intake_factor, report_factor,
			snack_drop, bool(w["owner"]), wear_rate, partial_rate, device_bias, bool(s["owner"]) or "weight_plan" in ov,
			float(s.get("measure_prob", 0.0)), ov)
		a = p["axis_a"][t.axis_a]
		if "gap_start_week_min" in a:
			gs = rng.randint(a["gap_start_week_min"], a["gap_start_week_max"])
			prof.gap = (gs, gs + rng.randint(a["gap_weeks_min"], a["gap_weeks_max"]))
		if "dropout_week_min" in a:
			prof.dropout_week = rng.randint(a["dropout_week_min"], a["dropout_week_max"])
		if "start_week_min" in a:
			prof.start_week = rng.randint(a["start_week_min"], a["start_week_max"])
		prof.null_body = bool(prof_ov.get("null_body", False))
		ex_days = p["expenditure"]["exercise_days_per_week_active"] if active else p["expenditure"]["exercise_days_per_week_default"]
		if det and not active:
			prof.exercise_weekdays = ()
		else:
			prof.exercise_weekdays = tuple(sorted(rng.sample(range(7), ex_days)))
		prof.late_night_rate = float(b.get("late_night_rate", p["intake"]["late_night_rate"]))
		prof.weekend_factor = float(b.get("weekend_factor", 1.0))
		prof.trend_pct = float(b.get("trend_pct_per_week", 0.0))
		prof.snack_share = 0.0 if det else p["intake"]["snack_share"]
		return prof

	# ---- schedules
	def records_day(self, prof: Profile, d: dt.date, rng: random.Random) -> bool:
		ov = prof.ov
		wk = self.week_index(d)
		if "record_weekdays_cycle" in ov:
			cyc = ov["record_weekdays_cycle"]
			return d.weekday() in cyc[wk % len(cyc)]
		if prof.axis_a == "A0":
			return False
		if prof.det:
			return True
		a = self.p["axis_a"][prof.axis_a]
		if prof.gap and prof.gap[0] <= wk < prof.gap[1]:
			return False
		if prof.dropout_week is not None and wk >= prof.dropout_week:
			return False
		if wk < prof.start_week:
			return False
		rates = ov.get("day_rate", a["day_rate"])
		rate = rates[1 if d.weekday() >= 5 else 0]
		return rng.random() < rate

	def wears(self, prof: Profile, d: dt.date, rng: random.Random) -> tuple[bool, bool]:
		"""(wear, partial)"""
		if not prof.wear_owner:
			return False, False
		ov = prof.ov
		wk_rel = self.week_rel(d)
		if "wear_from_week" in ov and wk_rel < int(ov["wear_from_week"]):
			return False, False
		if "wear_weekdays_cycle" in ov:
			cyc = ov["wear_weekdays_cycle"]
			return (d.weekday() in cyc[self.week_index(d) % len(cyc)]), False
		if prof.det or ov.get("wear_all"):
			return True, False
		if rng.random() >= prof.wear_rate:
			return False, False
		return True, rng.random() < prof.partial_rate

	def arrival_delay(self, prof: Profile, d: dt.date, rng: random.Random) -> int:
		ov = prof.ov
		sched = ov.get("arrival_schedule_last_week")
		if sched and self.week_rel(d) == -1:
			target = dt.date.fromisoformat(sched[str(d.weekday())])
			return (target - d).days
		if prof.det:
			return 0
		a = self.p["wearable"]["arrival"][prof.arrival]
		mu, sigma = lognormal_params(a["median_days"], a["p90_days"])
		return min(int(a["max_days"]), int(round(rng.lognormvariate(mu, sigma))))

	# ---- intake truth
	def intake_factor(self, prof: Profile, d: dt.date) -> float:
		ov = prof.ov
		wk_rel = self.week_rel(d)
		f = prof.intake_factor
		b = self.p["axis_b"][prof.axis_b]
		if prof.trend_pct:
			t0 = int(b["trend_start_week_from_end"])
			n = int(b["trend_weeks"])
			k = min(max(wk_rel - t0, 0), n)
			f *= (1 + prof.trend_pct / 100) ** k
		if d.weekday() >= 5:
			f *= prof.weekend_factor
		wf = ov.get("intake_week_factors", {})
		if str(wk_rel) in wf:
			f *= float(wf[str(wk_rel)])
		df = ov.get("intake_date_factors", {})
		if d.isoformat() in df:
			f *= float(df[d.isoformat()])
		if d > self.end and "extension_factor" in ov:
			f *= float(ov["extension_factor"])
		return f

	def macro_shares(self, prof: Profile, d: dt.date) -> tuple[float, float, float, float]:
		"""(carb, protein, fat, sodium mg/kcal)"""
		p = self.p["intake"]
		carb, prot, fat = p["macro_share"]["carb"], p["macro_share"]["protein"], p["macro_share"]["fat"]
		na = p["sodium_mg_per_kcal"]
		bias = self.bias(prof, d)
		if bias == "lowprotein":
			carb, prot, fat = 0.66, 0.11, 0.21
		elif bias == "satfat":
			carb, prot, fat = 0.52, 0.15, 0.31
		elif bias == "sodium":
			na = 4.0
		elif bias == "sugar":
			carb, prot, fat = 0.64, 0.13, 0.21
		return carb, prot, fat, na

	def bias(self, prof: Profile, d: dt.date) -> str | None:
		ov = prof.ov
		if "sodium_excess_weeks" in ov:
			return "sodium" if self.week_rel(d) in ov["sodium_excess_weeks"] else None
		return self.p["axis_b"][prof.axis_b].get("nutrient_bias")

	# ---- food composition
	def compose(self, rng: random.Random, meal_type: str, target: float, bias: str | None, det: bool) -> list[tuple[Food, float]]:
		pool = self.pool
		items: list[Food] = []
		main_slot = None
		if meal_type == "BREAKFAST":
			if rng.random() < 0.6:
				main_slot = "STAPLE"
				items.append(pool.pick(rng, "STAPLE", None))
				if rng.random() < (1.0 if bias == "sodium" else 0.6):
					items.append(pool.pick(rng, "SOUP", bias))
				for _ in range(rng.randint(0, 2)):
					items.append(pool.pick(rng, "SIDE", bias))
				if rng.random() < (0.9 if bias == "sodium" else 0.5):
					items.append(pool.pick(rng, "KIMCHI", None))
			else:
				main_slot = "BREAD"
				items.append(pool.pick(rng, "BREAD", bias if bias == "sugar" else None))
				if rng.random() < 0.7:
					items.append(pool.pick(rng, rng.choice(("DAIRY", "DRINK")), bias if bias == "sugar" else None))
		elif meal_type in ("LUNCH", "DINNER"):
			if rng.random() < 0.7:
				main_slot = "STAPLE"
				items.append(pool.pick(rng, "STAPLE", None))
				if rng.random() < (1.0 if bias == "sodium" else 0.7):
					items.append(pool.pick(rng, "SOUP", bias))
				for _ in range(rng.randint(1, 3)):
					items.append(pool.pick(rng, "SIDE", bias))
				if rng.random() < (0.9 if bias == "sodium" else 0.6):
					items.append(pool.pick(rng, "KIMCHI", None))
			else:
				main_slot = "NOODLE"
				items.append(pool.pick(rng, "NOODLE", bias))
				if rng.random() < 0.4:
					items.append(pool.pick(rng, "SIDE", bias))
				if rng.random() < 0.5:
					items.append(pool.pick(rng, "KIMCHI", None))
		else:  # snacks
			slot = rng.choices(("BREAD", "DRINK", "DAIRY"), weights=(0.45, 0.35, 0.20), k=1)[0]
			main_slot = slot
			items.append(pool.pick(rng, slot, bias if bias == "sugar" else None))
		qty = [1.0] * len(items)
		tol = self.p["food"]["kcal_tolerance"]
		main_i = next(i for i, f in enumerate(items) if f.slot == main_slot)
		others = sum(f.kcal * q for i, (f, q) in enumerate(zip(items, qty)) if i != main_i)
		if items[main_i].kcal > 0:
			q = (target - others) / items[main_i].kcal
			qty[main_i] = min(3.0, max(0.25, round(q * 4) / 4))
		total = sum(f.kcal * q for f, q in zip(items, qty))
		if total > 0 and abs(total - target) / target > tol:
			s = target / total
			qty = [max(0.25, round(q * s * 4) / 4) for q in qty]
		return list(zip(items, qty))

	# ---- per-user simulation
	def simulate(self, t: PersonaType, i: int):
		rng = random.Random(f"{self.seed}:{t.code}:{i}")
		prof = self.make_profile(t, i, rng)
		p = self.p
		ov = prof.ov
		end = dt.date.fromisoformat(ov["extend_to"]) if "extend_to" in ov else self.end
		det = prof.det
		intake = p["intake"]
		sigma_day = 0.0 if det else math.sqrt(math.log(1 + intake["day_cv"] ** 2))
		burn_sigma = 0.0 if det else math.sqrt(math.log(1 + p["expenditure"]["day_cv"] ** 2))
		weight = prof.weight0
		joined = self.start + dt.timedelta(days=7 * prof.start_week)
		# weight plan (E11): constant truth with an offset in the last 30 days, fixed measure days
		wplan = ov.get("weight_plan")
		plan_days: set[dt.date] = set()
		if wplan:
			last30 = [self.end - dt.timedelta(days=k) for k in range(29, -1, -1)]
			prior = [self.end - dt.timedelta(days=k) for k in range(179, 29, -1)]
			def spread(days, n):
				if n <= 0:
					return []
				step = len(days) / n
				return [days[int(k * step + step / 2)] for k in range(n)]
			plan_days = set(spread(prior, int(wplan["measure_days_prior"])) + spread(last30, int(wplan["measure_days_last30"])))
		recorded_kcal_days = 0
		d = self.start
		while d <= end:
			wk_rel = self.week_rel(d)
			weekend = d.weekday() >= 5
			# ---------- truth: expenditure
			exercise = d.weekday() in prof.exercise_weekdays and not (det and not p["axis_b"][prof.axis_b].get("active"))
			expenditure = prof.bmr * prof.pal * math.exp(rng.gauss(0, burn_sigma) if burn_sigma else 0.0)
			if exercise:
				expenditure += p["expenditure"]["exercise_kcal_mean"]
			# ---------- truth: intake
			base = prof.bmr * prof.pal  # 에너지 균형 기준. KNHANES 기대값은 manifest에 대조용으로만 둠
			factor = self.intake_factor(prof, d)
			total = base * factor * (math.exp(rng.gauss(0, sigma_day)) if sigma_day else 1.0)
			ive = ov.get("intake_vs_expenditure_kcal", {})
			if str(wk_rel) in ive:
				total = expenditure + float(ive[str(wk_rel)])
			carb_s, prot_s, fat_s, na_density = self.macro_shares(prof, d)
			# skips
			skipped: list[str] = []
			skip_ov = ov.get("skip_meals", {})
			for m in MAIN:
				pr = float(skip_ov.get(m, 0.0)) if (det or skip_ov) else intake["true_skip_prob"][m]
				if not det and m == "BREAKFAST" and prof.age >= 65 and m not in skip_ov:
					pr = intake["elderly_breakfast_skip_prob"]
				if rng.random() < pr:
					skipped.append(m)
			if len(skipped) == 3:
				skipped.remove("LUNCH")
			# snacks
			n_snacks = 0
			if ov.get("late_night_fixed"):
				n_snacks = 2
			elif not det and rng.random() < intake["snack_prob"]:
				n_snacks = 1 if rng.random() < 0.8 else 2
			snack_total = total * prof.snack_share if n_snacks else 0.0
			if ov.get("late_night_fixed"):
				snack_total = 2 * 150.0
			mains_total = total - snack_total
			skipped_share = sum(intake["main_share"][m] for m in skipped)
			mains_eff = mains_total * (1 - (1 - intake["skip_transfer"]) * skipped_share)
			live = [m for m in MAIN if m not in skipped]
			share_sum = sum(intake["main_share"][m] for m in live)
			meal_kcal = {m: mains_eff * intake["main_share"][m] / share_sum for m in live}
			late = False
			late_types: list[tuple[str, bool]] = []  # (meal_type, after_midnight)
			if ov.get("late_night_fixed"):
				late_types = [("LATE_NIGHT_SNACK", False), ("LATE_NIGHT_SNACK", True)]
				late = True
			else:
				p_late_day = min(0.95, prof.late_night_rate * 2.6)
				for k in range(n_snacks):
					if not det and rng.random() < p_late_day / max(n_snacks, 1):
						late_types.append(("LATE_NIGHT_SNACK", rng.random() < intake["late_night_after_midnight"]))
						late = True
					else:
						late_types.append((rng.choice(("MORNING_SNACK", "AFTERNOON_SNACK")), False))
			true_total = sum(meal_kcal.values()) + snack_total
			# ---------- truth: weight
			if wplan:
				weight = prof.weight0 + (float(wplan["offset_last30_kg"]) if d > self.end - dt.timedelta(days=30) else 0.0)
			else:
				delta = (true_total - expenditure) / p["weight"]["kcal_per_kg"] * p["weight"]["damping"]
				weight += max(-p["weight"]["max_daily_change_kg"], min(p["weight"]["max_daily_change_kg"], delta))
			# ---------- observation: diet
			rec_day = self.records_day(prof, d, rng)
			recorded_kcal = 0.0
			recorded_mains = 0
			if rec_day:
				a = p["axis_a"][prof.axis_a]
				rec_meals = ov.get("record_meals")
				full_day = det or rng.random() < a.get("full_day_prob", intake["full_day_prob"])
				for idx, m in enumerate(MAIN):
					hour_mu, hour_sd = intake["meal_hour"][m]
					hour = hour_mu if det else min(23.5, max(5.0, rng.gauss(hour_mu, hour_sd)))
					if not det and rng.random() < intake["late_log_rate"]:
						hour = rng.uniform(max(hour_mu + 2.0, hour), 23.9)  # 늦은 시각 기록(관측)
					eaten = dt.datetime.combine(d, dt.time(0), tzinfo=KST) + dt.timedelta(hours=hour)
					if m in skipped:
						if a.get("skipped_rows") and (det or rng.random() < 0.8):
							self.emit_meal(prof, d, m, eaten, None, "SKIPPED", rng, None, None)
						continue
					if rec_meals is not None and m not in rec_meals:
						continue
					if not det and not full_day and rng.random() >= a["meal_prob"][idx]:
						continue
					kcal_rec = meal_kcal[m] * prof.report_factor
					recorded_kcal += kcal_rec
					recorded_mains += 1
					meal_id = self.emit_meal(prof, d, m, eaten, kcal_rec, "COMPLETED", rng, self.bias(prof, d), None)
					if prof.axis_a == "A9" and not det:
						self.emit_extras(prof, d, m, eaten, kcal_rec, meal_id, rng, a)
				for k, (stype, after_mid) in enumerate(late_types):
					if not det and rng.random() >= a["meal_prob"][3] * (1 - prof.snack_drop):
						continue
					if stype == "LATE_NIGHT_SNACK":
						if after_mid:
							eaten = dt.datetime.combine(d + dt.timedelta(days=1), dt.time(0), tzinfo=KST) + dt.timedelta(
								hours=0.67 if det else rng.uniform(0.1, 3.5))
						else:
							hm, hs = intake["meal_hour"]["LATE_NIGHT_SNACK"]
							eaten = dt.datetime.combine(d, dt.time(0), tzinfo=KST) + dt.timedelta(
								hours=23.5 if det else min(23.9, max(21.0, rng.gauss(hm, hs))))
					else:
						hm, hs = intake["meal_hour"][stype]
						eaten = dt.datetime.combine(d, dt.time(0), tzinfo=KST) + dt.timedelta(hours=rng.gauss(hm, hs))
					kcal_s = (snack_total / max(n_snacks, 1)) * prof.report_factor
					if not det:
						kcal_s = max(30.0, min(400.0, rng.uniform(intake["snack_kcal_min"], intake["snack_kcal_max"]) * prof.report_factor))
					recorded_kcal += kcal_s
					self.emit_meal(prof, d, stype, eaten, kcal_s, "COMPLETED", rng, self.bias(prof, d), None)
				recorded_kcal_days += 1
			# ---------- observation: wearable
			wear, partial = self.wears(prof, d, rng)
			burn_avail = None
			if wear and d <= self.end:
				delay = self.arrival_delay(prof, d, rng)
				burn_avail = d + dt.timedelta(days=delay)
				self.emit_wearable(prof, d, expenditure, partial, exercise, rng)
			# ---------- observation: scale
			scale_measured = False
			weight_avail = None
			if prof.scale_owner and d <= self.end:
				if wplan:
					scale_measured = d in plan_days
				else:
					scale_measured = rng.random() < prof.scale_prob
				if scale_measured:
					noise = 0.0 if det else rng.gauss(0, p["weight"]["measure_noise_sd"])
					wobs = round(weight + noise, 1)
					weight_avail = d + dt.timedelta(days=0 if det else rng.randint(0, p["wearable"]["weight_arrival_max_days"]))
					self.emit_metric(prof.user_id, "weight_kg", d, wobs, 1)
					self.emit_metric(prof.user_id, "bmi", d, round(wobs / (prof.height / 100) ** 2, 1), 1)
			# ---------- truth row
			self.emit("persona_truth_daily", {
				"user_id": prof.user_id, "date": d, "week_index": self.week_index(d), "week_rel": wk_rel,
				"true_intake_kcal": round(true_total, 1), "true_carb_g": round(true_total * carb_s / 4, 1),
				"true_protein_g": round(true_total * prot_s / 4, 1), "true_fat_g": round(true_total * fat_s / 9, 1),
				"true_sodium_mg": round(true_total * na_density), "true_expenditure_kcal": round(expenditure, 1),
				"true_weight_kg": round(weight, 2), "skipped_meals": "|".join(skipped), "n_snacks": n_snacks,
				"late_night": late,
				"exercise_end_at": (dt.datetime.combine(d, dt.time(0), tzinfo=KST) + dt.timedelta(hours=p["expenditure"]["exercise_end_hour"])) if exercise else None,
				"recorded_day": rec_day, "recorded_kcal": round(recorded_kcal, 1), "recorded_main_meals": recorded_mains,
				"wear": wear, "partial": partial, "burn_available_from": burn_avail, "scale_measured": scale_measured,
				"weight_available_from": weight_avail,
			})
			d += dt.timedelta(days=1)
		# ---------- user_master + manifest
		now = self.computed_at
		self.emit("user_master", {
			"user_id": prof.user_id, "user_nm": f"{prof.code}-{prof.instance:02d}", "age": prof.age, "sex": prof.sex,
			"weight": None if prof.null_body else int(round(prof.weight0)),
			"height": None if prof.null_body else int(round(prof.height)),
			"joined_dt": joined, "created_at": now, "updated_at": now,
		})
		b = p["axis_b"][prof.axis_b]
		self.emit("persona_manifest", {
			"user_id": prof.user_id, "persona_code": prof.code, "persona_name": prof.name, "instance_no": prof.instance,
			"axis_a_recording": prof.axis_a, "axis_b_value": prof.axis_b, "axis_c_observation": prof.axis_c,
			"axis_w_wearable": prof.axis_w, "axis_s_scale": prof.axis_s, "guideline_code": prof.guideline or None,
			"arrival_profile": prof.arrival if prof.wear_owner else None, "deterministic": det,
			"sex": prof.sex, "age": prof.age, "height_cm": round(prof.height, 1), "weight_kg_start": round(prof.weight0, 1),
			"bmi_start": round(prof.weight0 / (prof.height / 100) ** 2, 2), "pal": round(prof.pal, 3), "bmr_kcal": round(prof.bmr),
			"expected_kcal": round(prof.expected_wd), "true_intake_factor": round(prof.intake_factor, 3),
			"trend_pct_per_week": prof.trend_pct, "weekend_factor": prof.weekend_factor, "snack_share": prof.snack_share,
			"late_night_rate": prof.late_night_rate, "underreport_factor": round(prof.report_factor, 3),
			"snack_drop_rate": prof.snack_drop, "wear_rate": prof.wear_rate if prof.wear_owner else None,
			"partial_rate": prof.partial_rate if prof.wear_owner else None,
			"device_bias": round(prof.device_bias, 3) if prof.wear_owner else None,
			"scale_measure_prob": prof.scale_prob if prof.scale_owner else None,
			"start_date": joined, "end_date": end,
			"gap_start": (self.start + dt.timedelta(days=7 * prof.gap[0])) if prof.gap else None,
			"gap_end": (self.start + dt.timedelta(days=7 * prof.gap[1])) if prof.gap else None,
			"overrides": json.dumps(ov, ensure_ascii=False) if ov else None, "seed": self.seed,
		})

	# ---- emitters
	def emit_meal(self, prof: Profile, d: dt.date, meal_type: str, eaten: dt.datetime, kcal: float | None,
			status: str, rng: random.Random, bias: str | None, edits: str | None, suffix: str = "") -> str:
		p = self.p
		ymd = eaten.astimezone(KST).strftime("%Y%m%d")
		meal_id = det_uuid(prof.user_id, d, meal_type, eaten.isoformat(), suffix)
		if prof.det:
			created = eaten + dt.timedelta(minutes=5)
		else:
			r = rng.random()
			if r < p["intake"]["record_delay_within_30min"]:
				created = eaten + dt.timedelta(minutes=rng.uniform(1, 30))
			elif r < p["intake"]["record_delay_within_30min"] + p["intake"]["record_delay_same_day"]:
				created = eaten + dt.timedelta(hours=rng.uniform(0.5, 6))
			else:
				created = eaten + dt.timedelta(hours=rng.uniform(10, 30))
		shares = p["food"]["input_type_share"]
		input_type = rng.choices(list(shares), weights=list(shares.values()), k=1)[0]
		row = {"meal_id": meal_id, "user_id": prof.user_id, "ymd": ymd, "eaten_at": eaten, "meal_type": meal_type,
			"input_type": input_type, "status": status, "edits_meal_id": edits, "created_at": created,
			"updated_at": created, "provided_at": created, "provided_timezone": "Asia/Seoul"}
		if status == "COMPLETED" and kcal is not None:
			totals: dict[str, float | None] = {c: None for c in NUTRIENTS}
			for seq, (food, qty) in enumerate(self.compose(rng, meal_type, kcal, bias, prof.det), start=1):
				unknown = (not prof.det) and rng.random() < p["food"]["unknown_status_rate"]
				name, norm = food.name, food.norm
				if not prof.det and rng.random() < p["food"]["name_variant_rate"]:
					v = rng.choice(p["food"]["name_variants"])
					name = food.name + v
					norm = (food.name + v).replace(" ", "")
				if input_type == "PHOTO":
					source = "PHOTO"
				elif input_type == "MANUAL":
					source = "MANUAL" if rng.random() < 0.8 else "MY_FOOD"
				else:
					source = rng.choice(("PHOTO", "MANUAL"))
				frow = {"meal_food_id": det_uuid(meal_id, seq), "meal_id": meal_id, "user_id": prof.user_id,
					"eaten_at": eaten, "seq": seq, "food_name": name, "food_name_norm": norm,
					"analysis_status": "UNKNOWN" if unknown else "DONE", "serving_qty": qty, "source": source,
					"estimated_amount_g": (round(food.serving_qty * qty, 1) if food.serving_unit == "g" else None),
					"created_at": created, "updated_at": created}
				for c in NUTRIENTS:
					v = food.nut.get(c)
					if unknown or v is None:
						frow[c] = None
					else:
						frow[c] = round(v * qty, 3)
						totals[c] = (totals[c] or 0.0) + frow[c]
				self.emit("meal_food", frow)
			for c in NUTRIENTS:
				row[c] = None if totals[c] is None else round(totals[c], 3)
		self.emit("meal", row)
		return meal_id

	def emit_extras(self, prof, d, m, eaten, kcal_rec, meal_id, rng, a):
		"""A9: duplicate rows, edits, drafts."""
		if rng.random() < a["duplicate_rate"]:
			self.emit_meal(prof, d, m, eaten + dt.timedelta(minutes=30), 150.0, "COMPLETED", rng, None, None, suffix="dup")
		if rng.random() < a["edit_rate"]:
			# the row just written becomes the "original"; the edit supersedes it with a different value
			self.emit_meal(prof, d, m, eaten, kcal_rec * 0.8, "COMPLETED", rng, None, meal_id, suffix="edit")
		if rng.random() < a["draft_rate"]:
			self.emit_meal(prof, d, "SNACK", eaten + dt.timedelta(hours=2), None, "DRAFT", rng, None, None, suffix="draft")

	def emit_metric(self, user_id: str, code: str, d: dt.date, value: float, n: int, vmin=None, vmax=None, vsd=None):
		self.emit("baseline_lifelog_daily", {
			"user_id": user_id, "metric_code": code, "measure_date": d, "value": value, "value_min": vmin,
			"value_max": vmax, "value_stddev": vsd, "n_records": n, "run_id": self.run_id, "computed_at": self.computed_at,
		})

	def emit_wearable(self, prof: Profile, d: dt.date, expenditure: float, partial: bool, exercise: bool, rng: random.Random):
		w = self.p["wearable"]
		if partial:
			n_hr = rng.randint(w["partial_n_records_min"], w["partial_n_records_max"])
			burn_factor = rng.uniform(w["partial_burn_factor_min"], w["partial_burn_factor_max"])
		else:
			n_hr = rng.randint(w["full_n_records_min"], w["full_n_records_max"])
			burn_factor = 1.0
		resting = rng.uniform(w["resting_hr_min"], w["resting_hr_max"])
		hr = round(resting + (0 if prof.det else rng.gauss(2, 3)), 1)
		self.emit_metric(prof.user_id, "heartrate_bpm", d, hr, n_hr, round(hr - 12, 1), round(hr + 55, 1), 11.5)
		total = round(expenditure * w["device_scale"] * prof.device_bias * burn_factor)
		self.emit_metric(prof.user_id, "total_kcal_burned", d, total, 1)
		self.emit_metric(prof.user_id, "active_kcal_burned", d, max(0, round(total - prof.bmr * 1.1)), 1)
		steps_mu = math.log(w["steps_median"]) + (prof.pal - 1.5) * 2.0
		steps = int(math.exp(steps_mu + (0 if prof.det else rng.gauss(0, w["steps_log_sd"]))) * burn_factor)
		self.emit_metric(prof.user_id, "step_count", d, steps, 1)
		if exercise:
			kcal = self.p["expenditure"]["exercise_kcal_mean"]
			self.emit_metric(prof.user_id, "activity_kcal", d, kcal, 1)
			self.emit_metric(prof.user_id, "activity_duration_min", d, 45, 1)

	# ---- local SQL
	def write_sql(self):
		schema = "sibc_persona"
		ddl = f"""-- 로컬 PostgreSQL 전용 적재 스크립트 (persona generator {self.p['meta']['version']}, run {self.run_id}).
-- 공유 DB(loop-dev, release)에는 실행하지 않는다. psql -h localhost -f load_local.sql
create schema if not exists {schema};
drop table if exists {schema}.user_master, {schema}.meal, {schema}.meal_food, {schema}.baseline_lifelog_daily,
	{schema}.persona_manifest, {schema}.persona_truth_daily;
create table {schema}.user_master (user_id uuid primary key, user_nm varchar, age integer, sex varchar, weight integer,
	height integer, joined_dt date, created_at timestamptz, updated_at timestamptz);
create table {schema}.meal (meal_id uuid primary key, user_id uuid, ymd char(8), eaten_at timestamptz, meal_type varchar,
	input_type varchar, status varchar, {', '.join(c + ' numeric' for c in NUTRIENTS)}, edits_meal_id uuid,
	created_at timestamptz, updated_at timestamptz, provided_at timestamptz, provided_timezone varchar);
create table {schema}.meal_food (meal_food_id uuid primary key, meal_id uuid, user_id uuid, eaten_at timestamptz,
	seq smallint, food_name varchar, food_name_norm varchar, analysis_status varchar, serving_qty numeric, source varchar,
	estimated_amount_g numeric, {', '.join(c + ' numeric' for c in NUTRIENTS)}, created_at timestamptz, updated_at timestamptz);
create table {schema}.baseline_lifelog_daily (user_id uuid, metric_code text, measure_date date, value double precision,
	value_min double precision, value_max double precision, value_stddev double precision, value_p25 double precision,
	value_p75 double precision, n_records integer, n_excluded integer, ref_median double precision, ref_p25 double precision,
	ref_p75 double precision, outlier_flag text, deviation_score double precision, run_id text, computed_at timestamptz,
	primary key (user_id, metric_code, measure_date));
create table {schema}.persona_manifest ({', '.join(c + ' text' for c in MANIFEST_COLS)});
create table {schema}.persona_truth_daily ({', '.join(c + ' text' for c in TRUTH_COLS)});
"""
		copies = "\n".join(
			f"\\copy {schema}.{t} from '{(self.out / (t + '.csv')).resolve()}' with (format csv, header true)"
			for t in ("user_master", "meal", "meal_food", "baseline_lifelog_daily", "persona_manifest", "persona_truth_daily"))
		(self.out / "load_local.sql").write_text(ddl + copies + "\n", encoding="utf-8")


# ----------------------------------------------------------------------------- main

def run(params_path: Path, types_path: Path, pool_path: Path, model_path: Path, out: Path, seed: int,
		codes: set[str] | None, scale: float, max_per_type: int | None) -> dict:
	params = tomllib.loads(params_path.read_text(encoding="utf-8"))
	types = load_types(types_path)
	pool = Pool(pool_path)
	energy = Energy(model_path)
	run_id = f"persona_{params['meta']['version'].rsplit('-', 1)[-1]}_seed{seed}"
	g = Generator(params, pool, energy, seed, out, run_id)
	g.open()
	n_users = 0
	try:
		for t in types:
			if codes and t.code not in codes:
				continue
			n = max(1, int(round(t.n * scale)))
			if max_per_type:
				n = min(n, max_per_type)
			for i in range(1, n + 1):
				g.simulate(t, i)
				n_users += 1
	finally:
		g.close()
	g.write_sql()
	info = {"version": params["meta"]["version"], "run_id": run_id, "seed": seed, "users": n_users,
		"period": {"start": g.start.isoformat(), "end": g.end.isoformat(), "today": g.today.isoformat(), "weeks": g.n_weeks},
		"rows": g.counts, "note": "synthetic persona data; local files only; never load into shared databases"}
	(out / "run_info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
	return info


def main() -> None:
	ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	ap.add_argument("--out", type=Path, default=ROOT / "01_Results" / "persona")
	ap.add_argument("--seed", type=int, default=20261027)
	ap.add_argument("--params", type=Path, default=ROOT / "data" / "persona_params_v1.toml")
	ap.add_argument("--types", type=Path, default=ROOT / "data" / "persona_types_v1.csv")
	ap.add_argument("--pool", type=Path, default=ROOT / "data" / "persona_food_pool_v1.csv")
	ap.add_argument("--model", type=Path, default=ROOT / "data" / "knhanes_reference_model.json")
	ap.add_argument("--codes", help="comma-separated persona codes to generate (default: all)")
	ap.add_argument("--scale", type=float, default=1.0, help="multiply every type's n")
	ap.add_argument("--max-per-type", type=int, default=None)
	args = ap.parse_args()
	codes = {c.strip() for c in args.codes.split(",")} if args.codes else None
	info = run(args.params, args.types, args.pool, args.model, args.out, args.seed, codes, args.scale, args.max_per_type)
	print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
	main()
