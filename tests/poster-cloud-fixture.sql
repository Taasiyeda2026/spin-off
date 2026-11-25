-- Run on a fresh, disposable PostgreSQL database only.
create role anon;
create role authenticated;
create schema extensions;
create schema auth;
create function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
$$;
grant usage on schema auth to anon, authenticated;
create schema storage;
create table storage.buckets(id text primary key, name text, public boolean, file_size_limit bigint, allowed_mime_types text[]);
create table storage.objects(bucket_id text, name text);
alter table storage.objects enable row level security;
grant usage on schema storage to anon, authenticated;
grant all on storage.objects to anon, authenticated;
create policy fixture_broad_storage on storage.objects for all using (true) with check (true);

create table public.users(user_id text primary key, emp_id bigint, auth_user_id uuid, role text, is_active boolean);
create table public.activities(row_id text primary key, emp_id bigint, emp_id_2 text,
  school text, grade text, class_group text, gefen_number text);
alter table public.activities enable row level security;
grant select on public.activities to anon, authenticated;
create policy activities_select_public on public.activities for select using (true);
insert into public.users values
  ('primary', 101, '00000000-0000-0000-0000-000000000101', 'instructor', true),
  ('secondary', 102, '00000000-0000-0000-0000-000000000102', 'instructor', true),
  ('other', 103, '00000000-0000-0000-0000-000000000103', 'instructor', true),
  ('admin', null, '00000000-0000-0000-0000-000000000104', 'admin', true),
  ('inactive', 101, '00000000-0000-0000-0000-000000000105', 'instructor', false);
insert into public.activities values
  ('space', 101, '102', 'Test School', '4', '4A', '57651'),
  ('different', 103, null, 'Other School', '5', '5A', '57651'),
  ('other-program', 101, null, 'Test School', '4', '4B', '11111');
