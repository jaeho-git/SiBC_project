"""Nutrient judgement against a selected guideline with KDRIs fallback."""

from dataclasses import dataclass

from .guidelines import Criterion, Thresholds, best_match, criteria_for
from .reference import DEFAULT_GUIDELINE, GUIDELINES, JUDGEMENT_SCALE, NUTRIENTS


@dataclass(frozen=True)
class Resolution:
	criterion: Criterion | None
	is_fallback: bool
	fallback_reason: str | None      # NO_NUMERIC_CRITERION / NOT_COVERED / NOT_COVERED_FOR_PROFILE
	selected_text: str | None        # selected guideline's own (qualitative) wording


def resolve(guideline: str, nutrient: str, sex: str | None, age: int | None) -> Resolution:
	"""The selected guideline's numeric criterion, otherwise the KDRIs criterion."""
	selected = best_match(guideline, nutrient, sex, age)
	if selected is not None and selected.numeric:
		return Resolution(selected, False, None, selected.text)
	default = best_match(DEFAULT_GUIDELINE, nutrient, sex, age, numeric_only=True)
	if guideline == DEFAULT_GUIDELINE:
		return Resolution(default, False, None, None)
	if selected is not None:
		reason = "NO_NUMERIC_CRITERION"
	elif criteria_for(guideline, nutrient):
		reason = "NOT_COVERED_FOR_PROFILE"
	else:
		reason = "NOT_COVERED"
	return Resolution(default, True, reason, selected.text if selected else None)


def applies(guideline: str, nutrient: str) -> bool:
	"""A nutrient is shown for a guideline when it or KDRIs has any criterion for it."""
	return bool(criteria_for(guideline, nutrient) or criteria_for(DEFAULT_GUIDELINE, nutrient))


def judge(value: float | None, thresholds: Thresholds, scale: float = 1.0) -> int:
	"""5-level judgement: 0 판정불가, 1 부족, 2 약간부족, 3 적절, 4 약간과잉, 5 과잉."""
	t = thresholds
	if value is None or all(x is None for x in (t.deficient, t.low, t.high, t.excess)):
		return 0
	if t.deficient is not None and value < t.deficient * scale:
		return 1
	if t.low is not None and value < t.low * scale:
		return 2
	if t.excess is not None and value > t.excess * scale:
		return 5
	if t.high is not None and value > t.high * scale:
		return 4
	return 3


def caution_note(guideline: str, nutrient: str, resolution: Resolution) -> str | None:
	"""Short notice when the selected guideline lacks the criterion (지표 누락)."""
	if not resolution.is_fallback:
		return None
	selected = GUIDELINES[guideline].short_name
	default = GUIDELINES[DEFAULT_GUIDELINE].short_name
	name = NUTRIENTS[nutrient].name_ko
	if resolution.fallback_reason == "NO_NUMERIC_CRITERION":
		return f"[지표 누락] {selected}에 {name} 수치 기준이 없어 {default} 기준으로 판정"
	return f"[지표 누락] {selected}에 {name} 기준이 없어 {default} 기준으로 판정"


def _r(x: float | None, digits: int = 2) -> float | None:
	return None if x is None else round(x, digits)


def evaluate(value: float | None, nutrient: str, guideline: str, sex: str | None, age: int | None,
		meal_share: float | None = 1.0) -> dict:
	"""Judgement record for one intake value.

	meal_share is the meal's share of the daily reference (1.0 for a day);
	it scales amount criteria only, never energy-ratio criteria. None (an
	unknown meal type) leaves amount criteria unjudged.
	"""
	res = resolve(guideline, nutrient, sex, age)
	c = res.criterion
	scale = meal_share if c is not None and c.allocate_to_meal else 1.0
	level = judge(value, c.thresholds(), scale) if c is not None and scale is not None else 0
	ref_value, ref_label, mark = c.primary_reference() if c is not None else (None, None, None)
	ref_scaled = None if ref_value is None or scale is None else ref_value * scale
	scaled = lambda x: None if c is None or x is None or scale is None else _r(x * scale)
	j = JUDGEMENT_SCALE[level]
	return {
		"applied_guideline_code": c.guideline if c else None,
		"applied_source": f"{c.source_doc} ({c.source_year})" if c else None,
		"criterion_text": c.text if c else None,
		"ref_kind": c.kind if c else None,
		"reference_scale": scale,
		"ear": scaled(c.ear if c else None),
		"rni": scaled(c.rni if c else None),
		"ai": scaled(c.ai if c else None),
		"ul": scaled(c.ul if c else None),
		"eer": scaled(c.eer if c else None),
		"range_low": scaled(c.lower if c else None),
		"range_high": scaled(c.upper if c else None),
		"primary_ref_value": _r(ref_scaled),
		"primary_ref_label": ref_label,
		"footnote_mark": mark,
		"pct_of_primary_ref": _r(100 * value / ref_scaled, 1) if value is not None and ref_scaled else None,
		"judgement_5": level,
		"label_5": j.label_5,
		"judgement_3": j.level_3,
		"label_3": j.label_3,
		"color_hex_5": j.color_5,
		"color_hex_3": j.color_3,
		"is_fallback": res.is_fallback,
		"fallback_reason": res.fallback_reason,
		"caution_note": caution_note(guideline, nutrient, res),
		"selected_guideline_text": res.selected_text,
		"needs_source_check": c.needs_source_check if c else False,
	}
