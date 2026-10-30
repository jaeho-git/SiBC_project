"""Static reference data: guideline catalog, nutrients, judgement scale, meal allocation.

Kept in git instead of database tables. Changing a value here changes every
judgement computed afterwards; review changes like code.
"""

from dataclasses import dataclass

DEFAULT_GUIDELINE = "KDRIs_2025"

# Stored with every judgement/period row so results can be traced to the rule set
# that produced them. Bump when criteria, bands, or allocation shares change.
RULE_VERSION = "2026.10.20-draft"


@dataclass(frozen=True)
class Guideline:
	code: str
	name_ko: str
	short_name: str
	issuer: str
	region: str
	publication_year: str
	selectable: bool
	source_ref: str
	note: str | None = None


# Selectable guidelines from 식이분석 가이드라인 리서치 보고서 (2026-09-09) PART III.
GUIDELINES: dict[str, Guideline] = {g.code: g for g in (
	Guideline("KDRIs_2025", "한국인 영양소 섭취기준 2025", "KDRIs 2025", "보건복지부·한국영양학회", "KR", "2025", True,
		"발간등록번호 11-1352000-100416-13", "기본값. 다른 가이드라인에 기준이 없으면 대체 적용"),
	Guideline("KDA_2023", "대한당뇨병학회 당뇨병 진료지침 2023", "대한당뇨병학회 2023", "대한당뇨병학회", "KR", "2023", True,
		"DOI 10.4093/jkd.2023.24.3.120"),
	Guideline("KSOLA_2022", "한국지질·동맥경화학회 이상지질혈증 진료지침 제5판", "한국지질·동맥경화학회 2022",
		"한국지질·동맥경화학회", "KR", "2022", True, "lipid.or.kr"),
	Guideline("WHO", "WHO 당류·나트륨 섭취 지침", "WHO", "WHO", "INTL", "2012/2015", True,
		"ISBN 978-92-4-154902-8 (당류), 978-92-4-150483-6 (나트륨)"),
	Guideline("US_DGA_2020_2025", "미국인 식생활지침 2020-2025", "미국 DGA 2020-2025", "HHS·USDA", "US", "2020", True,
		"odphp.health.gov"),
	Guideline("US_DGA_2025_2030", "미국인 식생활지침 2025-2030", "미국 DGA 2025-2030", "USDA·HHS", "US", "2026", True,
		"cdn.realfood.gov/DGA.pdf"),
	Guideline("US_AHA_ACC_2018", "AHA/ACC 콜레스테롤 관리 지침 2018", "AHA·ACC 2018", "AHA·ACC", "US", "2018", True,
		"DOI 10.1161/CIR.0000000000000625"),
	Guideline("US_ADA_2026", "ADA Standards of Care in Diabetes 2026", "ADA 2026", "ADA", "US", "2026", True,
		"Diabetes Care 2026;49(Suppl_1)"),
	Guideline("EU_ESC_EAS_2019", "ESC/EAS 이상지질혈증 관리 지침 2019", "ESC·EAS 2019", "ESC·EAS", "EU", "2019", True,
		"DOI 10.1093/eurheartj/ehz455"),
	Guideline("CN_CNS_DG_2022", "중국거민선식지남 2022", "중국거민선식지남 2022", "중국영양학회", "CN", "2022", True,
		"dg.cnsoc.org"),
	Guideline("CN_NHC_HYPERLIPIDEMIA_2023", "중국 고지혈증 식양지남 2023", "중국 고지혈증 식양지남 2023",
		"중국 국가위생건강위원회", "CN", "2023", True, "팀 내부 원문"),
	Guideline("CN_NHC_DIABETES_2023", "중국 당뇨병 식양지남 2023", "중국 당뇨병 식양지남 2023",
		"중국 국가위생건강위원회", "CN", "2023", True, "팀 내부 원문"),
	Guideline("CN_NHC_HYPERTENSION_2023", "중국 고혈압 식양지남 2023", "중국 고혈압 식양지남 2023",
		"중국 국가위생건강위원회", "CN", "2023", True, "팀 내부 원문"),
	Guideline("KSSO_OBESITY", "대한비만학회 비만 진료지침", "대한비만학회", "대한비만학회", "KR", "2020/2022", False,
		"general.kosso.or.kr", "BMI 분류 기준만 있어 영양소 판정에 사용하지 않음"),
	Guideline("KDCA_HTN_DIET", "질병관리청 고혈압 환자의 식이요법", "질병관리청 고혈압 식이", "질병관리청", "KR", "상시", False,
		"health.kdca.go.kr", "정성 권고만 있어 수치 판정에 사용하지 않음"),
)}

