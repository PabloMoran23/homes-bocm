-- Private first-party measurement. Tables have no browser-readable policies.
create schema if not exists homes_analytics_private;
revoke all on schema homes_analytics_private from public, anon, authenticated;
create table if not exists homes_analytics_private.config (
  singleton boolean primary key default true check (singleton), key_hash text not null
);
create table if not exists homes_analytics_private.rate_limits (
  bucket text primary key, requests integer not null, created_at timestamptz not null default now()
);
create table if not exists public.homes_analytics_events (
  id uuid primary key,
  session_id uuid not null,
  page_id uuid not null,
  event_name text not null check (event_name in ('page_view','page_engagement','document_click','outbound_click','boletin_buscar','ficha_proyecto_ver','estadisticas_filtro','mapa_buscar','mapa_seleccionar','ficha_pestana')),
  path text not null check (length(path) <= 240),
  source text not null check (source in ('google','bing','direct','internal','other')),
  occurred_at timestamptz not null,
  received_at timestamptz not null default now(),
  props jsonb not null default '{}'::jsonb check (octet_length(props::text) <= 4000)
);
create index if not exists homes_analytics_events_time on public.homes_analytics_events (occurred_at desc);
create index if not exists homes_analytics_events_session on public.homes_analytics_events (session_id, occurred_at);
alter table public.homes_analytics_events enable row level security;
revoke all on public.homes_analytics_events from anon, authenticated;

create or replace function public.homes_analytics_ingest(p_key text, p_bucket text, p_events jsonb)
returns boolean language plpgsql security definer set search_path = '' as $$
declare requests_count integer;
begin
  if not exists (select 1 from homes_analytics_private.config where key_hash = encode(extensions.digest(p_key, 'sha256'), 'hex')) then
    raise exception 'Unauthorized' using errcode = '42501';
  end if;
  if p_bucket !~ '^[0-9a-f]{64}$' or jsonb_typeof(p_events) <> 'array' or jsonb_array_length(p_events) not between 1 and 20 then
    raise exception 'Invalid batch';
  end if;
  insert into homes_analytics_private.rate_limits as r (bucket, requests) values (p_bucket, 1)
    on conflict (bucket) do update set requests = r.requests + 1 returning requests into requests_count;
  if requests_count > 30 then return false; end if;
  delete from homes_analytics_private.rate_limits where created_at < now() - interval '2 hours';
  insert into public.homes_analytics_events (id, session_id, page_id, event_name, path, source, occurred_at, props)
    select (e->>'id')::uuid, (e->>'session')::uuid, (e->>'page')::uuid, e->>'name', e->>'path', e->>'source',
      to_timestamp((e->>'at')::double precision / 1000), e->'props'
    from jsonb_array_elements(p_events) e
    where to_timestamp((e->>'at')::double precision / 1000) between now() - interval '1 day' and now() + interval '1 minute'
    on conflict (id) do nothing;
  -- Enforced on every write, report, and daily via the authenticated Vercel cron.
  delete from public.homes_analytics_events where received_at < now() - interval '90 days';
  return true;
end $$;

