"""스키마 앵커링 (가이드 v1.3, 7.2절) 계약 테스트."""
import pytest

from sibc_checkup.schema import (
    assert_no_public_only_columns,
    both_provider_features,
    own_only_features,
    target_names,
)


def test_public_only_feature_rejected():
    # NHANES 주변광 등 공공 전용 변수는 통합 테이블에 들어올 수 없다
    with pytest.raises(ValueError, match="schema anchoring violation"):
        assert_no_public_only_columns(["user_key", "ambient_light__w7__median"])


def test_known_columns_accepted():
    assert_no_public_only_columns([
        "user_key", "event_date", "source", "sample_weight",
        "sbp", "fasting_glucose",
        "step_count__w30__median", "grip_strength_kg__w7__median",
        "anchor_prev_label__sbp", "demo_age",
    ])


def test_targets_are_sibc_18_item_subset():
    # 목표는 SiBC 표준 검진 항목 매핑만 — HbA1c 등 공공 전용 검사항목 금지
    assert "hba1c" not in target_names()
    assert {"sbp", "dbp", "bmi", "fasting_glucose"} <= set(target_names())


def test_provider_partition():
    both, own = set(both_provider_features()), set(own_only_features())
    assert both.isdisjoint(own)
    # 심박·수면은 공공 소스가 없으므로 own 전용이어야 한다 (검증 결과 반영)
    assert {"heartrate_rest", "sleep_duration_min"} <= own
