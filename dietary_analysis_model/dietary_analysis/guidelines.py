"""Guideline criteria per nutrient, sex, and age.

Sources
- KDRIs 2025: 2025 한국인 영양소 섭취기준 요약표 (보건복지부·한국영양학회,
  정오 반영 2025-12-29). Ages 6 and older.
- Other guidelines: 식이분석 가이드라인 리서치 보고서 (2026-09-09) PART III 6·7장,
  adults 19 and older. needs_source_check=True values must be verified against
  the original document before clinical use.

Judgement bands are defined per reference kind, not per nutrient (see
docs/judgement_bands.md). Literature-backed boundaries are the reference values
themselves plus the KNHANES/KHEI energy cut-points; three design parameters
(AI_DEFICIENT_RATIO, UPPER_EXCESS_RATIO, RANGE_PCT_MARGIN) await expert review.

  EER        <60% 부족, <75% 약간부족, 75~125% 적절, >125% 약간과잉, >140% 과잉
  EAR_RNI    <EAR 부족, <RNI 약간부족, RNI~UL 적절, >UL 과잉 (약간과잉 없음)
  AI         <AI x 0.5 부족, <AI 약간부족, AI~UL 적절, >UL 과잉 (약간과잉 없음)
  AI_CDRR    <AI 약간부족(참고), AI~CDRR 적절, >CDRR 약간과잉, >CDRR x 1.4 과잉
  UPPER      <=limit 적절, >limit 약간과잉, >limit x 1.4 과잉
  RANGE_PCT  <lower-5%p 부족, <lower 약간부족, in range 적절, >upper 약간과잉, >upper+5%p 과잉
  RANGE_ABS  <lower x 0.75 부족, <lower 약간부족, in range 적절, >upper 약간과잉, >upper x 1.25 과잉
"""

from dataclasses import dataclass

from .reference import DEFAULT_GUIDELINE, NUTRIENTS

# Design parameters (expert review pending). Everything else is a reference value.
EER_DEFICIENT_RATIO = 0.60     # KHEI zero-score bound
EER_LOW_RATIO = 0.75           # KNHANES 영양섭취부족자 definition
EER_HIGH_RATIO = 1.25          # KNHANES 에너지/지방 과잉섭취자 definition
EER_EXCESS_RATIO = 1.40        # KHEI zero-score bound
AI_DEFICIENT_RATIO = 0.5       # design: far below AI -> 부족 가능성 (2020 KDRIs 활용 p.53 example)
UPPER_EXCESS_RATIO = 1.4       # design: matches KHEI saturated fat 7% -> 10% (x1.43)
RANGE_PCT_MARGIN = 5.0         # %p; matches KHEI fat 15~30% -> 10%/35%
RANGE_ABS_LOWER_RATIO = 0.75   # design (foreign absolute ranges only)
RANGE_ABS_UPPER_RATIO = 1.25


@dataclass(frozen=True)
class Thresholds:
	deficient: float | None = None   # value <  deficient -> 1 부족
	low: float | None = None         # value <  low       -> 2 약간부족
	high: float | None = None        # value >  high      -> 4 약간과잉
	excess: float | None = None      # value >  excess    -> 5 과잉


