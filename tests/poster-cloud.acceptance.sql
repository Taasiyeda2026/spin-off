-- Execute after the synthetic fixture and migration, never on production.
create function public.poster_assert(ok boolean, label text) returns void language plpgsql as $$
begin
  if ok is distinct from true then raise exception 'FAILED: %', label; end if;
  raise notice 'PASS: %', label;
end
$$;

set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000101', false);
select public.spacetech_poster('manage') as original \gset
select public.poster_assert(:'original'::jsonb ->> 'code' ~ '^[0-9]{4}$', 'four digit instructor code');
select public.poster_assert(public.spacetech_poster('manage') ->> 'code' = :'original'::jsonb ->> 'code', 'stable instructor code');
select public.poster_assert(jsonb_array_length(:'original'::jsonb -> 'activities') = 1, 'primary assignment and program filter');

set role anon;
select set_config('request.jwt.claim.sub', '', false);
select public.poster_assert((select count(*) from public.activities) = 3, 'fixture has broad SELECT');
select public.poster_assert(not has_schema_privilege('anon', 'poster_private', 'USAGE'), 'poster tables inaccessible');
select public.poster_assert(public.spacetech_poster('manage') ->> 'error' = 'denied', 'anonymous management denied');
select repeat('a',64) as ticket, repeat('b',64) as session, repeat('c',64) as other_session \gset
select public.spacetech_poster('activities', jsonb_build_object('code', :'original'::jsonb->>'code', 'ticket', :'ticket')) as offered \gset
select public.poster_assert(jsonb_array_length(:'offered'::jsonb->'activities') = 1, 'only assigned activity offered');
select jsonb_build_object('ticket', :'ticket', 'session', :'session',
  'activityId', 'space', 'requestId', gen_random_uuid(), 'participants', '[]'::jsonb) as creation \gset
select public.poster_assert(public.spacetech_poster('create', :'creation'::jsonb || '{"activityId":"different"}') ->> 'error' = 'denied',
  'creation cannot bypass assignment');
