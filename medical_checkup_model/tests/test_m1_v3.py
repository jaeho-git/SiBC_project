"""v3 규칙 계약: 구간 선택 우선순위, EB 축소 추정기, 하이브리드 MODEL_CROSS 서빙."""
import numpy as np
import pandas as pd

from sibc_checkup.m1 import EBShrinkageRegressor, _choose_interval
from sibc_checkup.serve import _predict_target


def test_interval_choice_prefers_coverage_over_width():
    # 상수 구간이 커버리지 미달(0.77)이고 CQR이 충족(0.82)이면, 더 넓어도 CQR
    assert _choose_interval({"constant": {"picp": 0.77, "width": 29.5},
                             "cqr": {"picp": 0.82, "width": 32.5}}) == "cqr"
    # 둘 다 충족하면 더 좁은 쪽
    assert _choose_interval({"constant": {"picp": 0.86, "width": 34.0},
                             "cqr": {"picp": 0.89, "width": 35.6}}) == "constant"
    assert _choose_interval({"constant": {"picp": 0.85, "width": 15.2},
                             "cqr": {"picp": 0.85, "width": 14.1}}) == "cqr"


def test_eb_shrinkage_moves_toward_population_when_history_is_noisy():
    rng = np.random.default_rng(0)
    n = 400
    X = pd.DataFrame({"anchor_prev_label__sbp": rng.normal(120, 10, n),
                      "trend_prev2__sbp": np.nan, "demo_age": rng.integers(30, 70, n),
                      "demo_sex": rng.choice([1.0, 2.0], n)})
    y = X["anchor_prev_label__sbp"] + rng.normal(0, 8, n)  # 개인 내 잡음 큼
    m = EBShrinkageRegressor(target="sbp").fit(X, y)
    test = pd.DataFrame({"anchor_prev_label__sbp": [160.0], "trend_prev2__sbp": [np.nan],
                         "demo_age": [50], "demo_sex": [1.0]})
    pred = m.predict(test)[0]
    pop = m.global_
    assert pop < pred < 160.0  # 극단 앵커는 모집단 쪽으로 축소되되 앵커 방향 유지


def test_model_cross_hybrid_uses_carry_forward_when_own_anchor_fresh():
    rule = {"route": "MODEL_CROSS", "model_file": "cross_ldl.joblib", "interval_offsets": [-30, 30],
            "cf_interval_offsets": [-20, 25], "max_anchor_age_days": 1095}
    row = pd.Series({"anchor_prev_label__ldl": 130.0, "anchor_days_since__ldl": 400.0,
                     "demo_age": 50.0, "demo_sex": 1.0})
    out = _predict_target(row, "ldl", rule, "m1_v3")
    assert out["route_ldl"] == "CARRY_FORWARD" and out["pred_ldl"] == 130.0
    assert out["pred_ldl_lower"] == 110.0 and out["pred_ldl_upper"] == 155.0
