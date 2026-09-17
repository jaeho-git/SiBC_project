"""M1 파이프라인 계약: 봉인 분리·승격 규칙·추세 특징."""
import numpy as np
import pandas as pd

from sibc_checkup.m1 import _add_trend, _promotion_rule, _sealed_split


def test_sealed_split_has_no_user_overlap():
    d = pd.DataFrame({"user_key": [f"u{i % 20}" for i in range(100)],
                      "x": np.arange(100)})
    train, sealed = _sealed_split(d)
    assert set(train["user_key"]).isdisjoint(set(sealed["user_key"]))
    assert len(train) + len(sealed) == len(d)


def test_promotion_requires_improvement_and_majority():
    good = {"cv_mae": 9.0, "cf_mae": 10.0, "fold_wins_vs_cf": 4, "n_folds": 5}
    assert _promotion_rule(good) == "MODEL"
    # 개선율 3% 미만 -> CARRY_FORWARD
    tiny = {"cv_mae": 9.9, "cf_mae": 10.0, "fold_wins_vs_cf": 5, "n_folds": 5}
    assert _promotion_rule(tiny) == "CARRY_FORWARD"
    # 평균은 좋지만 과반 폴드에서 지면 -> CARRY_FORWARD
    unstable = {"cv_mae": 8.0, "cf_mae": 10.0, "fold_wins_vs_cf": 2, "n_folds": 5}
    assert _promotion_rule(unstable) == "CARRY_FORWARD"


def test_promotion_blocked_by_sample_policy():
    # CV상 우수해도 학습 100명/봉인 30명 정책 미달이면 승격 불가 (소표본 착시 차단)
    good = {"cv_mae": 9.0, "cf_mae": 10.0, "fold_wins_vs_cf": 5, "n_folds": 5}
    assert _promotion_rule(good, n_users_train=50, n_users_sealed=12) == "CARRY_FORWARD"
    assert _promotion_rule(good, n_users_train=230, n_users_sealed=60) == "MODEL"


def test_trend_uses_only_prior_checkups():
    own = pd.DataFrame({
        "user_key": ["u1"] * 3,
        "event_date": ["2024-01-01", "2025-01-01", "2026-01-01"],
        "sbp": [120.0, 130.0, 140.0],
        "anchor_prev_label__sbp": [np.nan, 120.0, 130.0],
        "anchor_days_since__sbp": [np.nan, 366.0, 365.0],
    })
    out = _add_trend(own, "sbp")
    # 세 번째 검진의 추세는 1,2번째 값만 사용 (140은 미래이므로 미포함)
    assert out.iloc[2]["trend_prev2__sbp"] == 120.0
    assert abs(out.iloc[2]["trend_slope_per_year__sbp"] - 10.0) < 0.1
    assert np.isnan(out.iloc[1]["trend_prev2__sbp"])
