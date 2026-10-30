"""Build the food nutrient reference table (per 100 and per serving) from the full MFDS dataset.

	python tools/build_food_reference.py \
		--full "/Users/.../전국통합식품영양성분정보_전체_20260929.csv" \
		--out-dir "/Users/.../식이분석_데이터"

Outputs
	food_nutrient_reference.csv              one row per 식품코드: classification, basis, per-100 nutrients,
	                                         serving (1인분) with its source, per-serving nutrients, grade, quality flags
	food_nutrient_reference_per_serving.csv  rows that have a serving: identification, 1인분, nutrients per serving
	food_reference_profile.md                coverage and serving-rule profile

Nutrient values stay as published (per 100 g / 100 ml). Empty = not reported (NULL), never 0.

1인분 (serving) rules -- docs/food_reference.md 3.3
	음식·산출/분석  식품중량 = 1인분. Outside the 대분류 plausible range -> 대분류 표준 1인분 (MULTI_SERVING_SUSPECT)
	음식·수집      판매 단위. 피자·케이크 등은 조각으로 분할(SPLIT_PRODUCT), 범위 안이면 1개 = 1인분(PRODUCT_UNIT),
	               범위 초과면 대분류 표준 1인분(CATEGORY_STANDARD)
	가공식품       식약처 1회 섭취참고량 (대표식품 규칙, data/processed_food_serving_rule.csv). 포장이 더 작으면
	               1포장 = 1회(PACKAGE). 규칙이 없으면 5~600 g/ml 포장만 1포장 = 1회(PACKAGE_FALLBACK)
	원재료         1인분 없음(NONE) -- 식품군 분류가 없어 KDRIs 1인 1회 분량을 붙이지 못함
"""

import argparse
import collections
import csv
import os
import re

NUTRIENTS = [  # (csv column, reference column)
	("에너지(kcal)", "energy_kcal"), ("탄수화물(g)", "carbohydrate_g"), ("단백질(g)", "protein_g"), ("지방(g)", "fat_g"),
	("당류(g)", "sugar_g"), ("식이섬유(g)", "dietary_fiber_g"), ("포화지방산(g)", "saturated_fat_g"),
	("트랜스지방산(g)", "trans_fat_g"), ("콜레스테롤(mg)", "cholesterol_mg"), ("나트륨(mg)", "sodium_mg"),
	("칼륨(mg)", "potassium_mg"), ("칼슘(mg)", "calcium_mg"), ("인(mg)", "phosphorus_mg"), ("철(mg)", "iron_mg"),
	("비타민 A(μg RAE)", "vitamin_a_ug"), ("비타민 C(mg)", "vitamin_c_mg"), ("비타민 D(μg)", "vitamin_d_ug"),
	("티아민(mg)", "thiamin_mg"), ("리보플라빈(mg)", "riboflavin_mg"), ("니아신(mg)", "niacin_mg"),
]
EXTRA = [("수분(g)", "water_g"), ("레티놀(μg)", "retinol_ug"), ("베타카로틴(μg)", "beta_carotene_ug")]
CORE = ("energy_kcal", "carbohydrate_g", "protein_g", "fat_g", "sodium_mg")
MICRO = ("dietary_fiber_g", "potassium_mg", "calcium_mg", "phosphorus_mg", "iron_mg", "vitamin_a_ug",
	"vitamin_c_mg", "vitamin_d_ug", "thiamin_mg", "riboflavin_mg", "niacin_mg")

# 음식 대분류별 1인분 타당 범위와 표준 1인분 (g 또는 ml). 음식·산출 행의 10~90% 분포에서 정한 초안 (검수 대상).
DISH_RANGE: dict[str, tuple[float, float, float]] = {
	"밥류": (150, 500, 300), "국 및 탕류": (150, 700, 300), "찌개 및 전골류": (150, 800, 300),
	"면 및 만두류": (200, 900, 500), "죽 및 스프류": (150, 600, 300), "볶음류": (40, 400, 110),
	"구이류": (40, 350, 110), "조림류": (30, 300, 90), "찜류": (40, 450, 150), "전·적 및 부침류": (30, 300, 100),
	"튀김류": (30, 400, 100), "나물·숙채류": (20, 200, 60), "생채·무침류": (20, 250, 90), "김치류": (20, 150, 50),
	"장류, 양념류": (3, 60, 15), "장아찌·절임류": (5, 100, 30), "젓갈류": (3, 60, 15),
	"빵 및 과자류": (20, 300, 80), "음료 및 차류": (100, 1000, 350), "유제품류 및 빙과류": (50, 400, 150),
	"수·조·어·육류": (30, 300, 100), "곡류, 서류 제품": (30, 300, 100), "과일류": (50, 300, 100),
	"채소, 해조류": (20, 200, 60), "두류, 견과 및 종실류": (10, 100, 30),
}
DEFAULT_RANGE = (20, 700, 200)
# 판매 단위를 조각으로 나누는 대표식품 (수집 음식). 초안.
SPLIT_DIVISOR = {"피자": 8, "케이크": 8, "케익": 8, "치킨": 4, "통닭": 4, "족발": 4, "보쌈": 4}
SERVING_MIN, SERVING_MAX = 2, 1500
PACKAGE_FALLBACK_MAX = 600

