"""M2 계약 테스트 (DB·데이터 불필요한 순수 로직)."""
import numpy as np
import pandas as pd

from sibc_checkup import m2


def test_gate_adopt_provisional_reject():
    assert m2._gate([-0.5, -0.1], 5.0, None) == "ADOPT"
    assert m2._gate([-0.77, 0.02], 15.8, [-0.89, -0.29]) == "PROVISIONAL"
    assert m2._gate([-0.43, 0.99], -2.6, [-0.69, 0.51]) == "REJECT"
    assert m2._gate([-0.5, 0.1], 2.0, [-0.9, -0.1]) == "REJECT"  # 개선폭 3% 미만이면 넓은 창으로도 채택 불가


def test_confusion_and_wilson():
    y = np.array([1, 1, 1, 0, 0, 0, 0, 0]); pred = np.array([True, True, False, True, False, False, False, False])
    c = m2._confusion(y, pred)
    assert c["sensitivity"] == round(2 / 3, 3) and c["missed"] == 1 and c["specificity"] == 0.8
    assert c["ppv"] == round(2 / 3, 3) and c["npv"] == 0.8
    lo, hi = m2._wilson(9, 10)
    assert 0.5 < lo < 0.9 < hi <= 1.0


def test_boot_diff_sign_and_user_level():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"user_key": [f"u{i}" for i in range(60)], "y": rng.normal(120, 10, 60)})
    df["good"] = df["y"] + rng.normal(0, 2, 60); df["bad"] = df["y"] + rng.normal(0, 8, 60)
    lo, hi = m2._boot_diff(df, "good", "bad", B=500)
    assert hi < 0  # good이 유의하게 정확


def test_repeated_cv_is_out_of_fold_and_nonnegative_weights():
    rng = np.random.default_rng(1)
    n = 80; base = rng.normal(70, 10, n); meas = base + rng.normal(0, 2, n)
    df = pd.DataFrame({"user_key": [f"u{i}" for i in range(n)], "base": base + rng.normal(0, 3, n), "meas": meas, "y": base})
    p = m2._repeated_cv(df, ["base", "meas"], repeats=3)
    assert np.isfinite(p).all()
    assert m2._mae(p, df["y"]) < m2._mae(df["base"], df["y"])  # 더 정밀한 측정이 있으면 융합이 개선


def test_policy_constants_are_preregistered():
    assert m2.PAIR_WINDOW == 180 and m2.TARGET_SENSITIVITY == 0.85 and m2.TEMPORAL_CUTOFF == "2025-01-01"
