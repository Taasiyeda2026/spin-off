begin;
-- Class and school text are editable display values. Identity, logo authorization
-- and submission ownership remain bound to the unchanged activity.school_id.
do $migration$
declare definition text; locked_values text := $old$    full_state := jsonb_set(full_state, '{values}', (full_state->'values') || jsonb_build_object(
      'poster-school', coalesce(poster.state#>>'{values,poster-school}', ''),
      'poster-class', coalesce(poster.state#>>'{values,poster-class}', '')));
$old$;
begin
  definition:=pg_get_functiondef('public.spacetech_poster(text,jsonb)'::regprocedure);
  if position(locked_values in definition)=0 then raise exception 'Expected poster identity display lock was not found';end if;
  execute replace(definition,locked_values,'');
end $migration$;
create or replace function poster_private.poster_info(p poster_private.posters) returns jsonb
language sql stable set search_path=pg_catalog as $$
 select jsonb_build_object('id',p.id,'activityId',p.activity_id,'code',p.code,
 'revision',p.revision,'updatedAt',p.updated_at,'archived',p.archived_at is not null,'deleted',p.deleted_at is not null,
 'schoolId',a.school_id::text,'schoolLogo',l.image_hash,
 'schoolDefault',coalesce(a.school,''),'classDefault',coalesce(nullif(a.class_group,''),a.grade,''),
 'submittedAt',(select s.submitted_at from poster_private.submissions s where s.poster_id=p.id and s.revision=p.revision))
 from public.activities a left join poster_private.school_logos l on l.school_id=a.school_id where a.row_id=p.activity_id
$$;
notify pgrst,'reload schema';
commit;
