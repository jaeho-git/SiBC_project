"""KNHANES(국민건강영양조사) -> 통합 학습 테이블의 한국인 공공(knhanes) 행.

역할:
- **한국인 활동→검진 공공 행 (2014-2017)**: 가속도계 PAM(분 단위 걸음·강도)을
  개인 요약으로 집계하고, 같은 사람(ID)의 기본DB 검진값과 결합한다. 미국
  NHANES보다 도메인(한국인) 정합이 우수하다.
- **한국인 검진값 보정 기준 (2010-2024)**: 최신 검진값 분포를 출력 보정
  (calibration) 기준으로 저장한다.

스키마 앵커링(v1.3): SiBC 스키마에 있는 특징만 생성한다. PAM은 실제 걸음
(PAXSTEP)을 제공하므로 step_count 슬롯을 직접 채운다(공공이 own-provider
특징을 채우는 것은 허용 — 금지 대상은 '공공 전용 변수'뿐).
"""
from __future__ import annotations

import pandas as pd

from .env import PROJECT_ROOT

KN_DIR = PROJECT_ROOT / "00_Data" / "public" / "knhanes"

# 검진 기본DB: 사용 가능 연도(포맷 동일 확인). 2010-2024.
CHECKUP_YEARS = list(range(2010, 2025))
# 가속도계 PAM: 2014-2017만 존재.
PAM_YEARS = [2014, 2015, 2016, 2017]

# 기본DB HE_* -> 스키마 목표
CHECKUP_MAP = {
    "HE_sbp": "sbp", "HE_dbp": "dbp",
    "HE_wt": "weight", "HE_BMI": "bmi", "HE_wc": "waist",
    "HE_glu": "fasting_glucose", "HE_chol": "total_cholesterol",
    "HE_HDL_st2": "hdl", "HE_LDL_drct": "ldl", "HE_TG": "triglyceride",
}
# 분 단위 강도 활동 판정 임계 (PAXINTEN counts/min). 보수적 초기값.
ACTIVE_MIN_INTENSITY = 500


def _all_path(year: int):
    yy = f"{year % 100:02d}"
    return KN_DIR / f"ex_ALL_{year}" / f"hn{yy}_all.sas7bdat"


def _pam_path(year: int):
    yy = f"{year % 100:02d}"
    d = KN_DIR / f"ex_PAM_{year}"
    for name in (f"HN{yy}_PAM.sas7bdat", f"hn{yy}_pam.sas7bdat"):
        if (d / name).is_file():
            return d / name
    return None


def load_checkup(year: int) -> pd.DataFrame:
    """기본DB -> (person_key, demo_age, demo_sex, <targets>) per person."""
    df = pd.read_sas(_all_path(year), format="sas7bdat", encoding="latin1")
    id_col = next((c for c in df.columns if c.lower() == "id"), None)
    if id_col is None:
        raise KeyError(f"{year}: no id column in {list(df.columns)[:5]}")
    out = pd.DataFrame()
    out["person_key"] = f"kn{year}_" + df[id_col].astype(str)
    out["demo_age"] = pd.to_numeric(df.get("age"), errors="coerce")
    out["demo_sex"] = pd.to_numeric(df.get("sex"), errors="coerce")  # 1=남,2=여
    for src, tgt in CHECKUP_MAP.items():
        if src in df.columns:
            out[tgt] = pd.to_numeric(df[src], errors="coerce")
    return out


def load_pam_summary(year: int) -> pd.DataFrame:
    """분 단위 PAM -> 개인 요약 (걸음·강도·활동시간의 유효일 중앙값)."""
    path = _pam_path(year)
    if path is None:
        return pd.DataFrame()
    pam = pd.read_sas(path, format="sas7bdat", encoding="latin1")
    pam = pam.rename(columns={c: c.upper() for c in ["id", "paxday", "paxinten", "paxstep"]
                              if c in pam.columns})
    pam["ID"] = pam["ID"].astype(str)
    pam["PAXINTEN"] = pd.to_numeric(pam["PAXINTEN"], errors="coerce").fillna(0)
    pam["PAXSTEP"] = pd.to_numeric(pam.get("PAXSTEP"), errors="coerce").fillna(0)
    pam = pam[pam["PAXINTEN"] >= 0]  # 음수 = 비착용/결측 코드

    # 일별 집계 (ID x PAXDAY)
    daily = pam.groupby(["ID", "PAXDAY"]).agg(
        day_steps=("PAXSTEP", "sum"),
        day_volume=("PAXINTEN", "sum"),
        active_min=("PAXINTEN", lambda s: int((s >= ACTIVE_MIN_INTENSITY).sum())),
        wear_min=("PAXINTEN", lambda s: int((s > 0).sum())),
    ).reset_index()
    daily = daily[daily["wear_min"] >= 600]  # 하루 10시간 이상 착용일만

    person = daily.groupby("ID").agg(
        step_count=("day_steps", "median"),
        activity_daily_volume=("day_volume", "median"),
        active_hours=("active_min", lambda s: float(s.median()) / 60.0),
        valid_days=("PAXDAY", "nunique"),
    ).reset_index()
    person = person[person["valid_days"] >= 4]
    person["person_key"] = f"kn{year}_" + person["ID"].astype(str)
    return person.drop(columns=["ID", "valid_days"])


def build_public_rows() -> pd.DataFrame:
    """2014-2017: PAM 활동요약 + 검진값 결합 -> 한국인 공공 학습 행."""
    frames = []
    for year in PAM_YEARS:
        chk = load_checkup(year)
        pam = load_pam_summary(year)
        if pam.empty:
            continue
        merged = pam.merge(chk, on="person_key", how="inner")
        frames.append(merged)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    # NHANES 브리징과 동일하게 w7 median 슬롯에 매핑
    df = df.rename(columns={
        "step_count": "step_count__w7__median",
        "activity_daily_volume": "activity_daily_volume__w7__median",
        "active_hours": "activity_active_hours__w7__median",
    })
    df["source"] = "knhanes"
    df["user_key"] = df["person_key"]
    df["event_date"] = pd.NA
    return df.drop(columns=["person_key"])


def korean_calibration_reference(years: list[int] | None = None) -> pd.DataFrame:
    """최신 검진값 분포(연령·성별별 평균/표준편차) — 출력 보정 기준."""
    years = years or [2019, 2020, 2021, 2022, 2023, 2024]
    frames = [load_checkup(y) for y in years]
    df = pd.concat(frames, ignore_index=True)
    df["age_band"] = pd.cut(df["demo_age"], [0, 30, 40, 50, 60, 70, 200],
                            labels=["<30", "30s", "40s", "50s", "60s", "70+"])
    rows = []
    for tgt in CHECKUP_MAP.values():
        if tgt not in df.columns:
            continue
        g = df.groupby(["demo_sex", "age_band"], observed=True)[tgt].agg(["mean", "std", "count"])
        for (sex, band), r in g.iterrows():
            rows.append({"target": tgt, "sex": sex, "age_band": str(band),
                         "mean": round(float(r["mean"]), 2) if pd.notna(r["mean"]) else None,
                         "std": round(float(r["std"]), 2) if pd.notna(r["std"]) else None,
                         "n": int(r["count"])})
    return pd.DataFrame(rows)
