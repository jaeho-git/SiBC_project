SELECT
    table_name,
    column_name,
    data_type,
    ordinal_position
FROM information_schema.columns
WHERE table_schema = 'discovery'
  AND table_name IN (
      'disc_medical_user_info',
      'disc_health_user_info',
      'disc_lifelog_user_info',
      'disc_lifelog_user_step'
  )
ORDER BY table_name, ordinal_position;