@dataclass(frozen=True)
class Criterion:
	guideline: str
	nutrient: str
	sex: str                          # M, F, or A (all)
	age_min: int
	age_max: int | None
	kind: str                         # EER, EAR_RNI, AI, AI_CDRR, UPPER, RANGE_PCT, RANGE_ABS, QUALITATIVE
	text: str
	source_doc: str
	source_year: str
	ear: float | None = None
	rni: float | None = None
	ai: float | None = None
	ul: float | None = None
	eer: float | None = None
	lower: float | None = None
	upper: float | None = None
	needs_source_check: bool = False
	note: str | None = None

	@property
	def numeric(self) -> bool:
		return self.kind != "QUALITATIVE"

	@property
	def allocate_to_meal(self) -> bool:
		"""Daily amounts are scaled to a meal; energy ratios apply unchanged."""
		return NUTRIENTS[self.nutrient].kind == "AMOUNT"

	def matches(self, sex: str | None, age: int | None) -> bool:
		if age is None or self.sex not in (sex, "A"):
			return False
		return self.age_min <= age and (self.age_max is None or age <= self.age_max)

	def thresholds(self) -> Thresholds:
		match self.kind:
			case "EER":
				return Thresholds(self.eer * EER_DEFICIENT_RATIO, self.eer * EER_LOW_RATIO,
					self.eer * EER_HIGH_RATIO, self.eer * EER_EXCESS_RATIO)
			case "EAR_RNI":
				return Thresholds(self.ear, self.rni, self.ul, self.ul)
			case "AI":
				return Thresholds(self.ai * AI_DEFICIENT_RATIO, self.ai, self.ul, self.ul)
			case "AI_CDRR":
				return Thresholds(None, self.ai, self.upper, self.upper * UPPER_EXCESS_RATIO)
			case "UPPER":
				return Thresholds(None, None, self.upper, self.upper * UPPER_EXCESS_RATIO)
			case "RANGE_PCT":
				return Thresholds(self.lower - RANGE_PCT_MARGIN, self.lower, self.upper, self.upper + RANGE_PCT_MARGIN)
			case "RANGE_ABS":
				return Thresholds(self.lower * RANGE_ABS_LOWER_RATIO, self.lower, self.upper, self.upper * RANGE_ABS_UPPER_RATIO)
		return Thresholds()

	def primary_reference(self) -> tuple[float | None, str | None, str | None]:
		"""(value, label, footnote mark) shown next to the intake (적정섭취수준 병기)."""
		match self.kind:
			case "EER":
				return self.eer, "필요추정량", None
			case "EAR_RNI":
				return self.rni, "권장섭취량", "*"
			case "AI":
				return self.ai, "충분섭취량", "**"
			case "AI_CDRR":
				return self.upper, "만성질환위험감소섭취량", None
			case "UPPER":
				return self.upper, "상한 기준", "†"
			case "RANGE_PCT":
				return None, "적정비율", None
			case "RANGE_ABS":
				return None, "권고 범위", None
		return None, None, None


# -----------------------------------------------------------------------------
# KDRIs 2025, sex/age specific. Band order: 6-8, 9-11, 12-14, 15-18, 19-29,
# 30-49, 50-64, 65-74, 75+.
# -----------------------------------------------------------------------------
_KDRIS_BANDS: tuple[tuple[int, int | None], ...] = (
	(6, 8), (9, 11), (12, 14), (15, 18), (19, 29), (30, 49), (50, 64), (65, 74), (75, None),
)
_KDRIS_DOC = "2025 한국인 영양소 섭취기준 요약표"
_RETINOL_UL_NOTE = "상한섭취량은 레티놀(preformed) 기준이라 총 RAE 판정에 적용하지 않음"
_NIACIN_UL_NOTE = "상한섭취량은 니코틴산/니코틴아미드(보충제) 기준이라 식품 판정에 적용하지 않음"

