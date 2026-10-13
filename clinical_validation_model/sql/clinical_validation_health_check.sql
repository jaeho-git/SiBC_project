SELECT
    count(*)::bigint AS linked_health_record_count,
    count(*) FILTER (WHERE h.health_info_data IS NULL)::bigint AS missing_payload_count
FROM discovery.disc_medical_user_info AS m
JOIN discovery.disc_health_user_info AS h
  ON h.user_health_sn = m.user_health_sn;

