
-- Store the server receive time. Bots report a frozen browser clock, which
-- piled every event at 02:00. The client clock stays in props when it fits.
-- The 90-day delete no longer runs on this hot path; homes_analytics_cleanup
-- and the daily Vercel cron already do that.

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
      now(),
      case
        when coalesce(e->>'at', '') ~ '^[0-9]{1,16}$' then
          case
            when octet_length((coalesce(e->'props', '{}'::jsonb) || jsonb_build_object('client_at_ms', (e->>'at')::bigint))::text) <= 4000
              then coalesce(e->'props', '{}'::jsonb) || jsonb_build_object('client_at_ms', (e->>'at')::bigint)
            else coalesce(e->'props', '{}'::jsonb)
          end
        else coalesce(e->'props', '{}'::jsonb)
      end
    from jsonb_array_elements(p_events) e
    on conflict (id) do nothing;
  return true;
end $$;

-- A raw "human" session with one page and no action, active time, or scroll
-- is counted as a bot. Personas are the sessions that actually did something.

create or replace function public.homes_analytics_dashboard(
  p_key text,
  p_from timestamptz,
  p_to timestamptz,
  p_source text default 'all',
  p_traffic text default 'all',
  p_section text default 'all'
) returns jsonb
language plpgsql
stable
security definer
set search_path = ''
set statement_timeout = '3s'
as $$
declare
  result jsonb;
  v_span interval;
  v_prev_from timestamptz;
  v_gran text;
