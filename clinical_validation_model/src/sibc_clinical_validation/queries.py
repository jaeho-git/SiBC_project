from __future__ import annotations

from .config import ACTIVE_ENVIRONMENT, PrototypeConfig
from .sql_guard import ManagedQuery, load_managed_query


def health_check_query() -> ManagedQuery:
    return load_managed_query("health_check")


def wearable_query() -> ManagedQuery:
    return load_managed_query("wearable")


def temporal_cohort_query() -> ManagedQuery:
    return load_managed_query("temporal_cohort")


def data_quality_query() -> ManagedQuery:
    return load_managed_query("data_quality")


def release_query_bundle(config: PrototypeConfig) -> tuple[ManagedQuery, ...]:
    """Return only hash-pinned release read queries; no environment fallback."""

    if config.data_env != ACTIVE_ENVIRONMENT or config.execution_mode != "db":
        raise RuntimeError("BLOCKED_BY_RELEASE_ACCESS")
    return (
        health_check_query(),
        wearable_query(),
        temporal_cohort_query(),
        data_quality_query(),
    )
