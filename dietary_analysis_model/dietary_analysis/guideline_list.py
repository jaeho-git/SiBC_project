"""Prints docs/guidelines.md: the guideline catalog and each guideline's criteria.

	python -m dietary_analysis.guideline_list > docs/guidelines.md

Generated from reference.py / guidelines.py so the document never drifts from
what the refresh job actually applies.
"""

from .guidelines import CRITERIA
from .reference import DEFAULT_GUIDELINE, GUIDELINES, NUTRIENTS, RULE_VERSION

_KIND_KO = {
	"EER": "필요추정량", "EAR_RNI": "평균필요량·권장섭취량", "AI": "충분섭취량",
	"AI_CDRR": "충분섭취량·만성질환위험감소섭취량", "UPPER": "상한형", "RANGE_PCT": "에너지적정비율",
	"RANGE_ABS": "절대량 범위", "QUALITATIVE": "정성 권고(수치 없음)",
}


def _fmt(x: float | None) -> str:
	return "" if x is None else f"{x:g}"


def _criteria_table(guideline: str) -> str:
	rows = [c for c in CRITERIA if c.guideline == guideline]
	if not rows:
		return "_기준 없음_\n"
	if guideline == DEFAULT_GUIDELINE:
		# KDRIs: summarise per nutrient (values are sex/age specific)
		lines = ["| 영양소 | 기준 유형 | 성별·연령 구분 | 비고 |", "|---|---|---|---|"]
		seen: dict[str, list] = {}
		for c in rows:
			seen.setdefault(c.nutrient, []).append(c)
		for code, cs in seen.items():
			n = NUTRIENTS[code]
			sexes = sorted({c.sex for c in cs})
			ages = sorted({(c.age_min, c.age_max) for c in cs})
			span = f"{ages[0][0]}세 이상" if len(ages) == 1 and ages[0][1] is None else f"{len(ages)}개 연령대"
			sex_txt = "남/여 구분" if sexes != ["A"] else "공통"
			notes = {c.note for c in cs if c.note}
			lines.append(f"| {n.name_ko} ({code}) | {_KIND_KO[cs[0].kind]} | {sex_txt}, {span} | {' / '.join(sorted(notes))} |")
		return "\n".join(lines) + "\n"
	lines = ["| 영양소 | 기준 유형 | 기준 | 적용 연령 | 원문 확인 | 비고 |", "|---|---|---|---|---|---|"]
	for c in rows:
		n = NUTRIENTS[c.nutrient]
		age = f"{c.age_min}세 이상" if c.age_max is None else f"{c.age_min}~{c.age_max}세"
		check = "필요" if c.needs_source_check else ""
		lines.append(f"| {n.name_ko} ({c.nutrient}) | {_KIND_KO[c.kind]} | {c.text} | {age} | {check} | {c.note or ''} |")
	return "\n".join(lines) + "\n"


def render() -> str:
	out = [
		"# 식이분석 가이드라인 목록",
		"",
		f"`python -m dietary_analysis.guideline_list`로 생성. 규칙 버전 `{RULE_VERSION}`. 코드 값은 대소문자를 구분합니다.",
		"",
		"## 1. 선택 가능한 가이드라인",
		"",
		"| 코드 (`guideline_code`) | 이름 | 발행기관 | 지역 | 연도 | 수치 기준 영양소 수 | 출처 | 비고 |",
		"|---|---|---|---|---|---|---|---|",
	]
	for code, g in GUIDELINES.items():
		if not g.selectable:
			continue
		numeric = sum(1 for c in CRITERIA if c.guideline == code and c.numeric)
		nutrients = len({c.nutrient for c in CRITERIA if c.guideline == code and c.numeric})
		default = " **(기본값)**" if code == DEFAULT_GUIDELINE else ""
		out.append(f"| `{code}`{default} | {g.name_ko} | {g.issuer} | {g.region} | {g.publication_year} | "
			f"{nutrients} | {g.source_ref} | {g.note or ''} |")
	out += [
		"",
		"- `KDRIs_2025`는 모든 사용자·모든 영양소(23개)에 항상 계산됩니다.",
		"- 다른 가이드라인은 **자체 수치 기준이 있는 영양소만** 계산·저장됩니다. 나머지 영양소는 앱이 `KDRIs_2025` 행을 쓰고 \"지표 누락\"을 표시합니다.",
		"- 수치 기준 영양소 수가 0인 가이드라인(`KDA_2023`, `US_ADA_2026`)은 정성 권고만 있어 저장 행이 없습니다. 권고 문구는 아래 표에 있습니다.",
		"",
		"## 2. 선택하지 않는 가이드라인 (목록에만 유지)",
		"",
		"| 코드 | 이름 | 이유 |",
		"|---|---|---|",
	]
	for code, g in GUIDELINES.items():
		if not g.selectable:
			out.append(f"| `{code}` | {g.name_ko} | {g.note or ''} |")
	out += ["", "## 3. 가이드라인별 기준", ""]
	for code, g in GUIDELINES.items():
		if not g.selectable:
			continue
		out.append(f"### `{code}` — {g.name_ko}")
		out.append("")
		out.append(_criteria_table(code))
	out += [
		"## 4. 영양소 코드",
		"",
		"| 코드 (`nutrient_code`) | 이름 | 단위 | 값 종류 | 판정 대상 |",
		"|---|---|---|---|---|",
	]
	for code, n in NUTRIENTS.items():
		out.append(f"| `{code}` | {n.name_ko} | {n.unit} | {'에너지비' if n.kind == 'ENERGY_PCT' else '절대량'} | "
			f"{'예' if n.judged else '아니오(에너지비로 판정)'} |")
	return "\n".join(out) + "\n"


if __name__ == "__main__":
	print(render(), end="")
