begin;
create extension if not exists pgcrypto with schema extensions;
create schema poster_private;
revoke all on schema poster_private from public, anon, authenticated;

create table poster_private.instructor_codes (
  user_id text primary key,
  code text not null unique check (code ~ '^[0-9]{4}$')
);
create table poster_private.tickets (
  token_hash bytea primary key,
  instructor_id text not null references poster_private.instructor_codes(user_id),
  expires_at timestamptz not null
);
create table poster_private.issued_codes (
  code text primary key check (code ~ '^[1-9][0-9]{5}$')
);
create table poster_private.posters (
  id uuid primary key default gen_random_uuid(),
  -- The server validates the live row at creation and on access. A foreign key
  -- here would change the Dashboard's existing activity deletion behavior.
  activity_id text not null,
  code text not null unique check (code ~ '^[1-9][0-9]{5}$'),
  creation_id uuid not null unique,
  ticket_hash bytea not null unique,
  state jsonb not null,
  revision bigint not null default 0,
  updated_at timestamptz not null default now(),
  archived_at timestamptz,
  deleted_at timestamptz
);
create index on poster_private.posters(activity_id);
create table poster_private.sessions (
  token_hash bytea primary key,
  poster_id uuid not null references poster_private.posters(id),
  expires_at timestamptz not null
);
create table poster_private.attempts (
  action text,
  window_seconds integer,
  bucket bigint,
  used integer not null,
  primary key (action, window_seconds, bucket)
);

alter table poster_private.instructor_codes enable row level security;
alter table poster_private.tickets enable row level security;
alter table poster_private.issued_codes enable row level security;
alter table poster_private.posters enable row level security;
alter table poster_private.sessions enable row level security;
alter table poster_private.attempts enable row level security;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('spacetech-posters', 'spacetech-posters', false, 8388608,
  array['image/png','image/jpeg','image/webp','image/gif','image/avif']);

-- Block inherited permissive Storage policies from granting direct browser access.
create policy spacetech_posters_server_only on storage.objects as restrictive
for all to anon, authenticated
using (bucket_id is distinct from 'spacetech-posters')
with check (bucket_id is distinct from 'spacetech-posters');

create function poster_private.random_number(span integer) returns integer
language sql volatile set search_path = pg_catalog as $$
  select (('x' || encode(extensions.gen_random_bytes(4), 'hex'))::bit(32)::bigint % span)::integer
$$;

create function poster_private.admit(p_action text, p_seconds integer, p_limit integer)
returns boolean language plpgsql set search_path = pg_catalog as $$
declare
  current_bucket bigint := floor(extract(epoch from clock_timestamp()) / p_seconds);
  accepted integer;
begin
  insert into poster_private.attempts as counter values (p_action, p_seconds, current_bucket, 1)
  on conflict (action, window_seconds, bucket) do update set used = counter.used + 1
    where counter.used < p_limit
  returning used into accepted;
  return accepted is not null;
end
$$;

create function poster_private.activity_member(p_activity public.activities, p_employee text)
returns boolean language sql immutable set search_path = pg_catalog as $$
  select coalesce(nullif(btrim(p_employee), '') is not null and
    (p_activity.emp_id::text = btrim(p_employee) or btrim(p_activity.emp_id_2) = btrim(p_employee)), false)
$$;

create function poster_private.token_hash(p_token text) returns bytea
language sql immutable set search_path = pg_catalog as $$
  select case when p_token ~ '^[0-9a-f]{64}$' then extensions.digest(p_token, 'sha256') end
$$;

create function poster_private.activity_info(a public.activities) returns jsonb
language sql stable set search_path = pg_catalog as $$
  select jsonb_build_object('id', a.row_id, 'school', a.school, 'grade', a.grade, 'classGroup', a.class_group)
$$;

create function poster_private.poster_info(p poster_private.posters) returns jsonb
language sql stable set search_path = pg_catalog as $$
  select jsonb_build_object('id', p.id, 'activityId', p.activity_id, 'code', p.code,
    'revision', p.revision, 'updatedAt', p.updated_at, 'archived', p.archived_at is not null,
    'deleted', p.deleted_at is not null)
$$;

