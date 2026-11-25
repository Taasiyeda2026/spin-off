-- Synthetic Dashboard contracts for a fresh local Supabase CLI project.
-- Auth, Storage, PostgREST and Edge Runtime come from Supabase itself.
create table public.users (
  user_id text primary key, auth_user_id uuid unique references auth.users(id),
  emp_id text, role text not null, is_active boolean not null default true,
  full_name text not null, name text, username text not null unique, auth_email text not null
);
create table public.activities (
  row_id text primary key, emp_id bigint, emp_id_2 text,
  school text, grade text, class_group text, gefen_number text, activity_manager text, activity_season text not null default 'school_2027', status text not null default 'פתוח'
);
create table public.contacts_instructors (emp_id bigint, direct_manager text, active text);
alter table public.users enable row level security;
alter table public.activities enable row level security;
alter table public.contacts_instructors enable row level security;
grant select on public.activities to anon, authenticated;
grant insert, update on public.users, public.activities, public.contacts_instructors to service_role;
create policy activities_select_public on public.activities for select using (true);
create function public.lookup_login_user_by_username(p_username text)
returns table(auth_email text, auth_user_id uuid, role text)
language sql security definer set search_path = pg_catalog as $$
  select u.auth_email, u.auth_user_id, u.role from public.users u
  where u.username = lower(btrim(p_username)) and u.is_active
$$;
revoke all on function public.lookup_login_user_by_username(text) from public;
grant execute on function public.lookup_login_user_by_username(text) to anon, authenticated;