# (nutrient, kind, sex, {field: values per band}, note)
_KDRIS_BY_BAND = (
	("ENERGY_KCAL", "EER", "M", {"eer": (1700, 2000, 2500, 2700, 2600, 2500, 2200, 2000, 1900)}, None),
	("ENERGY_KCAL", "EER", "F", {"eer": (1500, 1800, 2000, 2000, 2000, 1900, 1700, 1600, 1500)}, None),
	("DIETARY_FIBER_G", "AI", "M", {"ai": (20, 20, 25, 25, 30, 30, 30, 30, 30)}, None),
	("DIETARY_FIBER_G", "AI", "F", {"ai": (15, 20, 20, 20, 20, 20, 25, 25, 25)}, None),
	("PROTEIN_G", "EAR_RNI", "M", {"ear": (30, 40, 50, 55, 50, 50, 50, 50, 50), "rni": (35, 50, 60, 65, 65, 65, 60, 60, 60)}, None),
	("PROTEIN_G", "EAR_RNI", "F", {"ear": (30, 40, 45, 45, 45, 40, 40, 40, 40), "rni": (35, 45, 55, 55, 55, 50, 50, 50, 50)}, None),
	("VITAMIN_A_UG", "EAR_RNI", "M", {"ear": (310, 410, 540, 620, 570, 560, 530, 520, 500), "rni": (450, 600, 750, 850, 800, 800, 750, 700, 700)}, _RETINOL_UL_NOTE),
	("VITAMIN_A_UG", "EAR_RNI", "F", {"ear": (290, 390, 480, 450, 460, 450, 430, 410, 410), "rni": (400, 550, 650, 650, 650, 650, 600, 600, 600)}, _RETINOL_UL_NOTE),
	("VITAMIN_D_UG", "AI", "M", {"ai": (5, 5, 10, 10, 10, 10, 10, 15, 15), "ul": (40, 60, 100, 100, 100, 100, 100, 100, 100)}, None),
	("VITAMIN_D_UG", "AI", "F", {"ai": (5, 5, 10, 10, 10, 10, 10, 15, 15), "ul": (40, 60, 100, 100, 100, 100, 100, 100, 100)}, None),
	("VITAMIN_E_MG", "AI", "M", {"ai": (7, 9, 11, 12, 12, 12, 12, 12, 12), "ul": (200, 300, 400, 500, 540, 540, 540, 540, 540)}, None),
	("VITAMIN_E_MG", "AI", "F", {"ai": (7, 9, 11, 12, 12, 12, 12, 12, 12), "ul": (200, 300, 400, 500, 540, 540, 540, 540, 540)}, None),
	("VITAMIN_C_MG", "EAR_RNI", "M", {"ear": (40, 55, 70, 80, 75, 75, 75, 75, 75), "rni": (50, 70, 90, 100, 100, 100, 100, 100, 100), "ul": (750, 1100, 1400, 1600, 2000, 2000, 2000, 2000, 2000)}, None),
	("VITAMIN_C_MG", "EAR_RNI", "F", {"ear": (40, 55, 70, 80, 75, 75, 75, 75, 75), "rni": (50, 70, 90, 100, 100, 100, 100, 100, 100), "ul": (750, 1100, 1400, 1600, 2000, 2000, 2000, 2000, 2000)}, None),
	("THIAMIN_MG", "EAR_RNI", "M", {"ear": (0.5, 0.7, 0.9, 1.1, 1.0, 1.0, 1.0, 0.9, 0.9), "rni": (0.7, 0.9, 1.1, 1.3, 1.2, 1.2, 1.2, 1.1, 1.1)}, None),
	("THIAMIN_MG", "EAR_RNI", "F", {"ear": (0.6, 0.8, 0.9, 0.9, 0.9, 0.9, 0.9, 0.8, 0.7), "rni": (0.7, 0.9, 1.1, 1.1, 1.1, 1.1, 1.1, 1.0, 0.8)}, None),
	("RIBOFLAVIN_MG", "EAR_RNI", "M", {"ear": (0.7, 0.9, 1.2, 1.4, 1.3, 1.3, 1.3, 1.2, 1.1), "rni": (0.9, 1.1, 1.5, 1.7, 1.5, 1.5, 1.5, 1.4, 1.4)}, None),
	("RIBOFLAVIN_MG", "EAR_RNI", "F", {"ear": (0.6, 0.8, 1.0, 1.0, 1.0, 1.0, 1.0, 0.9, 0.8), "rni": (0.8, 1.0, 1.2, 1.2, 1.2, 1.2, 1.2, 1.1, 1.0)}, None),
	("NIACIN_MG", "EAR_RNI", "M", {"ear": (7, 9, 11, 13, 12, 12, 12, 11, 10), "rni": (8, 11, 14, 16, 14, 14, 14, 13, 12)}, _NIACIN_UL_NOTE),
	("NIACIN_MG", "EAR_RNI", "F", {"ear": (7, 9, 11, 11, 11, 11, 11, 10, 9), "rni": (8, 11, 14, 13, 13, 13, 13, 12, 11)}, _NIACIN_UL_NOTE),
	("CALCIUM_MG", "EAR_RNI", "M", {"ear": (600, 700, 800, 700, 650, 650, 650, 650, 650), "rni": (700, 800, 950, 800, 800, 800, 800, 800, 800), "ul": (3000, 3000, 3000, 3000, 3000, 2500, 2500, 2500, 2500)}, None),
	("CALCIUM_MG", "EAR_RNI", "F", {"ear": (600, 700, 700, 550, 500, 500, 650, 600, 600), "rni": (700, 800, 850, 700, 650, 650, 750, 750, 750), "ul": (2500, 2500, 2500, 2500, 2500, 2000, 2000, 2000, 2000)}, None),
	("PHOSPHORUS_MG", "EAR_RNI", "M", {"ear": (500, 1000, 1000, 900, 540, 540, 540, 540, 540), "rni": (600, 1200, 1200, 1100, 650, 650, 650, 650, 650), "ul": (3000, 3500, 3500, 3500, 3500, 3500, 3500, 3500, 3000)}, None),
	("PHOSPHORUS_MG", "EAR_RNI", "F", {"ear": (500, 1000, 950, 850, 540, 540, 540, 540, 540), "rni": (600, 1200, 1100, 1000, 650, 650, 650, 650, 650), "ul": (3000, 3500, 3500, 3500, 3500, 3500, 3500, 3500, 3000)}, None),
	("SODIUM_MG", "AI_CDRR", "M", {"ai": (1100, 1300, 1500, 1500, 1500, 1500, 1500, 1300, 1200), "upper": (1700, 2000, 2300, 2300, 2300, 2300, 2300, 1900, 1800)}, None),
	("SODIUM_MG", "AI_CDRR", "F", {"ai": (1100, 1300, 1500, 1500, 1500, 1500, 1500, 1300, 1200), "upper": (1700, 2000, 2300, 2300, 2300, 2300, 2300, 1900, 1800)}, None),
	("POTASSIUM_MG", "AI", "M", {"ai": (2600, 3100, 3500, 3500, 3500, 3500, 3500, 3500, 3500)}, None),
	("POTASSIUM_MG", "AI", "F", {"ai": (2600, 3100, 3500, 3500, 3500, 3500, 3500, 3500, 3500)}, None),
	("IRON_MG", "EAR_RNI", "M", {"ear": (5, 6, 8, 8, 6, 6, 6, 6, 5), "rni": (7, 8, 11, 11, 8, 8, 8, 8, 7), "ul": (40, 40, 40, 45, 45, 45, 45, 45, 45)}, None),
	("IRON_MG", "EAR_RNI", "F", {"ear": (5, 6, 8, 7, 7, 7, 5, 4, 4), "rni": (7, 8, 13, 12, 12, 12, 7, 6, 6), "ul": (40, 40, 40, 45, 45, 45, 45, 45, 45)}, None),
)