create or replace function public.homes_analytics_report(p_key text, p_days integer default 30, p_source text default 'all')
returns jsonb language plpgsql security definer set search_path = '' as $$
declare result jsonb;
begin
  if not exists (select 1 from homes_analytics_private.config where key_hash = encode(extensions.digest(p_key, 'sha256'), 'hex')) then
    raise exception 'Unauthorized' using errcode = '42501';
  end if;
  if p_days not between 1 and 90 or p_source not in ('all','google','bing','direct','internal','other') then raise exception 'Invalid filter'; end if;
  delete from public.homes_analytics_events where received_at < now() - interval '90 days';
  with events as materialized (
    select * from public.homes_analytics_events where occurred_at >= now() - make_interval(days => p_days)
      and (p_source = 'all' or source = p_source)
  ), pages as (
    select session_id, page_id, max(path) as path,
      max(case when event_name = 'page_engagement' then coalesce((props->>'active_seconds')::integer,0) else 0 end) as active_seconds,
      max(case when event_name = 'page_engagement' then coalesce((props->>'scroll_percent')::integer,0) else 0 end) as scroll_percent,
      bool_or(event_name = 'page_view') as viewed
    from events group by session_id, page_id
  ), sessions as (
    select e.session_id, min(e.occurred_at) as started_at, max(e.occurred_at) as last_at,
      (array_agg(e.source order by e.occurred_at, e.id))[1] as source,
      (array_agg(e.path order by e.occurred_at, e.id))[1] as entry_path,
      count(*) filter (where e.event_name = 'page_view') as pageviews,
      count(*) filter (where e.event_name in ('document_click','outbound_click','boletin_buscar','estadisticas_filtro','mapa_buscar','mapa_seleccionar','ficha_pestana')) as actions,
      coalesce((select sum(p.active_seconds) from pages p where p.session_id = e.session_id),0) as active_seconds,
      count(*) filter (where e.event_name = 'page_view') > 100 as suspicious
    from events e group by e.session_id
  ), top_pages as (
    select path, count(*) filter (where viewed) as pageviews, count(distinct session_id) as sessions,
      round(avg(active_seconds) filter (where viewed)) as active_seconds,
      round(avg(scroll_percent) filter (where viewed)) as scroll_percent
    from pages group by path order by pageviews desc limit 25
  ), sources as (
    select source, count(*) as sessions, sum(pageviews) as pageviews from sessions group by source order by sessions desc
  ), actions as (
    select event_name, count(*) as count from events where event_name not in ('page_view','page_engagement','ficha_proyecto_ver') group by event_name order by count desc
  ), journeys as (
    select s.*, (select coalesce(jsonb_agg(to_jsonb(x) order by x.occurred_at, x.id), '[]'::jsonb) from (
      select e.id, e.event_name, e.path, e.occurred_at, e.props from events e where e.session_id = s.session_id and e.event_name <> 'page_engagement' order by e.occurred_at, e.id limit 60
    ) x) as events from sessions s order by started_at desc limit 50
  ) select jsonb_build_object(
    'days',p_days,'source',p_source,
    'overview',(select jsonb_build_object('sessions',count(*),'pageviews',coalesce(sum(pageviews),0),'active_sessions',count(*) filter (where actions > 0 or active_seconds >= 10 or pageviews > 1),
      'single_page_sessions',count(*) filter (where pageviews = 1),'without_interaction',count(*) filter (where pageviews = 1 and actions = 0 and active_seconds < 10),
      'suspicious_sessions',count(*) filter (where suspicious),'avg_active_seconds',coalesce(round(avg(active_seconds)),0)) from sessions),
    'pages',coalesce((select jsonb_agg(to_jsonb(p)) from top_pages p),'[]'::jsonb),
    'sources',coalesce((select jsonb_agg(to_jsonb(s)) from sources s),'[]'::jsonb),
    'actions',coalesce((select jsonb_agg(to_jsonb(a)) from actions a),'[]'::jsonb),
    'journeys',coalesce((select jsonb_agg(to_jsonb(j)) from journeys j),'[]'::jsonb)
  ) into result;
  return result;
end $$;
revoke all on function public.homes_analytics_ingest(text,text,jsonb) from public;
revoke all on function public.homes_analytics_report(text,integer,text) from public;
grant execute on function public.homes_analytics_ingest(text,text,jsonb) to anon, service_role;
grant execute on function public.homes_analytics_report(text,integer,text) to anon, service_role;

create or replace function public.homes_analytics_cleanup(p_key text)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if not exists (select 1 from homes_analytics_private.config where key_hash = encode(extensions.digest(p_key, 'sha256'), 'hex')) then
    raise exception 'Unauthorized' using errcode = '42501';
  end if;
  delete from public.homes_analytics_events where received_at < now() - interval '90 days';
  delete from homes_analytics_private.rate_limits where created_at < now() - interval '2 hours';
end $$;
revoke all on function public.homes_analytics_cleanup(text) from public;
grant execute on function public.homes_analytics_cleanup(text) to anon, service_role;
notify pgrst, 'reload schema';
