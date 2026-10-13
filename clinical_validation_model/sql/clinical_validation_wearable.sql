SELECT
    count(*)::bigint AS step_record_count,
    count(DISTINCT i.user_id)::bigint AS pseudonymization_required_user_count,
    min(s.measured_dt) AS earliest_measured_datetime,
    max(s.measured_dt) AS latest_measured_datetime
FROM discovery.disc_lifelog_user_step AS s
JOIN discovery.disc_lifelog_user_info AS i
  ON i.user_lifelog_sn = s.user_lifelog_sn
WHERE s.measured_dt IS NOT NULL;

