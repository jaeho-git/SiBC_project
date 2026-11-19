-- Study 03 extracts from irs.irs_data_log and irs.disease_info.
-- Original statements of the 2026-11-18/19 extracts (whitespace reformatted only; the logic is unchanged).
-- Run each block with 00_common/src/run_extract.py (read-only session through db_query.sh, timezone Asia/Seoul).
-- {{seqs_b}}, {{seqs_miss}}, {{seqs_ob}} are filled with --list from seq-list files:
--   seqs_b.txt    written by src/b1.py (baseline / follow-up pairs and bridge pairs)
--   seqs_miss.txt written by src/x7.py (seqs still missing after res_b and res_p1)
--   seqs_ob.txt   baseline and follow-up seqs of the comparison set still missing after res_b, res_p1 and res_miss;
--                 the 2026-11-19 list is kept in 00_Data/frozen_20261119/seqs_ob.txt.
-- Output files are never committed. irs.csv is kept for provenance; the 1-9 pipeline does not read it.

-- @extract irs_full
-- irs_full.csv: one row per calculation; mode, model/algorithm/engine version, sex, age, biological age, district,
-- md5 hashes of genotypes / medicalRecord / lifestyleLog, hypertension IRS-MRS-LRS-PRS values and ranks, SBP / DBP / fasting glucose.
select seq,
       user_id,
       create_date,
       raw_data->>'Mode' mode,
       raw_data->>'modelVersion' ver,
       raw_data->>'algorithmVersion' aver,
       raw_data->>'engineVersion' ever,
       raw_data->>'SEX' sex,
       raw_data->'medicalRecord'->>'1_AGE' age,
       raw_data->>'BiologicalAGE' bage,
       raw_data->>'DIST_ID' dist,
       raw_data ? 'genotypes' has_geno,
       md5((raw_data->'genotypes')::text) geno_h,
       md5((raw_data->'medicalRecord')::text) med_h,
       md5((select jsonb_agg(v order by k) from jsonb_each(raw_data->'lifestyleLog') e(k,v))::text) life_h,
       h->>'IRS' irs_p,
       h->>'MRS' mrs_p,
       h->>'LRS' lrs_p,
       h->>'PRS' prs_p,
       h->>'IRSp' irsp_p,
       h->>'initIRS' init_p,
       h->>'IRS-rank' irs_r,
       h->>'MRS-rank' mrs_r,
       h->>'LRS-rank' lrs_r,
       h->>'PRS-rank' prs_r,
       h->>'IRSp-rank' irsp_r,
       raw_data->'medicalRecord'->>'SBP' sbp,
       raw_data->'medicalRecord'->>'DBP' dbp,
       raw_data->'medicalRecord'->>'FastingGlucose' fbg
from (select *, raw_data->'Results'->'hypertension' h from irs.irs_data_log) z;
-- @end

-- @extract irs_inputs
-- irs_inputs.csv: medicalRecord JSON and flattened lifestyleLog JSON per calculation.
select seq,
       raw_data->'medicalRecord' med,
       (select jsonb_object_agg(k2, v2) from jsonb_each(raw_data->'lifestyleLog') e(k,v), jsonb_each(v) e2(k2,v2)) life
from irs.irs_data_log;
-- @end

-- @extract irs
-- irs.csv: earlier per-calculation summary (hypertension / diabetes / hyperlipidemia ranks and input hashes).
select seq,
       user_id,
       create_date,
       raw_data->>'Mode' mode,
       raw_data->>'modelVersion' ver,
       raw_data->'Results'->'hypertension'->>'IRS-rank' htn_irs,
       raw_data->'Results'->'hypertension'->>'MRS-rank' htn_mrs,
       raw_data->'Results'->'hypertension'->>'LRS-rank' htn_lrs,
       raw_data->'Results'->'hypertension'->>'PRS-rank' htn_prs,
       raw_data->'Results'->'type_2_diabetes'->>'IRS-rank' dm_irs,
       raw_data->'Results'->'hyperlipidemia'->>'IRS-rank' lip_irs,
       md5((raw_data->'medicalRecord')::text) med_h,
       md5((select jsonb_agg(v order by k) from jsonb_each(raw_data->'lifestyleLog') e(k,v))::text) life_h,
       md5((raw_data->'Results')::text) res_h,
       (select count(*) from jsonb_object_keys(raw_data->'Results')) n_dis
from irs.irs_data_log;
-- @end

-- @extract res_b
-- res_b.csv: per seq x disease values and ranks for the seqs in seqs_b.txt.
select seq,
       raw_data->>'SEX' sex,
       d.key disease,
       d.value->>'IRS' irs_p,
       d.value->>'MRS' mrs_p,
       d.value->>'LRS' lrs_p,
       d.value->>'PRS' prs_p,
       d.value->>'IRS-rank' irs_r,
       d.value->>'MRS-rank' mrs_r,
       d.value->>'LRS-rank' lrs_r,
       d.value->>'PRS-rank' prs_r
from irs.irs_data_log,
       jsonb_each(raw_data->'Results') d
where seq in ({{seqs_b}});
-- @end

-- @extract res_p1
-- res_p1.csv: per seq x disease values and ranks for calculations from 2026-07-01 to before 2026-08-02 (KST).
select seq,
       raw_data->>'SEX' sex,
       d.key disease,
       d.value->>'IRS' irs_p,
       d.value->>'MRS' mrs_p,
       d.value->>'LRS' lrs_p,
       d.value->>'PRS' prs_p,
       d.value->>'IRS-rank' irs_r,
       d.value->>'MRS-rank' mrs_r,
       d.value->>'LRS-rank' lrs_r,
       d.value->>'PRS-rank' prs_r
from irs.irs_data_log,
       jsonb_each(raw_data->'Results') d
where create_date >= '2026-07-01 00:00:00+09' and create_date < '2026-08-02 00:00:00+09';
-- @end

-- @extract res_miss
-- res_miss.csv: per seq x disease values and ranks for the seqs in seqs_miss.txt.
select seq,
       raw_data->>'SEX' sex,
       d.key disease,
       d.value->>'IRS' irs_p,
       d.value->>'MRS' mrs_p,
       d.value->>'LRS' lrs_p,
       d.value->>'PRS' prs_p,
       d.value->>'IRS-rank' irs_r,
       d.value->>'MRS-rank' mrs_r,
       d.value->>'LRS-rank' lrs_r,
       d.value->>'PRS-rank' prs_r
from irs.irs_data_log,
       jsonb_each(raw_data->'Results') d
where seq in ({{seqs_miss}});
-- @end

-- @extract res_ob
-- res_ob.csv: per seq x disease values and ranks for the seqs in seqs_ob.txt.
select seq,
       raw_data->>'SEX' sex,
       d.key disease,
       d.value->>'IRS' irs_p,
       d.value->>'MRS' mrs_p,
       d.value->>'LRS' lrs_p,
       d.value->>'PRS' prs_p,
       d.value->>'IRS-rank' irs_r,
       d.value->>'MRS-rank' mrs_r,
       d.value->>'LRS-rank' lrs_r,
       d.value->>'PRS-rank' prs_r
from irs.irs_data_log,
       jsonb_each(raw_data->'Results') d
where seq in ({{seqs_ob}});
-- @end

-- @extract dis_info
-- dis_info.csv: disease id, Korean name and category.
select disease_id,
       disease_nm,
       category_nm
from irs.disease_info;
-- @end
