"""가명화: 원본 user_id(UUID)는 디스크 산출물에 저장하지 않는다."""
from __future__ import annotations

import hashlib

from .env import pseudo_salt


def pseudonymize(user_id: str) -> str:
    digest = hashlib.sha256(f"{pseudo_salt()}::{user_id}".encode()).hexdigest()
    return f"u_{digest[:16]}"
