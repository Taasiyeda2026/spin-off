-- Run this single SELECT via the authorized reader for szinlhjuwyiyszdpsdop.
-- Share the report cell. It contains schema metadata and aggregate counts only.
with required_columns as (
  select table_schema, table_name, column_name, data_type, udt_name, is_nullable
  from information_schema.columns
  where table_schema = 'public' and (
    (table_name = 'activities' and column_name in
      ('row_id','gefen_number','emp_id','emp_id_2','school','grade','class_group','activity_manager','activity_season','status'))
    or (table_name = 'users' and column_name in
      ('user_id','emp_id','auth_user_id','role','is_active','full_name','name','username'))
    or (table_name = 'contacts_instructors' and column_name in ('emp_id','direct_manager','active'))
  ) or (table_schema = 'storage' and table_name = 'buckets'
    and column_name in ('file_size_limit','allowed_mime_types'))
), unique_constraints as (
  select conrelid::regclass::text as relation, contype, pg_get_constraintdef(oid) as definition
  from pg_constraint where conrelid in (to_regclass('public.activities'),to_regclass('public.users'))
    and contype in ('p','u')
), role_names as (
  select distinct role::text as role from public.users
), duplicate_ids as (
  select auth_user_id from public.users where auth_user_id is not null
  group by auth_user_id having count(*) > 1
    and bool_or(is_active and role::text in ('instructor','activities_manager','admin'))
), functions as (
  select n.nspname as schema, p.proname, pg_get_function_identity_arguments(p.oid) as arguments,
    pg_get_function_result(p.oid) as result, p.prosecdef as security_definer,
    has_function_privilege('anon',p.oid,'EXECUTE') as anon_execute
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where (n.nspname,p.proname) in (
    ('public','lookup_login_user_by_username'), ('private','feedback_can_share_staff_activity'),
    ('public','get_manager_team_roster'), ('public','spacetech_poster')
  )
), manager_names as (
  select coalesce(nullif(btrim(full_name), ''), nullif(btrim(name), ''),
    nullif(btrim(username), '')) as name
  from public.users where is_active and role::text = 'activities_manager'
), manager_keys as (
  select name, lower(regexp_replace(name, '[[:space:]]+', ' ', 'g')) as key from manager_names
), classified as (
  select a.emp_id, nullif(btrim(a.emp_id_2), '') as secondary,
    coalesce(nullif(btrim(a.activity_season),''),'unspecified') as season,
    case lower(btrim(coalesce(a.status,'')))
      when 'פתוח' then 'open' when 'open' then 'open'
      when 'סגור' then 'closed' when 'closed' then 'closed'
      else 'other_or_missing' end as lifecycle,
    (select count(*) from manager_keys m
      where m.key = lower(regexp_replace(btrim(a.activity_manager), '[[:space:]]+', ' ', 'g'))) as owner_matches,
    exists(select 1 from manager_keys m join public.contacts_instructors ci
      on lower(btrim(ci.direct_manager)) = lower(m.name)
      where m.key = lower(regexp_replace(btrim(a.activity_manager), '[[:space:]]+', ' ', 'g'))
        and (ci.emp_id::text = a.emp_id::text or ci.emp_id::text = btrim(a.emp_id_2))
        and lower(btrim(coalesce(ci.active::text,''))) not in ('no','false','0','לא')) as team_match
  from public.activities a where a.gefen_number = '57651'
), activity_counts as (
  select count(*) as spacetech_activities, count(emp_id) as with_primary,
    count(*) filter (where secondary !~ '^[0-9]+$') as non_numeric_secondary,
    count(*) filter (where secondary ~ '^0[0-9]+$') as secondary_with_leading_zero,
    count(*) filter (where owner_matches = 0) as no_manager_match,
    count(*) filter (where owner_matches > 1) as ambiguous_manager,
    count(*) filter (where owner_matches = 1 and not team_match) as manager_without_assigned_team_instructor
  from classified
), manager_audit as (
  select season, lifecycle,
    case when emp_id is not null then 'primary_assigned'
      when secondary is not null then 'secondary_only'
      else 'no_assigned_instructor' end as assignment,
    case when owner_matches = 0 then 'no_active_manager'
      when owner_matches > 1 then 'ambiguous_manager'
      when not team_match then 'no_assigned_team_instructor'
      else 'matched' end as manager_scope,
    count(*) as activity_count
  from classified
  group by 1,2,3,4
), policies as (
  select schemaname, tablename, policyname, roles, cmd, permissive,
    coalesce(qual in ('true', '(true)'), false) as unrestricted_select
  from pg_policies where (schemaname,tablename) in (('public','activities'),('storage','objects'))
)
select jsonb_build_object(
  'columns', (select jsonb_agg(to_jsonb(c) order by table_schema,table_name,column_name) from required_columns c),
  'unique_constraints', (select jsonb_agg(to_jsonb(c) order by relation,definition) from unique_constraints c),
  'roles', (select jsonb_agg(role order by role) from role_names),
  'active_staff_without_application_id', (select count(*) from public.users
    where is_active and role::text in ('instructor','activities_manager','admin') and user_id is null),
  'duplicate_linked_staff_identities', (select count(*) from duplicate_ids),
  'functions', (select jsonb_agg(to_jsonb(f) order by schema,proname,arguments) from functions f),
  'feedback_uses_activity_owner', coalesce(position('a.activity_manager' in pg_get_functiondef(to_regprocedure(
    'private.feedback_can_share_staff_activity(text)'))) > 0, false),
  'roster_uses_direct_manager', coalesce(position('ci.direct_manager' in pg_get_functiondef(to_regprocedure(
    'public.get_manager_team_roster(text,text)'))) > 0, false),
  'activity_counts', (select to_jsonb(c) from activity_counts c),
  'manager_audit_by_season_status_and_assignment',
    (select jsonb_agg(to_jsonb(m) order by season,lifecycle,assignment,manager_scope) from manager_audit m),
  'pgcrypto_schema', (select extnamespace::regnamespace::text from pg_extension where extname='pgcrypto'),
  'storage_objects_rls', (select relrowsecurity from pg_class where oid=to_regclass('storage.objects')),
  'storage_service_role_can_select_buckets', has_table_privilege('service_role','storage.buckets','SELECT'),
  'storage_service_role_can_manage_objects', has_table_privilege('service_role','storage.objects','SELECT')
    and has_table_privilege('service_role','storage.objects','INSERT'),
  'poster_bucket_exists', exists(select 1 from storage.buckets where id='spacetech-posters'),
  'poster_schema_exists', to_regnamespace('poster_private') is not null,
  'policies', (select jsonb_agg(to_jsonb(p) order by schemaname,tablename,policyname) from policies p)
) as report;
