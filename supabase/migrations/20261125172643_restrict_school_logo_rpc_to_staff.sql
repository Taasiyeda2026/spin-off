-- Students read their school logo through their authorized poster session only.
-- School administration requires an authenticated, scoped manager.
revoke execute on function public.spacetech_school_logo(text,jsonb) from anon;
notify pgrst,'reload schema';