def _kdris_text(kind: str, v: dict[str, float]) -> str:
	match kind:
		case "EER":
			return f"필요추정량 {v['eer']:g} kcal/일"
		case "EAR_RNI":
			ul = f", 상한섭취량 {v['ul']:g}" if "ul" in v else ""
			return f"평균필요량 {v['ear']:g}, 권장섭취량 {v['rni']:g}{ul}"
		case "AI":
			ul = f", 상한섭취량 {v['ul']:g}" if "ul" in v else ""
			return f"충분섭취량 {v['ai']:g}{ul}"
		case "AI_CDRR":
			return f"충분섭취량 {v['ai']:g}, 만성질환위험감소섭취량 {v['upper']:g}"
	return ""


def _kdris_banded() -> list[Criterion]:
	out = []
	for nutrient, kind, sex, fields, note in _KDRIS_BY_BAND:
		for i, (age_min, age_max) in enumerate(_KDRIS_BANDS):
			values = {k: float(v[i]) for k, v in fields.items()}
			out.append(Criterion(DEFAULT_GUIDELINE, nutrient, sex, age_min, age_max, kind,
				_kdris_text(kind, values), _KDRIS_DOC, "2025", note=note, **values))
	return out


def _c(guideline, nutrient, kind, text, doc, year, age_min=19, age_max=None, **kw) -> Criterion:
	return Criterion(guideline, nutrient, "A", age_min, age_max, kind, text, doc, year, **kw)


