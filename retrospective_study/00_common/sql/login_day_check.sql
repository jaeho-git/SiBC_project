-- Login-day check extracts, run 2026-11-23 (read-only session, timezone Asia/Seoul). User x KST day aggregates only.
-- Output files go to 00_common/00_Data/extract_20261123/ (never committed). Used by 00_common/src/login_day_check.py.
-- Every source time column is timestamptz: it is converted with AT TIME ZONE 'Asia/Seoul', then cut to ::date and
-- extract(hour ...). Rows at or after 2026-11-18 00:00 KST are left out (data cutoff 2026-11-17).
-- Run each block from retrospective_study/ with 00_common/src/run_extract.py, for example:
--   python3 00_common/src/run_extract.py 00_common/sql/login_day_check.sql event_days 00_common/00_Data/extract_<date>/event_days.csv

-- @extract event_days
-- event_days.csv: n_action = user-response event codes (lifestyle survey update, mission detail record response,
-- meal registration, daily feedback response, weekly check-up response); n_any = every event code
select user_id, (created_at at time zone 'Asia/Seoul')::date d,
       count(*) filter (where event_type in ('40303101','40303104','40303105','40303106','40303117')) n_action,
       count(*) n_any
from sibc.user_event_log
where created_at < '2026-11-18 00:00:00+09'
group by 1, 2;
-- @end

-- @extract inbound_days
-- inbound_days.csv: push clicks and floating-window dismissals
select user_id, (occurred_at at time zone 'Asia/Seoul')::date d, count(*) n
from sibc.inbound_event_log
where occurred_at < '2026-11-18 00:00:00+09' and user_id is not null
group by 1, 2;
-- @end

-- @extract mood_days
-- mood_days.csv: mood record responses by response time
select user_id, (responded_at at time zone 'Asia/Seoul')::date d, count(*) n
from sibc.jitai_user_mood_record
where responded_at is not null and responded_at < '2026-11-18 00:00:00+09'
group by 1, 2;
-- @end

-- @extract weekly_checkup_days
-- weekly_checkup_days.csv: weekly check-up answers by answer time
select user_id, (answered_at at time zone 'Asia/Seoul')::date d, count(*) n
from sibc.weekly_checkup_answer
where answered_at is not null and answered_at < '2026-11-18 00:00:00+09'
group by 1, 2;
-- @end

-- @extract login_hours_days
-- login_hours_days.csv: one login-history row is one issued token; n = tokens that day, n_night = tokens 01:00-05:59,
-- first_h / last_h = first and last hour (0-23) of the day
select user_id, (login_dt at time zone 'Asia/Seoul')::date d, count(*) n,
       count(*) filter (where extract(hour from login_dt at time zone 'Asia/Seoul') between 1 and 5) n_night,
       min(extract(hour from login_dt at time zone 'Asia/Seoul'))::int first_h,
       max(extract(hour from login_dt at time zone 'Asia/Seoul'))::int last_h
from ichms.auth_user_login_history
where login_dt < '2026-11-18 00:00:00+09'
group by 1, 2;
-- @end
