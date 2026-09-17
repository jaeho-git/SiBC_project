"""자체 웨어러블 일별 특징.

- 심박 등 대용량 소스는 DB 측에서 일별로 사전집계한다 (공유 DB 부하 관리).
- 시간 누출 방지: 특징은 build_windows()에서 검진일(event_date) 이전 데이터만 사용.
"""
from __future__ import annotations

import pandas as pd

from .db import fetch_df
from .schema import windows
from .security import pseudonymize

# 일별 사전집계 SQL (모두 read-only, 일 단위 grain)
SQL_DAILY = {
    "step_count": """
        SELECT i.user_id::text AS user_id, s.measured_dt::date AS d,
               max(s.step_cnt)::float AS value
        FROM discovery.disc_lifelog_user_step s
        JOIN discovery.disc_lifelog_user_info i USING (user_lifelog_sn)
        GROUP BY 1, 2
    """,
    "heartrate_rest_device": """
        SELECT i.user_id::text AS user_id, h.measured_dt::date AS d,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY h.heartrate_cnt)::float AS value
        FROM discovery.disc_lifelog_user_heartrate h
        JOIN discovery.disc_lifelog_user_info i USING (user_lifelog_sn)
        WHERE trim(h.heartrate_se_cd) = '20301202'   -- 기기 산출 휴지기 심박수
        GROUP BY 1, 2
    """,
    "sleep_duration_min": """
        SELECT i.user_id::text AS user_id, s.total_measure_end_dt::date AS d,
               sum(EXTRACT(EPOCH FROM (s.total_measure_end_dt - s.total_measure_start_dt)) / 60.0)::float AS value
        FROM discovery.disc_lifelog_user_sleep s
        JOIN discovery.disc_lifelog_user_info i ON i.user_lifelog_sn = s.user_lifelog_sn
        WHERE s.total_measure_end_dt > s.total_measure_start_dt
        GROUP BY 1, 2
    """,
    "grip_strength_kg": """
        SELECT i.user_id::text AS user_id, g.measured_dt::date AS d,
               (max(g.left_hand_grip_strength) + max(g.right_hand_grip_strength))::float AS value
        FROM discovery.disc_lifelog_user_grip_strength g
        JOIN discovery.disc_lifelog_user_info i USING (user_lifelog_sn)
        WHERE g.left_hand_grip_strength IS NOT NULL AND g.right_hand_grip_strength IS NOT NULL
        GROUP BY 1, 2
    """,
    "spo2_median": """
        SELECT i.user_id::text AS user_id, o.measured_dt::date AS d,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY o.oxygen_saturation)::float AS value
        FROM discovery.disc_lifelog_user_oxygen_saturation o
        JOIN discovery.disc_lifelog_user_info i USING (user_lifelog_sn)
        GROUP BY 1, 2
    """,
    "bp_systolic_measured": """
        SELECT i.user_id::text AS user_id, b.measured_dt::date AS d,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY b.systolic)::float AS value
        FROM discovery.disc_lifelog_user_bloodpressure b
        JOIN discovery.disc_lifelog_user_info i USING (user_lifelog_sn)
        GROUP BY 1, 2
    """,
    "bp_diastolic_measured": """
        SELECT i.user_id::text AS user_id, b.measured_dt::date AS d,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY b.diastolic)::float AS value
        FROM discovery.disc_lifelog_user_bloodpressure b
        JOIN discovery.disc_lifelog_user_info i USING (user_lifelog_sn)
        GROUP BY 1, 2
    """,
    "body_weight_measured": """
        SELECT i.user_id::text AS user_id, b.measured_dt::date AS d,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY b.weight)::float AS value
        FROM discovery.disc_lifelog_user_body_info b
        JOIN discovery.disc_lifelog_user_info i USING (user_lifelog_sn)
        WHERE b.weight IS NOT NULL
        GROUP BY 1, 2
    """,
}