create function public.spacetech_poster(p_action text, p jsonb default '{}') returns jsonb
language plpgsql security definer set search_path = pg_catalog as $$
declare
  actor public.users;
  instructor public.users;
  activity public.activities;
  poster poster_private.posters;
  instructor_code text;
  generated_code text;
  ticket bytea := poster_private.token_hash(p->>'ticket');
  session_hash bytea := poster_private.token_hash(p->>'session');
  result jsonb;
  full_state jsonb;
  staff boolean;
  admin boolean;
  permitted boolean;
  n integer;
  code_allocated boolean := false;
begin
  if jsonb_typeof(p) is distinct from 'object' or octet_length(p::text) > 65536 then
    return jsonb_build_object('error', 'invalid');
  end if;

  select u.* into actor from public.users u
    where u.auth_user_id = auth.uid() and u.is_active is true
      and u.role::text in ('instructor', 'admin')
      and (select count(*) from public.users linked where linked.auth_user_id = auth.uid()) = 1;
  staff := actor.user_id is not null;
  admin := staff and actor.role::text = 'admin';

  if p_action = 'activities' then
    -- Global budgets apply before lookup, including misses, independent of client headers.
    if not poster_private.admit(p_action, 60, 30) or not poster_private.admit(p_action, 86400, 500) then
      return jsonb_build_object('error', 'rate_limit');
    end if;
    if ticket is null then return jsonb_build_object('error', 'invalid'); end if;
    select u.* into instructor
      from poster_private.instructor_codes c join public.users u on u.user_id::text = c.user_id
      where c.code = p->>'code' and u.is_active is true and u.role::text = 'instructor';
    select coalesce(jsonb_agg(poster_private.activity_info(a) order by a.school, a.grade, a.class_group, a.row_id), '[]')
      into result from public.activities a
      where a.gefen_number = '57651' and poster_private.activity_member(a, instructor.emp_id::text);
    if result = '[]'::jsonb then return jsonb_build_object('error', 'code'); end if;
    insert into poster_private.tickets values (ticket, instructor.user_id::text, now() + interval '20 minutes')
      on conflict do nothing;
    return jsonb_build_object('activities', result);
  end if;

  if p_action = 'create' then
    if ticket is null or session_hash is null or (p->>'requestId') is null
      or jsonb_typeof(p->'participants') is distinct from 'array' then
      return jsonb_build_object('error', 'invalid');
    end if;
    if jsonb_array_length(p->'participants') not between 1 and 8
      or exists (select 1 from jsonb_array_elements(p->'participants') entry
        where jsonb_typeof(entry) <> 'string' or length(btrim(entry #>> '{}')) not between 1 and 80) then
      return jsonb_build_object('error', 'invalid');
    end if;
    -- Lock the ticket to serialize retries and allow only one creation per lookup.
    perform 1 from poster_private.tickets t where t.token_hash = ticket and t.expires_at > now() for update;
    if not found then return jsonb_build_object('error', 'code'); end if;
    select u.* into instructor from poster_private.tickets t
      join public.users u on t.instructor_id = u.user_id::text
      where t.token_hash = ticket and u.is_active is true and u.role::text = 'instructor';
    select a.* into activity from public.activities a
      where a.row_id = p->>'activityId' and a.gefen_number = '57651'
        and poster_private.activity_member(a, instructor.emp_id::text);
    if not found then return jsonb_build_object('error', 'denied'); end if;
    select x.* into poster from poster_private.posters x where x.ticket_hash = ticket;
    if found then
      if poster.creation_id <> (p->>'requestId')::uuid or poster.activity_id <> activity.row_id
        or poster.deleted_at is not null or poster.archived_at is not null then
        return jsonb_build_object('error', 'denied');
      end if;
    else
      full_state := jsonb_build_object('values', jsonb_build_object(
        'poster-school', coalesce(activity.school, ''),
        'poster-class', coalesce(nullif(activity.class_group, ''), activity.grade, ''),
        'poster-students', (select string_agg(entry, ', ' order by ordinal)
          from jsonb_array_elements_text(p->'participants') with ordinality as names(entry, ordinal))),
        'participants', p->'participants');
      for n in 1..40 loop
        generated_code := (100000 + poster_private.random_number(900000))::text;
        insert into poster_private.issued_codes values (generated_code) on conflict do nothing;
        continue when not found;
        insert into poster_private.posters(activity_id, code, creation_id, ticket_hash, state)
          values (activity.row_id, generated_code, (p->>'requestId')::uuid, ticket, full_state)
          returning * into poster;
        exit;
      end loop;
      if poster.id is null then return jsonb_build_object('error', 'capacity'); end if;
    end if;
    insert into poster_private.sessions values (session_hash, poster.id, now() + interval '8 hours')
      on conflict do nothing;
    return poster_private.poster_info(poster) || jsonb_build_object('state', poster.state);
  end if;

  if p_action = 'resume' then
    if not poster_private.admit(p_action, 60, 30) or not poster_private.admit(p_action, 86400, 500) then
      return jsonb_build_object('error', 'rate_limit');
    end if;
    select x.* into poster from poster_private.posters x
      where x.code = p->>'code' and x.deleted_at is null and x.archived_at is null
        and exists (select 1 from public.activities a where a.row_id = x.activity_id and a.gefen_number = '57651');
    if not found or session_hash is null then return jsonb_build_object('error', 'code'); end if;
    insert into poster_private.sessions values (session_hash, poster.id, now() + interval '8 hours')
      on conflict do nothing;
    return poster_private.poster_info(poster) || jsonb_build_object('state', poster.state);
  end if;

  if p_action = 'manage' then
    if not staff then return jsonb_build_object('error', 'denied'); end if;
    if not admin then
      perform pg_advisory_xact_lock(hashtextextended(actor.user_id::text, 94217));
      select c.code into instructor_code from poster_private.instructor_codes c where c.user_id = actor.user_id::text;
      if not found then
        for n in 1..40 loop
          insert into poster_private.instructor_codes values (
            actor.user_id::text, lpad(poster_private.random_number(10000)::text, 4, '0'))
            on conflict do nothing returning code into instructor_code;
          exit when found;
        end loop;
      end if;
      if instructor_code is null then return jsonb_build_object('error', 'capacity'); end if;
    end if;
    with scoped as (
      select a.row_id as id, poster_private.activity_info(a) as info,
        a.school, a.grade, a.class_group
      from public.activities a where a.gefen_number = '57651'
        and (admin or poster_private.activity_member(a, actor.emp_id::text))
      union all
      (select distinct on (x.activity_id) x.activity_id,
        jsonb_build_object('id', x.activity_id, 'school', x.state#>>'{values,poster-school}',
          'classGroup', x.state#>>'{values,poster-class}', 'unavailable', true),
        x.state#>>'{values,poster-school}', null, x.state#>>'{values,poster-class}'
      from poster_private.posters x
      where admin and not exists (select 1 from public.activities a
        where a.row_id = x.activity_id and a.gefen_number = '57651')
      order by x.activity_id, x.updated_at desc)
    )
    select coalesce(jsonb_agg(scoped.info || jsonb_build_object('posters', (
      select coalesce(jsonb_agg(poster_private.poster_info(x) || jsonb_build_object(
        'title', x.state#>>'{values,poster-project}', 'participants', x.state#>>'{values,poster-students}')
        order by x.updated_at desc), '[]')
      from poster_private.posters x where x.activity_id = scoped.id and (admin or x.deleted_at is null)
    )) order by scoped.school, scoped.grade, scoped.class_group, scoped.id), '[]') into result
    from scoped;
    return jsonb_build_object('name', coalesce(to_jsonb(actor)->>'full_name', to_jsonb(actor)->>'name',
      to_jsonb(actor)->>'username', actor.user_id::text), 'code', instructor_code, 'admin', admin, 'activities', result);
  end if;

  select x.* into poster from poster_private.posters x where x.id = (p->>'id')::uuid for update;
  if not found then return jsonb_build_object('error', 'denied'); end if;
  select admin or exists(select 1 from public.activities a where a.row_id = poster.activity_id
    and a.gefen_number = '57651' and staff and poster_private.activity_member(a, actor.emp_id::text))
    into permitted;

  if p_action in ('delete', 'restore', 'archive', 'unarchive', 'rotate') then
    if not permitted or (p_action in ('restore', 'archive', 'unarchive') and not admin) then
      return jsonb_build_object('error', 'denied');
    end if;
    if p_action = 'rotate' then
      if poster.deleted_at is not null or poster.archived_at is not null then
        return jsonb_build_object('error', 'denied');
      end if;
      for n in 1..40 loop
        generated_code := (100000 + poster_private.random_number(900000))::text;
        insert into poster_private.issued_codes values (generated_code) on conflict do nothing;
        if found then
          code_allocated := true;
          update poster_private.posters set code = generated_code where id = poster.id returning * into poster;
          exit;
        end if;
      end loop;
      if not code_allocated then return jsonb_build_object('error','capacity'); end if;
      delete from poster_private.sessions where poster_id = poster.id;
    else
      update poster_private.posters set
        deleted_at = case p_action when 'delete' then coalesce(deleted_at, now()) when 'restore' then null else deleted_at end,
        archived_at = case p_action when 'archive' then coalesce(archived_at, now()) when 'unarchive' then null else archived_at end
        where id = poster.id returning * into poster;
      if p_action in ('archive', 'delete') then delete from poster_private.sessions where poster_id = poster.id; end if;
    end if;
    return poster_private.poster_info(poster);
  end if;

  if poster.deleted_at is not null or (poster.archived_at is not null and not permitted)
    or (not permitted and not exists (select 1 from poster_private.sessions s
      join public.activities a on a.row_id = poster.activity_id and a.gefen_number = '57651'
      where s.token_hash = session_hash and s.poster_id = poster.id and s.expires_at > now())) then
    return jsonb_build_object('error', 'denied');
  end if;

  if p_action = 'load' then
    return poster_private.poster_info(poster) || jsonb_build_object('state', poster.state);
  elsif p_action = 'media' then
    if coalesce(p->>'hash', '') !~ '^[0-9a-f]{64}$' then
      return jsonb_build_object('error', 'invalid');
    end if;
    if p->>'mode' = 'read' and exists (
      select 1 from jsonb_each_text(poster.state->'media') m where m.value = p->>'hash'
    ) then
      return jsonb_build_object('allowed', true);
    end if;
    if p->>'mode' = 'write' and poster.archived_at is null
      and poster_private.admit('upload:' || poster.id::text, 3600, 60)
      and (select count(*) from storage.objects o
        where o.bucket_id = 'spacetech-posters' and o.name like poster.id::text || '/%') < 250 then
      return jsonb_build_object('allowed', true);
    end if;
  elsif p_action = 'save' then
    if poster.archived_at is not null then return jsonb_build_object('error', 'denied'); end if;
    full_state := p->'state';
    if jsonb_typeof(full_state) is distinct from 'object' or jsonb_typeof(full_state->'values') is distinct from 'object'
      or jsonb_typeof(full_state->'media') is distinct from 'object' then
      return jsonb_build_object('error', 'invalid');
    end if;
    if exists (select 1 from jsonb_each_text(full_state->'media') m
      where m.key not in ('main','one','two','logo','background') or m.value is null or m.value !~ '^[0-9a-f]{64}$')
      or full_state ? 'images' or (full_state->'design') ? 'bgImage'
      or full_state::text ~* 'data:[^,]*;base64,'
      or exists (select 1 from jsonb_each_text(full_state->'media') m
        where not exists (select 1 from storage.objects o where o.bucket_id = 'spacetech-posters'
          and o.name = poster.id::text || '/' || m.value)) then
      return jsonb_build_object('error', 'invalid');
    end if;
    full_state := jsonb_set(full_state, '{values}', (full_state->'values') || jsonb_build_object(
      'poster-school', coalesce(poster.state#>>'{values,poster-school}', ''),
      'poster-class', coalesce(poster.state#>>'{values,poster-class}', '')));
    if full_state = poster.state then return poster_private.poster_info(poster); end if;
    if (p->>'revision')::bigint is distinct from poster.revision then
      return jsonb_build_object('error', 'conflict');
    end if;
    update poster_private.posters set state = full_state, revision = revision + 1, updated_at = now()
      where id = poster.id returning * into poster;
    return poster_private.poster_info(poster);
  end if;
  return jsonb_build_object('error', 'invalid');
exception
  when invalid_text_representation or numeric_value_out_of_range then
    return jsonb_build_object('error', 'invalid');
end
$$;

revoke all on function public.spacetech_poster(text, jsonb) from public;
grant execute on function public.spacetech_poster(text, jsonb) to anon, authenticated;
commit;
