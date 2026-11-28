-- Synthetic fixtures only, after submission/logo acceptance. Transaction rolls back all test data.
reset role;
begin;
insert into public.users(user_id,username,role,is_active,auth_user_id,permissions)
values ('3030','esraaa','business_development_manager',true,'00000000-0000-0000-0000-000000003030','{"view_israa_management":"yes","view_permissions":"no"}');
\ir ../supabase/migrations/20261128104853_poster_manage_all_permission.sql
-- Migration commits intentionally; start a new disposable-data transaction.
begin;
select public.poster_assert((select permissions-'manage_all_posters' = '{"view_israa_management":"yes","view_permissions":"no"}'::jsonb and role='business_development_manager' from public.users where user_id='3030'), 'only poster capability added');
insert into public.activities(row_id,emp_id,school,grade,class_group,gefen_number,activity_manager,activity_season)
values ('global-test-a',101,'Global A','4','A','57651','Manager A','school_2027'),
('global-test-b',103,'Global B','4','B','57651','Manager B','school_2027'),
('global-test-old',103,'Old season','4','B','57651','Manager B','school_2026'),
('global-test-other',103,'Other course','4','B','11111','Manager B','school_2027');
insert into poster_private.posters(activity_id,code,creation_id,ticket_hash,state)
select id,code,gen_random_uuid(),extensions.digest(id,'sha256'),'{"values":{"poster-project":"Synthetic"},"media":{}}'
from (values ('global-test-a','800001'),('global-test-b','800002'),('global-test-old','800003'),('global-test-other','800004')) seed(id,code);
select jsonb_build_object('id',id) a from poster_private.posters where activity_id='global-test-a' \gset
select jsonb_build_object('id',id) b from poster_private.posters where activity_id='global-test-b' \gset
select jsonb_build_object('id',id) old from poster_private.posters where activity_id='global-test-old' \gset
select jsonb_build_object('id',id) other from poster_private.posters where activity_id='global-test-other' \gset
set role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000003030',false);
select public.poster_assert(public.spacetech_poster('load',:'a')->'state' is not null and public.spacetech_poster('load',:'b')->'state' is not null,'cross-manager read');
select public.poster_assert(public.spacetech_poster('manage')->>'admin'='true','poster administration');
select public.poster_assert(public.spacetech_poster('load',:'old')->>'error'='denied' and public.spacetech_poster('load',:'other')->>'error'='denied','season and course scope preserved');
select public.poster_assert(public.spacetech_poster('media',:'b'::jsonb||jsonb_build_object('mode','write','hash',repeat('a',64)))->>'allowed'='true','cross-manager media');
select public.poster_assert(public.spacetech_poster('save',:'a'::jsonb||'{"revision":0,"state":{"values":{"poster-project":"Edited A"},"media":{}}}')->>'revision'='1','edit manager A');
select public.poster_assert(public.spacetech_poster('save',:'b'::jsonb||'{"revision":0,"state":{"values":{"poster-project":"Edited B"},"media":{}}}')->>'revision'='1','edit manager B');
select public.poster_assert(public.spacetech_poster('delete',:'b')->>'deleted'='true','delete synthetic poster');
select public.poster_assert(public.spacetech_poster('restore',:'b')->>'deleted'='false','restore synthetic poster');
reset role;
update public.users set permissions=jsonb_set(permissions,'{manage_all_posters}','"no"') where user_id='3030';
set role authenticated;
select public.poster_assert(public.spacetech_poster('load',:'b')->>'error'='denied' and public.spacetech_poster('manage')->>'error'='denied','revocation immediate');
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000201',false);
select public.poster_assert(public.spacetech_poster('load',:'b')->>'error'='denied','ordinary manager cannot cross teams');
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000101',false);
select public.poster_assert(public.spacetech_poster('load',:'b')->>'error'='denied','instructor cannot cross teams');
set role anon;
select set_config('request.jwt.claim.sub','',false);
select public.poster_assert(public.spacetech_poster('load',:'b')->>'error'='denied','anonymous access denied');
reset role;
rollback;
