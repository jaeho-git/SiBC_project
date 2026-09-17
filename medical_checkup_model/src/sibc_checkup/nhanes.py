"""NHANES 2011-2014 -> 통합 학습 테이블의 공공(public) 행.

스키마 앵커링(v1.3): SiBC 스키마에 있는 특징만 생성한다.
- demo_age, demo_sex           <- DEMO (RIDAGEYR, RIAGENDR)
- grip_strength_kg             <- MGX  (MGDCGSZ, kg — SiBC 악력과 동일 단위)
- activity_daily_volume        <- PAXHR 시간 단위 MIMS의 일합 (브리징: 공공 -> SiBC 방향)
- activity_active_hours        <- MIMS 임계 초과 시간 수
목표: sbp/dbp <- BPX, weight/bmi/waist <- BMX, fasting_glucose <- GLU,
      total_cholesterol <- TCHOL, hdl <- HDL, ldl/triglyceride <- TRIGLY
NHANES 전용 변수(주변광, 인종 등)는 여기서 읽지 않는다.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .env import PROJECT_ROOT

PUBLIC_DIR = PROJECT_ROOT / "00_Data" / "public" / "nhanes"
CYCLES = {"G": "2011_2012", "H": "2013_2014"}

# 활동 시간 판정 임계 (hourly MIMS). PAXHR 분포 기반의 보수적 초기값.
ACTIVE_HOUR_MIMS = 500.0


def _read(cycle: str, stem: str) -> pd.DataFrame:
    path = PUBLIC_DIR / CYCLES[cycle] / f"{stem}_{cycle}.xpt"
    if not path.is_file():
        raise FileNotFoundError(f"missing NHANES file: {path}")
    return pd.read_sas(path, format="xport")


def _mean_of(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    present = [c for c in cols if c in df.columns]
    return df[present].mean(axis=1) if present else pd.Series(np.nan, index=df.index)


def _find_col(df: pd.DataFrame, prefixes: list[str]) -> str | None:
    for p in prefixes:
        for c in df.columns:
            if c.upper().startswith(p):
                return c
    return None


def _activity_from_paxhr(cycle: str) -> pd.DataFrame:
    hr = _read(cycle, "PAXHR")
    mims_col = _find_col(hr, ["PAXMTSH", "PAXMTS"])
    day_col = _find_col(hr, ["PAXDAYH", "PAXDAY"])
    if mims_col is None or day_col is None:
        raise ValueError(
            f"PAXHR_{cycle}: MIMS/day column not found; columns={list(hr.columns)}"
        )
    hr = hr[["SEQN", day_col, mims_col]].rename(columns={day_col: "day", mims_col: "mims"})
    hr = hr[hr["mims"] >= 0]  # 음수 코드는 결측/품질 불량
    daily = hr.groupby(["SEQN", "day"]).agg(
        daily_mims=("mims", "sum"),
        active_hours=("mims", lambda s: int((s > ACTIVE_HOUR_MIMS).sum())),
    ).reset_index()
    person = daily.groupby("SEQN").agg(
        activity_daily_volume=("daily_mims", "median"),
        activity_active_hours=("active_hours", "median"),
        wear_days=("day", "nunique"),
    ).reset_index()
    return person[person["wear_days"] >= 4].drop(columns=["wear_days"])


def build_cycle(cycle: str) -> pd.DataFrame:
    demo = _read(cycle, "DEMO")[["SEQN", "RIDAGEYR", "RIAGENDR"]].rename(
        columns={"RIDAGEYR": "demo_age", "RIAGENDR": "demo_sex"})

    bpx = _read(cycle, "BPX")
    bpx_out = pd.DataFrame({"SEQN": bpx["SEQN"]})
    bpx_out["sbp"] = _mean_of(bpx, ["BPXSY1", "BPXSY2", "BPXSY3"])
    bpx_out["dbp"] = _mean_of(bpx, ["BPXDI1", "BPXDI2", "BPXDI3"])

    bmx = _read(cycle, "BMX")[["SEQN", "BMXWT", "BMXBMI", "BMXWAIST"]].rename(
        columns={"BMXWT": "weight", "BMXBMI": "bmi", "BMXWAIST": "waist"})
    glu = _read(cycle, "GLU")[["SEQN", "LBXGLU"]].rename(columns={"LBXGLU": "fasting_glucose"})
    tchol = _read(cycle, "TCHOL")[["SEQN", "LBXTC"]].rename(columns={"LBXTC": "total_cholesterol"})
    hdl = _read(cycle, "HDL")[["SEQN", "LBDHDD"]].rename(columns={"LBDHDD": "hdl"})
    trig = _read(cycle, "TRIGLY")[["SEQN", "LBXTR", "LBDLDL"]].rename(
        columns={"LBXTR": "triglyceride", "LBDLDL": "ldl"})

    mgx = _read(cycle, "MGX")
    grip_col = "MGDCGSZ" if "MGDCGSZ" in mgx.columns else _find_col(mgx, ["MGDCGSZ"])
    grip = mgx[["SEQN", grip_col]].rename(columns={grip_col: "grip_strength_kg"})

    act = _activity_from_paxhr(cycle)

    out = demo
    for part in (act, grip, bpx_out, bmx, glu, tchol, hdl, trig):
        out = out.merge(part, on="SEQN", how="left")
    # 성인 + 가속도 착용자만 공공 행으로 사용
    out = out[(out["demo_age"] >= 18) & out["activity_daily_volume"].notna()]
    out["user_key"] = "nhanes_" + cycle + "_" + out["SEQN"].astype(int).astype(str)
    return out.drop(columns=["SEQN"])


def build_public_rows() -> pd.DataFrame:
    frames = [build_cycle(c) for c in CYCLES]
    df = pd.concat(frames, ignore_index=True)
    df["source"] = "nhanes"
    df["event_date"] = pd.NA  # 검진·착용이 동일 조사 주기 (단면)
    return df