_QTY = re.compile(r"^\s*([\d.,]+)\s*(g|ml|mL|kg|l|L)\s*$")


def parse_qty(s: str) -> tuple[float | None, str | None]:
	m = _QTY.match(s or "")
	if not m:
		return None, None
	v = float(m.group(1).replace(",", ""))
	u = m.group(2).lower()
	if u == "kg":
		return v * 1000, "g"
	if u == "l":
		return v * 1000, "ml"
	return v, u


def num(s: str) -> float | None:
	s = (s or "").strip()
	if s in ("", "-"):
		return None
	try:
		return float(s.replace(",", ""))
	except ValueError:
		return None


def load_prefix_map(path: str):
	by = collections.defaultdict(dict)
	lengths = {}
	with open(path, encoding="utf-8") as fh:
		for r in csv.DictReader(fh):
			key = (r["데이터구분코드"], r["레벨"])
			by[key][r["코드접두어(하이픈제거)"]] = (r["분류코드"], r["분류명"])
			lengths[key] = int(r["접두어길이"])
	return by, lengths


def load_serving_rule(path: str):
	"""(대표식품명, 중분류명) -> (qty, unit, text); plus 대표식품명 -> best single rule."""
	exact, by_rep = {}, {}
	with open(path, encoding="utf-8") as fh:
		for r in csv.DictReader(fh):
			qty = num(r["1회량"])
			rec = (qty, r["단위"] or None, r["1회섭취참고량_원문"], int(r["표본수"]))
			exact[(r["대표식품명"], r["식품중분류명"])] = rec
			if r["대표식품명"] not in by_rep or rec[3] > by_rep[r["대표식품명"]][3]:
				by_rep[r["대표식품명"]] = rec
	return exact, by_rep


def dish_serving(method: str, major: str, rep: str, name: str, weight: float | None, flags: list[str]):
	"""Returns (serving, source, note)."""
	lo, hi, std = DISH_RANGE.get(major, DEFAULT_RANGE)
	if weight is None:
		return std, "CATEGORY_STANDARD", "식품중량 없음 → 대분류 표준 1인분"
	if method == "수집":
		div = next((d for k, d in SPLIT_DIVISOR.items() if k in (rep or "") or k in (name or "")), None)
		if div and weight > hi:
			return round(weight / div, 1), "SPLIT_PRODUCT", f"판매 단위 {weight:g} ÷ {div}"
		if weight > hi:
			flags.append("MULTI_SERVING_SUSPECT")
			return std, "CATEGORY_STANDARD", f"판매 단위 {weight:g} > 범위 {hi:g} → 표준 {std:g} (약 {weight / std:.1f}인분)"
		if weight < lo:
			flags.append("SMALL_SERVING")
		return weight, "PRODUCT_UNIT", "메뉴 1개 = 1인분"
	# 산출 / 분석
	if weight > hi:
		flags.append("MULTI_SERVING_SUSPECT")
		return std, "CATEGORY_STANDARD", f"식품중량 {weight:g} > 범위 {hi:g} → 표준 {std:g} (약 {weight / std:.1f}인분)"
	if weight < lo:
		flags.append("SMALL_SERVING")
	return weight, "DISH_WEIGHT", "식품중량 = 1인분"


def processed_serving(rep: str, mid: str, weight: float | None, weight_unit: str | None, rule_exact, rule_rep, flags):
	rule = rule_exact.get((rep, mid)) or rule_rep.get(rep)
	if rule and rule[0] is not None:
		qty, unit, text, _ = rule
		if weight is not None and weight < qty:
			return weight, "PACKAGE", f"포장 {weight:g} < 1회 참고량 {qty:g} → 1포장 = 1회"
		return qty, "CATEGORY_RULE", f"식약처 1회 섭취참고량 {text}"
	if rule and rule[2] in ("1식", "1인분") and weight is not None:
		return weight, "PACKAGE", f"1회 참고량 '{rule[2]}' → 1포장 = 1회"
	if weight is not None and SERVING_MIN <= weight <= PACKAGE_FALLBACK_MAX:
		flags.append("SERVING_FALLBACK")
		return weight, "PACKAGE_FALLBACK", "1회 참고량 규칙 없음 → 1포장 = 1회 (참고)"
	flags.append("NO_SERVING")
	return None, "NONE", "1회 참고량 규칙 없음, 포장 중량으로 추정 불가"


