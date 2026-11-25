-- Disposable fixture only. Run after cloud and manager acceptance fixtures.
reset role;
update public.activities set activity_manager='Manager A' where row_id='team-a';
update public.contacts_instructors set active='כן' where emp_id=103;
create table if not exists public.schools(id bigint primary key,school_name text);
alter table public.activities add column if not exists school_id bigint references public.schools(id);
insert into public.schools values (1,'Fixture A'),(2,'Fixture B');
update public.activities set school_id=case when row_id in ('space','team-a','outside-team') then 1 else 2 end;
\ir ../supabase/migrations/20261125172304_spacetech_submission_school_logos.sql
\ir ../supabase/migrations/20261125172643_restrict_school_logo_rpc_to_staff.sql
reset role;
insert into storage.objects(bucket_id,name) values('spacetech-posters','schools/1/'||repeat('a',64)),('spacetech-posters','schools/2/'||repeat('b',64));
select id::text as poster_a from poster_private.posters where activity_id='team-a' \gset
set role anon;
select set_config('request.jwt.claim.sub','',false);
do $$ begin
  begin
    perform public.spacetech_school_logo('list');
    raise exception 'anonymous logo RPC unexpectedly accessible';
  exception when insufficient_privilege then null;
  end;
end $$;
set role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000101',false);
select public.poster_assert(public.spacetech_school_logo('list')->>'error'='denied','instructors cannot manage logos');
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000201',false);
select public.poster_assert(public.spacetech_school_logo('set',jsonb_build_object('schoolId','2','hash',repeat('b',64)))->>'error'='denied','manager cannot change another school');
select public.poster_assert(public.spacetech_school_logo('set',jsonb_build_object('schoolId','1','hash',repeat('a',64)))->>'saved'='true','manager can set scoped school logo');
select public.poster_assert(public.spacetech_poster('load',jsonb_build_object('id',:'poster_a'))->>'schoolLogo'=repeat('a',64),'existing poster inherits logo by school ID');
select public.poster_assert(public.spacetech_school_logo('media',jsonb_build_object('schoolId','1','hash',repeat('a',64),'mode','read'))->>'allowed'='true','manager can preview school logo');
select public.spacetech_poster('load',jsonb_build_object('id',:'poster_a')) as saved \gset
select public.poster_assert(public.spacetech_poster('submit',jsonb_build_object('id',:'poster_a','revision',(:'saved'::jsonb->>'revision')::bigint))->>'submittedAt' is not null,'submission receipt created');
select public.spacetech_poster('submit',jsonb_build_object('id',:'poster_a','revision',(:'saved'::jsonb->>'revision')::bigint));
reset role;
select public.poster_assert((select count(*)=1 from poster_private.submissions where poster_id=:'poster_a'::uuid),'duplicate submission is idempotent');
select public.poster_assert((select s.activity_id=p.activity_id and s.school_id=1 and s.state=p.state from poster_private.submissions s join poster_private.posters p on p.id=s.poster_id where p.id=:'poster_a'::uuid),'receipt preserves answers and activity/school binding');
set role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000201',false);
select public.poster_assert(public.spacetech_poster('submit',jsonb_build_object('id',:'poster_a','revision',-1))->>'error'='conflict','stale revision cannot submit');
select public.poster_assert(public.spacetech_school_logo('remove','{"schoolId":"1"}')->>'saved'='true','manager can remove logo');
select public.poster_assert(public.spacetech_poster('load',jsonb_build_object('id',:'poster_a'))->>'schoolLogo' is null,'removal propagates to existing poster');
reset role;
select public.poster_assert(not has_table_privilege('authenticated','poster_private.school_logos','UPDATE'),'no direct logo table writes');
select public.poster_assert(not has_table_privilege('anon','poster_private.submissions','SELECT'),'receipts are private');
select 'PASS: school scope, roles, inherited logo, removal, submission binding, stale revision and idempotency';
\ir ../supabase/migrations/20261125174151_editable_poster_school_class.sql
set role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000201',false);
select public.spacetech_poster('load',jsonb_build_object('id',:'poster_a')) as before_edit \gset
select public.spacetech_poster('save',jsonb_build_object('id',:'poster_a',
 'revision',(:'before_edit'::jsonb->>'revision')::bigint,
 'state',jsonb_set(:'before_edit'::jsonb->'state','{values}',
 (:'before_edit'::jsonb#>'{state,values}')||'{"poster-school":"مدرسة معدّلة","poster-class":"الصف الخامس ب"}'::jsonb))) as after_edit \gset
select public.poster_assert(:'after_edit'::jsonb->>'schoolId'=:'before_edit'::jsonb->>'schoolId','editable display labels do not change school ownership');
select public.spacetech_poster('load',jsonb_build_object('id',:'poster_a')) as reloaded_edit \gset
select public.poster_assert(:'reloaded_edit'::jsonb#>>'{state,values,poster-school}'='مدرسة معدّلة' and :'reloaded_edit'::jsonb#>>'{state,values,poster-class}'='الصف الخامس ب','edited school and class persist across reopening');
select public.poster_assert(:'reloaded_edit'::jsonb->>'schoolDefault' is not null and :'reloaded_edit'::jsonb->>'classDefault' is not null,'automatic defaults available separately from edited display labels');
reset role;
set role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000201',false);
select public.spacetech_poster('load',jsonb_build_object('id',:'poster_a')) as before_type \gset
select public.spacetech_poster('save',jsonb_build_object('id',:'poster_a',
 'revision',(:'before_type'::jsonb->>'revision')::bigint,
 'state',jsonb_set(:'before_type'::jsonb->'state','{values}',
 (:'before_type'::jsonb#>'{state,values}')||jsonb_build_object('solution-type','smart','short-desc',repeat('x',135))))) as saved_type \gset
select public.spacetech_poster('load',jsonb_build_object('id',:'poster_a')) as type_reloaded \gset
select public.poster_assert(:'type_reloaded'::jsonb#>>'{state,values,solution-type}'='smart' and length(:'type_reloaded'::jsonb#>>'{state,values,short-desc}')=135,'type and 135-character description persist independently');
reset role;
