-- independent recount: site-linked users with operator/test flags, first login date (KST) and withdrawal date (KST); run 2026-11-19, read-only session (timezone Asia/Seoul)
with site as (select c.user_id, min(c.linked_dt) ld from ichms.auth_user_customer c where c.customer_id in ('2e0a3387-7058-4f9e-a134-2017f7b7000b','778d4ff7-ab76-4070-a9a9-716fac93d9c9') group by 1),
op as (select distinct user_id from ichms.auth_user_customer where customer_id in ('51d08d27-5063-49de-bb39-048036a3b98c','5ed973ec-87d8-4ff9-92a9-59a0587b8cc8','447662ba-7277-49c1-856e-fe1b0ec10381')),
te as (select distinct mg.member_id user_id from ichms.oper_member_group mg join ichms.oper_group g using (oper_group_sn) where g.group_name like '%테스트%'),
fl as (select user_id, min((login_dt at time zone 'Asia/Seoul')::date) d0 from ichms.auth_user_login_history group by 1),
wd as (select user_id, max((withdraw_dt at time zone 'Asia/Seoul')::date) wd from ichms.auth_user_withdraw_history group by 1)
select s.user_id, fl.d0, wd.wd, (s.user_id in (select user_id from op)) is_op, (s.user_id in (select user_id from te)) is_test from site s left join fl using (user_id) left join wd using (user_id);
