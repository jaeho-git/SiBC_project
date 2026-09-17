"""release 환경 로더.

프로젝트 상위(SiBC_project/)의 .env.release를 읽는다.
.env.release.ddl 이 존재하면 그것을 우선 사용한다.
release 전용이며 다른 환경으로의 fallback은 하지 않는다.
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # medical_checkup_model/
ENV_DIR = PROJECT_ROOT.parent                        # SiBC_project/

ENV_CANDIDATES = [
    PROJECT_ROOT / ".env.release.ddl",  # medical_checkup_model/ (사용자 배치 위치)
    ENV_DIR / ".env.release.ddl",
    ENV_DIR / ".env.release",
]


RELEASE_DB_NAME = "invites_loop"  # release 전용 계약 — dev/stg 병합 금지


def load_release_env() -> dict[str, str]:
    """Parse the release env file into a dict. Never prints values.

    DB_NAME이 release(invites_loop)가 아닌 파일은 이름이 .release여도 건너뛴다
    (release/dev/stg 사용자 데이터 병합 금지 원칙).
    """
    import sys

    for path in ENV_CANDIDATES:
        if not path.is_file():
            continue
        env = _parse(path)
        if env.get("DB_NAME") != RELEASE_DB_NAME:
            print(
                f"[env] skip {path.name}: DB_NAME={env.get('DB_NAME')!r} is not "
                f"the release database ({RELEASE_DB_NAME!r})",
                file=sys.stderr,
            )
            continue
        return env
    raise FileNotFoundError(
        f"release env with DB_NAME={RELEASE_DB_NAME!r} not found; "
        f"looked for {[str(p) for p in ENV_CANDIDATES]}"
    )


def _parse(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def db_dsn() -> dict[str, str]:
    env = load_release_env()
    user = env.get("DB_USER") or env.get("DB_USERNAME")
    missing = [k for k, v in {
        "DB_HOST": env.get("DB_HOST"), "DB_NAME": env.get("DB_NAME"),
        "DB_USER/DB_USERNAME": user, "DB_PASSWORD": env.get("DB_PASSWORD"),
    }.items() if not v]
    if missing:
        raise KeyError(f".env.release missing keys: {missing}")
    return {
        "host": env["DB_HOST"],
        "host_public": env.get("DB_HOST_PUBLIC", ""),
        "port": env.get("DB_PORT", "5432"),
        "dbname": env["DB_NAME"],
        "user": user,
        "password": env["DB_PASSWORD"],
    }


def pseudo_salt() -> str:
    env = load_release_env()
    return env.get("SIBC_PSEUDO_SALT") or os.environ.get("SIBC_PSEUDO_SALT", "sibc-release-pseudo")
