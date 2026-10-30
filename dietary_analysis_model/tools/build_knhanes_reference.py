"""국민건강영양조사(KNHANES) 기본DB(SAS)에서 맥락 층 외부 참조 분포를 만든다.

	uv run python tools/build_knhanes_reference.py \
		--sas 00_Data/knhanes/HN22/hn22_all.sas7bdat 00_Data/knhanes/HN23/hn23_all.sas7bdat 00_Data/knhanes/HN24/hn24_all.sas7bdat \
		--out-person 01_Results/knhanes/knhanes_person_2022_2024.csv \
		--out-dist data/knhanes_reference_dist.csv \
		--out-model data/knhanes_reference_model.json

산출물 (설계 §3.3 맥락 층, §5.3 집단 참조 품질)
	- out-person: 개인 단위 추출(성·연령·신장·체중·BMI·조사 요일·가중치·영양소). 원자료에 준하므로 git 제외(01_Results).
	- out-dist:   성별 × 연령대 × BMI 구간별 영양소 가중 분포(표본 수, 가중 평균·표준편차, 5/10/25/50/75/90/95 백분위). git 추적.
	- out-model:  영양소별 회귀 표준화 계수(log(영양소) ~ 성별 + 연령 + 연령² + 신장 + 체중 + 주말), 잔차 표준편차. git 추적.
	  사용자 기대값 = exp(Xβ), z = (log(섭취) − Xβ) / 잔차SD, 백분위 = Φ(z). 칸 나누기 없이 성·연령·체형을 연속으로 반영한다.

선정 기준
	- 만 19세 이상, 영양조사 참여(N_EN 있음), 영양조사 가중치 > 0
	- 생리적으로 불가능한 하루 열량 제외: 500 kcal 미만 또는 5,000 kcal 초과 (관행적 범위)
	- 세 해를 합치고 가중치는 연도 수로 나눠 합산 가중치의 규모를 1개년 수준으로 맞춘다
"""

from __future__ import annotations

import argparse
import json
import math

import numpy as np
import pandas as pd
import pyreadstat

REFERENCE_VERSION = "KNHANES_2022_2024_v1"

# KNHANES 변수 → 우리 영양소 코드 (단위는 KNHANES 기준: g, mg, µg RAE, kcal)
NUTRIENTS = {
	"N_EN": ("ENERGY_KCAL", "kcal"),
	"N_CHO": ("CARBOHYDRATE_G", "g"),
	"N_PROT": ("PROTEIN_G", "g"),
	"N_FAT": ("FAT_G", "g"),
	"N_SUGAR": ("SUGAR_G", "g"),
	"N_NA": ("SODIUM_MG", "mg"),
	"N_SFA": ("SATURATED_FAT_G", "g"),
	"N_CHOL": ("CHOLESTEROL_MG", "mg"),
	"N_TDF": ("DIETARY_FIBER_G", "g"),
	"N_CA": ("CALCIUM_MG", "mg"),
	"N_K": ("POTASSIUM_MG", "mg"),
	"N_FE": ("IRON_MG", "mg"),
	"N_PHOS": ("PHOSPHORUS_MG", "mg"),
	"N_VA_RAE": ("VITAMIN_A_UG", "ug RAE"),
	"N_VITC": ("VITAMIN_C_MG", "mg"),
	"N_VITD": ("VITAMIN_D_UG", "ug"),
	"N_VITE": ("VITAMIN_E_MG", "mg"),
	"N_B1": ("THIAMIN_MG", "mg"),
	"N_B2": ("RIBOFLAVIN_MG", "mg"),
	"N_NIAC": ("NIACIN_MG", "mg"),
}
BASE_COLS = ["ID", "year", "sex", "age", "HE_ht", "HE_wt", "HE_BMI", "wt_ntr", "N_DAY", "N_DUSUAL"]
AGE_BANDS = [(19, 29), (30, 49), (50, 64), (65, 74), (75, 120)]
BMI_CLASSES = [("UNDER", 0, 18.5), ("NORMAL", 18.5, 23), ("PRE_OBESE", 23, 25), ("OBESE", 25, 99)]
PCTS = [5, 10, 25, 50, 75, 90, 95]
MIN_CELL_N = 30


def read_one(path: str) -> pd.DataFrame:
	cols = BASE_COLS + list(NUTRIENTS)
	try:
		df, _ = pyreadstat.read_sas7bdat(path, usecols=cols, encoding="cp949")
	except Exception:
		df, _ = pyreadstat.read_sas7bdat(path, usecols=cols)
	return df


def age_band(a: float) -> str:
	for lo, hi in AGE_BANDS:
		if lo <= a <= hi:
			return f"{lo}-{hi if hi < 120 else ''}".rstrip("-") + ("+" if hi >= 120 else "")
	return "NA"


def bmi_class(b: float) -> str:
	for name, lo, hi in BMI_CLASSES:
		if lo <= b < hi:
			return name
	return "NA"


def wquantile(x: np.ndarray, w: np.ndarray, q: float) -> float:
	order = np.argsort(x)
	x, w = x[order], w[order]
	cw = np.cumsum(w) - 0.5 * w
	return float(np.interp(q * w.sum(), cw, x))


