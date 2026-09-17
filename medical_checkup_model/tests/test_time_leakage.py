"""시간 누출 방지: 관측창 특징은 검진일 이전 데이터만 사용해야 한다."""
import pandas as pd

from sibc_checkup.features_own import build_windows


def test_windows_exclude_event_day_and_future():
    daily = pd.DataFrame({
        "user_key": ["u1"] * 3,
        "d": pd.to_datetime(["2026-01-01", "2026-01-10", "2026-02-01"]),
        "feature": ["step_count"] * 3,
        "value": [1000.0, 2000.0, 9999.0],
    })
    events = pd.DataFrame({"user_key": ["u1"], "event_date": ["2026-01-10"]})
    out = build_windows(daily, events)
    # 1/10(당일)과 2/1(미래)은 제외 -> w30 중앙값은 1/1의 1000
    assert out.loc[0, "step_count__w30__median"] == 1000.0
    assert out.loc[0, "step_count__w30__days"] == 1


def test_windows_respect_window_length():
    daily = pd.DataFrame({
        "user_key": ["u1"] * 2,
        "d": pd.to_datetime(["2025-10-01", "2026-01-05"]),
        "feature": ["step_count"] * 2,
        "value": [5000.0, 1000.0],
    })
    events = pd.DataFrame({"user_key": ["u1"], "event_date": ["2026-01-10"]})
    out = build_windows(daily, events)
    # w7에는 1/5만 포함 (10/1은 90일 밖)
    assert out.loc[0, "step_count__w7__median"] == 1000.0
    assert "step_count__w90__median" in out.columns
