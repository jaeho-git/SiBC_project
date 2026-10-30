"""Build the food-name -> 식품코드 mapping table from the per-serving reference.

	python tools/build_food_code_map.py \
		--names "<text file: one food_name_norm per line, optional |count>" \
		--reference "/Users/.../food_nutrient_reference.csv" \
		--out data/food_code_map.csv [--existing data/food_code_map.csv]

Matching (docs/food_reference.md 규칙 A)
	1. normalise both names (spaces, punctuation, case)
	2. candidates: EXACT name match -> BASE match (참조 '음식명_재료' 앞부분) -> PREFIX (our name starts a
	   reference name, >= 2 chars, Korean only) ; no candidates -> UNMAPPED
	3. drop candidates with no serving, MULTI_SERVING_SUSPECT / SERVING_OUT_OF_RANGE / ENERGY_* flags,
	   and processed foods whose package is > 1,000 g/ml (업소용)
	4. rank: grade FULL > PARTIAL > CORE, type 음식 > 원재료 > 가공식품, method 산출 > 분석 > 수집,
	   fewer quality flags, serving inside 2~1,500, then shorter reference name
	5. the top candidate is written with match_type and the number of alternatives; a row needs review
	   (reviewed = N) when the match is not EXACT, when alternatives disagree on energy by > 30 %, or
	   when the chosen row has any flag

Rows already marked reviewed = Y in --existing are kept as they are.
"""

import argparse
import collections
import csv
import os
import re

GRADE = {"FULL": 0, "PARTIAL": 1, "CORE": 2, "NONE": 3}
TYPE = {"음식": 0, "원재료성 식품": 1, "가공식품": 2}
METHOD = {"산출": 0, "분석": 1, "수집": 2}
HARD_FLAGS = ("MULTI_SERVING_SUSPECT", "SERVING_OUT_OF_RANGE", "ENERGY_INCONSISTENT", "ENERGY_OUT_OF_RANGE",
	"SODIUM_OUT_OF_RANGE", "SUGAR_GT_CARB")
PACKAGE_MAX = 1000


def norm(s: str) -> str:
	return re.sub(r"[\s_\-()\[\]·,./]", "", str(s or "")).lower()


def num(v):
	try:
		return float(v)
	except (TypeError, ValueError):
		return None


def usable(r: dict) -> bool:
	if not r["serving_qty"]:
		return False
	if any(f in r["quality_flag"] for f in HARD_FLAGS):
		return False
	w = num(r["weight_qty"])
	if r["data_type"] == "가공식품" and w is not None and w > PACKAGE_MAX:
		return False
	return True


def rank_key(r: dict):
	serving = num(r["serving_qty"]) or 0
	typical = 1 if (r["data_type"] == "음식" and r["serving_source"] == "DISH_WEIGHT" and serving < 100) else 0
	return (GRADE.get(r["grade"], 9), TYPE.get(r["data_type"], 9), METHOD.get(r["method"], 9),
		len([f for f in r["quality_flag"].split("|") if f]), typical, len(r["food_name"]))


