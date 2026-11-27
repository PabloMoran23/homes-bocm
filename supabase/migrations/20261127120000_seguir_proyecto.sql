-- Project follow-up on the existing launch waitlist.
-- Additive: new columns are nullable, so rows already stored stay valid.
-- A repeated email+project does not rewrite the original row.
-- A segment answer fills segmento only while it is still null.
-- Apply this file before deploying the web change that sends the new arguments.
-- Do not run it from the app. It does not send email and does not delete rows.

alter table public.homes_launch_waitlist
  add column if not exists municipio text,
  add column if not exists posicion text,
  add column if not exists referrer text,
  add column if not exists utm jsonb,
  add column if not exists segmento text,
  add column if not exists aviso text,
  add column if not exists ambito text;

alter table public.homes_launch_waitlist drop constraint if exists homes_launch_waitlist_posicion_check;
alter table public.homes_launch_waitlist
  add constraint homes_launch_waitlist_posicion_check
  check (posicion is null or posicion in ('cabecera', 'documentos', 'pie', 'barra'));

alter table public.homes_launch_waitlist drop constraint if exists homes_launch_waitlist_segmento_check;
alter table public.homes_launch_waitlist
  add constraint homes_launch_waitlist_segmento_check
  check (
    segmento is null or segmento in (
      'Vivo o tengo una propiedad cerca',
      'Busco comprar vivienda',
      'Trabajo en el sector',
      'Invierto',
      'Otro'
    )
  );

alter table public.homes_launch_waitlist drop constraint if exists homes_launch_waitlist_municipio_check;
alter table public.homes_launch_waitlist
  add constraint homes_launch_waitlist_municipio_check
  check (municipio is null or length(municipio) between 1 and 120);

alter table public.homes_launch_waitlist drop constraint if exists homes_launch_waitlist_referrer_check;
alter table public.homes_launch_waitlist
  add constraint homes_launch_waitlist_referrer_check
  check (referrer is null or length(referrer) between 1 and 300);

alter table public.homes_launch_waitlist drop constraint if exists homes_launch_waitlist_aviso_check;
alter table public.homes_launch_waitlist
  add constraint homes_launch_waitlist_aviso_check
  check (aviso is null or aviso in ('proyecto', 'zona'));

alter table public.homes_launch_waitlist drop constraint if exists homes_launch_waitlist_ambito_check;
alter table public.homes_launch_waitlist
  add constraint homes_launch_waitlist_ambito_check
  check (ambito is null or length(ambito) between 1 and 80);

alter table public.homes_launch_waitlist drop constraint if exists homes_launch_waitlist_utm_check;
alter table public.homes_launch_waitlist
  add constraint homes_launch_waitlist_utm_check
  check (utm is null or (jsonb_typeof(utm) = 'object' and octet_length(utm::text) <= 800));

comment on table public.homes_launch_waitlist is
  'Emails for project follow-up notices and earlier launch-notice requests. Not a newsletter. Project rows may include municipio, form position, referrer, utm and an optional segment.';

comment on column public.homes_launch_waitlist.posicion is
  'Where the person signed up on the project page: cabecera, documentos, pie or barra. Null on older rows.';

comment on column public.homes_launch_waitlist.segmento is
  'Optional answer to why they follow the project. Null until they answer, and not overwritten once set.';

comment on column public.homes_launch_waitlist.utm is
  'utm_source, utm_medium, utm_campaign, utm_term and utm_content from the signup page. Null when absent.';

comment on column public.homes_launch_waitlist.aviso is
  'proyecto: the file can still change phase. zona: closed file or the general plan, so the notice is about that place.';

comment on column public.homes_launch_waitlist.ambito is
  'Place named in the form: barrio, distrito or municipality. Null on older rows.';

create index if not exists homes_launch_waitlist_project_created_idx
  on public.homes_launch_waitlist (created_at desc)
  where source = 'project';

-- The previous 4-argument signature cannot gain parameters in place.
-- Dropping the function does not touch table rows. Defaults keep a 4-argument call valid.
drop function if exists public.homes_launch_waitlist_register(text, text, text, text);
drop function if exists public.homes_launch_waitlist_register(text, text, text, text, text, text, text, jsonb, text);
drop function if exists public.homes_launch_waitlist_register(text, text, text, text, text, text, text, jsonb, text, text, text);

create function public.homes_launch_waitlist_register(
  p_key text,
  p_email text,
  p_source text,
  p_context_key text default '',
  p_posicion text default null,
  p_municipio text default null,
  p_referrer text default null,
  p_utm jsonb default null,
  p_segmento text default null,
  p_aviso text default null,
  p_ambito text default null
) returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  utm_key text;
  utm_value text;