SELECTABLE_GUIDELINES: tuple[str, ...] = tuple(code for code, g in GUIDELINES.items() if g.selectable)


@dataclass(frozen=True)
class Nutrient:
	code: str
	name_ko: str
	unit: str
	kind: str                    # AMOUNT or ENERGY_PCT
	category: str
	column: str                  # AMOUNT: table column; ENERGY_PCT: numerator column
	kcal_per_g: float | None = None
	judged: bool = True
	macro_ratio: bool = False


NUTRIENTS: dict[str, Nutrient] = {n.code: n for n in (
	Nutrient("ENERGY_KCAL", "에너지", "kcal", "AMOUNT", "ENERGY", "energy_kcal"),
	Nutrient("CARB_PCT", "탄수화물 에너지비", "%", "ENERGY_PCT", "MACRO", "carbohydrate_g", 4, macro_ratio=True),
	Nutrient("PROTEIN_PCT", "단백질 에너지비", "%", "ENERGY_PCT", "MACRO", "protein_g", 4, macro_ratio=True),
	Nutrient("FAT_PCT", "지방 에너지비", "%", "ENERGY_PCT", "MACRO", "fat_g", 9, macro_ratio=True),
	Nutrient("CARBOHYDRATE_G", "탄수화물", "g", "AMOUNT", "MACRO", "carbohydrate_g"),
	Nutrient("PROTEIN_G", "단백질", "g", "AMOUNT", "MACRO", "protein_g"),
	Nutrient("FAT_G", "지방", "g", "AMOUNT", "MACRO", "fat_g", judged=False),
	Nutrient("DIETARY_FIBER_G", "식이섬유", "g", "AMOUNT", "MACRO", "dietary_fiber_g"),
	Nutrient("SUGAR_G", "당류", "g", "AMOUNT", "SUGAR", "sugar_g", judged=False),
	Nutrient("SUGAR_PCT", "총당류 에너지비", "%", "ENERGY_PCT", "SUGAR", "sugar_g", 4),
	Nutrient("SATURATED_FAT_G", "포화지방", "g", "AMOUNT", "LIPID", "saturated_fat_g", judged=False),
	Nutrient("SAT_FAT_PCT", "포화지방 에너지비", "%", "ENERGY_PCT", "LIPID", "saturated_fat_g", 9),
	Nutrient("TRANS_FAT_G", "트랜스지방", "g", "AMOUNT", "LIPID", "trans_fat_g"),
	Nutrient("TRANS_FAT_PCT", "트랜스지방 에너지비", "%", "ENERGY_PCT", "LIPID", "trans_fat_g", 9),
	Nutrient("CHOLESTEROL_MG", "콜레스테롤", "mg", "AMOUNT", "LIPID", "cholesterol_mg"),
	Nutrient("SODIUM_MG", "나트륨", "mg", "AMOUNT", "MINERAL", "sodium_mg"),
	Nutrient("POTASSIUM_MG", "칼륨", "mg", "AMOUNT", "MINERAL", "potassium_mg"),
	Nutrient("CALCIUM_MG", "칼슘", "mg", "AMOUNT", "MINERAL", "calcium_mg"),
	Nutrient("PHOSPHORUS_MG", "인", "mg", "AMOUNT", "MINERAL", "phosphorus_mg"),
	Nutrient("IRON_MG", "철", "mg", "AMOUNT", "MINERAL", "iron_mg"),
	Nutrient("VITAMIN_A_UG", "비타민 A", "μg RAE", "AMOUNT", "VITAMIN", "vitamin_a_ug"),
	Nutrient("VITAMIN_D_UG", "비타민 D", "μg", "AMOUNT", "VITAMIN", "vitamin_d_ug"),
	Nutrient("VITAMIN_E_MG", "비타민 E", "mg α-TE", "AMOUNT", "VITAMIN", "vitamin_e_mg"),
	Nutrient("VITAMIN_C_MG", "비타민 C", "mg", "AMOUNT", "VITAMIN", "vitamin_c_mg"),
	Nutrient("THIAMIN_MG", "티아민", "mg", "AMOUNT", "VITAMIN", "thiamin_mg"),
	Nutrient("RIBOFLAVIN_MG", "리보플라빈", "mg", "AMOUNT", "VITAMIN", "riboflavin_mg"),
	Nutrient("NIACIN_MG", "니아신", "mg NE", "AMOUNT", "VITAMIN", "niacin_mg"),
)}

