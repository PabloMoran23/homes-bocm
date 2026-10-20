import type { AnalyticsReport, PageStat, PeriodStats } from "@/lib/analytics-dashboard";
import type { ResolvedAnalyticsQuery } from "@/lib/analytics-filters";

/** Fixed illustration for local screenshots. It is not a measurement. */
export function sampleReport(query: ResolvedAnalyticsQuery): AnalyticsReport {
  const buckets = bucketStarts(query);
  const unfiltered = buckets.map((bucket, index) => {
    const human = 5 + (index % 4);
    const bot = index >= buckets.length - 2 ? 16 + (index % 3) * 4 : 2 + (index % 3);
    const admin = index % 4 === 0 ? 1 : 0;
    return {
      bucket: bucket.toISOString(),
      human_sessions: human,
      bot_sessions: bot,
      admin_sessions: admin,
      pageviews: human * 2 + bot + admin,
    };
  });
  const series = unfiltered.map((point) => {
    const scaled = scale(point, query.source === "all" ? 1 : query.source === "google" ? 0.45 : 0.2);
    if (query.traffic === "human") return { ...scaled, bot_sessions: 0, admin_sessions: 0, pageviews: scaled.human_sessions * 2 };
    if (query.traffic === "bot") return { ...scaled, human_sessions: 0, admin_sessions: 0, pageviews: scaled.bot_sessions };
    if (query.traffic === "admin") return { ...scaled, human_sessions: 0, bot_sessions: 0, pageviews: scaled.admin_sessions };
    return scaled;
  });
  const sectionFactor = query.section === "all" ? 1 : query.section === "otra" ? 0 : 0.55;
  const visible = series.map((point) => ({
    ...point,
    human_sessions: Math.round(point.human_sessions * sectionFactor),
    bot_sessions: Math.round(point.bot_sessions * sectionFactor),
    admin_sessions: Math.round(point.admin_sessions * sectionFactor),
    pageviews: Math.round(point.pageviews * sectionFactor),
  }));
  const mixSource = unfiltered.reduce(
    (acc, point) => ({
      human: acc.human + point.human_sessions,
      bot: acc.bot + point.bot_sessions,
      admin: acc.admin + point.admin_sessions,
    }),
    { human: 0, bot: 0, admin: 0 },
  );
  const mix = scaleMix(mixSource, (query.source === "all" ? 1 : 0.5) * sectionFactor);
  const current = periodFrom(visible, query.traffic);
  const previous = {
    ...current,
    sessions: Math.round(current.sessions * 0.72),
    pageviews: Math.round(current.pageviews * 0.64),
    avg_active_seconds: Math.max(0, current.avg_active_seconds - 8),
    avg_scroll_percent: current.avg_scroll_percent == null ? null : Math.max(0, current.avg_scroll_percent - 6),
    bounce_rate: Math.min(1, current.bounce_rate + 0.06),
    measured_pages: Math.round(current.measured_pages * 0.7),
  };
  const earlierBots = unfiltered.slice(0, -2).map((point) => point.bot_sessions);
  const recentBots = unfiltered.slice(-2).map((point) => point.bot_sessions);
  const lastBots = recentBots.length ? Math.max(...recentBots) : 0;
  const median = medianOf(earlierBots);
  const pages = pagesFor(query.section);
  return {
    from: query.from.toISOString(),
    to: query.to.toISOString(),
    granularity: query.granularity,
    source: query.source,
    traffic: query.traffic,
    section: query.section,
    current,
    previous,
    mix,
    previous_mix: {
      human: Math.round(mix.human * 0.8),
      bot: Math.round(mix.bot * 0.55),
      admin: mix.admin,
    },
    series: visible,
    pages,
    projects: pages.filter((row) => row.section === "proyecto").slice(0, 8),
    places: pages.filter((row) => row.section === "proyectos" || row.section === "ubicacion"),
    entries: pages.slice(0, 5).map((row) => ({ path: row.path, sessions: row.sessions })),
    sources: [
      { source: "google", sessions: 28, pageviews: 61 },
      { source: "direct", sessions: 19, pageviews: 24 },
      { source: "internal", sessions: 4, pageviews: 11 },
      { source: "bing", sessions: 2, pageviews: 3 },
    ].filter((row) => query.source === "all" || row.source === query.source),
    sections: [
      { section: "proyecto", sessions: 40, pageviews: 52 },
      { section: "proyectos", sessions: 14, pageviews: 18 },
      { section: "explore", sessions: 9, pageviews: 11 },
      { section: "inicio", sessions: 8, pageviews: 8 },
      { section: "boletin", sessions: 6, pageviews: 7 },
      { section: "madrid", sessions: 4, pageviews: 5 },
      { section: "ubicacion", sessions: 2, pageviews: 2 },
    ].filter((row) => query.section === "all" || row.section === query.section),
    actions: [
      { event_name: "ficha_proyecto_ver", count: 18 },
      { event_name: "ficha_pestana", count: 7 },
      { event_name: "document_click", count: 4 },
      { event_name: "mapa_buscar", count: 3 },
      { event_name: "boletin_buscar", count: 2 },
    ],
    active_buckets: [
      { label: "0 s", count: query.traffic === "human" ? 4 : 22 },
      { label: "1–9 s", count: 9 },
      { label: "10–29 s", count: 7 },
      { label: "30 s–2 min", count: 5 },
      { label: "2 min o más", count: 2 },
    ],
    scroll_buckets: [
      { label: "0%", count: 3 },
      { label: "1–24%", count: 6 },
      { label: "25–49%", count: 8 },
      { label: "50–74%", count: 5 },
      { label: "75–100%", count: 4 },
    ],
    recent: [
      recent("2026-10-20T13:10:00Z", "direct", "bot", "/proyecto/711-1999-16314", 1, 0, false),
      recent("2026-10-20T12:40:00Z", "google", "human", "/explore", 3, 64, false),
      recent("2026-10-20T11:05:00Z", "direct", "bot", "/proyectos/madrid/madrid", 1, 0, false),
      recent("2026-10-20T10:12:00Z", "google", "human", "/", 2, 41, false),
      recent("2026-10-20T09:02:00Z", "direct", "admin", "/admin/analitica", 4, 180, false),
    ].filter((row) => query.traffic === "all" || row.traffic === query.traffic),
    signals: {
      bot_sessions: mix.bot,
      bot_share: share(mix.bot, mix.human + mix.bot + mix.admin),
      previous_bot_share: 0.41,
      last_bucket_bots: Math.round(lastBots * sectionFactor),
      median_bucket_bots: Math.round(median * sectionFactor * 10) / 10,
      bot_spike: sectionFactor > 0 && buckets.length >= 3 && lastBots >= 8 && lastBots >= median * 2,
      suspicious_sessions: 0,
    },
  };
}

