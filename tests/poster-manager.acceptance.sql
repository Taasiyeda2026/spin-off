-- Run after poster-cloud.acceptance.sql, using only the synthetic database.
reset role;
truncate poster_private.attempts;
insert into public.users(user_id, auth_user_id, role, is_active, full_name, name) values
  ('manager-a', '00000000-0000-0000-0000-000000000201', 'activities_manager', true, ' Manager A ', null),
  ('manager-b', '00000000-0000-0000-0000-000000000202', 'activities_manager', true, null, 'Manager B');
insert into public.contacts_instructors values
  (101, 'Manager A', 'no'), (102, ' manager a ', 'true'), (103, 'Manager B', 'כן');
insert into public.activities(row_id, emp_id, emp_id_2, school, grade, class_group, gefen_number, activity_manager) values
  ('team-a', 103, '102', 'Fixture A', '4', 'A', '57651', ' MANAGER   A '),
  ('team-b', 103, null, 'Fixture B', '4', 'B', '57651', 'Manager B'),
  ('outside-team', 103, null, 'Fixture C', '4', 'C', '57651', 'Manager A'),
  ('outside-activity', 102, null, 'Fixture D', '4', 'D', '57651', 'Manager B');
insert into poster_private.posters(activity_id, code, creation_id, ticket_hash, state)
select id, code, gen_random_uuid(), extensions.digest(id, 'sha256'), '{"values":{"poster-project":"Fixture"},"media":{}}'
from (values ('team-a','700001'), ('team-b','700002'), ('outside-team','700003'), ('outside-activity','700004')) as seed(id,code);
select jsonb_build_object('id', id) as a from poster_private.posters where activity_id = 'team-a' \gset
select jsonb_build_object('id', id) as b from poster_private.posters where activity_id = 'team-b' \gset

set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000201', false);
select public.spacetech_poster('manage') as managed \gset
select public.poster_assert(jsonb_array_length(:'managed'::jsonb->'activities') = 1
  and :'managed'::jsonb#>>'{activities,0,id}' = 'team-a', 'manager A requires both ownership and an active team assignment');
select public.poster_assert(:'managed'::jsonb->>'code' is null
  and :'managed'::jsonb#>>'{activities,0,posters,0,code}' = '700001', 'manager sees group code without receiving an instructor code');
select public.poster_assert(public.spacetech_poster('load', :'a')->'state' is not null, 'manager can read scoped answers');
select public.poster_assert(public.spacetech_poster('media', :'a'::jsonb ||
  jsonb_build_object('mode','write','hash',repeat('a',64)))->>'allowed' = 'true', 'manager can manage scoped media');
select public.poster_assert(public.spacetech_poster('save', :'a'::jsonb ||
  '{"revision":0,"state":{"values":{"poster-project":"Manager edit"},"media":{}}}')->>'revision' = '1', 'manager can edit');
select public.poster_assert(public.spacetech_poster('load', :'b')->>'error' = 'denied'
  and public.spacetech_poster('delete', :'b')->>'error' = 'denied'
  and public.spacetech_poster('media', :'b'::jsonb || '{"mode":"write"}')->>'error' = 'denied'
  and public.spacetech_poster('save', :'b'::jsonb || '{"revision":0}')->>'error' = 'denied', 'manager A cannot operate on manager B posters');

select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000202', false);
select public.poster_assert(public.spacetech_poster('load', :'a')->>'error' = 'denied'
  and public.spacetech_poster('load', :'b')->'state' is not null, 'manager B is independently scoped');
select public.poster_assert(public.spacetech_poster('delete', :'b')->>'deleted' = 'true', 'manager can soft-delete scoped poster');

select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000102', false);
select public.poster_assert(public.spacetech_poster('load', :'a')->>'revision' = '1'
  and public.spacetech_poster('load', :'b')->>'error' = 'denied', 'instructor access stays independently scoped');

set role anon;
select set_config('request.jwt.claim.sub', '', false);
select public.poster_assert(public.spacetech_poster('resume', jsonb_build_object('code','700001','session',repeat('e',64)))
  ->>'id' = :'a'::jsonb->>'id', 'student can resume own poster');
select public.poster_assert(public.spacetech_poster('load', :'b'::jsonb || jsonb_build_object('session',repeat('e',64)))->>'error' = 'denied',
  'valid student session cannot read another poster');

reset role;
insert into public.users(user_id, auth_user_id, role, is_active, full_name) values
  ('duplicate', '00000000-0000-0000-0000-000000000203', 'activities_manager', true, 'Manager A');
set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000201', false);
select public.poster_assert(public.spacetech_poster('load', :'a')->>'error' = 'denied', 'ambiguous manager display name fails closed');
reset role;
delete from public.users where user_id = 'duplicate';
update public.activities set activity_manager = 'Manager B' where row_id = 'team-a';
set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000201', false);
select public.poster_assert(public.spacetech_poster('load', :'a')->>'error' = 'denied', 'live activity reassignment revokes previous manager');
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000202', false);
select public.poster_assert(public.spacetech_poster('load', :'a')->>'revision' = '1', 'new manager with a team instructor gains access');
reset role;
update public.contacts_instructors set active = 'לא' where emp_id = 103;
set role authenticated;
select public.poster_assert(public.spacetech_poster('load', :'a')->>'error' = 'denied', 'live team change revokes manager');
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000104', false);
select public.poster_assert(public.spacetech_poster('restore', :'b')->>'deleted' = 'false', 'admin restores another team poster');
select public.poster_assert(public.spacetech_poster('load', :'a')->>'revision' = '1'
  and public.spacetech_poster('load', :'b')->'state' is not null, 'admin can read across teams');
select public.poster_assert(public.spacetech_poster('save', :'b'::jsonb ||
  '{"revision":0,"state":{"values":{"poster-project":"Admin edit"},"media":{}}}')->>'revision' = '1',
  'admin can edit without assignment');
