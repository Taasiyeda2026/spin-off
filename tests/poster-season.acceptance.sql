-- Run after the other fixture suites on a disposable PostgreSQL database.
reset role;
truncate poster_private.attempts;
insert into public.activities
  (row_id, emp_id, school, grade, class_group, gefen_number, activity_manager, activity_season, status)
values
  ('season-current',101,'Current','4','A','57651','Manager A','school_2027','סגור'),
  ('season-old',101,'Historical','4','A','57651','Manager A','school_2026','סגור'),
  ('season-other',101,'Other program','4','A','11111','Manager A','school_2027','פתוח');
insert into poster_private.posters(activity_id, code, creation_id, ticket_hash, state)
values ('season-old','799001',gen_random_uuid(),extensions.digest('season-old','sha256'),'{"values":{"poster-project":"Historical"},"media":{}}');
select jsonb_build_object('id',id) as historical from poster_private.posters where activity_id='season-old' \gset
insert into poster_private.sessions(token_hash,poster_id,expires_at)
select poster_private.token_hash(repeat('f',64)),id,now()+interval '1 hour'
from poster_private.posters where activity_id='season-old';

set role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000101',false);
select public.spacetech_poster('manage')->>'code' as instructor_code \gset
select public.poster_assert(exists (
  select 1 from jsonb_array_elements(public.spacetech_poster('manage')->'activities') a where a->>'id'='season-current'
), 'the approved scope uses program and season without adding a status rule');

set role anon;
select set_config('request.jwt.claim.sub','',false);
select public.spacetech_poster('activities',jsonb_build_object('code',:'instructor_code','ticket',repeat('9',64))) as offered \gset
select public.poster_assert(not exists (
  select 1 from jsonb_array_elements(:'offered'::jsonb->'activities') a where a->>'id' in ('season-old','season-other')
), 'student lookup excludes earlier seasons and other programs');
select public.poster_assert(public.spacetech_poster('create',jsonb_build_object(
  'activityId','season-old','ticket',repeat('9',64),'session',repeat('3',64),
  'requestId',gen_random_uuid(),'participants',jsonb_build_array('Fixture')
))->>'error'='denied','a valid current instructor ticket cannot create a historical poster');
select public.poster_assert(public.spacetech_poster('resume',jsonb_build_object(
  'code','799001','session',repeat('4',64)
))->>'error'='code','historical code cannot open a new student session');
select public.poster_assert(public.spacetech_poster('load',:'historical'::jsonb ||
  jsonb_build_object('session',repeat('f',64)))->>'error'='denied','existing student session cannot open a historical poster');

set role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000104',false);
select public.poster_assert(not exists (
  select 1 from jsonb_array_elements(public.spacetech_poster('manage')->'activities') a where a->>'id' in ('season-old','season-other')
), 'admin listing excludes earlier seasons and other programs');
select set_config('test.historical',:'historical',false);
do $$
declare action text;
begin
  foreach action in array array['load','save','media','delete','restore','archive','unarchive','rotate'] loop
    perform public.poster_assert(public.spacetech_poster(action,current_setting('test.historical')::jsonb)->>'error'='denied',
      'admin historical ' || action || ' denied');
  end loop;
end
$$;
reset role;
select public.poster_assert(exists(select 1 from poster_private.posters where activity_id='season-old'
  and state#>>'{values,poster-project}'='Historical' and deleted_at is null and archived_at is null), 'historical poster data remains intact');