# 심박(10.6M행) 고해상도 특징 — 공유 DB 부하를 고려해 '단일 패스'로 모든 집계를 계산한다.
# 야간(현지 00~05시) 중앙값·최솟값, 야간 연속차 RMS(RMSSD 대리; RR간격 없이 HR 시계열로 근사),
# 주간 표준편차(SDNN 대리), p90, 안정심박(p10), 중앙값.
SQL_DAILY_HR = """
WITH hr AS (
  SELECT i.user_id::text AS user_id, h.measured_dt::date AS d,
         (h.measured_dt AT TIME ZONE 'Asia/Seoul') AS lt, h.heartrate_cnt::float AS hr
  FROM discovery.disc_lifelog_user_heartrate h
  JOIN discovery.disc_lifelog_user_info i USING (user_lifelog_sn)
  WHERE trim(h.heartrate_se_cd) = '20301201' AND h.heartrate_cnt BETWEEN 30 AND 220
), base AS (
  SELECT user_id, d, hr,
         (EXTRACT(HOUR FROM lt) BETWEEN 0 AND 5) AS is_night,
         hr - LAG(hr) OVER (PARTITION BY user_id, d, (EXTRACT(HOUR FROM lt) BETWEEN 0 AND 5)
                            ORDER BY lt) AS dhr
  FROM hr
)
SELECT user_id, d,
  percentile_cont(0.5) WITHIN GROUP (ORDER BY hr)::float AS heartrate_median,
  percentile_cont(0.1) WITHIN GROUP (ORDER BY hr)::float AS heartrate_rest,
  percentile_cont(0.9) WITHIN GROUP (ORDER BY hr)::float AS heartrate_p90,
  stddev_samp(hr)::float AS heartrate_sd_day,
  (percentile_cont(0.5) WITHIN GROUP (ORDER BY hr) FILTER (WHERE is_night))::float AS heartrate_night_median,
  (min(hr) FILTER (WHERE is_night))::float AS heartrate_night_min,
  sqrt(avg(dhr * dhr) FILTER (WHERE is_night AND dhr IS NOT NULL))::float AS heartrate_rmssd_night
FROM base GROUP BY 1, 2
"""
HR_FEATURES = ["heartrate_median", "heartrate_rest", "heartrate_p90", "heartrate_sd_day",
               "heartrate_night_median", "heartrate_night_min", "heartrate_rmssd_night"]


def fetch_daily_features(use_cache: bool = True) -> pd.DataFrame:
    """모든 자체 소스의 일별 long 테이블 (user_key, d, feature, value).

    공유 DB 부하 관리: 당일 생성된 캐시(00_Data/processed/daily_features_<date>.parquet)가
    있으면 재조회하지 않는다. 캐시는 가명키만 포함하며 git 제외 경로에 저장된다.
    """
    from datetime import date

    from .env import PROJECT_ROOT

    cache_dir = PROJECT_ROOT / "00_Data" / "processed"
    cache = cache_dir / f"daily_features_{date.today().isoformat()}.parquet"
    if use_cache and cache.is_file():
        return pd.read_parquet(cache)
    daily = _fetch_daily_features_db()
    cache_dir.mkdir(parents=True, exist_ok=True)
    daily.to_parquet(cache, index=False)
    return daily


def _fetch_daily_features_db() -> pd.DataFrame:
    frames = []
    for feature, sql in SQL_DAILY.items():
        df = fetch_df(sql)
        if df.empty:
            continue
        df["feature"] = feature
        frames.append(df)
    hr = fetch_df(SQL_DAILY_HR, statement_timeout_ms=900_000)
    if not hr.empty:
        hr_long = hr.melt(id_vars=["user_id", "d"], value_vars=HR_FEATURES,
                          var_name="feature", value_name="value").dropna(subset=["value"])
        frames.append(hr_long)
    daily = pd.concat(frames, ignore_index=True)
    daily["user_key"] = daily["user_id"].map(pseudonymize)
    daily["d"] = pd.to_datetime(daily["d"])
    return daily[["user_key", "d", "feature", "value"]]


def build_windows(daily: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """검진 이벤트별 관측창 특징. event_date '이전' 데이터만 사용 (시간 누출 금지).

    events: (user_key, event_date) — 자체 검진 이벤트
    반환: user_key, event_date, <feature>__w<window>__<stat> ...
    """
    daily = daily.copy()
    events = events.copy()
    events["event_date"] = pd.to_datetime(events["event_date"])
    out_rows = []
    grouped = {k: g for k, g in daily.groupby("user_key")}
    for ev in events.itertuples(index=False):
        g = grouped.get(ev.user_key)
        row: dict = {"user_key": ev.user_key,
                     "event_date": ev.event_date.strftime("%Y-%m-%d")}
        if g is not None:
            hist = g[g["d"] < ev.event_date]
            for w in windows():
                win = hist[hist["d"] >= ev.event_date - pd.Timedelta(days=w)]
                for feature, fg in win.groupby("feature"):
                    v = fg["value"]
                    row[f"{feature}__w{w}__median"] = float(v.median())
                    row[f"{feature}__w{w}__mean"] = float(v.mean())
                    row[f"{feature}__w{w}__std"] = float(v.std()) if len(v) > 1 else 0.0
                    row[f"{feature}__w{w}__days"] = int(fg["d"].nunique())
        out_rows.append(row)
    return pd.DataFrame(out_rows)
