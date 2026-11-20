-- 01 wearable extracts, run 2026-11-19 and 2026-11-20 (read-only session, statement_timeout 120000, timezone Asia/Seoul).
-- Output files go to 01_wearable_metrics/00_Data/ (never committed). Dates are KST calendar days.
-- Run each block from retrospective_study/ with 00_common/src/run_extract.py, for example:
--   python3 00_common/src/run_extract.py 01_wearable_metrics/sql/wearable_extracts.sql steps 01_wearable_metrics/00_Data/extract_<date>/steps.csv

-- @extract steps
-- steps.csv: user x day total steps, smallest platform code of the day, number of source rows
select i.user_id, (s.measured_dt at time zone 'Asia/Seoul')::date d, min(i.measure_platform) plat, sum(s.step_cnt) steps, count(*) n
from discovery.disc_lifelog_user_step s join discovery.disc_lifelog_user_info i using (user_lifelog_sn)
group by 1, 2;
-- @end

-- @extract sleep
-- sleep.csv: user x day (day of sleep end) total sleep minutes
select i.user_id, (s.total_measure_end_dt at time zone 'Asia/Seoul')::date d, min(i.measure_platform) plat,
       sum(extract(epoch from s.total_measure_end_dt - s.total_measure_start_dt)) / 60 mins
from discovery.disc_lifelog_user_sleep s join discovery.disc_lifelog_user_info i using (user_lifelog_sn)
group by 1, 2;
-- @end

-- @extract bp
-- bp.csv: user x day x platform x device mean blood pressure.
-- Site measurement (Ulsan centers) = platform 20301103 with device 20301301.
select i.user_id, (b.measured_dt at time zone 'Asia/Seoul')::date d, i.measure_platform plat, i.measure_device_type dev,
       avg(b.systolic) sbp, avg(b.diastolic) dbp, count(*) n
from discovery.disc_lifelog_user_bloodpressure b join discovery.disc_lifelog_user_info i using (user_lifelog_sn)
group by 1, 2, 3, 4;
-- @end

-- @extract body
-- body.csv: user x day x platform x device mean weight and height.
-- Site measurement (Ulsan centers) = platform 20301103.
select i.user_id, (b.measured_dt at time zone 'Asia/Seoul')::date d, i.measure_platform plat, i.measure_device_type dev,
       avg(b.weight) weight, avg(b.height) height
from discovery.disc_lifelog_user_body_info b join discovery.disc_lifelog_user_info i using (user_lifelog_sn)
group by 1, 2, 3, 4;
-- @end

-- Checks added 2026-11-20 (DB_TODO items 6 and 7). Aggregates only; results go to 01_wearable_metrics/docs/local/.

-- @extract site_location
-- site_location.csv: site-measurement records (platform 20301103) by table x customer x device x measure_location.
select t.tbl, i.customer_id, i.measure_device_type dev, coalesce(i.measure_location, '(null)') loc,
       count(*) n_rows, count(distinct i.user_id) n_users,
       min((i.ins_dt at time zone 'Asia/Seoul')::date) first_ins_d, max((i.ins_dt at time zone 'Asia/Seoul')::date) last_ins_d
from (select 'bp' tbl, user_lifelog_sn from discovery.disc_lifelog_user_bloodpressure
      union all select 'body' tbl, user_lifelog_sn from discovery.disc_lifelog_user_body_info) t
join discovery.disc_lifelog_user_info i using (user_lifelog_sn)
where i.measure_platform = '20301103'
group by 1, 2, 3, 4;
-- @end

-- @extract site_location_user
-- site_location_user.csv: user x table x device x measure_location x KST measured day for platform 20301103, used to check
-- whether records from a location outside the Ulsan centres enter the 01 site-measurement baseline or follow-up.
select i.user_id, t.tbl, i.measure_device_type dev, coalesce(i.measure_location, '(null)') loc, (t.measured_dt at time zone 'Asia/Seoul')::date d, count(*) n
from (select 'bp' tbl, user_lifelog_sn, measured_dt from discovery.disc_lifelog_user_bloodpressure
      union all select 'body' tbl, user_lifelog_sn, measured_dt from discovery.disc_lifelog_user_body_info) t
join discovery.disc_lifelog_user_info i using (user_lifelog_sn)
where i.measure_platform = '20301103'
group by 1, 2, 3, 4, 5;
-- @end

-- @extract bp_origin
-- bp_origin.csv: blood-pressure records by platform x device x data_origin (data_origin exists only in the blood-pressure table).
select i.measure_platform plat, i.measure_device_type dev, coalesce(b.data_origin, '(null)') origin,
       count(*) n_rows, count(distinct i.user_id) n_users
from discovery.disc_lifelog_user_bloodpressure b join discovery.disc_lifelog_user_info i using (user_lifelog_sn)
group by 1, 2, 3;
-- @end

-- @extract step_origin
-- step_origin.csv: user x KST step day x platform x device x KST upload day (disc_lifelog_user_info.ins_dt), source rows.
-- The step table has no data_origin column; a record uploaded long after its step day is history imported at a later sync.
select i.user_id, (s.measured_dt at time zone 'Asia/Seoul')::date d, i.measure_platform plat, i.measure_device_type dev,
       (i.ins_dt at time zone 'Asia/Seoul')::date ins_d, count(*) n
