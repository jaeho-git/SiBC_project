from __future__ import annotations

from .models import ValidationStatus


def decide_handoff(
    status: ValidationStatus,
    rule_status: str | None,
    reference_standard_status: str = "BLOCKED_BY_REFERENCE_STANDARD",
) -> tuple[bool, bool, str, str, bool]:
    technical_gate_passed = status in {
        ValidationStatus.VALIDATED,
        ValidationStatus.VALIDATED_WITH_LIMITATIONS,
    }
    if not technical_gate_passed:
        return (
            False,
            False,
            "BLOCKED",
            f"VALIDATION_STATUS_{status.value}",
            False,
        )
    if rule_status != "APPROVED_FOR_OPERATION":
        return (
            False,
            False,
            "TEST_ONLY_BLOCKED",
            "RULE_NOT_APPROVED_FOR_OPERATION",
            True,
        )
    if reference_standard_status != "APPROVED":
        return (
            False,
            False,
            "BLOCKED",
            "BLOCKED_BY_REFERENCE_STANDARD",
            True,
        )
    mode = (
        "ALLOWED_WITH_LIMITATIONS"
        if status == ValidationStatus.VALIDATED_WITH_LIMITATIONS
        else "ALLOWED"
    )
    return True, True, mode, "VALIDATED_OPERATIONAL_RULE", True