begin
  if not exists (
    select 1 from public.homes_launch_waitlist_config
    where key_hash = encode(extensions.digest(p_key, 'sha256'), 'hex')
  ) then
    raise exception 'Unauthorized' using errcode = '42501';
  end if;

  if p_email is null or length(p_email) > 254
     or p_email <> lower(trim(p_email))
     or p_email !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'
     or p_source is null or p_source not in ('project', 'boletin', 'dashboard')
     or p_context_key is null or length(p_context_key) > 200
     or (p_source = 'project' and length(trim(p_context_key)) = 0)
     or (p_source <> 'project' and p_context_key <> '') then
    raise exception 'Invalid request' using errcode = '22023';
  end if;

  if p_segmento is not null then
    if p_source <> 'project' or p_segmento not in (
      'Vivo o tengo una propiedad cerca',
      'Busco comprar vivienda',
      'Trabajo en el sector',
      'Invierto',
      'Otro'
    ) then
      raise exception 'Invalid request' using errcode = '22023';
    end if;
    update public.homes_launch_waitlist
      set segmento = p_segmento
      where email = p_email
        and source = p_source
        and context_key = p_context_key
        and segmento is null;
    return;
  end if;

  if p_source = 'project' then
    if p_posicion is null or p_posicion not in ('cabecera', 'documentos', 'pie', 'barra') then
      raise exception 'Invalid request' using errcode = '22023';
    end if;
  elsif p_posicion is not null or p_municipio is not null or p_referrer is not null or p_utm is not null
     or p_aviso is not null or p_ambito is not null then
    raise exception 'Invalid request' using errcode = '22023';
  end if;

  if p_aviso is not null and p_aviso not in ('proyecto', 'zona') then
    raise exception 'Invalid request' using errcode = '22023';
  end if;
  if p_source = 'project' and p_aviso is null then
    raise exception 'Invalid request' using errcode = '22023';
  end if;
  if p_ambito is not null and (
    length(p_ambito) > 80 or p_ambito <> trim(p_ambito) or p_ambito ~ '[[:cntrl:]]'
  ) then
    raise exception 'Invalid request' using errcode = '22023';
  end if;

  if p_municipio is not null and (
    length(p_municipio) > 120 or p_municipio <> trim(p_municipio) or p_municipio ~ '[[:cntrl:]]'
  ) then
    raise exception 'Invalid request' using errcode = '22023';
  end if;

  if p_referrer is not null and (
    length(p_referrer) > 300 or p_referrer ~ '[[:cntrl:][:space:]@?]'
  ) then
    raise exception 'Invalid request' using errcode = '22023';
  end if;

  if p_utm is not null then
    if jsonb_typeof(p_utm) <> 'object' or octet_length(p_utm::text) > 800 then
      raise exception 'Invalid request' using errcode = '22023';
    end if;
    for utm_key, utm_value in select key, value from jsonb_each_text(p_utm)
    loop
      if utm_key not in ('utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content')
         or length(utm_value) = 0 or length(utm_value) > 120
         or utm_value ~ '[[:cntrl:]@]' then
        raise exception 'Invalid request' using errcode = '22023';
      end if;
    end loop;
  end if;

  insert into public.homes_launch_waitlist (
    email, source, context_key, consent_version, municipio, posicion, referrer, utm, aviso, ambito
  ) values (
    p_email,
    p_source,
    p_context_key,
    case
      when p_source = 'project' then 'seguir-proyecto-v1'
      else 'launch-notice-' || p_source || '-v1'
    end,
    p_municipio,
    p_posicion,
    p_referrer,
    p_utm,
    p_aviso,
    p_ambito
  )
  on conflict (email, source, context_key) do nothing;
end $$;

revoke all on function public.homes_launch_waitlist_register(text, text, text, text, text, text, text, jsonb, text, text, text) from public;
grant execute on function public.homes_launch_waitlist_register(text, text, text, text, text, text, text, jsonb, text, text, text) to anon, authenticated, service_role;

-- Same analytics table. New names only; existing events stay valid.
do $$
declare
  constraint_name text;
begin
  for constraint_name in
    select con.conname
    from pg_constraint con
    where con.conrelid = 'public.homes_analytics_events'::regclass
      and con.contype = 'c'
      and pg_get_constraintdef(con.oid) ilike '%event_name%'
  loop
    execute format('alter table public.homes_analytics_events drop constraint %I', constraint_name);
  end loop;
end $$;

alter table public.homes_analytics_events
  add constraint homes_analytics_events_event_name_check
  check (event_name in (
    'page_view',
    'page_engagement',
    'document_click',
    'outbound_click',
    'boletin_buscar',
    'ficha_proyecto_ver',
    'estadisticas_filtro',
    'mapa_buscar',
    'mapa_seleccionar',
    'ficha_pestana',
    'seguir_visto',
    'seguir_clic',
    'seguir_alta',
    'seguir_segmento'
  ));