def main() -> None:
	here = os.path.dirname(os.path.abspath(__file__))
	ap = argparse.ArgumentParser()
	ap.add_argument("--full", required=True)
	ap.add_argument("--out-dir", required=True)
	ap.add_argument("--prefix-map", default=os.path.join(here, "..", "data", "food_code_classification.csv"))
	ap.add_argument("--serving-rule", default=os.path.join(here, "..", "data", "processed_food_serving_rule.csv"))
	args = ap.parse_args()

	prefix_map, lengths = load_prefix_map(args.prefix_map)
	rule_exact, rule_rep = load_serving_rule(args.serving_rule)

	rows: dict[str, dict] = {}
	raw_count = 0
	with open(args.full, encoding="utf-8-sig", newline="") as fh:
		for r in csv.DictReader(fh):
			raw_count += 1
			code = r["식품코드"]
			if code in rows and rows[code]["데이터기준일자"] >= r["데이터기준일자"]:
				continue
			rows[code] = r

	out_rows = []
	stats = collections.Counter()
	blank = collections.Counter()
	by_type = collections.Counter()
	by_type_blank = collections.defaultdict(collections.Counter)
	serving_src = collections.defaultdict(collections.Counter)
	flag_cnt = collections.Counter()
	grade_cnt = collections.defaultdict(collections.Counter)

	for code, r in rows.items():
		letter = code[0]
		compact = code.replace("-", "")
		cls = {}
		for level in ("대분류", "대표식품", "중분류"):
			key = (letter, level)
			L = lengths.get(key)
			cls[level] = prefix_map[key].get(compact[:L]) if L else None
		major = cls["대분류"][1] if cls["대분류"] else ""
		rep = cls["대표식품"][1] if cls["대표식품"] else ""
		mid = cls["중분류"][1] if cls["중분류"] else ""
		kind = r["데이터구분명"]
		method = r["데이터생성방법명"]
		by_type[kind] += 1
		basis_v, basis_u = parse_qty(r["영양성분함량기준량"])
		weight_v, weight_u = parse_qty(r["식품중량"])
		flags: list[str] = []

		# ---- nutrients per 100
		nut = {}
		for col, ref in NUTRIENTS + EXTRA:
			v = num(r[col])
			nut[ref] = v
			if v is None and (col, ref) in NUTRIENTS:
				blank[ref] += 1
				by_type_blank[kind][ref] += 1
		core_ok = all(nut[c] is not None for c in CORE)
		micro_n = sum(1 for c in MICRO if nut[c] is not None)
		grade = "FULL" if core_ok and micro_n == len(MICRO) else ("PARTIAL" if core_ok and micro_n else ("CORE" if core_ok else "NONE"))

		# ---- quality checks
		e, c, p, f = nut["energy_kcal"], nut["carbohydrate_g"], nut["protein_g"], nut["fat_g"]
		if None not in (e, c, p, f) and e > 0 and abs(4 * c + 4 * p + 9 * f - e) / e > 0.25:
			flags.append("ENERGY_INCONSISTENT")
		if e is not None and e > 900:
			flags.append("ENERGY_OUT_OF_RANGE")
		if nut["sodium_mg"] is not None and nut["sodium_mg"] > 20000:
			flags.append("SODIUM_OUT_OF_RANGE")
		if nut["sugar_g"] is not None and c is not None and nut["sugar_g"] > c + 1:
			flags.append("SUGAR_GT_CARB")

		# ---- serving
		if kind == "음식":
			serving, src, note = dish_serving(method, major, rep, r["식품명"], weight_v, flags)
			serving_u = weight_u or basis_u
		elif kind == "가공식품":
			serving, src, note = processed_serving(rep, mid, weight_v, weight_u, rule_exact, rule_rep, flags)
			serving_u = (rule_exact.get((rep, mid)) or rule_rep.get(rep) or (None, None))[1] if src == "CATEGORY_RULE" else weight_u
		else:
			serving, src, note = None, "NONE", "원재료: 식품군 분류 없음"
			serving_u = None
			flags.append("NO_SERVING")
		if serving is not None and serving_u and basis_u and serving_u != basis_u:
			flags.append("DENSITY_ASSUMED")  # g vs ml: density 1.0 assumed
		if serving is not None and not (SERVING_MIN <= serving <= SERVING_MAX):
			flags.append("SERVING_OUT_OF_RANGE")
		serving_src[kind][src] += 1
		for fl in flags:
			flag_cnt[fl] += 1
		grade_cnt[kind][grade] += 1
		stats["classified"] += bool(major)
		stats["has_serving"] += serving is not None

		o = {
			"food_code": code, "food_name": r["식품명"], "data_type": kind, "method": method,
			"major_code": cls["대분류"][0] if cls["대분류"] else "", "major_name": major,
			"rep_code": cls["대표식품"][0] if cls["대표식품"] else "", "rep_name": rep,
			"mid_code": cls["중분류"][0] if cls["중분류"] else "", "mid_name": mid,
			"basis_qty": basis_v, "basis_unit": basis_u, "weight_qty": weight_v, "weight_unit": weight_u,
			"serving_qty": serving, "serving_unit": serving_u, "serving_source": src, "serving_note": note,
			"grade": grade, "micro_present_cnt": micro_n, "quality_flag": "|".join(flags),
			"refuse_pct": num(r["폐기율(%)"]), "source_name": r["출처명"], "company_name": r["업체명"],
			"created_date": r["데이터생성일자"], "reference_date": r["데이터기준일자"],
		}
		for _, ref in NUTRIENTS + EXTRA:
			o[ref] = nut[ref]
		for _, ref in NUTRIENTS:
			v = nut[ref]
			o[ref + "_per_serving"] = None if (v is None or serving is None) else round(v * serving / 100, 3)
		out_rows.append(o)

	os.makedirs(args.out_dir, exist_ok=True)
	out_csv = os.path.join(args.out_dir, "food_nutrient_reference.csv")
	with open(out_csv, "w", encoding="utf-8-sig", newline="") as fh:
		w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
		w.writeheader()
		w.writerows(out_rows)

	# per-serving table: identification + 1인분 + nutrients per serving
	ps_csv = os.path.join(args.out_dir, "food_nutrient_reference_per_serving.csv")
	ps_cols = ["food_code", "food_name", "data_type", "method", "major_name", "rep_name", "grade", "quality_flag",
		"serving_qty", "serving_unit", "serving_source", "serving_note"] + [ref + "_per_serving" for _, ref in NUTRIENTS]
	with open(ps_csv, "w", encoding="utf-8-sig", newline="") as fh:
		w = csv.DictWriter(fh, fieldnames=ps_cols, extrasaction="ignore")
		w.writeheader()
		w.writerows(o for o in out_rows if o["serving_qty"] is not None)

	n = len(out_rows)
	lines = [
		"# food_nutrient_reference profile", "",
		f"- raw API rows: {raw_count:,}; unique 식품코드: {n:,}",
		f"- by 데이터구분: {dict(by_type)}",
		f"- classified by code prefix: {stats['classified']:,} ({100 * stats['classified'] / n:.1f}%)",
		f"- has 1인분 (serving): {stats['has_serving']:,} ({100 * stats['has_serving'] / n:.1f}%)",
		"", "## serving source by type", "",
	]
	for t, c in serving_src.items():
		lines.append(f"- {t}: " + ", ".join(f"{k} {v:,} ({100 * v / by_type[t]:.0f}%)" for k, v in c.most_common()))
	lines += ["", "## grade by type (FULL = core + 11 micronutrients)", ""]
	for t, c in grade_cnt.items():
		lines.append(f"- {t}: " + ", ".join(f"{k} {v:,} ({100 * v / by_type[t]:.0f}%)" for k, v in c.most_common()))
	lines += ["", "## quality flags", ""] + [f"- {k}: {v:,}" for k, v in flag_cnt.most_common()]
	lines += ["", "## blank share per nutrient (all / by type)", "",
		"| nutrient | all | " + " | ".join(by_type) + " |", "|---|---|" + "---|" * len(by_type)]
	for _, ref in NUTRIENTS:
		cells = [f"{100 * by_type_blank[t][ref] / by_type[t]:.0f}%" for t in by_type]
		lines.append(f"| {ref} | {100 * blank[ref] / n:.0f}% | " + " | ".join(cells) + " |")
	with open(os.path.join(args.out_dir, "food_reference_profile.md"), "w", encoding="utf-8") as fh:
		fh.write("\n".join(lines) + "\n")
	print("\n".join(lines))
	print(f"\n-> {out_csv}\n-> {ps_csv} (rows with a serving)")


if __name__ == "__main__":
	main()
