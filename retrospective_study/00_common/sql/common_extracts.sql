-- Common extracts for studies 01-03: users.csv and login.csv.
-- Original statements of the 2026-11-18/19 extracts (whitespace reformatted only; the logic is unchanged).
-- Run each block with 00_common/src/run_extract.py (read-only session through db_query.sh, timezone Asia/Seoul):
--   python3 00_common/src/run_extract.py 00_common/sql/common_extracts.sql users 00_common/00_Data/extract_<date>/users.csv
-- Output files are never committed. Site, operator and public customer ids are the approved ids in 00_common/README.md.

-- @extract users
-- users.csv: one row per user (ichms auth users plus sibc master users without an auth row).
-- Site links: earliest link to the site A / site B deployment customer and whether an active link remains; operator customers; public customer;
-- app customer link; latest withdrawal; test-group membership; current operator-group names.
select u.user_id,
       u.created_dt auth_created,
       m.joined_dt,
       m.created_at master_created,
       m.age,
       m.sex,
       (select min(linked_dt) from ichms.auth_user_customer c where c.user_id=u.user_id and c.customer_id='2e0a3387-7058-4f9e-a134-2017f7b7000b') site_a_linked,
       (select bool_or(unlinked_dt is null) from ichms.auth_user_customer c where c.user_id=u.user_id and c.customer_id='2e0a3387-7058-4f9e-a134-2017f7b7000b') site_a_active,
       (select min(linked_dt) from ichms.auth_user_customer c where c.user_id=u.user_id and c.customer_id='778d4ff7-ab76-4070-a9a9-716fac93d9c9') site_b_linked,
       (select bool_or(unlinked_dt is null) from ichms.auth_user_customer c where c.user_id=u.user_id and c.customer_id='778d4ff7-ab76-4070-a9a9-716fac93d9c9') site_b_active,
       exists(select 1 from ichms.auth_user_customer c where c.user_id=u.user_id and c.customer_id in ('51d08d27-5063-49de-bb39-048036a3b98c','5ed973ec-87d8-4ff9-92a9-59a0587b8cc8','447662ba-7277-49c1-856e-fe1b0ec10381')) is_operator,
       exists(select 1 from ichms.auth_user_customer c where c.user_id=u.user_id and c.customer_id='b04d38cb-aa0c-463d-a21d-30900589050e') is_public,
       (select min(linked_dt) from ichms.auth_user_customer c where c.user_id=u.user_id and c.customer_id='b576a0e4-82c4-4c7e-a066-850c7383bcb8') app_linked,
       (select max(withdraw_dt) from ichms.auth_user_withdraw_history w where w.user_id=u.user_id) withdraw_dt,
       exists(select 1 from ichms.oper_member_group mg join ichms.oper_group g using (oper_group_sn) where mg.member_id=u.user_id and g.group_name like '%테스트%') in_test_group,
       (select string_agg(distinct g.group_name, '|') from ichms.oper_member_group mg join ichms.oper_group g using (oper_group_sn) where mg.member_id=u.user_id and mg.deleted_dt is null) grp
from (select user_id, created_dt from ichms.auth_user union select user_id, null from sibc.user_master where user_id not in (select user_id from ichms.auth_user)) u left join sibc.user_master m using (user_id);
-- @end

-- @extract login
-- login.csv: user x customer x KST day login count.
select user_id,
       customer_id,
       (login_dt at time zone 'Asia/Seoul')::date d,
       count(*) n
from ichms.auth_user_login_history
group by 1,2,3;
-- @end
