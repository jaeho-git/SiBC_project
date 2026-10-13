"""산출 v2 계약: 실측·예측 분리, 예측 입력에 같은 항목 측정값 없음, 판정 필드 없음."""
import json

from sibc_checkup import predict as P


def test_units_and_labels_cover_all_items():
    from sibc_checkup.schema import target_names
    for t in target_names():
        assert t in P.UNITS and t in P.KOR


def test_forbidden_inputs_regex():
    assert P.FORBIDDEN_INPUT.match("bp_systolic_measured__w30__median")
    assert P.FORBIDDEN_INPUT.match("body_weight_measured__w7__mean")
    assert not P.FORBIDDEN_INPUT.match("step_count__w7__median")
    assert not P.FORBIDDEN_INPUT.match("anchor_prev_label__sbp")


def test_joint_model_inputs_exclude_same_item_measurements():
    if not (P.JOINT_DIR / "sbp.joblib").is_file():
        return
    assert P.joint_inputs_are_clean()


def test_schema_separates_measured_and_predicted_and_excludes_judgment():
    s = P.write_schema()
    assert set(s["kind"]) == {"MEASURED", "PREDICTED"}
    assert set(s["method"]) == {"DEVICE", "DEVICE_DERIVED", "HISTORY", "HISTORY_WEARABLE", "WEARABLE_ONLY"}
    assert set(s["validation"]) == {"VALIDATED_OWN", "REFERENCE_ONLY", "UNVALIDATED", "N/A"}
    assert any("판정" in g for g in s["guarantees"]) and any("측정값을 입력으로 쓰지 않는다" in g for g in s["guarantees"])
    for f in s["fields"]:
        assert not f.startswith(("flag_", "tier_", "refer_", "direction_", "risk_")), f
    assert json.loads(P.SCHEMA_PATH.read_text())["version"] == "2.0"