from discovery.disc_lifelog_user_step s join discovery.disc_lifelog_user_info i using (user_lifelog_sn)
group by 1, 2, 3, 4, 5;
-- @end

-- Indicator extracts added 2026-11-20 (study 01 covers every wearable indicator). User x KST day aggregates only.

-- @extract activity
-- activity.csv: user x day (session start) exercise sessions and minutes
select i.user_id, (coalesce(a.measured_start_dt, a.measured_dt) at time zone 'Asia/Seoul')::date d, min(i.measure_platform) plat,
       count(*) n_sessions, sum(extract(epoch from a.measured_end_dt - a.measured_start_dt)) / 60 mins
from discovery.disc_lifelog_user_activity a join discovery.disc_lifelog_user_info i using (user_lifelog_sn)
group by 1, 2;
-- @end

-- @extract oxygen_saturation
-- oxygen_saturation.csv: user x day mean SpO2 and number of readings
select i.user_id, (o.measured_dt at time zone 'Asia/Seoul')::date d, min(i.measure_platform) plat,
       avg(o.oxygen_saturation) spo2, count(*) n
from discovery.disc_lifelog_user_oxygen_saturation o join discovery.disc_lifelog_user_info i using (user_lifelog_sn)
group by 1, 2;
-- @end

-- @extract calories
-- calories.csv: user x day calorie records (total and active burned; daily value rule is fixed in the analysis plan)
select i.user_id, (c.measured_dt at time zone 'Asia/Seoul')::date d, min(i.measure_platform) plat,
       sum(c.total_calories_burned) total_kcal, sum(c.active_calories_burned) active_kcal, max(c.total_calories_burned) max_total_kcal, count(*) n
from discovery.disc_lifelog_user_calories c join discovery.disc_lifelog_user_info i using (user_lifelog_sn)
group by 1, 2;
-- @end

-- @extract bodyfat
-- bodyfat.csv: user x day x platform x device mean body composition
select i.user_id, (b.measured_dt at time zone 'Asia/Seoul')::date d, i.measure_platform plat, i.measure_device_type dev,
       avg(b.body_fat_percentage) fat_pct, avg(b.body_fat_mass) fat_mass, avg(b.skeletal_muscle_mass) muscle_mass, count(*) n
from discovery.disc_lifelog_user_bodyfat b join discovery.disc_lifelog_user_info i using (user_lifelog_sn)
group by 1, 2, 3, 4;
-- @end

-- @extract grip_strength
-- grip_strength.csv: user x day x platform x device mean of the stronger hand
select i.user_id, (g.measured_dt at time zone 'Asia/Seoul')::date d, i.measure_platform plat, i.measure_device_type dev,
       avg(greatest(g.left_hand_grip_strength, g.right_hand_grip_strength)) grip, count(*) n
from discovery.disc_lifelog_user_grip_strength g join discovery.disc_lifelog_user_info i using (user_lifelog_sn)
group by 1, 2, 3, 4;
-- @end

-- @extract heartrate_days
-- heartrate_days.csv: user x KST day on which at least one heart-rate record exists (presence only).
-- The heart-rate table is very large, so this block is written to use only the (user_lifelog_sn, measured_dt) index:
-- distinct batches by a recursive skip scan (a LATERAL ... LIMIT 1 step, so every access shows up as a plan node),
-- their first/last time, then one LIMIT 1 probe per day (a LIMIT subquery is not flattened into a join). The plan is still the planner's choice, so always run it with
--   run_extract.py ... heartrate_days <out> --forbid-scan disc_lifelog_user_heartrate
-- which runs EXPLAIN first and refuses to extract unless every access to the table is an index scan. The check is a
-- preflight: the extraction is planned again when it runs, so run both together in one command as above.
-- Daily heart-rate values need a full scan and are left for a separately cleared extract.
with recursive sns as (
  (select h.user_lifelog_sn sn from discovery.disc_lifelog_user_heartrate h order by h.user_lifelog_sn limit 1)
  union all
  select n.sn
  from sns s
  cross join lateral (select h.user_lifelog_sn sn from discovery.disc_lifelog_user_heartrate h
                      where h.user_lifelog_sn > s.sn order by h.user_lifelog_sn limit 1) n
),
b as (
  select s.sn,
         (select h.measured_dt from discovery.disc_lifelog_user_heartrate h
          where h.user_lifelog_sn = s.sn and h.measured_dt is not null order by h.measured_dt limit 1) mn,
         (select h.measured_dt from discovery.disc_lifelog_user_heartrate h
          where h.user_lifelog_sn = s.sn and h.measured_dt is not null order by h.measured_dt desc limit 1) mx
  from sns s
)
select i.user_id, x.kday d, min(i.measure_platform) plat
from b join discovery.disc_lifelog_user_info i on i.user_lifelog_sn = b.sn
cross join lateral (select g::date as kday from generate_series((b.mn at time zone 'Asia/Seoul')::date, (b.mx at time zone 'Asia/Seoul')::date, interval '1 day') g) x
where (select 1 from discovery.disc_lifelog_user_heartrate h
       where h.user_lifelog_sn = b.sn
         and h.measured_dt >= (x.kday::timestamp at time zone 'Asia/Seoul')
         and h.measured_dt < ((x.kday + 1)::timestamp at time zone 'Asia/Seoul')
       limit 1) is not null
group by 1, 2;
-- @end
