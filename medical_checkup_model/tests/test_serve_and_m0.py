"""서빙 규칙·M0 forward 선별 계약 테스트 (오프라인)."""
import numpy as np
import pandas as pd

from sibc_checkup.m0_forward_eval import forward_rows
from sibc_checkup.serve import _coverage_grade, _predict_target

RULE_CF = {"route": "CARRY_FORWARD", "interval_offsets": [-3.0, 3.5], "max_anchor_age_days": 1095}


def test_abstain_without_prior_checkup():
    row = pd.Series({"anchor_prev_label__sbp": np.nan})
    out = _predict_target(row, "sbp", RULE_CF, "m1_v2")
    assert out["route_sbp"] == "ABSTAIN" and out["abstain_reason_sbp"] == "no_prior_checkup"
    assert np.isnan(out["pred_sbp"])


def test_abstain_when_anchor_stale():
    row = pd.Series({"anchor_prev_label__sbp": 120.0, "anchor_days_since__sbp": 2000.0})
    out = _predict_target(row, "sbp", RULE_CF, "m1_v2")
    assert out["route_sbp"] == "ABSTAIN" and out["abstain_reason_sbp"].startswith("stale_anchor")


def test_carry_forward_returns_anchor_with_interval():
    row = pd.Series({"anchor_prev_label__weight": 70.0, "anchor_days_since__weight": 300.0})
    out = _predict_target(row, "weight", RULE_CF, "m1_v2")
    assert out["route_weight"] == "CARRY_FORWARD"
    assert out["pred_weight"] == 70.0
    assert out["pred_weight_lower"] == 67.0 and out["pred_weight_upper"] == 73.5


def test_coverage_grade_thresholds():
    assert _coverage_grade(pd.Series({"step_count__w30__days": 25})) == "A"
    assert _coverage_grade(pd.Series({"step_count__w30__days": 12})) == "B"
    assert _coverage_grade(pd.Series({"step_count__w30__days": 3})) == "C"
    assert _coverage_grade(pd.Series({"step_count__w30__days": np.nan})) == "none"


def test_forward_rows_require_real_wearable_window():
    # 앵커(과거 검진)만 있고 관측창이 없는 행은 forward 쌍이 아니다 (누출 방지)
    own = pd.DataFrame({
        "user_key": ["a", "b"],
        "anchor_prev_label__weight": [60.0, 61.0],
        "step_count__w7__median": [np.nan, 5000.0],
    })
    fwd = forward_rows(own)
    assert list(fwd["user_key"]) == ["b"]