select public.spacetech_poster('create', :'creation') as created \gset
select public.poster_assert(:'created'::jsonb->>'code' ~ '^[1-9][0-9]{5}$', 'six digit group code');
select public.poster_assert(:'created'::jsonb#>>'{state,values,poster-students}' = '' and :'created'::jsonb#>'{state,participants}' = '[]'::jsonb, 'create without participant names');
select public.poster_assert(public.spacetech_poster('create', :'creation')->>'id' = :'created'::jsonb->>'id', 'idempotent create');
select public.poster_assert(public.spacetech_poster('create', :'creation'::jsonb || jsonb_build_object('requestId',gen_random_uuid()))->>'error' = 'denied', 'one poster per ticket');
select jsonb_build_object('id', :'created'::jsonb->>'id', 'session', :'session') as access \gset
select public.poster_assert(public.spacetech_poster('load', :'access')->'state' #>> '{values,poster-school}' = 'Test School', 'activity metadata persisted');
select public.poster_assert(public.spacetech_poster('load', :'access'::jsonb || jsonb_build_object('session',:'other_session'))->>'error' = 'denied', 'foreign session denied');
select public.poster_assert(public.spacetech_poster('media', :'access'::jsonb || jsonb_build_object('mode', 'write', 'hash', repeat('1',64)))->>'allowed' = 'true', 'scoped media access');
select public.poster_assert(public.spacetech_poster('delete', :'access')->>'error' = 'denied', 'student delete denied');
select jsonb_build_object('revision',0,'state', '{"values":{"poster-project":"Draft A","poster-school":"forged"},"media":{}}'::jsonb) || :'access'::jsonb as save \gset
select public.poster_assert(public.spacetech_poster('save', :'save')->>'revision' = '1', 'save advances revision');
select public.poster_assert(public.spacetech_poster('save', :'save')->>'revision' = '1', 'identical retry does not advance revision');
select public.poster_assert(public.spacetech_poster('save', jsonb_set(:'save', '{state,values,poster-project}', '"Draft B"'))->>'error' = 'conflict', 'stale edit rejected');
select public.poster_assert(public.spacetech_poster('resume', jsonb_build_object('code', :'created'::jsonb->>'code', 'session', :'other_session'))
  ->'state'#>>'{values,poster-school}' = 'Test School', 'another device can resume and school is immutable');

begin;
reset role;
update poster_private.sessions set expires_at = now() - interval '1 second';
set role anon;
select public.poster_assert(public.spacetech_poster('load', :'access')->>'error' = 'denied', 'expired sessions deny access');
rollback;

begin;
reset role;
insert into storage.objects values ('spacetech-posters', (:'created'::jsonb->>'id') || '/' || repeat('4',64));
set role anon;
select jsonb_build_object('id', :'created'::jsonb->>'id', 'session', :'session',
  'revision', 1, 'state', jsonb_build_object('values', '{"poster-project":"With picture"}'::jsonb,
    'media', jsonb_build_object('main', repeat('4',64)))) as media_save \gset
select public.poster_assert(public.spacetech_poster('save', jsonb_set(:'media_save',
  '{state,media,main}', to_jsonb(repeat('3',64))))->>'error' = 'invalid', 'unknown or foreign image rejected');
select public.poster_assert(public.spacetech_poster('save', :'media_save')->>'revision' = '2', 'private image reference saved');
select public.poster_assert(public.spacetech_poster('media', :'access'::jsonb ||
  jsonb_build_object('mode','read','hash',repeat('4',64)))->>'allowed' = 'true', 'current image can be read');
select public.poster_assert(public.spacetech_poster('media', :'access'::jsonb ||
  jsonb_build_object('mode','read','hash',repeat('3',64)))->>'error' = 'invalid', 'other image denied');
rollback;

set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000102', false);
select public.poster_assert(public.spacetech_poster('load', jsonb_build_object('id', :'created'::jsonb->>'id'))->>'revision' = '1', 'secondary instructor can load');
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000103', false);
select public.poster_assert(public.spacetech_poster('load', jsonb_build_object('id', :'created'::jsonb->>'id'))->>'error' = 'denied', 'unassigned instructor denied');
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000105', false);
select public.poster_assert(public.spacetech_poster('manage')->>'error' = 'denied', 'inactive instructor denied');

reset role;
update public.activities set emp_id = 103, emp_id_2 = null where row_id = 'space';
insert into storage.objects values ('spacetech-posters', (:'created'::jsonb->>'id') || '/' || repeat('1',64));
set role anon;
select public.poster_assert((select count(*) from storage.objects) = 0, 'private media hidden despite broad Storage policy');

set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000101', false);
select public.poster_assert(public.spacetech_poster('load', jsonb_build_object('id', :'created'::jsonb->>'id'))->>'error' = 'denied', 'previous instructor loses access');
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000103', false);
select public.poster_assert(public.spacetech_poster('load', jsonb_build_object('id', :'created'::jsonb->>'id'))->>'revision' = '1', 'replacement gains access');
select public.spacetech_poster('rotate', jsonb_build_object('id', :'created'::jsonb->>'id')) as rotated \gset
select public.poster_assert(:'created'::jsonb->>'code' <> :'rotated'::jsonb->>'code', 'rotation changes code');
select public.poster_assert(public.spacetech_poster('delete', jsonb_build_object('id', :'created'::jsonb->>'id'))->>'deleted' = 'true', 'authorized soft delete');
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000104', false);
select public.poster_assert(public.spacetech_poster('restore', jsonb_build_object('id', :'created'::jsonb->>'id'))->>'deleted' = 'false', 'admin restore');
select public.poster_assert(public.spacetech_poster('archive', jsonb_build_object('id', :'created'::jsonb->>'id'))->>'archived' = 'true', 'admin archive');
select public.poster_assert(public.spacetech_poster('unarchive', jsonb_build_object('id', :'created'::jsonb->>'id'))->>'archived' = 'false', 'admin unarchive');

set role anon;
select set_config('request.jwt.claim.sub', '', false);
select public.poster_assert(public.spacetech_poster('load', :'access')->>'error' = 'denied', 'old session revoked');
select public.poster_assert(public.spacetech_poster('resume', jsonb_build_object('code', :'created'::jsonb->>'code', 'session', :'session'))->>'error' = 'code', 'old code rejected');
-- Exercise a rush of successful classroom requests and a separate failure budget
-- without affecting fixtures used by the hierarchy suite.
begin;
reset role;
truncate poster_private.attempts;
update public.activities set emp_id = 101 where row_id = 'space';
select jsonb_build_object('code', :'original'::jsonb->>'code') as valid_teacher \gset
set role anon;
select set_config('test.valid_teacher', :'valid_teacher', true);
do $$
declare r jsonb;
begin
  for i in 1..90 loop
    r := public.spacetech_poster('activities', current_setting('test.valid_teacher')::jsonb ||
      jsonb_build_object('ticket', replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '')));
    if not (r ? 'activities') then raise exception 'Classroom request % rejected: %', i, r; end if;
  end loop;
  perform public.poster_assert(true, '90 valid classroom lookups share one instructor code');
end
$$;

reset role;
select min(format('%s', n)) as wrong_code
  from generate_series(100000, 100040) n
  where not exists (select 1 from poster_private.issued_codes c where c.code = n::text) \gset
set role anon;
select set_config('test.wrong_code', :'wrong_code', true);
do $$
declare r jsonb;
begin
  for i in 1..31 loop
    r := public.spacetech_poster('resume', jsonb_build_object(
      'code', current_setting('test.wrong_code'), 'session', repeat('b',64)));
  end loop;
  perform public.poster_assert(r->>'error' = 'rate_limit', 'failed code attempts rate limited');
end
$$;
select public.poster_assert(public.spacetech_poster('resume',
  jsonb_build_object('code', :'rotated'::jsonb->>'code', 'session', repeat('d',64)))->>'error' = 'rate_limit',
  'exhausted failure budget denies even a valid code before lookup');
rollback;

reset role;
delete from public.activities where row_id = 'space';
set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000104', false);
select public.poster_assert(not exists(select 1 from jsonb_array_elements(public.spacetech_poster('manage')->'activities') a
  where a->>'id' = 'space'), 'activity without a verifiable season is hidden even from admin');
select public.poster_assert(public.spacetech_poster('load', jsonb_build_object('id', :'created'::jsonb->>'id'))->>'error' = 'denied',
  'admin cannot open a poster without a verifiable activity');
reset role;
select public.poster_assert(exists(select 1 from poster_private.posters x where x.id::text = :'created'::jsonb->>'id' and x.revision = 1),
  'Dashboard activity deletion preserves historical poster data');