begin
  if not exists (
    select 1 from homes_analytics_private.config
    where key_hash = encode(extensions.digest(p_key, 'sha256'), 'hex')
  ) then
    raise exception 'Unauthorized' using errcode = '42501';
  end if;

  if p_from is null or p_to is null or p_to <= p_from
     or p_to - p_from > interval '90 days'
     or p_from < now() - interval '200 days'
     or p_to > now() + interval '36 hours'
     or p_source not in ('all','google','bing','direct','internal','other')
     or p_traffic not in ('all','human','bot','admin')
     or p_section not in ('all','inicio','proyecto','proyectos','ubicacion','explore','boletin','madrid','admin','otra')
  then
    raise exception 'Invalid filter' using errcode = '22023';
  end if;

  v_span := p_to - p_from;
  v_prev_from := p_from - v_span;
  v_gran := case when v_span <= interval '48 hours' then 'hour' else 'day' end;

  with slice as (
    select
      e.session_id,
      e.page_id,
      e.event_name,
      e.path,
      e.source,
      e.occurred_at,
      e.id,
      coalesce(e.props->>'traffic_type', '') as traffic_type,
      case
        when e.event_name = 'page_engagement' and coalesce(e.props->>'active_seconds', '') ~ '^[0-9]+$'
          then least((e.props->>'active_seconds')::integer, 86400)
        else 0
      end as active_seconds,
      case
        when e.event_name = 'page_engagement' and coalesce(e.props->>'scroll_percent', '') ~ '^[0-9]+$'
          then least((e.props->>'scroll_percent')::integer, 100)
        else null
      end as scroll_percent,
      case
        when e.path = '/' then 'inicio'
        when e.path = '/proyectos' or e.path like '/proyectos/%' then 'proyectos'
        when e.path = '/proyecto' or e.path like '/proyecto/%' then 'proyecto'
        when e.path = '/ubicacion' or e.path like '/ubicacion/%' then 'ubicacion'
        when e.path = '/explore' or e.path like '/explore/%' then 'explore'
        when e.path = '/boletin' or e.path like '/boletin/%' then 'boletin'
        when e.path = '/madrid' or e.path like '/madrid/%' then 'madrid'
        when e.path = '/admin' or e.path like '/admin/%' then 'admin'
        else 'otra'
      end as section,
      e.occurred_at >= p_from as is_current
    from public.homes_analytics_events e
    where e.occurred_at >= v_prev_from
      and e.occurred_at < p_to
      and (p_source = 'all' or e.source = p_source)
  ),
  classes as (
    select
      session_id,
      case
        when bool_or(traffic_type = 'bot') then 'bot'
        when bool_or(traffic_type = 'admin' or section = 'admin') then 'admin'
        else 'human'
      end as traffic
    from slice
    group by session_id
  ),
  scoped as (
    select * from slice
    where p_section = 'all' or section = p_section
  ),
  timed as (
    select
      s.*,
      (date_trunc(v_gran, s.occurred_at at time zone 'Europe/Madrid') at time zone 'Europe/Madrid') as bucket
    from scoped s
  ),
  page_roll as (
    select
      session_id,
      is_current,
      page_id,
      max(path) as path,
      max(section) as section,
      bool_or(event_name = 'page_view') as viewed,
      bool_or(event_name = 'page_engagement') as measured,
      max(active_seconds) as active_seconds,
      max(scroll_percent) as scroll_percent
    from scoped
    group by session_id, is_current, page_id
  ),
  page_totals as (
    select
      session_id,
      is_current,
      coalesce(sum(active_seconds), 0)::integer as active_seconds,
      count(*) filter (where measured)::integer as measured_pages,
      max(scroll_percent) as max_scroll
    from page_roll
    group by session_id, is_current
  ),
  session_roll as (
    select
      e.session_id,
      e.is_current,
      case
        when c.traffic <> 'human' then c.traffic
        when count(*) filter (where e.event_name = 'page_view') > 1
          or count(*) filter (where e.event_name in (
            'document_click','outbound_click','boletin_buscar','estadisticas_filtro',
            'mapa_buscar','mapa_seleccionar','ficha_pestana'
          )) > 0
          or coalesce(max(pt.active_seconds), 0) >= 10
          or coalesce(max(pt.max_scroll), 0) >= 10
        then 'human'
        else 'bot'
      end as traffic,
      min(e.occurred_at) as started_at,
      (array_agg(e.source order by e.occurred_at, e.id))[1] as source,
      coalesce(
        (array_agg(e.path order by e.occurred_at, e.id) filter (where e.event_name = 'page_view'))[1],
        (array_agg(e.path order by e.occurred_at, e.id))[1]
      ) as entry_path,
      count(*) filter (where e.event_name = 'page_view')::integer as pageviews,
      count(*) filter (where e.event_name in (
        'document_click','outbound_click','boletin_buscar','estadisticas_filtro',
        'mapa_buscar','mapa_seleccionar','ficha_pestana'
      ))::integer as actions,
      coalesce(max(pt.active_seconds), 0)::integer as active_seconds,
      count(*) filter (where e.event_name = 'page_view') > 100 as suspicious
    from scoped e
    join classes c using (session_id)
    left join page_totals pt using (session_id, is_current)
    group by e.session_id, e.is_current, c.traffic
  ),
  filtered as (
    select * from session_roll
    where p_traffic = 'all' or traffic = p_traffic
  ),
  scroll_avg as (
    select
      p.is_current,
      round(avg(p.scroll_percent))::integer as avg_scroll,
      count(*)::integer as measured_pages
    from page_roll p
    join filtered f on f.session_id = p.session_id and f.is_current = p.is_current
    where p.measured
    group by p.is_current
  ),
  buckets as (
    select (gs at time zone 'Europe/Madrid') as bucket
    from generate_series(
      date_trunc(v_gran, p_from at time zone 'Europe/Madrid'),
      date_trunc(v_gran, (p_to - interval '1 microsecond') at time zone 'Europe/Madrid'),
      case when v_gran = 'hour' then interval '1 hour' else interval '1 day' end
    ) as gs
  ),
  series_agg as (
    select
      t.bucket,
      count(distinct t.session_id) filter (where f.traffic = 'human')::integer as human_sessions,
      count(distinct t.session_id) filter (where f.traffic = 'bot')::integer as bot_sessions,
      count(distinct t.session_id) filter (where f.traffic = 'admin')::integer as admin_sessions,
      count(*) filter (where t.event_name = 'page_view')::integer as pageviews
    from timed t
    join session_roll f on f.session_id = t.session_id and f.is_current = t.is_current
    where t.is_current
      and (p_traffic = 'all' or f.traffic = p_traffic)
    group by t.bucket
  ),
  bot_counts as (
    select t.bucket, count(distinct t.session_id)::integer as bots
    from timed t
    join session_roll f on f.session_id = t.session_id and f.is_current = t.is_current
    where t.is_current and f.traffic = 'bot'
    group by t.bucket
  ),
  bucket_stats as (
    select
      b.bucket,
      coalesce(bc.bots, 0)::integer as bots,
      row_number() over (order by b.bucket) as rn,
      count(*) over () as n
    from buckets b
    left join bot_counts bc on bc.bucket = b.bucket
  ),
  top_pages as (
    select
      p.path,
      max(p.section) as section,
      count(*) filter (where p.viewed)::integer as pageviews,
      count(distinct p.session_id)::integer as sessions,
      round(avg(p.active_seconds) filter (where p.viewed))::integer as active_seconds,
      round(avg(p.scroll_percent) filter (where p.measured))::integer as scroll_percent
    from page_roll p
    join filtered f on f.session_id = p.session_id and f.is_current = p.is_current
    where p.is_current and p.viewed
    group by p.path
    order by pageviews desc, sessions desc, p.path
    limit 15
  ),
  top_projects as (
    select
      p.path,
      max(p.section) as section,
      count(*) filter (where p.viewed)::integer as pageviews,
      count(distinct p.session_id)::integer as sessions,
      round(avg(p.active_seconds) filter (where p.viewed))::integer as active_seconds,
      round(avg(p.scroll_percent) filter (where p.measured))::integer as scroll_percent
    from page_roll p
    join filtered f on f.session_id = p.session_id and f.is_current = p.is_current
    where p.is_current and p.viewed and p.section = 'proyecto'
    group by p.path
    order by pageviews desc, sessions desc, p.path
    limit 10
  ),
  top_places as (
    select
      p.path,
      max(p.section) as section,
      count(*) filter (where p.viewed)::integer as pageviews,
      count(distinct p.session_id)::integer as sessions,
      round(avg(p.active_seconds) filter (where p.viewed))::integer as active_seconds,
      round(avg(p.scroll_percent) filter (where p.measured))::integer as scroll_percent
    from page_roll p
    join filtered f on f.session_id = p.session_id and f.is_current = p.is_current
    where p.is_current and p.viewed and p.section in ('proyectos', 'ubicacion')
    group by p.path
    order by pageviews desc, sessions desc, p.path
    limit 10
  ),
  entry_rows as (
    select coalesce(entry_path, '') as path, count(*)::integer as sessions
    from filtered
    where is_current
    group by 1
    order by sessions desc, path
    limit 8
  ),
  source_rows as (
    select source, count(*)::integer as sessions, coalesce(sum(pageviews), 0)::integer as pageviews
    from filtered
    where is_current
    group by source
    order by sessions desc, source
  ),
  section_rows as (
    select
      p.section,
      count(distinct p.session_id)::integer as sessions,
      count(*) filter (where p.viewed)::integer as pageviews
    from page_roll p
    join filtered f on f.session_id = p.session_id and f.is_current = p.is_current
    where p.is_current
    group by p.section
    order by pageviews desc, sessions desc, p.section
  ),
  action_rows as (
    select e.event_name, count(*)::integer as count
    from timed e
    join filtered f on f.session_id = e.session_id and f.is_current = e.is_current
    where e.is_current
      and e.event_name not in ('page_view', 'page_engagement')
    group by e.event_name
    order by count desc, e.event_name
  ),
  active_defs as (
    select * from (values
      (1, '0 s', 0, 0),
      (2, '1–9 s', 1, 9),
      (3, '10–29 s', 10, 29),
      (4, '30 s–2 min', 30, 119),
      (5, '2 min o más', 120, 1000000000)
    ) as v(ord, label, lo, hi)
  ),
  active_counts as (
    select d.ord, d.label, count(f.session_id)::integer as count
    from active_defs d
    left join filtered f
      on f.is_current
     and f.active_seconds between d.lo and d.hi
    group by d.ord, d.label
  ),
  scroll_defs as (
    select * from (values
      (1, '0%', 0, 0),
      (2, '1–24%', 1, 24),
      (3, '25–49%', 25, 49),
      (4, '50–74%', 50, 74),
      (5, '75–100%', 75, 100)
    ) as v(ord, label, lo, hi)
  ),
  measured_pages as (
    select p.page_id, p.scroll_percent
    from page_roll p
    join filtered f on f.session_id = p.session_id and f.is_current = p.is_current
    where p.is_current and p.measured and p.scroll_percent is not null
  ),
  scroll_counts as (
    select d.ord, d.label, count(p.page_id)::integer as count
    from scroll_defs d
    left join measured_pages p on p.scroll_percent between d.lo and d.hi
    group by d.ord, d.label
  ),
  recent_rows as (
    select
      started_at,
      source,
      traffic,
      coalesce(entry_path, '') as entry_path,
      pageviews,
      active_seconds,
      suspicious
    from filtered
    where is_current
    order by started_at desc
    limit 12
  ),
  mix_current as (
    select
      count(*) filter (where traffic = 'human')::integer as human,
      count(*) filter (where traffic = 'bot')::integer as bot,
      count(*) filter (where traffic = 'admin')::integer as admin
    from session_roll
    where is_current
  ),
  mix_previous as (
    select
      count(*) filter (where traffic = 'human')::integer as human,
      count(*) filter (where traffic = 'bot')::integer as bot,
      count(*) filter (where traffic = 'admin')::integer as admin
    from session_roll
    where not is_current
  ),
  spike as (
    select
      coalesce((select max(bots) from bucket_stats where rn > n - 2), 0)::integer as last_bots,
      coalesce((
        select percentile_cont(0.5) within group (order by bots)
        from bucket_stats
        where rn <= n - 2
      ), 0) as median_bots,
      coalesce((select max(n) from bucket_stats), 0)::integer as n
  )
  select jsonb_build_object(
    'from', p_from,
    'to', p_to,
    'granularity', v_gran,
    'source', p_source,
    'traffic', p_traffic,
    'section', p_section,
    'current', (
      select jsonb_build_object(
        'sessions', count(*)::integer,
        'pageviews', coalesce(sum(pageviews), 0)::integer,
        'human_sessions', count(*) filter (where traffic = 'human')::integer,
        'bot_sessions', count(*) filter (where traffic = 'bot')::integer,
        'admin_sessions', count(*) filter (where traffic = 'admin')::integer,
        'avg_active_seconds', coalesce(round(avg(active_seconds)), 0)::integer,
        'avg_scroll_percent', (select avg_scroll from scroll_avg where is_current),
        'measured_pages', coalesce((select measured_pages from scroll_avg where is_current), 0),
        'bounce_sessions', count(*) filter (where pageviews <= 1 and actions = 0 and active_seconds < 10)::integer,
        'bounce_rate', case
          when count(*) = 0 then 0
          else round(count(*) filter (where pageviews <= 1 and actions = 0 and active_seconds < 10)::numeric / count(*), 4)
        end,
        'engaged_sessions', count(*) filter (where pageviews > 1 or actions > 0 or active_seconds >= 10)::integer,
        'suspicious_sessions', count(*) filter (where suspicious)::integer
      )
      from filtered
      where is_current
    ),
    'previous', (
      select jsonb_build_object(
        'sessions', count(*)::integer,
        'pageviews', coalesce(sum(pageviews), 0)::integer,
        'human_sessions', count(*) filter (where traffic = 'human')::integer,
        'bot_sessions', count(*) filter (where traffic = 'bot')::integer,
        'admin_sessions', count(*) filter (where traffic = 'admin')::integer,
        'avg_active_seconds', coalesce(round(avg(active_seconds)), 0)::integer,
        'avg_scroll_percent', (select avg_scroll from scroll_avg where not is_current),
        'measured_pages', coalesce((select measured_pages from scroll_avg where not is_current), 0),
        'bounce_sessions', count(*) filter (where pageviews <= 1 and actions = 0 and active_seconds < 10)::integer,
        'bounce_rate', case
          when count(*) = 0 then 0
          else round(count(*) filter (where pageviews <= 1 and actions = 0 and active_seconds < 10)::numeric / count(*), 4)
        end,
        'engaged_sessions', count(*) filter (where pageviews > 1 or actions > 0 or active_seconds >= 10)::integer,
        'suspicious_sessions', count(*) filter (where suspicious)::integer
      )
      from filtered
      where not is_current
    ),
    'mix', (select jsonb_build_object('human', human, 'bot', bot, 'admin', admin) from mix_current),
    'previous_mix', (select jsonb_build_object('human', human, 'bot', bot, 'admin', admin) from mix_previous),
    'series', coalesce((
      select jsonb_agg(jsonb_build_object(
        'bucket', b.bucket,
        'human_sessions', coalesce(s.human_sessions, 0),
        'bot_sessions', coalesce(s.bot_sessions, 0),
        'admin_sessions', coalesce(s.admin_sessions, 0),
        'pageviews', coalesce(s.pageviews, 0)
      ) order by b.bucket)
      from buckets b
      left join series_agg s on s.bucket = b.bucket
    ), '[]'::jsonb),
    'pages', coalesce((select jsonb_agg(jsonb_build_object(
      'path', path, 'section', section, 'pageviews', pageviews, 'sessions', sessions,
      'active_seconds', active_seconds, 'scroll_percent', scroll_percent
    ) order by pageviews desc, sessions desc, path) from top_pages), '[]'::jsonb),
    'projects', coalesce((select jsonb_agg(jsonb_build_object(
      'path', path, 'section', section, 'pageviews', pageviews, 'sessions', sessions,
      'active_seconds', active_seconds, 'scroll_percent', scroll_percent
    ) order by pageviews desc, sessions desc, path) from top_projects), '[]'::jsonb),
    'places', coalesce((select jsonb_agg(jsonb_build_object(
      'path', path, 'section', section, 'pageviews', pageviews, 'sessions', sessions,
      'active_seconds', active_seconds, 'scroll_percent', scroll_percent
    ) order by pageviews desc, sessions desc, path) from top_places), '[]'::jsonb),
    'entries', coalesce((select jsonb_agg(jsonb_build_object('path', path, 'sessions', sessions) order by sessions desc, path) from entry_rows), '[]'::jsonb),
    'sources', coalesce((select jsonb_agg(jsonb_build_object('source', source, 'sessions', sessions, 'pageviews', pageviews) order by sessions desc, source) from source_rows), '[]'::jsonb),
    'sections', coalesce((select jsonb_agg(jsonb_build_object('section', section, 'sessions', sessions, 'pageviews', pageviews) order by pageviews desc, section) from section_rows), '[]'::jsonb),
    'actions', coalesce((select jsonb_agg(jsonb_build_object('event_name', event_name, 'count', count) order by count desc, event_name) from action_rows), '[]'::jsonb),
    'active_buckets', coalesce((select jsonb_agg(jsonb_build_object('label', label, 'count', count) order by ord) from active_counts), '[]'::jsonb),
    'scroll_buckets', coalesce((select jsonb_agg(jsonb_build_object('label', label, 'count', count) order by ord) from scroll_counts), '[]'::jsonb),
    'recent', coalesce((select jsonb_agg(jsonb_build_object(
      'started_at', started_at, 'source', source, 'traffic', traffic, 'entry_path', entry_path,
      'pageviews', pageviews, 'active_seconds', active_seconds, 'suspicious', suspicious
    ) order by started_at desc) from recent_rows), '[]'::jsonb),
    'signals', (
      select jsonb_build_object(
        'bot_sessions', m.bot,
        'bot_share', case when m.human + m.bot + m.admin = 0 then 0 else round(m.bot::numeric / (m.human + m.bot + m.admin), 4) end,
        'previous_bot_share', case when p.human + p.bot + p.admin = 0 then 0 else round(p.bot::numeric / (p.human + p.bot + p.admin), 4) end,
        'last_bucket_bots', s.last_bots,
        'median_bucket_bots', round(s.median_bots::numeric, 1),
        'bot_spike', s.n >= 3 and s.last_bots >= 8 and s.last_bots >= s.median_bots * 2,
        'suspicious_sessions', coalesce((select suspicious_sessions from (
          select count(*) filter (where suspicious)::integer as suspicious_sessions
          from filtered where is_current
        ) q), 0)
      )
      from mix_current m, mix_previous p, spike s
    )
  ) into result;

  return result;
end $$;

revoke all on function public.homes_analytics_dashboard(text, timestamptz, timestamptz, text, text, text) from public;
grant execute on function public.homes_analytics_dashboard(text, timestamptz, timestamptz, text, text, text) to anon, service_role;

