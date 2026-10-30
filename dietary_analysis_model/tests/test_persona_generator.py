"""Offline tests for the persona data generator (tools/build_persona_data.py).

Runs a small deterministic subset into a temporary directory and checks structure, integrity and the
edge-persona behaviours the design document relies on. No database, no network.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import importlib.util
import sys
import tomllib
from collections import defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KST = dt.timezone(dt.timedelta(hours=9))
CODES = "P01,P02,P04,P09,P18,P20,P21,E01,E02,E08,E09,E10,E11a,E13,E14,E16,E17"


def _load(name: str):
	spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
	mod = importlib.util.module_from_spec(spec)
	sys.modules[name] = mod
	spec.loader.exec_module(mod)
	return mod


gen = _load("build_persona_data")
chk = _load("check_persona_calibration")


def _read(d: Path, name: str):
	with (d / f"{name}.csv").open(encoding="utf-8", newline="") as f:
		return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def out(tmp_path_factory) -> Path:
	d = tmp_path_factory.mktemp("persona")
	gen.run(ROOT / "data/persona_params_v1.toml", ROOT / "data/persona_types_v1.csv",
		ROOT / "data/persona_food_pool_v1.csv", ROOT / "data/knhanes_reference_model.json",
		d, 7, set(CODES.split(",")), 1.0, 2)
	return d


@pytest.fixture(scope="module")
def data(out):
	return {n: _read(out, n) for n in ("user_master", "meal", "meal_food", "baseline_lifelog_daily",
		"persona_manifest", "persona_truth_daily")}


@pytest.fixture(scope="module")
def params():
	return tomllib.loads((ROOT / "data/persona_params_v1.toml").read_text(encoding="utf-8"))


def _by_code(data, code):
	return [m["user_id"] for m in data["persona_manifest"] if m["persona_code"] == code]


def test_outputs_exist_and_no_db_code(out):
	for n in ("user_master", "meal", "meal_food", "baseline_lifelog_daily", "persona_manifest", "persona_truth_daily"):
		assert (out / f"{n}.csv").exists()
	assert (out / "load_local.sql").exists() and (out / "run_info.json").exists()
	src = (ROOT / "tools/build_persona_data.py").read_text(encoding="utf-8")
	for forbidden in ("import psycopg2", "os.environ", "getenv", ".connect("):
		assert forbidden not in src
	sql = (out / "load_local.sql").read_text(encoding="utf-8")
	assert "로컬 PostgreSQL 전용" in sql and "sibc_persona" in sql
	assert "loop-dev" not in sql.split("\n", 3)[3]  # only the warning line mentions shared DBs


def test_user_ids_and_manifest(data, params):
	prefix = params["meta"]["user_id_prefix"]
	ids = {u["user_id"] for u in data["user_master"]}
	assert ids == {m["user_id"] for m in data["persona_manifest"]}
	assert all(i.startswith(prefix) for i in ids)
	assert len(ids) == len(data["user_master"])


def test_meal_totals_equal_food_sums_and_ymd_matches_kst(data):
	food_sum = defaultdict(float)
	food_cnt = defaultdict(int)
	for f in data["meal_food"]:
		food_cnt[f["meal_id"]] += 1
		if f["energy_kcal"]:
			food_sum[f["meal_id"]] += float(f["energy_kcal"])
	n_checked = 0
	for m in data["meal"]:
		eaten = dt.datetime.fromisoformat(m["eaten_at"]).astimezone(KST)
		assert eaten.strftime("%Y%m%d") == m["ymd"]
		if m["status"] == "COMPLETED" and food_cnt[m["meal_id"]]:
			if m["energy_kcal"] == "":
				# every food of this meal is UNKNOWN (nutrients NULL): the meal total is NULL, not 0
				assert food_sum[m["meal_id"]] == 0.0
			else:
				assert abs(float(m["energy_kcal"]) - food_sum[m["meal_id"]]) < 0.01
				n_checked += 1
		if m["status"] in ("SKIPPED", "DRAFT"):
			assert m["energy_kcal"] == "" and food_cnt[m["meal_id"]] == 0
	assert n_checked > 1000


def test_wearable_rows_only_on_wear_days_and_partial_flag(data):
	truth = {(t["user_id"], t["date"]): t for t in data["persona_truth_daily"]}
	seen_partial = seen_full = False
	for b in data["baseline_lifelog_daily"]:
		if b["metric_code"] in ("heartrate_bpm", "total_kcal_burned", "active_kcal_burned", "step_count"):
			t = truth[(b["user_id"], b["measure_date"])]
			assert t["wear"] == "true"
			if b["metric_code"] == "heartrate_bpm":
				partial = int(b["n_records"]) < 480
				assert partial == (t["partial"] == "true")
				seen_partial |= partial
				seen_full |= not partial
	assert seen_partial and seen_full
	# no rows for users without a wearable
	owners = {m["user_id"] for m in data["persona_manifest"] if m["axis_w_wearable"] != "W0"}
	for b in data["baseline_lifelog_daily"]:
		if b["metric_code"] == "total_kcal_burned":
			assert b["user_id"] in owners


def test_e01_alternates_four_and_three_recording_days(data):
	uid = _by_code(data, "E01")[0]
	per_week = defaultdict(set)
	start = dt.date(2026, 3, 30)
	for m in data["meal"]:
		if m["user_id"] == uid and m["status"] == "COMPLETED":
			d = dt.datetime.strptime(m["ymd"], "%Y%m%d").date()
			per_week[(d - start).days // 7].add(d)
	counts = [len(per_week[w]) for w in sorted(per_week)]
	assert counts[:4] == [4, 3, 4, 3]


def test_e02_overlap_days_alternate_three_and_two(data):
	uid = _by_code(data, "E02")[0]
	start = dt.date(2026, 3, 30)
	diet = defaultdict(set)
	burn = defaultdict(set)
	for m in data["meal"]:
		if m["user_id"] == uid and m["status"] == "COMPLETED":
			d = dt.datetime.strptime(m["ymd"], "%Y%m%d").date()
			diet[(d - start).days // 7].add(d)
	for b in data["baseline_lifelog_daily"]:
		if b["user_id"] == uid and b["metric_code"] == "total_kcal_burned":
			d = dt.date.fromisoformat(b["measure_date"])
			burn[(d - start).days // 7].add(d)
	overlap = [len(diet[w] & burn[w]) for w in range(4)]
	assert overlap == [3, 2, 3, 2]


def test_e08_breakfast_skipped_rows(data):
	uid = _by_code(data, "E08")[0]
	rows = [m for m in data["meal"] if m["user_id"] == uid and m["meal_type"] == "BREAKFAST"]
	assert rows and all(r["status"] == "SKIPPED" for r in rows)
	lunches = [m for m in data["meal"] if m["user_id"] == uid and m["meal_type"] == "LUNCH"]
	assert lunches and all(r["status"] == "COMPLETED" for r in lunches)


def test_e09_two_meals_exceed_daily_reference(data):
	uid = _by_code(data, "E09")[0]
	types = {m["meal_type"] for m in data["meal"] if m["user_id"] == uid}
	assert types == {"BREAKFAST", "LUNCH"}
	per_day = defaultdict(float)
	for m in data["meal"]:
		if m["user_id"] == uid and m["energy_kcal"]:
			per_day[m["ymd"]] += float(m["energy_kcal"])
	# KDRIs EER for men 50-64 is 2,200 kcal; two recorded meals must already exceed it
	assert min(per_day.values()) > 2200


def test_e10_after_midnight_snack_belongs_to_next_day(data):
	uid = _by_code(data, "E10")[0]
	late = [m for m in data["meal"] if m["user_id"] == uid and m["meal_type"] == "LATE_NIGHT_SNACK"]
	assert late
	hours = defaultdict(int)
	for m in late:
		eaten = dt.datetime.fromisoformat(m["eaten_at"]).astimezone(KST)
		hours["after" if eaten.hour < 4 else "before"] += 1
		assert eaten.strftime("%Y%m%d") == m["ymd"]
	assert hours["after"] > 0 and hours["before"] > 0


def test_e11_weight_offset_and_measure_days(data):
	uid = _by_code(data, "E11a")[0]
	rows = sorted((b for b in data["baseline_lifelog_daily"] if b["user_id"] == uid and b["metric_code"] == "weight_kg"),
		key=lambda b: b["measure_date"])
	end = dt.date(2026, 10, 25)
	last30 = [float(b["value"]) for b in rows if dt.date.fromisoformat(b["measure_date"]) > end - dt.timedelta(days=30)]
	prior = [float(b["value"]) for b in rows if dt.date.fromisoformat(b["measure_date"]) <= end - dt.timedelta(days=30)]
	assert len(last30) == 3 and len(prior) == 6
	assert abs((sum(last30) / 3) - (sum(prior) / 6) - 0.9) < 0.11


def test_e13_arrival_schedule(data):
	uid = _by_code(data, "E13")[0]
	rows = {t["date"]: t for t in data["persona_truth_daily"] if t["user_id"] == uid}
	assert rows["2026-10-19"]["burn_available_from"] == "2026-10-26"   # Monday of last week
	assert rows["2026-10-21"]["burn_available_from"] == "2026-10-29"   # Wednesday
	assert rows["2026-10-25"]["burn_available_from"] == "2026-11-05"   # Sunday
	assert rows["2026-10-12"]["burn_available_from"] == "2026-10-12"   # earlier weeks: no delay (deterministic)


def test_e14_extension_days_are_lower_than_last_week(data):
	uid = _by_code(data, "E14")[0]
	rows = {t["date"]: float(t["true_intake_kcal"]) for t in data["persona_truth_daily"] if t["user_id"] == uid}
	assert "2026-10-28" in rows and "2026-10-29" not in rows
	last_week = sum(rows[f"2026-10-{d}"] for d in range(19, 26)) / 7
	assert rows["2026-10-27"] < last_week * 0.75


def test_e16_null_body_in_user_master(data):
	uid = _by_code(data, "E16")[0]
	u = next(u for u in data["user_master"] if u["user_id"] == uid)
	assert u["weight"] == "" and u["height"] == ""


def test_e17_wearable_starts_four_weeks_before_end(data):
	uid = _by_code(data, "E17")[0]
	days = sorted(dt.date.fromisoformat(b["measure_date"]) for b in data["baseline_lifelog_daily"]
		if b["user_id"] == uid and b["metric_code"] == "total_kcal_burned")
	assert days[0] == dt.date(2026, 9, 28) and days[-1] == dt.date(2026, 10, 25) and len(days) == 28


def test_p18_has_skipped_rows_and_p20_has_edits(data):
	p18 = set(_by_code(data, "P18"))
	assert any(m["status"] == "SKIPPED" for m in data["meal"] if m["user_id"] in p18)
	p20 = set(_by_code(data, "P20"))
	edits = [m for m in data["meal"] if m["user_id"] in p20 and m["edits_meal_id"]]
	ids = {m["meal_id"] for m in data["meal"]}
	assert edits and all(e["edits_meal_id"] in ids for e in edits)
	assert any(m["status"] == "DRAFT" for m in data["meal"] if m["user_id"] in p20)


def test_truth_weight_tracks_energy_balance(data):
	# P02 (B2, steady excess) must gain clearly; P04 (B3, late gradual increase) must gain; P01 (B1) stays within 1 kg
	def path(code):
		uid = _by_code(data, code)[0]
		rows = sorted((t for t in data["persona_truth_daily"] if t["user_id"] == uid), key=lambda t: t["date"])
		return float(rows[0]["true_weight_kg"]), float(rows[-1]["true_weight_kg"])
	w0, w1 = path("P02")
	assert w1 - w0 > 1.5
	w0, w1 = path("P04")
	assert w1 > w0
	w0, w1 = path("P01")
	assert abs(w1 - w0) < 1.0


def test_integrity_checker_passes_on_output(out, params):
	result, problems = chk.compute_metrics(out, params)
	assert problems == []
	assert result["extra"]["n_users"] > 0


def test_generation_is_deterministic(tmp_path):
	args = (ROOT / "data/persona_params_v1.toml", ROOT / "data/persona_types_v1.csv",
		ROOT / "data/persona_food_pool_v1.csv", ROOT / "data/knhanes_reference_model.json")
	d1, d2 = tmp_path / "a", tmp_path / "b"
	gen.run(*args, d1, 11, {"P01", "E01"}, 1.0, 1)
	gen.run(*args, d2, 11, {"P01", "E01"}, 1.0, 1)
	for n in ("meal", "meal_food", "baseline_lifelog_daily", "persona_truth_daily"):
		h1 = hashlib.sha256((d1 / f"{n}.csv").read_bytes()).hexdigest()
		h2 = hashlib.sha256((d2 / f"{n}.csv").read_bytes()).hexdigest()
		assert h1 == h2, n
