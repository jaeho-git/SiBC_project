-- 02 health checkup extract (read-only session, statement_timeout 120000, timezone Asia/Seoul).
-- Source: the approved checkup source of medical_checkup_model (docs/SiBC_웨어러블_건강검진예측모델_구축가이드_20260901.md):
--   discovery.disc_medical_user_info.user_health_sn -> discovery.disc_health_user_info.health_info_data
--   (JSON array; elements with medicalUserMeasDetails; exam date = measuredDt).
-- Site measurements (lifelog tables), IRS medical inputs and user_checkup_log are NOT used for study 02.
-- Output: 02_checkup_metrics/00_Data/<extract folder>/checkup_events.csv (never committed).
-- One row per user x source record x exam element x detail field.
--
-- Version 2 (used from the 2026-11-20 extract): adds the full insertion timestamp (ins_ts, KST) and stable record keys
-- (health_sn, elem_no, det_no) so that "latest inserted value" is deterministic, and keeps blank / null values so that
-- a newer blank entry can supersede an older value (build_usable_users.py drops invalid values only after choosing the
-- latest insertion). The 2026-11-19 file was produced by version 1, which had only ins_d and dropped blank values.
-- @extract checkup_events
WITH h AS (
  SELECT h.* FROM discovery.disc_health_user_info h
  WHERE json_typeof(h.health_info_data) = 'array'
    AND EXISTS (SELECT 1 FROM discovery.disc_medical_user_info m WHERE m.user_health_sn = h.user_health_sn)
),
elems AS (
  SELECT h.user_id::text user_id, h.source_se_cd src, h.ins_dt, h.user_health_sn health_sn, e.elem, e.elem_no
  FROM h, json_array_elements(h.health_info_data) WITH ORDINALITY e(elem, elem_no)
),
det AS (
  SELECT x.user_id, x.src, x.ins_dt, x.health_sn, x.elem_no, x.elem->>'measuredDt' measured_dt, d.det, d.det_no
  FROM elems x, json_array_elements(x.elem->'medicalUserMeasDetails') WITH ORDINALITY d(det, det_no)
  WHERE x.elem->'medicalUserMeasDetails' IS NOT NULL
)
SELECT user_id, src, (ins_dt at time zone 'Asia/Seoul')::date ins_d,
       to_char(ins_dt at time zone 'Asia/Seoul', 'YYYY-MM-DD HH24:MI:SS.US') ins_ts, health_sn, elem_no, det_no,
       measured_dt, lower(trim(det->>'fieldNm')) field_nm, trim(det->>'value') value
FROM det
WHERE lower(trim(det->>'fieldNm')) IN ('height', 'weight', 'bmi', 'waist', 'bloodpressure', 'systolic', 'diastolic',
                                       'fastingbloodsuger', 'fastingglucose', 'totalcholesterol', 'triglyceride',
                                       'hdlcholesterol', 'ldlcholesterol')
ORDER BY user_id, health_sn, elem_no, det_no;
-- @end

-- Version 1 (used for the 2026-11-19 file), kept for provenance and for comparing versions on the same day:
-- @extract checkup_events_v1
WITH h AS (SELECT h.* FROM discovery.disc_health_user_info h WHERE json_typeof(h.health_info_data)='array'
           AND EXISTS (SELECT 1 FROM discovery.disc_medical_user_info m WHERE m.user_health_sn=h.user_health_sn)),
elems AS (SELECT h.user_id::text user_id, h.source_se_cd src, h.ins_dt, json_array_elements(h.health_info_data) e FROM h),
det AS (SELECT user_id, src, ins_dt, e->>'measuredDt' measured_dt, json_array_elements(e->'medicalUserMeasDetails') d
        FROM elems WHERE e->'medicalUserMeasDetails' IS NOT NULL)
SELECT user_id, src, (ins_dt at time zone 'Asia/Seoul')::date ins_d, measured_dt, lower(trim(d->>'fieldNm')) field_nm,
       trim(d->>'value') value FROM det
WHERE nullif(trim(d->>'value'),'') IS NOT NULL AND lower(trim(d->>'fieldNm')) IN ('height','weight','bmi','waist',
  'bloodpressure','systolic','diastolic','fastingbloodsuger','fastingglucose','totalcholesterol','triglyceride',
  'hdlcholesterol','ldlcholesterol');
-- @end