def main() -> None:
	ap = argparse.ArgumentParser()
	ap.add_argument("--names", required=True)
	ap.add_argument("--reference", required=True)
	ap.add_argument("--out", required=True)
	ap.add_argument("--existing", default=None)
	args = ap.parse_args()

	names = []
	for line in open(args.names, encoding="utf-8").read().splitlines():
		if line.strip():
			parts = line.split("|")
			names.append((parts[0].strip(), int(parts[1]) if len(parts) > 1 and parts[1].strip().isdigit() else 0))

	ref = list(csv.DictReader(open(args.reference, encoding="utf-8-sig")))
	exact = collections.defaultdict(list)
	base = collections.defaultdict(list)
	for r in ref:
		k = norm(r["food_name"])
		exact[k].append(r)
		base[norm(r["food_name"].split("_")[0])].append(r)
	exact_keys = list(exact.keys())

	kept = {}
	if args.existing and os.path.exists(args.existing):
		for r in csv.DictReader(open(args.existing, encoding="utf-8")):
			if r.get("reviewed") == "Y":
				kept[r["food_name_norm"]] = r

	out = []
	stats = collections.Counter()
	for name, cnt in names:
		if name in kept:
			out.append(kept[name])
			stats["kept"] += 1
			continue
		k = norm(name)
		cands, how = [], "UNMAPPED"
		if k in exact:
			cands, how = exact[k], "EXACT"
		elif k in base:
			cands, how = base[k], "BASE"
		elif len(k) >= 2 and not k.isascii():
			# PREFIX: our name starts a reference name (떡볶이 -> 떡볶이_국물); ASCII-only names are left for review
			hits = [key for key in exact_keys if key.startswith(k)]
			cands = [r for key in hits for r in exact[key]]
			how = "PREFIX" if cands else "UNMAPPED"
		usable_c = [r for r in cands if usable(r)]
		pool = usable_c or cands
		pool = sorted(pool, key=rank_key)
		stats[how] += 1
		if not pool:
			out.append({"food_name_norm": name, "record_cnt": cnt, "food_code": "", "ref_food_name": "", "data_type": "",
				"method": "", "grade": "", "serving_qty": "", "serving_unit": "", "serving_source": "",
				"energy_kcal_per_serving": "", "match_type": "UNMAPPED", "candidate_cnt": 0, "usable_cnt": 0,
				"energy_spread": "", "reviewed": "N", "note": "참조에 일치하는 식품명 없음"})
			continue
		top = pool[0]
		energies = [num(r["energy_kcal_per_serving"]) for r in pool[:10] if num(r["energy_kcal_per_serving"])]
		spread = (max(energies) / min(energies)) if len(energies) > 1 and min(energies) > 0 else 1.0
		review_reasons = []
		if how != "EXACT":
			review_reasons.append(f"{how} 매칭")
		if spread > 1.3:
			review_reasons.append(f"후보 간 1인분 kcal 차이 {spread:.1f}배")
		if top["quality_flag"]:
			review_reasons.append("플래그: " + top["quality_flag"])
		if not usable_c:
			review_reasons.append("사용 가능 후보 없음(플래그 있는 후보 선택)")
		out.append({
			"food_name_norm": name, "record_cnt": cnt, "food_code": top["food_code"], "ref_food_name": top["food_name"],
			"data_type": top["data_type"], "method": top["method"], "grade": top["grade"],
			"serving_qty": top["serving_qty"], "serving_unit": top["serving_unit"], "serving_source": top["serving_source"],
			"energy_kcal_per_serving": top["energy_kcal_per_serving"], "match_type": how,
			"candidate_cnt": len(cands), "usable_cnt": len(usable_c), "energy_spread": f"{spread:.2f}",
			"reviewed": "N" if review_reasons else "AUTO", "note": "; ".join(review_reasons),
		})
	fields = ["food_name_norm", "record_cnt", "food_code", "ref_food_name", "data_type", "method", "grade",
		"serving_qty", "serving_unit", "serving_source", "energy_kcal_per_serving", "match_type", "candidate_cnt",
		"usable_cnt", "energy_spread", "reviewed", "note"]
	with open(args.out, "w", encoding="utf-8", newline="") as fh:
		w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
		w.writeheader()
		w.writerows(out)
	auto = sum(1 for r in out if r["reviewed"] == "AUTO")
	review = sum(1 for r in out if r["reviewed"] == "N" and r["match_type"] != "UNMAPPED")
	unmapped = sum(1 for r in out if r["match_type"] == "UNMAPPED")
	print(f"names {len(out)}: match {dict(stats)} | AUTO {auto}, review {review}, unmapped {unmapped} -> {args.out}")


if __name__ == "__main__":
	main()
