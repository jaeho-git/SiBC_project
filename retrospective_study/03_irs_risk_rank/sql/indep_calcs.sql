-- independent recount: one row per IRS calculation with mode, sex, genotype hash, lifestyle validity and the 14 raw checkup values; run 2026-11-19, read-only
select l.seq, l.user_id, (l.create_date at time zone 'Asia/Seoul') t, l.raw_data->>'Mode' mode, l.raw_data->>'SEX' sex, md5((l.raw_data->'genotypes')::text) gh,
 (jsonb_typeof(l.raw_data->'lifestyleLog')='object' and l.raw_data->'lifestyleLog' <> '{}'::jsonb) life_ok,
 l.raw_data->'medicalRecord'->>'SBP' sbp, l.raw_data->'medicalRecord'->>'DBP' dbp, l.raw_data->'medicalRecord'->>'FastingGlucose' fbg, l.raw_data->'medicalRecord'->>'2_TCHL' tc,
 l.raw_data->'medicalRecord'->>'2_HDL' hdl, l.raw_data->'medicalRecord'->>'2_TG' tg, l.raw_data->'medicalRecord'->>'WEIGHT' wt, l.raw_data->'medicalRecord'->>'HEIGHT' ht,
 l.raw_data->'medicalRecord'->>'2_WAIST' waist, l.raw_data->'medicalRecord'->>'2_HB' hb, l.raw_data->'medicalRecord'->>'2_AST' ast, l.raw_data->'medicalRecord'->>'2_ALT' alt,
 l.raw_data->'medicalRecord'->>'2_R_GTP' gtp, l.raw_data->'medicalRecord'->>'2_CREATINE' cr from irs.irs_data_log l;
