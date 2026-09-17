"""임상 플래그/방향 서빙 게이트 계약."""
import numpy as np
import pandas as pd

from sibc_checkup.serve import _clinical_outputs


def test_ungated_problems_are_not_served():
    crules = {"thresholds": {"high_triglyceride_ge150": {"serve": False, "reason": "BLOCKED_BY_POLICY"}},
              "direction": {"weight": {"serve": False, "reason": "does_not_beat_baseline"}}}
    row = pd.Series({"anchor_prev_label__triglyceride": 120.0, "anchor_prev_label__weight": 70.0})
    out = _clinical_outputs(row, crules)
    assert np.isnan(out["flag_high_triglyceride_ge150_prob"]) and out["flag_high_triglyceride_ge150"] is None
    assert out["direction_weight"] is None and np.isnan(out["direction_weight_worsen_prob"])


def test_flag_requires_fresh_anchor_of_base_target():
    # 모델 로딩 전에 앵커 게이트에서 걸러져야 함 (model_file 없음이 로딩 시도 시 오류)
    crules = {"thresholds": {"hypertension_140_90": {"serve": True, "base_target": "sbp",
                                                     "model_file": "missing.joblib"}},
              "direction": {}}
    out = _clinical_outputs(pd.Series({"anchor_prev_label__sbp": np.nan}), crules)
    assert np.isnan(out["flag_hypertension_140_90_prob"])
    out = _clinical_outputs(pd.Series({"anchor_prev_label__sbp": 130.0, "anchor_days_since__sbp": 5000.0}), crules)
    assert np.isnan(out["flag_hypertension_140_90_prob"])
