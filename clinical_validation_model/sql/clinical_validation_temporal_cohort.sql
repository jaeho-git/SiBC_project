SELECT
    count(*) FILTER (WHERE s.measured_dt <= CURRENT_TIMESTAMP)::bigint AS non_future_event_count,
    count(*) FILTER (WHERE s.measured_dt > CURRENT_TIMESTAMP)::bigint AS future_event_count
FROM discovery.disc_lifelog_user_step AS s;

