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
