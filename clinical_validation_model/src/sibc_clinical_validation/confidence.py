from __future__ import annotations

from typing import Any


def uncalibrated_decision_confidence(
    components: dict[str, float],
) -> dict[str, Any]:
    """Return policy-compliant metadata without implying a diagnosis probability."""

    return {
        "model_decision_confidence": 0.0,
        "confidence_type": "rule_decision_stability_index",
        "calibration_status": "NOT_CALIBRATED",
        "components": dict(components),
    }