function periodFrom(series: AnalyticsReport["series"], traffic: string): PeriodStats {
  const sessions = series.reduce((sum, point) => sum + point.human_sessions + point.bot_sessions + point.admin_sessions, 0);
  const pageviews = series.reduce((sum, point) => sum + point.pageviews, 0);
  const bots = series.reduce((sum, point) => sum + point.bot_sessions, 0);
  const bounce = traffic === "human" ? 0.28 : traffic === "bot" ? 0.96 : 0.71;
  return {
    sessions,
    pageviews,
    human_sessions: series.reduce((sum, point) => sum + point.human_sessions, 0),
    bot_sessions: bots,
    admin_sessions: series.reduce((sum, point) => sum + point.admin_sessions, 0),
    avg_active_seconds: traffic === "bot" ? 1 : traffic === "human" ? 54 : 18,
    avg_scroll_percent: sessions ? 37 : null,
    measured_pages: Math.round(sessions * 0.4),
    bounce_sessions: Math.round(sessions * bounce),
    bounce_rate: sessions ? bounce : 0,
    engaged_sessions: Math.round(sessions * (1 - bounce)),
    suspicious_sessions: 0,
  };
}

function pagesFor(section: string): PageStat[] {
  const rows: PageStat[] = [
    page("/proyecto/711-1999-16314", "proyecto", 22, 18, 36, 48),
    page("/proyectos/madrid/madrid", "proyectos", 14, 12, 22, 30),
    page("/", "inicio", 9, 8, 18, 40),
    page("/explore", "explore", 8, 7, 44, 55),
    page("/boletin", "boletin", 6, 5, 27, 33),
    page("/madrid/estadisticas", "madrid", 5, 4, 61, 72),
    page("/proyecto/711-2009-20398", "proyecto", 4, 4, 15, 20),
    page("/ubicacion", "ubicacion", 2, 2, 11, 18),
  ];
  return rows.filter((row) => section === "all" || row.section === section);
}

function page(path: string, section: string, pageviews: number, sessions: number, active: number, scroll: number): PageStat {
  return { path, section, pageviews, sessions, active_seconds: active, scroll_percent: scroll };
}

function recent(
  started_at: string,
  source: string,
  traffic: string,
  entry_path: string,
  pageviews: number,
  active_seconds: number,
  suspicious: boolean,
): AnalyticsReport["recent"][number] {
  return { started_at, source, traffic, entry_path, pageviews, active_seconds, suspicious };
}

function scale(
  point: AnalyticsReport["series"][number],
  factor: number,
): AnalyticsReport["series"][number] {
  return {
    bucket: point.bucket,
    human_sessions: Math.round(point.human_sessions * factor),
    bot_sessions: Math.round(point.bot_sessions * factor),
    admin_sessions: Math.round(point.admin_sessions * factor),
    pageviews: Math.round(point.pageviews * factor),
  };
}

function scaleMix(mix: AnalyticsReport["mix"], factor: number): AnalyticsReport["mix"] {
  return {
    human: Math.round(mix.human * factor),
    bot: Math.round(mix.bot * factor),
    admin: Math.round(mix.admin * factor),
  };
}

function share(part: number, total: number): number {
  return total ? Math.round((part / total) * 10000) / 10000 : 0;
}

function medianOf(values: number[]): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function bucketStarts(query: ResolvedAnalyticsQuery): Date[] {
  const end = new Date(query.to.getTime() - 1);
  const step = query.granularity === "hour" ? 60 * 60 * 1000 : 24 * 60 * 60 * 1000;
  const start = query.granularity === "hour" ? new Date(query.from) : startOfUtcHour(query.from);
  const points: Date[] = [];
  for (let time = start.getTime(); time <= end.getTime() && points.length < 96; time += step) {
    points.push(new Date(time));
  }
  return points.length ? points : [query.from];
}

function startOfUtcHour(date: Date): Date {
  const copy = new Date(date);
  copy.setUTCMinutes(0, 0, 0);
  return copy;
}