def build_dist(df: pd.DataFrame) -> pd.DataFrame:
	rows = []
	for (sex, band, cls), g in df.groupby(["sex_code", "age_band", "bmi_class"]):
		if len(g) < MIN_CELL_N:
			continue
		w = g["weight"].to_numpy()
		for var, (code, unit) in NUTRIENTS.items():
			x = g[var].to_numpy(dtype=float)
			ok = ~np.isnan(x)
			if ok.sum() < MIN_CELL_N:
				continue
			xx, ww = x[ok], w[ok]
			mean = float(np.average(xx, weights=ww))
			sd = float(math.sqrt(np.average((xx - mean) ** 2, weights=ww)))
			row = {"reference_version": REFERENCE_VERSION, "sex": sex, "age_band": band, "bmi_class": cls,
				"nutrient_code": code, "unit": unit, "n": int(ok.sum()), "weighted_mean": round(mean, 3), "weighted_sd": round(sd, 3)}
			for p in PCTS:
				row[f"p{p}"] = round(wquantile(xx, ww, p / 100), 3)
			rows.append(row)
	return pd.DataFrame(rows)


def fit_model(df: pd.DataFrame) -> dict:
	"""가중 최소제곱: log(x) ~ 1 + female + age + age^2 + height + weight + weekend."""
	X = np.column_stack([
		np.ones(len(df)),
		(df["sex_code"] == "F").astype(float),
		df["age"].astype(float),
		(df["age"].astype(float) ** 2) / 100.0,
		df["HE_ht"].astype(float),
		df["HE_wt"].astype(float),
		df["weekend"].astype(float),
	])
	names = ["intercept", "female", "age", "age2_per100", "height_cm", "weight_kg", "weekend"]
	w = df["weight"].to_numpy(dtype=float)
	models = {}
	for var, (code, unit) in NUTRIENTS.items():
		y = df[var].to_numpy(dtype=float)
		ok = ~np.isnan(y) & (y > 0)
		if ok.sum() < 200:
			continue
		ly = np.log(y[ok])
		Xo, wo = X[ok], w[ok]
		sw = np.sqrt(wo)
		beta, *_ = np.linalg.lstsq(Xo * sw[:, None], ly * sw, rcond=None)
		resid = ly - Xo @ beta
		resid_sd = float(math.sqrt(np.average(resid ** 2, weights=wo)))
		ss_tot = float(np.average((ly - np.average(ly, weights=wo)) ** 2, weights=wo))
		models[code] = {
			"unit": unit, "n": int(ok.sum()), "transform": "log",
			"coefficients": {n: round(float(b), 6) for n, b in zip(names, beta)},
			"residual_sd": round(resid_sd, 6),
			"r2_weighted": round(1 - resid_sd ** 2 / ss_tot, 4) if ss_tot > 0 else None,
		}
	return models


def main() -> None:
	ap = argparse.ArgumentParser()
	ap.add_argument("--sas", nargs="+", required=True)
	ap.add_argument("--out-person", required=True)
	ap.add_argument("--out-dist", required=True)
	ap.add_argument("--out-model", required=True)
	args = ap.parse_args()

	frames = [read_one(p) for p in args.sas]
	df = pd.concat(frames, ignore_index=True)
	n_raw = len(df)
	df = df[(df["age"] >= 19) & df["N_EN"].notna() & (df["wt_ntr"] > 0)
		& df["HE_ht"].notna() & df["HE_wt"].notna()].copy()
	n_adult = len(df)
	df = df[(df["N_EN"] >= 500) & (df["N_EN"] <= 5000)].copy()
	n_kept = len(df)
	n_years = df["year"].nunique()
	df["weight"] = df["wt_ntr"] / n_years
	df["sex_code"] = np.where(df["sex"] == 1, "M", "F")
	df["age_band"] = df["age"].apply(age_band)
	df["bmi"] = df["HE_wt"] / (df["HE_ht"] / 100) ** 2
	df["bmi_class"] = df["bmi"].apply(bmi_class)
	# N_DAY: 영양조사 요일, 한글 문자열("월요일"…"일요일"). 주말 = 토·일. 조사는 대부분 평일(화~목)에 이루어져 주말 표본이 적다.
	df["weekend"] = df["N_DAY"].astype(str).str.strip().isin(["토요일", "일요일"]).astype(int)

	person_cols = ["ID", "year", "sex_code", "age", "age_band", "HE_ht", "HE_wt", "bmi", "bmi_class", "N_DAY", "weekend",
		"N_DUSUAL", "wt_ntr", "weight"] + list(NUTRIENTS)
	df[person_cols].rename(columns={v: k for v, (k, _) in NUTRIENTS.items()}).to_csv(args.out_person, index=False, encoding="utf-8-sig")

	dist = build_dist(df)
	dist.to_csv(args.out_dist, index=False, encoding="utf-8-sig")

	models = fit_model(df)
	out = {
		"reference_version": REFERENCE_VERSION,
		"source": "국민건강영양조사 기본DB 2022·2023·2024 (질병관리청 원시자료)",
		"selection": {"rows_raw": n_raw, "adults_with_nutrition_and_anthropometry": n_adult, "kept_after_energy_filter": n_kept,
			"energy_filter_kcal": [500, 5000], "min_age": 19, "weight": "wt_ntr / n_years"},
		"design_columns": ["intercept", "female", "age", "age2_per100", "height_cm", "weight_kg", "weekend"],
		"usage": "expected_log = Σ coef·x ; z = (log(intake) − expected_log) / residual_sd ; percentile = Φ(z)",
		"models": models,
	}
	with open(args.out_model, "w", encoding="utf-8") as fh:
		json.dump(out, fh, ensure_ascii=False, indent=1)
	print(f"rows raw={n_raw} adults={n_adult} kept={n_kept} years={n_years}")
	print(f"dist rows={len(dist)} cells={dist[['sex','age_band','bmi_class']].drop_duplicates().shape[0]} -> {args.out_dist}")
	print(f"models={len(models)} -> {args.out_model}; person -> {args.out_person}")


if __name__ == "__main__":
	main()
