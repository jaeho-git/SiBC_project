"""자체 사용자 인구통계 특징 (demo_age, demo_sex).

- demo_sex: release invites_loop의 ichms.auth_user_profile.gender_se_cd
  (10101301=남성, 10101302=여성; ichms.com_code_language_map으로 확인)
  -> NHANES 인코딩(1=남, 2=여)으로 통일한다.
- demo_age: iccoli의 tb_ext_user_mapper + tb_user_personal_info.birth(YYMMDD).
  iccoli 접속은 libpq service("iccoli")를 사용하며, 불가하면 결측으로 둔다.
- PII: 생년월일 원문은 메모리에서만 사용하고 나이(정수)만 반환한다.
  원본 uuid는 가명키로 치환된다.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from .db import fetch_df
from .security import pseudonymize

SEX_CODE_MAP = {"10101301": 1, "10101302": 2}  # -> NHANES: 1=male, 2=female
ICCOLI_SERVICE = "iccoli"


def fetch_sex() -> pd.DataFrame:
    df = fetch_df("""
        SELECT user_id::text AS user_id, trim(gender_se_cd) AS gender_se_cd
        FROM ichms.auth_user_profile
    """)
    df["demo_sex"] = df["gender_se_cd"].map(SEX_CODE_MAP)
    df["user_key"] = df["user_id"].map(pseudonymize)
    return df[["user_key", "demo_sex"]].dropna()


def _birth_year(yymmdd: str, today: date) -> int | None:
    if not (isinstance(yymmdd, str) and len(yymmdd) == 6 and yymmdd.isdigit()):
        return None
    yy = int(yymmdd[:2])
    year = 2000 + yy
    if year > today.year - 10:  # 사용자 최소 연령 가정으로 세기 결정
        year = 1900 + yy
    return year


def fetch_birth_year() -> pd.DataFrame:
    """iccoli 매핑 경유 출생연도. 접속 불가 시 빈 프레임 (demo_age는 결측 처리)."""
    import sys

    try:
        import psycopg

        with psycopg.connect(service=ICCOLI_SERVICE,
                             options="-c default_transaction_read_only=on") as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT m.ext_user_uuid::text, p.birth
                    FROM tb_ext_user_mapper m
                    JOIN tb_user_personal_info p USING (user_no)
                    WHERE p.birth IS NOT NULL
                """)
                rows = cur.fetchall()
    except Exception as exc:  # noqa: BLE001 — 선택적 소스: 실패는 결측으로 강등
        print(f"[demo] iccoli unavailable ({type(exc).__name__}); demo_age will be missing",
              file=sys.stderr)
        return pd.DataFrame(columns=["user_key", "birth_year"])

    today = date.today()
    recs = []
    for uuid_str, birth in rows:
        year = _birth_year(birth, today)
        if year is not None:
            recs.append({"user_key": pseudonymize(uuid_str), "birth_year": year})
    return pd.DataFrame(recs).drop_duplicates("user_key")


def add_demo_features(own: pd.DataFrame) -> pd.DataFrame:
    """own rows(user_key, event_date, ...)에 demo_age/demo_sex를 병합."""
    own = own.merge(fetch_sex(), on="user_key", how="left")
    birth = fetch_birth_year()
    if not birth.empty:
        own = own.merge(birth, on="user_key", how="left")
        event_year = pd.to_datetime(own["event_date"]).dt.year
        own["demo_age"] = (event_year - own["birth_year"]).astype("float")
        own.loc[(own["demo_age"] < 0) | (own["demo_age"] > 110), "demo_age"] = pd.NA
        own = own.drop(columns=["birth_year"])
    else:
        own["demo_age"] = pd.NA
    return own
