"""가이드라인 판정 계약 테스트: 경계값·출처 무결성."""
from sibc_checkup import guideline as g
from sibc_checkup.m2 import combine_tier


def test_boundaries_default_tiers():
    assert [g.grade_value("sbp", v) for v in (119, 120, 139, 140)] == ["정상", "주의", "주의", "위험"]
    assert [g.grade_value("dbp", v) for v in (79, 80, 89, 90)] == ["정상", "주의", "주의", "위험"]
    assert [g.grade_value("fasting_glucose", v) for v in (99, 100, 125, 126)] == ["정상", "주의", "주의", "위험"]
    assert [g.grade_value("bmi", v) for v in (22.9, 23, 24.9, 25)] == ["정상", "주의", "주의", "위험"]
    assert [g.grade_value("ldl", v) for v in (129, 130, 159, 160)] == ["정상", "주의", "주의", "위험"]
    assert [g.grade_value("triglyceride", v) for v in (149, 150, 199, 200)] == ["정상", "주의", "주의", "위험"]
    assert [g.grade_value("hdl", v) for v in (39, 40, 59, 60)] == ["위험", "주의", "주의", "정상"]
    assert g.grade_value("waist", 89, 1) == "정상" and g.grade_value("waist", 90, 1) == "위험"
    assert g.grade_value("waist", 84, 2) == "정상" and g.grade_value("waist", 85, 2) == "위험"


def test_bp_uses_worse_of_two_and_stage_names():
    assert g.grade_bp(118, 92) == "위험" and g.grade_bp(125, 70) == "주의"
    assert g.bp_stage(125, 70) == "주의혈압" and g.bp_stage(118, 85) == "고혈압전단계"
    assert g.bp_stage(150, 85) == "고혈압 1기" and g.bp_stage(150, 105) == "고혈압 2기"


def test_sources_differ_and_are_preserved():
    assert g.stage_by_source("bmi", 24, "KSSO2022").startswith("비만전단계") and g.stage_by_source("bmi", 24, "NHS_KR") == "정상A"
    assert g.stage_by_source("ldl", 195, "KSoLA2022") == "매우 높음"


def test_every_default_tier_cites_a_known_source_with_locator():
    cfg = g.load()
    for item, t in cfg["default_tiers"].items():
        for s in t["basis"]:
            src = cfg["sources"][s]
            assert src.get("pmid") or src.get("doi") or src.get("url"), (item, s)


def test_disease_profile_goals():
    r = g.goal_status("diabetes", sbp=134, dbp=78, fasting_glucose=120, ldl=110)
    assert r == {"blood_pressure": "조절 필요", "fasting_glucose": "목표 달성", "ldl": "조절 필요"}
    assert g.goal_status("hypertension", sbp=134, dbp=78) == {"blood_pressure": "목표 달성"}


def test_prediction_upper_bound_escalates_and_combine():
    assert g.grade_prediction("sbp", 118, 142) == "주의" and g.grade_prediction("sbp", 118, 130) == "정상"
    assert combine_tier(["정상"], 0.1, 0.5, 0.6, 0.07) == "위험"
    assert combine_tier(["정상"], 0.1, 0.5, 0.10, 0.07) == "주의"
    assert combine_tier(["정상"], 0.1, 0.5, 0.01, 0.07) == "정상"
    assert combine_tier([None], float("nan"), None, float("nan"), None) is None
