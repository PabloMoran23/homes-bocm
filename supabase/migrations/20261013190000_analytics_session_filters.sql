-- Filter entire sessions before computing every metric and the latest 50 journeys.
create or replace function public.homes_analytics_report_filtered(p_key text, p_days integer default 30, p_source text default 'all', p_traffic text default 'all')
returns jsonb language plpgsql security definer set search_path = '' as $$
declare result jsonb;
begin
  if not exists (select 1 from homes_analytics_private.config where key_hash = encode(extensions.digest(p_key, 'sha256'), 'hex')) then
    raise exception 'Unauthorized' using errcode = '42501';
  end if;
  if p_days not between 1 and 90 or p_source not in ('all','google','bing','direct','internal','other') or p_traffic not in ('all','interesting','bot','admin','unclassified') then raise exception 'Invalid filter'; end if;
  delete from public.homes_analytics_events where received_at < now() - interval '90 days';
  with raw_events as materialized (
    select * from public.homes_analytics_events where occurred_at >= now() - make_interval(days => p_days)
      and (p_source = 'all' or source = p_source)
  ), raw_pages as (
    select session_id, page_id,
      max(case when event_name = 'page_engagement' then coalesce((props->>'active_seconds')::integer,0) else 0 end) as active_seconds
    from raw_events group by session_id, page_id
  ), eligible_sessions as (
    select e.session_id from raw_events e group by e.session_id
    having p_traffic = 'all'
      or (p_traffic = 'bot' and bool_or(coalesce(e.props->>'traffic_type','') = 'bot'))
      or (p_traffic = 'admin' and bool_or(coalesce(e.props->>'traffic_type','') = 'admin'))
      or (p_traffic in ('interesting','unclassified')
        and not bool_or(coalesce(e.props->>'traffic_type','') in ('bot','admin') or e.path like '/admin%')
        and (p_traffic = 'unclassified' or (
          count(*) filter (where e.event_name = 'page_view') between 1 and 100
          and (count(*) filter (where e.event_name = 'page_view') > 1
            or count(*) filter (where e.event_name in ('document_click','outbound_click','boletin_buscar','estadisticas_filtro','mapa_buscar','mapa_seleccionar','ficha_pestana')) > 0
            or (select sum(p.active_seconds) from raw_pages p where p.session_id = e.session_id) >= 10)
        )))
  ), events as materialized (
    select e.* from raw_events e join eligible_sessions s using (session_id)
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
    'days',p_days,'source',p_source,'traffic',p_traffic,
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
revoke all on function public.homes_analytics_report_filtered(text,integer,text,text) from public;
grant execute on function public.homes_analytics_report_filtered(text,integer,text,text) to anon, service_role;
notify pgrst, 'reload schema';