# Nutrient columns of sibc.dietary_analysis / sibc.meal / sibc.meal_food.
NUTRIENT_COLUMNS: tuple[str, ...] = (
	"energy_kcal", "carbohydrate_g", "protein_g", "fat_g", "sugar_g", "dietary_fiber_g",
	"saturated_fat_g", "trans_fat_g", "cholesterol_mg", "sodium_mg", "potassium_mg", "calcium_mg",
	"phosphorus_mg", "iron_mg", "vitamin_a_ug", "vitamin_c_mg", "vitamin_d_ug", "vitamin_e_mg",
	"thiamin_mg", "riboflavin_mg", "niacin_mg",
)


@dataclass(frozen=True)
class Judgement:
	level_5: int
	label_5: str
	level_3: str
	label_3: str
	color_5: str
	color_3: str


# CAN-Pro 5단계 라벨. 3단계 색상: 과잉 빨강, 부족 노랑, 적절 녹색, 판정불가 회색.
JUDGEMENT_SCALE: dict[int, Judgement] = {j.level_5: j for j in (
	Judgement(0, "판정불가", "UNKNOWN", "판정불가", "#BDBDBD", "#BDBDBD"),
	Judgement(1, "부족", "DEFICIENT", "부족", "#E0A800", "#F2C94C"),
	Judgement(2, "약간부족", "DEFICIENT", "부족", "#F6D776", "#F2C94C"),
	Judgement(3, "적절", "ADEQUATE", "적절", "#27AE60", "#27AE60"),
	Judgement(4, "약간과잉", "EXCESS", "과잉", "#F1948A", "#EB5757"),
	Judgement(5, "과잉", "EXCESS", "과잉", "#C0392B", "#EB5757"),
)}


@dataclass(frozen=True)
class MealSlot:
	meal_type: str
	name_ko: str
	energy_share: float
	main_meal: bool
	order: int


# Daily amount references are multiplied by energy_share for a single meal.
# Basis: 2020 KDRIs 활용 (세 끼 균등 배분 + 간식 1~3회) and KNHANES 2019 lunch
# share of daily energy 33.1% (M) / 33.5% (F) (Han & Yang 2021,
# DOI 10.7318/KJFC/2021.36.6.583). Main meals 85%, each snack 5%.
MEAL_SLOTS: dict[str, MealSlot] = {s.meal_type: s for s in (
	MealSlot("BREAKFAST", "아침", 0.25, True, 1),
	MealSlot("MORNING_SNACK", "오전간식", 0.05, False, 2),
	MealSlot("LUNCH", "점심", 0.30, True, 3),
	MealSlot("AFTERNOON_SNACK", "오후간식", 0.05, False, 4),
	MealSlot("DINNER", "저녁", 0.30, True, 5),
	MealSlot("LATE_NIGHT_SNACK", "야식", 0.05, False, 6),
	MealSlot("SNACK", "간식", 0.05, False, 7),
	MealSlot("DAY_TOTAL", "하루 전체", 1.00, False, 9),
)}

PERIOD_WINDOWS: tuple[int, ...] = (7, 14, 30, 60, 180)  # 2026-10-26: 60일 유지 결정. 웨어러블 baseline DB(7/14/30/180)에 60일 추가 검토
# Period snapshots: keep every as_of_date for this many days, then weekly only.
PERIOD_DAILY_RETENTION_DAYS = 180
PERIOD_WEEKLY_KEEP_ISO_WEEKDAY = 1   # Monday
# A period is labelled LOW (참고용) when fewer than this share of its days have records.
PERIOD_MIN_RECORD_SHARE = 0.5
