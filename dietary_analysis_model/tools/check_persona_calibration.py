"""Calibration and integrity check for generated persona data (docs/persona_data_spec_20261027.md §6, §9).

Reads the CSV files written by tools/build_persona_data.py, recomputes the calibration metrics over
the last eight weeks of the generation period and compares them with the production aggregates stored
in data/persona_params_v1.toml ([[calibration]]). Also runs structural integrity checks. Local files
only; no database access.

Usage:
	python tools/check_persona_calibration.py --dir 01_Results/persona [--write-summary docs/persona_calibration_20261027.md]
Exit code 1 when any calibration target or integrity check fails.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
import statistics as st
import tomllib
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KST = dt.timezone(dt.timedelta(hours=9))
MAIN = ("BREAKFAST", "LUNCH", "DINNER")


def pct(xs, q):
	xs = sorted(xs)
	if not xs:
		return float("nan")
	k = (len(xs) - 1) * q
	lo, hi = math.floor(k), math.ceil(k)
	return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def med(xs):
	return st.median(xs) if xs else float("nan")


def mifflin(sex, w, h, age):
	b = 10 * w + 6.25 * h - 5 * age
	return b + 5 if sex == "M" else b - 161


def read(dir_: Path, name: str):
	with (dir_ / f"{name}.csv").open(encoding="utf-8", newline="") as f:
		return list(csv.DictReader(f))


def compute_metrics(dir_: Path, params: dict) -> tuple[dict, list[str]]:
	w0: dt.date = params["meta"]["calibration_window_start"]
	w1: dt.date = params["meta"]["calibration_window_end"]
	start: dt.date = params["period"]["start"]
	users = read(dir_, "user_master")
	meals = read(dir_, "meal")
	foods = read(dir_, "meal_food")
	base = read(dir_, "baseline_lifelog_daily")
	truth = read(dir_, "persona_truth_daily")
	manifest = {r["user_id"]: r for r in read(dir_, "persona_manifest")}
	problems: list[str] = []
	# Deterministic edge personas (E*) are hand-built test fixtures, not population samples:
	# integrity checks include them, calibration metrics exclude them.
	det_users = {u for u, r in manifest.items() if r["deterministic"] == "true"}
	prefix = params["meta"]["user_id_prefix"]

	# ---------------- integrity
	if len(users) != len(manifest):
		problems.append(f"user_master rows {len(users)} != manifest rows {len(manifest)}")
	for u in users:
		if not u["user_id"].startswith(prefix):
			problems.append(f"user_id without persona prefix: {u['user_id']}")
			break
	food_sum = defaultdict(float)
	food_cnt = defaultdict(int)
	for f in foods:
		food_cnt[f["meal_id"]] += 1
		if f["energy_kcal"]:
			food_sum[f["meal_id"]] += float(f["energy_kcal"])
	bad_sum = bad_ymd = 0
	bad_examples: list[str] = []
	for m in meals:
		eaten = dt.datetime.fromisoformat(m["eaten_at"]).astimezone(KST)
		if eaten.strftime("%Y%m%d") != m["ymd"]:
			bad_ymd += 1
		if m["status"] == "COMPLETED" and food_cnt[m["meal_id"]] and m["energy_kcal"]:
			if abs(float(m["energy_kcal"]) - food_sum[m["meal_id"]]) > 0.01:
				bad_sum += 1
				if len(bad_examples) < 3:
					bad_examples.append(f"{m['meal_id']} meal={m['energy_kcal']} foods={food_sum[m['meal_id']]:.3f}")
		if m["status"] in ("SKIPPED", "DRAFT") and (m["energy_kcal"] or food_cnt[m["meal_id"]]):
			problems.append(f"{m['status']} meal has nutrients/foods: {m['meal_id']}")
	if bad_sum:
		problems.append(f"{bad_sum} meals where energy != sum(meal_food): " + "; ".join(bad_examples))
	if bad_ymd:
		problems.append(f"{bad_ymd} meals where ymd != KST date of eaten_at")
	# wearable rows only on wear days; partial iff n_records < 480
	wear_days = {(t["user_id"], t["date"]): (t["wear"] == "true", t["partial"] == "true") for t in truth}
	hr_rows = 0
	for b in base:
		key = (b["user_id"], b["measure_date"])
		if b["metric_code"] in ("heartrate_bpm", "total_kcal_burned", "active_kcal_burned", "step_count"):
			wear, partial = wear_days.get(key, (False, False))
			if not wear:
				problems.append(f"device row on non-wear day: {key} {b['metric_code']}")
				break
			if b["metric_code"] == "heartrate_bpm":
				hr_rows += 1
				if (int(b["n_records"]) < 480) != partial:
					problems.append(f"partial flag mismatch: {key}")
					break

	# ---------------- calibration metrics (window = last 8 weeks, non-deterministic users only)
	n_det = len(det_users)
	users = [x for x in users if x["user_id"] not in det_users]
	meals = [x for x in meals if x["user_id"] not in det_users]
	base = [x for x in base if x["user_id"] not in det_users]
	truth = [x for x in truth if x["user_id"] not in det_users]
	in_win = lambda d: w0 <= d <= w1
	rec_days = defaultdict(set)
	main_present = defaultdict(set)      # (user, ymd) -> set(main types)
	snack_days = set()
	day_kcal = defaultdict(float)
	day_macro = defaultdict(lambda: [0.0, 0.0, 0.0])
	n_meals = 0
	late = 0
	meal_kcal = defaultdict(list)
	for m in meals:
		d = dt.datetime.strptime(m["ymd"], "%Y%m%d").date()
		if not in_win(d) or m["status"] != "COMPLETED":
			continue
		key = (m["user_id"], m["ymd"])
		rec_days[m["user_id"]].add(d)
		n_meals += 1
		h = dt.datetime.fromisoformat(m["eaten_at"]).astimezone(KST).hour
		if h >= 21 or h < 4:
			late += 1
		if m["meal_type"] in MAIN:
			main_present[key].add(m["meal_type"])
		else:
			snack_days.add(key)
		if m["energy_kcal"]:
			k = float(m["energy_kcal"])
			day_kcal[key] += k
			mt = m["meal_type"] if m["meal_type"] in MAIN else "SNACK"
			meal_kcal[mt].append(k)
			if m["carbohydrate_g"] and m["protein_g"] and m["fat_g"]:
				day_macro[key][0] += 4 * float(m["carbohydrate_g"])
				day_macro[key][1] += 4 * float(m["protein_g"])
				day_macro[key][2] += 9 * float(m["fat_g"])
	all_days = set(day_kcal) | set(main_present) | snack_days
	n_users = len(users)
	recorders = {u for u in rec_days if rec_days[u]}
	# core recorders: >=4 days in >=6 of the 8 weeks
	core = set()
	for u, days in rec_days.items():
		per_week = defaultdict(int)
		for d in days:
			per_week[(d - w0).days // 7] += 1
		if sum(1 for v in per_week.values() if v >= 4) >= 6:
			core.add(u)
	buckets = defaultdict(int)
	for u in recorders:
		n = len(rec_days[u])
		b = "48_56" if n >= 48 else "32_47" if n >= 32 else "16_31" if n >= 16 else "8_15" if n >= 8 else "1_7"
		buckets[b] += 1
	three = sum(1 for k in all_days if len(main_present.get(k, ())) == 3)
	absent = {m: sum(1 for k in all_days if m not in main_present.get(k, ())) for m in MAIN}
	full_keys = [k for k in all_days if len(main_present.get(k, ())) == 3 and day_kcal.get(k)]
	full_kcal = [day_kcal[k] for k in full_keys]
	# within-user CV of full-day kcal (users with >= 14 full days)
	by_user = defaultdict(list)
	for k in full_keys:
		by_user[k[0]].append(day_kcal[k])
	cvs = [st.pstdev(v) / st.mean(v) for v in by_user.values() if len(v) >= 14 and st.mean(v) > 0]
	# intake / BMR on full days
	um = {u["user_id"]: u for u in users}
	ratios = []
	for k in full_keys:
		u = um[k[0]]
		if u["weight"] and u["height"] and u["age"]:
			ratios.append(day_kcal[k] / mifflin(u["sex"], float(u["weight"]), float(u["height"]), int(u["age"])))
	macro = [[], [], []]
	for k in all_days:
		tot = sum(day_macro[k])
		if tot > 500:
			for i in range(3):
				macro[i].append(day_macro[k][i] / tot)
	# wearable
	burn_days = defaultdict(set)
	burn_vals = defaultdict(list)
	hr_partial = hr_total = 0
	weight_days = defaultdict(set)
	for b in base:
		d = dt.date.fromisoformat(b["measure_date"])
		if not in_win(d):
			continue
		if b["metric_code"] == "total_kcal_burned":
			burn_days[b["user_id"]].add(d)
			burn_vals[b["user_id"]].append(float(b["value"]))
		elif b["metric_code"] == "heartrate_bpm":
			hr_total += 1
			hr_partial += int(b["n_records"]) < 480
		elif b["metric_code"] == "weight_kg":
			weight_days[b["user_id"]].add(d)
	heavy_with_burn = sum(1 for u in core if burn_days.get(u)) / len(core) if core else float("nan")
	heavy_with_scale = sum(1 for u in core if weight_days.get(u)) / len(core) if core else float("nan")
	# complete-week share among core recorders' 4+ diet-day weeks
	complete = weeks4 = 0
	for u in core:
		per_week_diet = defaultdict(int)
		per_week_burn = defaultdict(int)
		for d in rec_days[u]:
			per_week_diet[(d - w0).days // 7] += 1
		for d in burn_days.get(u, ()):
			per_week_burn[(d - w0).days // 7] += 1
		for wk, n in per_week_diet.items():
			if n >= 4:
				weeks4 += 1
				complete += per_week_burn.get(wk, 0) >= 4
	burn_all = [v for vs in burn_vals.values() for v in vs]
	burn_cv = [st.pstdev(v) / st.mean(v) for v in burn_vals.values() if len(v) >= 20]
	# weight SD over whole period, users with >= 20 measurements
	wseries = defaultdict(list)
	for b in base:
		if b["metric_code"] == "weight_kg":
			wseries[b["user_id"]].append(float(b["value"]))
	wsd = [st.pstdev(v) for v in wseries.values() if len(v) >= 20]
	# arrival delay
	delays = []
	for t in truth:
		if t["burn_available_from"] and t["wear"] == "true":
			d = dt.date.fromisoformat(t["date"])
			if in_win(d):
				delays.append((dt.date.fromisoformat(t["burn_available_from"]) - d).days)
	# population
	elderly = sum(1 for u in users if u["age"] and int(u["age"]) >= 65) / n_users
	bmi23 = sum(1 for u in users if u["weight"] and u["height"] and float(u["weight"]) / (float(u["height"]) / 100) ** 2 >= 23) / \
		max(1, sum(1 for u in users if u["weight"] and u["height"]))

	nr = max(1, len(recorders))
	metrics = {
		"recorder_share": len(recorders) / n_users,
		"core_recorder_share": len(core) / n_users,
		"rec_days_bucket_1_7": buckets["1_7"] / nr,
		"rec_days_bucket_48_56": buckets["48_56"] / nr,
		"three_main_share": three / max(1, len(all_days)),
		"absent_breakfast": absent["BREAKFAST"] / max(1, len(all_days)),
		"absent_lunch": absent["LUNCH"] / max(1, len(all_days)),
		"absent_dinner": absent["DINNER"] / max(1, len(all_days)),
		"snack_day_share": len(snack_days) / max(1, len(all_days)),
		"late_night_share": late / max(1, n_meals),
		"full_day_kcal_p50": med(full_kcal),
		"meal_kcal_breakfast": med(meal_kcal["BREAKFAST"]),
		"meal_kcal_lunch": med(meal_kcal["LUNCH"]),
		"meal_kcal_dinner": med(meal_kcal["DINNER"]),
		"meal_kcal_snack": med(meal_kcal["SNACK"]),
		"intake_cv_median": med(cvs),
		"intake_bmr_ratio_p50": med(ratios),
		"macro_carb": med(macro[0]), "macro_protein": med(macro[1]), "macro_fat": med(macro[2]),
		"heavy_with_burn": heavy_with_burn,
		"complete_week_share": complete / weeks4 if weeks4 else float("nan"),
		"burn_p50": med(burn_all),
		"burn_cv_median": med(burn_cv),
		"hr_partial_share": hr_partial / hr_total if hr_total else float("nan"),
		"heavy_with_scale": heavy_with_scale,
		"weight_days_median": med([len(v) for v in weight_days.values()]),
		"weight_sd_median": med(wsd),
		"arrival_delay_p50": pct(delays, 0.5),
		"arrival_delay_p90": pct(delays, 0.9),
		"elderly_share": elderly,
		"bmi23_share": bmi23,
	}
	extra = {
		"n_users": n_users, "n_deterministic_excluded": n_det, "n_recorders": len(recorders), "n_core": len(core), "n_meals_window": n_meals,
		"n_recorded_days_window": len(all_days), "full_day_kcal_p10": pct(full_kcal, 0.1), "full_day_kcal_p90": pct(full_kcal, 0.9),
		"intake_bmr_ratio_p25": pct(ratios, 0.25), "intake_bmr_ratio_p75": pct(ratios, 0.75),
		"burn_p10": pct(burn_all, 0.1), "burn_p90": pct(burn_all, 0.9),
	}
	return {"metrics": metrics, "extra": extra}, problems


def compare(metrics: dict, params: dict) -> list[tuple[str, str, float, float, float, bool]]:
	rows = []
	for c in params["calibration"]:
		got = metrics.get(c["key"], float("nan"))
		ok = (not math.isnan(got)) and abs(got - c["value"]) <= c["tol"]
		rows.append((c["key"], c["label"], c["value"], c["tol"], got, ok))
	return rows


def render(rows, extra, problems, dir_: Path, version: str) -> str:
	out = [f"# 페르소나 데이터 보정 검사 결과 ({dt.date.today().isoformat()})", "",
		f"생성기 {version}, 데이터 폴더 `{dir_}`. 합성 데이터이며 실제 성능 근거가 아니다.", "",
		"| 지표 | 운영 목표 | 허용 | 생성값 | 판정 |", "|---|---|---|---|---|"]
	for key, label, val, tol, got, ok in rows:
		g = "nan" if math.isnan(got) else (f"{got:.3f}" if abs(val) < 10 else f"{got:,.0f}")
		v = f"{val:.3f}" if abs(val) < 10 else f"{val:,.0f}"
		out.append(f"| {label} | {v} | ±{tol:g} | {g} | {'통과' if ok else '**미달**'} |")
	out += ["", "보조 수치: " + ", ".join(f"{k} = {v:,.2f}" if isinstance(v, float) else f"{k} = {v}" for k, v in extra.items()), ""]
	out += ["정합성 검사: " + ("문제 없음" if not problems else "; ".join(problems))]
	return "\n".join(out) + "\n"


def main() -> None:
	ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	ap.add_argument("--dir", type=Path, default=ROOT / "01_Results" / "persona")
	ap.add_argument("--params", type=Path, default=ROOT / "data" / "persona_params_v1.toml")
	ap.add_argument("--write-summary", type=Path, default=None)
	args = ap.parse_args()
	params = tomllib.loads(args.params.read_text(encoding="utf-8"))
	result, problems = compute_metrics(args.dir, params)
	rows = compare(result["metrics"], params)
	text = render(rows, result["extra"], problems, args.dir, params["meta"]["version"])
	print(text)
	if args.write_summary:
		args.write_summary.write_text(text, encoding="utf-8")
	failed = [r for r in rows if not r[5]]
	raise SystemExit(1 if failed or problems else 0)


if __name__ == "__main__":
	main()