_KDA = ("당뇨병 진료지침", "2023")
_KSOLA = ("이상지질혈증 진료지침 제5판", "2022")
_ESC = ("2019 ESC/EAS Guidelines for the management of dyslipidaemias", "2019")
_CN_DG = ("중국거민선식지남", "2022")
_NOT_MEASURABLE = " - 현재 데이터는 총당류만 있어 수치 적용 불가"

CRITERIA: tuple[Criterion, ...] = tuple(_kdris_banded() + [
	# KDRIs 2025, shared by sex
	_c("KDRIs_2025", "CARBOHYDRATE_G", "EAR_RNI", "평균필요량 100 g, 권장섭취량 130 g", _KDRIS_DOC, "2025", 6, ear=100, rni=130),
	_c("KDRIs_2025", "CARB_PCT", "RANGE_PCT", "에너지적정비율 50~65%", _KDRIS_DOC, "2025", 6, lower=50, upper=65),
	_c("KDRIs_2025", "PROTEIN_PCT", "RANGE_PCT", "에너지적정비율 10~20%", _KDRIS_DOC, "2025", 6, lower=10, upper=20),
	_c("KDRIs_2025", "FAT_PCT", "RANGE_PCT", "에너지적정비율 15~30%", _KDRIS_DOC, "2025", 6, lower=15, upper=30),
	_c("KDRIs_2025", "SAT_FAT_PCT", "UPPER", "포화지방산 에너지 8% 미만 (3~18세)", _KDRIS_DOC, "2025", 6, 18, upper=8),
	_c("KDRIs_2025", "SAT_FAT_PCT", "UPPER", "포화지방산 에너지 7% 미만", _KDRIS_DOC, "2025", 19, upper=7),
	_c("KDRIs_2025", "TRANS_FAT_PCT", "UPPER", "트랜스지방산 에너지 1% 미만", _KDRIS_DOC, "2025", 6, upper=1),
	_c("KDRIs_2025", "CHOLESTEROL_MG", "UPPER", "콜레스테롤 19세 이상 300 mg/일 미만 권고", _KDRIS_DOC, "2025", 19, upper=300),
	_c("KDRIs_2025", "SUGAR_PCT", "UPPER", "총당류 에너지 20% 이내 (첨가당 10% 이내)", _KDRIS_DOC, "2025", 6, upper=20),
	# 대한당뇨병학회 2023: no numeric criteria
	_c("KDA_2023", "ENERGY_KCAL", "QUALITATIVE", "과체중·비만 시 5% 이상 체중 감량", *_KDA),
	_c("KDA_2023", "CARB_PCT", "QUALITATIVE", "이상적 탄수화물 비율 없음, 개별화", *_KDA),
	_c("KDA_2023", "PROTEIN_PCT", "QUALITATIVE", "단백질 섭취를 제한하지 않음", *_KDA),
	_c("KDA_2023", "SAT_FAT_PCT", "QUALITATIVE", "포화지방을 불포화지방으로 대체 권고", *_KDA),
	_c("KDA_2023", "TRANS_FAT_PCT", "QUALITATIVE", "트랜스지방을 불포화지방으로 대체 권고", *_KDA),
	_c("KDA_2023", "SUGAR_PCT", "QUALITATIVE", "첨가당 최소화, 가당음료 줄이기", *_KDA),
	# 한국지질·동맥경화학회 2022
	_c("KSOLA_2022", "FAT_PCT", "UPPER", "총지방 에너지 30% 이내", *_KSOLA, upper=30),
	_c("KSOLA_2022", "SAT_FAT_PCT", "UPPER", "포화지방산 에너지 7% 이내", *_KSOLA, upper=7),
	_c("KSOLA_2022", "CHOLESTEROL_MG", "UPPER", "콜레스테롤 300 mg/일 미만 바람직", *_KSOLA, upper=300),
	_c("KSOLA_2022", "TRANS_FAT_PCT", "QUALITATIVE", "트랜스지방 가급적 피할 것", *_KSOLA),
	_c("KSOLA_2022", "DIETARY_FIBER_G", "QUALITATIVE", "통곡물·채소·콩류 급원 권장", *_KSOLA),
	# WHO
	_c("WHO", "SODIUM_MG", "UPPER", "나트륨 2,000 mg/일 미만 (소금 5 g)", "Guideline: Sodium intake for adults and children", "2012", upper=2000),
	_c("WHO", "SUGAR_PCT", "QUALITATIVE", "유리당 에너지 10% 미만(강력), 5% 미만(조건부)" + _NOT_MEASURABLE,
		"Guideline: Sugars intake for adults and children", "2015"),
	# 미국 HHS·USDA, AHA·ACC, ADA
	_c("US_DGA_2020_2025", "SAT_FAT_PCT", "UPPER", "포화지방 에너지 10% 미만", "Dietary Guidelines for Americans 2020-2025", "2020", upper=10),
	_c("US_DGA_2020_2025", "SODIUM_MG", "UPPER", "나트륨 2,300 mg/일 미만", "Dietary Guidelines for Americans 2020-2025", "2020", upper=2300),
	_c("US_DGA_2020_2025", "SUGAR_PCT", "QUALITATIVE", "첨가당 에너지 10% 미만" + _NOT_MEASURABLE, "Dietary Guidelines for Americans 2020-2025", "2020"),
	_c("US_DGA_2025_2030", "SAT_FAT_PCT", "UPPER", "포화지방 에너지 10% 미만", "Dietary Guidelines for Americans 2025-2030", "2026", upper=10),
	_c("US_DGA_2025_2030", "SODIUM_MG", "UPPER", "나트륨 2,300 mg/일 미만", "Dietary Guidelines for Americans 2025-2030", "2026", upper=2300,
		needs_source_check=True, note="보고서에 DGA 판 구분 없이 기재됨"),
	_c("US_AHA_ACC_2018", "SAT_FAT_PCT", "UPPER", "포화지방 에너지 5~6%", "2018 AHA/ACC Guideline on the Management of Blood Cholesterol", "2018",
		upper=6, note="권고 범위 상단 6%를 상한으로 적용"),
	_c("US_ADA_2026", "CARB_PCT", "QUALITATIVE", "탄수화물 비율 개별화 원칙", "Standards of Care in Diabetes-2026", "2026"),
	# 유럽 ESC·EAS
	_c("EU_ESC_EAS_2019", "FAT_PCT", "UPPER", "총지방 에너지 35% 초과 주의", *_ESC, upper=35),
	_c("EU_ESC_EAS_2019", "SAT_FAT_PCT", "UPPER", "포화지방 에너지 10% 미만 (고콜레스테롤혈증 7% 미만)", *_ESC, upper=10),
	_c("EU_ESC_EAS_2019", "TRANS_FAT_PCT", "QUALITATIVE", "트랜스지방 가급적 회피", *_ESC),
	# 중국 (소금 5 g = 나트륨 1,967 mg, NaCl 중 Na 39.34%)
	_c("CN_CNS_DG_2022", "TRANS_FAT_G", "UPPER", "트랜스지방 2 g/일 이하", *_CN_DG, upper=2),
	_c("CN_CNS_DG_2022", "SODIUM_MG", "UPPER", "소금 5 g/일 이하 (나트륨 1,967 mg 환산)", *_CN_DG, upper=1967),
	_c("CN_CNS_DG_2022", "SUGAR_PCT", "QUALITATIVE", "첨가당 50 g/일 이하, 가급적 25 g 미만" + _NOT_MEASURABLE, *_CN_DG),
	_c("CN_CNS_DG_2022", "FAT_PCT", "QUALITATIVE", "조리유 25~30 g/일 - 조리유 섭취량 데이터 없음", *_CN_DG),
	_c("CN_NHC_HYPERLIPIDEMIA_2023", "CARB_PCT", "RANGE_PCT", "탄수화물 에너지 50~60%", "고지혈증 식양지남", "2023",
		lower=50, upper=60, needs_source_check=True, note='보고서 표기 "50~60% 초과" - 원문 확인 필요'),
	_c("CN_NHC_HYPERLIPIDEMIA_2023", "FAT_PCT", "RANGE_PCT", "지방 에너지 20~25%, 조리유 25 g 이하", "고지혈증 식양지남", "2023",
		lower=20, upper=25, needs_source_check=True, note='보고서 표기 "20~25% 초과" - 원문 확인 필요'),
	_c("CN_NHC_HYPERLIPIDEMIA_2023", "CHOLESTEROL_MG", "UPPER", "콜레스테롤 300 mg/일 미만 (고콜레스테롤혈증 200 mg/일 미만)",
		"고지혈증 식양지남", "2023", upper=300),
	_c("CN_NHC_HYPERLIPIDEMIA_2023", "DIETARY_FIBER_G", "RANGE_ABS", "식이섬유 25~40 g/일 (수용성 7~13 g)", "고지혈증 식양지남", "2023",
		lower=25, upper=40),
	_c("CN_NHC_HYPERLIPIDEMIA_2023", "SAT_FAT_PCT", "QUALITATIVE", "포화지방·트랜스지방·콜레스테롤 제한 명시", "고지혈증 식양지남", "2023"),
	_c("CN_NHC_DIABETES_2023", "CARBOHYDRATE_G", "RANGE_ABS", "탄수화물 1일 200~300 g", "당뇨병 식양지남", "2023", lower=200, upper=300),
	_c("CN_NHC_DIABETES_2023", "SODIUM_MG", "UPPER", "소금 5 g/일 이하 (나트륨 1,967 mg 환산)", "당뇨병 식양지남", "2023", upper=1967),
	_c("CN_NHC_HYPERTENSION_2023", "SODIUM_MG", "UPPER", "소금 5 g/일 이하 (나트륨 1,967 mg 환산)", "고혈압 식양지남", "2023", upper=1967),
])

_BY_KEY: dict[tuple[str, str], list[Criterion]] = {}
for _criterion in CRITERIA:
	_BY_KEY.setdefault((_criterion.guideline, _criterion.nutrient), []).append(_criterion)


def criteria_for(guideline: str, nutrient: str) -> list[Criterion]:
	return _BY_KEY.get((guideline, nutrient), [])


def best_match(guideline: str, nutrient: str, sex: str | None, age: int | None,
		numeric_only: bool = False) -> Criterion | None:
	"""Most specific criterion: sex-specific before shared, then the narrowest age band."""
	candidates = [
		c for c in criteria_for(guideline, nutrient)
		if c.matches(sex, age) and (c.numeric or not numeric_only)
	]
	candidates.sort(key=lambda c: (c.sex == "A", -c.age_min))
	return candidates[0] if candidates else None
