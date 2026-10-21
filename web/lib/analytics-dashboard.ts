import { getSupabaseServer } from "@/lib/supabase/server";
import {
  formatBucketLabel,
  type AnalyticsGranularity,
  type ResolvedAnalyticsQuery,
} from "@/lib/analytics-filters";
import { describeDelta, formatCount, formatPercent, formatSeconds, type DeltaModel } from "@/lib/analytics-format";
import {
  labelAnalyticsEvent,
  labelAnalyticsPath,
  labelAnalyticsSection,
  labelAnalyticsSource,
} from "@/lib/analytics-labels";

export type PeriodStats = {
  sessions: number;
  pageviews: number;
  human_sessions: number;
  bot_sessions: number;
  admin_sessions: number;
  avg_active_seconds: number;
  avg_scroll_percent: number | null;
  measured_pages: number;
  bounce_sessions: number;
  bounce_rate: number;
  engaged_sessions: number;
  suspicious_sessions: number;
};

export type TrafficCounts = { human: number; bot: number; admin: number };

export type SeriesPoint = {
  bucket: string;
  human_sessions: number;
  bot_sessions: number;
  admin_sessions: number;
  pageviews: number;
};

export type PageStat = {
  path: string;
  section: string;
  pageviews: number;
  sessions: number;
  active_seconds: number | null;
  scroll_percent: number | null;
};

export type AnalyticsReport = {
  from: string;
  to: string;
  granularity: AnalyticsGranularity;
  source: string;
  traffic: string;
  section: string;
  current: PeriodStats;
  previous: PeriodStats;
  mix: TrafficCounts;
  previous_mix: TrafficCounts;
  series: SeriesPoint[];
  pages: PageStat[];
  projects: PageStat[];
  places: PageStat[];
  entries: { path: string; sessions: number }[];
  sources: { source: string; sessions: number; pageviews: number }[];
  sections: { section: string; sessions: number; pageviews: number }[];
  actions: { event_name: string; count: number }[];
  active_buckets: { label: string; count: number }[];
  scroll_buckets: { label: string; count: number }[];
  recent: {
    started_at: string;
    source: string;
    traffic: string;
    entry_path: string;
    pageviews: number;
    active_seconds: number;
    suspicious: boolean;
  }[];
  signals: {
    bot_sessions: number;
    bot_share: number;
    previous_bot_share: number;
    last_bucket_bots: number;
    median_bucket_bots: number;
    bot_spike: boolean;
    suspicious_sessions: number;
  };
};

export type RankRow = {
  key: string;
  label: string;
  href?: string;
  value: number;
  valueLabel: string;
  hint?: string;
};

export type KpiModel = {
  id: string;
  label: string;
  value: string;
  detail?: string;
  delta: DeltaModel;
  invert?: boolean;
};

export type RecentModel = {
  key: string;
  when: string;
  traffic: string;
  trafficKey: string;
  source: string;
  entry: string;
  href?: string;
  pageviews: string;
  active: string;
  suspicious: boolean;
};

export type ChartModel = {
  granularity: AnalyticsGranularity;
  series: { label: string; human: number; bot: number; admin: number; pageviews: number }[];
  mix: TrafficCounts;
  active: { label: string; value: number }[];
  scroll: { label: string; value: number }[];
};

export type DashboardView = {
  sample: boolean;
  empty: boolean;
  kpis: KpiModel[];
  alert: { title: string; body: string } | null;
  charts: ChartModel;
  pages: RankRow[];
  projects: RankRow[];
  places: RankRow[];
  placesNote: string;
  entries: RankRow[];
  sources: RankRow[];
  sections: RankRow[];
  actions: RankRow[];
  recent: RecentModel[];
};

const EMPTY_PERIOD: PeriodStats = {
  sessions: 0,
  pageviews: 0,
  human_sessions: 0,
  bot_sessions: 0,
  admin_sessions: 0,
  avg_active_seconds: 0,
  avg_scroll_percent: null,
  measured_pages: 0,
  bounce_sessions: 0,
  bounce_rate: 0,
  engaged_sessions: 0,
  suspicious_sessions: 0,
};

export async function getAnalyticsDashboard(query: ResolvedAnalyticsQuery): Promise<AnalyticsReport> {
  const supabase = getSupabaseServer();
  const key = process.env.ANALYTICS_RPC_KEY;
  if (!supabase || !key) {
    throw new Error("La recogida de sesiones todavía no está configurada.");
  }
  const { data, error } = await supabase.rpc("homes_analytics_dashboard", {
    p_key: key,
    p_from: query.from.toISOString(),
    p_to: query.to.toISOString(),
    p_source: query.source,
    p_traffic: query.traffic,
    p_section: query.section,
  });
  if (error) throw new Error(dashboardErrorMessage(error));
  return parseReport(data);
}

export function toDashboardView(report: AnalyticsReport, query: ResolvedAnalyticsQuery, sample = false): DashboardView {
  const current = report.current ?? EMPTY_PERIOD;
  const previous = report.previous ?? EMPTY_PERIOD;
  const mix = report.mix ?? { human: 0, bot: 0, admin: 0 };
  const previousMix = report.previous_mix ?? { human: 0, bot: 0, admin: 0 };
  const mixTotal = mix.human + mix.bot + mix.admin;
  const previousMixTotal = previousMix.human + previousMix.bot + previousMix.admin;
  const humanShare = mixTotal ? mix.human / mixTotal : 0;
  const previousHumanShare = previousMixTotal ? previousMix.human / previousMixTotal : 0;
  const scrollCurrent = current.avg_scroll_percent;
  const scrollPrevious = previous.avg_scroll_percent;

  const kpis: KpiModel[] = [
    {
      id: "sessions",
      label: "Sesiones",
      value: formatCount(current.sessions),
      detail: query.traffic === "all" ? undefined : "Con el filtro de tipo aplicado",
      delta: describeDelta(current.sessions, previous.sessions, "count"),
    },
    {
      id: "pageviews",
      label: "Páginas vistas",
      value: formatCount(current.pageviews),
      delta: describeDelta(current.pageviews, previous.pageviews, "count"),
    },
    {
      id: "humans",
      label: "Parte de personas",
      value: mixTotal ? formatPercent(humanShare, 0) : "—",
      detail: mixTotal
        ? `${formatPercent(mix.bot / mixTotal, 0)} bots · ${formatPercent(mix.admin / mixTotal, 0)} admin · personas con actividad`
        : "Sin sesiones en este corte",
      delta:
        mixTotal === 0 && previousMixTotal === 0
          ? { text: "sin sesiones", direction: "none" }
          : describeDelta(humanShare, previousHumanShare, "points"),
    },
    {
      id: "time",
      label: "Tiempo activo medio",
      value: formatSeconds(current.avg_active_seconds),
      detail: "Por sesión, ceros incluidos",
      delta: describeDelta(current.avg_active_seconds, previous.avg_active_seconds, "count"),
    },
    {
      id: "scroll",
      label: "Scroll medio",
      value: scrollCurrent == null ? "—" : `${formatCount(scrollCurrent)}%`,
      detail: current.measured_pages ? `${formatCount(current.measured_pages)} páginas medidas` : "Sin medición de scroll",
      delta:
        scrollCurrent == null || scrollPrevious == null
          ? { text: "sin base anterior", direction: "none" }
          : describeDelta(scrollCurrent / 100, scrollPrevious / 100, "points"),
    },
    {
      id: "bounce",
      label: "Rebote aproximado",
      value: current.sessions ? formatPercent(current.bounce_rate, 0) : "—",
      detail: "Una página, sin acción y menos de 10 s",
      delta: describeDelta(current.bounce_rate, previous.bounce_rate, "points"),
      invert: true,
    },
  ];

  return {
    sample,
    empty: current.sessions === 0 && mixTotal === 0,
    kpis,
    alert: buildAlert(report, query),
    charts: {
      granularity: report.granularity === "hour" ? "hour" : "day",
      series: (report.series ?? []).map((point) => ({
        label: formatBucketLabel(point.bucket, report.granularity === "hour" ? "hour" : "day"),
        human: point.human_sessions,
        bot: point.bot_sessions,
        admin: point.admin_sessions,
        pageviews: point.pageviews,
      })),
      mix,
      active: (report.active_buckets ?? []).map((bucket) => ({ label: bucket.label, value: bucket.count })),
      scroll: (report.scroll_buckets ?? []).map((bucket) => ({ label: bucket.label, value: bucket.count })),
    },
    pages: (report.pages ?? []).map((row) => pageRank(row)),
    projects: (report.projects ?? []).map((row) => pageRank(row)),
    places: (report.places ?? []).map((row) => pageRank(row)),
    placesNote: "Directorio por municipio y fichas de ubicación. Las direcciones no se guardan sueltas.",
    entries: (report.entries ?? []).map((row) => {
      const labeled = labelAnalyticsPath(row.path || "/");
      return {
        key: row.path || "empty",
        label: row.path ? labeled.label : "Sin página",
        href: row.path ? labeled.href : undefined,
        value: row.sessions,
        valueLabel: `${formatCount(row.sessions)} sesiones`,
      };
    }),
    sources: (report.sources ?? []).map((row) => ({
      key: row.source,
      label: labelAnalyticsSource(row.source),
      value: row.sessions,
      valueLabel: `${formatCount(row.sessions)} sesiones`,
      hint: `${formatCount(row.pageviews)} vistas`,
    })),
    sections: (report.sections ?? []).map((row) => ({
      key: row.section,
      label: labelAnalyticsSection(row.section),
      value: row.pageviews,
      valueLabel: `${formatCount(row.pageviews)} vistas`,
      hint: `${formatCount(row.sessions)} sesiones`,
    })),
    actions: (report.actions ?? []).map((row) => ({
      key: row.event_name,
      label: labelAnalyticsEvent(row.event_name),
      value: row.count,
      valueLabel: formatCount(row.count),
    })),
    recent: (report.recent ?? []).map((row, index) => {
      const labeled = labelAnalyticsPath(row.entry_path || "/");
      return {
        key: `${row.started_at}-${index}`,
        when: new Date(row.started_at).toLocaleString("es-ES", {
          timeZone: "Europe/Madrid",
          day: "numeric",
          month: "short",
          hour: "2-digit",
          minute: "2-digit",
        }),
        traffic: row.traffic === "bot" ? "Bot" : row.traffic === "admin" ? "Admin" : "Persona",
        trafficKey: row.traffic,
        source: labelAnalyticsSource(row.source),
        entry: row.entry_path ? labeled.label : "Sin página",
        href: row.entry_path ? labeled.href : undefined,
        pageviews: formatCount(row.pageviews),
        active: formatSeconds(row.active_seconds),
        suspicious: row.suspicious,
      };
    }),
  };
}

function pageRank(row: PageStat): RankRow {
  const labeled = labelAnalyticsPath(row.path);
  const bits = [`${formatCount(row.sessions)} sesiones`, formatSeconds(row.active_seconds ?? 0)];
  if (row.scroll_percent != null) bits.push(`${formatCount(row.scroll_percent)}% scroll`);
  return {
    key: row.path,
    label: labeled.label,
    href: labeled.href,
    value: row.pageviews,
    valueLabel: `${formatCount(row.pageviews)} vistas`,
    hint: bits.join(" · "),
  };
}

function buildAlert(report: AnalyticsReport, query: ResolvedAnalyticsQuery): DashboardView["alert"] {
  const signals = report.signals;
  if (!signals) return null;
  const lines: string[] = [];
  if (signals.bot_spike) {
    lines.push(
      `Pico de bots en los últimos tramos: ${formatCount(signals.last_bucket_bots)} sesiones, frente a una mediana de ${signals.median_bucket_bots.toLocaleString("es-ES")} en el resto del periodo.`,
    );
  } else if (signals.bot_share >= 0.45 && signals.bot_sessions >= 15) {
    lines.push(`Los bots son el ${formatPercent(signals.bot_share, 0)} de las sesiones de este periodo (${formatCount(signals.bot_sessions)}).`);
  }
  if (signals.suspicious_sessions > 0) {
    lines.push(
      `${formatCount(signals.suspicious_sessions)} ${signals.suspicious_sessions === 1 ? "sesión tiene" : "sesiones tienen"} más de 100 páginas vistas.`,
    );
  }
  if (!lines.length) return null;
  if (query.traffic !== "all") {
    lines.push("Este aviso usa las fechas, el origen y la sección, y no el filtro de tipo.");
  }
  lines.push("El cortafuegos no anota los bots que bloquea antes de cargar la página. Aquí solo aparecen automatizaciones que ejecutaron la medición.");
  return {
    title: signals.bot_spike ? "Subida de bots" : "Tráfico a revisar",
    body: lines.join(" "),
  };
}

function dashboardErrorMessage(error: { code?: string; message?: string }): string {
  const code = error.code ?? "";
  const message = error.message ?? "";
  if (code === "PGRST202" || /schema cache/i.test(message) || /could not find the function/i.test(message)) {
    return "Falta aplicar la migración 20261020150000_analytics_dashboard en la base de datos. Hasta entonces el panel no consulta los eventos.";
  }
  if (code === "supabase_unreachable" || code === "57014" || /timeout|no respondió|statement timeout/i.test(message)) {
    return "La base de datos no respondió a tiempo. La consulta se ha cortado para no cargarla.";
  }
  if (code === "42501" || /unauthorized/i.test(message)) {
    return "La clave de analítica del servidor no está autorizada.";
  }
  if (code === "22023" || /invalid filter/i.test(message)) {
    return "Ese filtro no es válido. Prueba otro periodo o sección.";
  }
  return "No se ha podido consultar la analítica.";
}

function parseReport(data: unknown): AnalyticsReport {
  if (!data || typeof data !== "object") {
    throw new Error("No se ha podido consultar la analítica.");
  }
  const row = data as Partial<AnalyticsReport>;
  if (!row.current || !Array.isArray(row.series)) {
    throw new Error("No se ha podido consultar la analítica.");
  }
  return {
    from: String(row.from ?? ""),
    to: String(row.to ?? ""),
    granularity: row.granularity === "hour" ? "hour" : "day",
    source: String(row.source ?? "all"),
    traffic: String(row.traffic ?? "all"),
    section: String(row.section ?? "all"),
    current: parsePeriod(row.current),
    previous: parsePeriod(row.previous),
    mix: parseMix(row.mix),
    previous_mix: parseMix(row.previous_mix),
    series: (row.series ?? []).map((point) => ({
      bucket: String(point.bucket),
      human_sessions: num(point.human_sessions),
      bot_sessions: num(point.bot_sessions),
      admin_sessions: num(point.admin_sessions),
      pageviews: num(point.pageviews),
    })),
    pages: (row.pages ?? []).map(parsePage),
    projects: (row.projects ?? []).map(parsePage),
    places: (row.places ?? []).map(parsePage),
    entries: (row.entries ?? []).map((entry) => ({ path: String(entry.path ?? ""), sessions: num(entry.sessions) })),
    sources: (row.sources ?? []).map((source) => ({
      source: String(source.source),
      sessions: num(source.sessions),
      pageviews: num(source.pageviews),
    })),
    sections: (row.sections ?? []).map((section) => ({
      section: String(section.section),
      sessions: num(section.sessions),
      pageviews: num(section.pageviews),
    })),
    actions: (row.actions ?? []).map((action) => ({ event_name: String(action.event_name), count: num(action.count) })),
    active_buckets: (row.active_buckets ?? []).map((bucket) => ({ label: String(bucket.label), count: num(bucket.count) })),
    scroll_buckets: (row.scroll_buckets ?? []).map((bucket) => ({ label: String(bucket.label), count: num(bucket.count) })),
    recent: (row.recent ?? []).map((item) => ({
      started_at: String(item.started_at),
      source: String(item.source),
      traffic: String(item.traffic),
      entry_path: String(item.entry_path ?? ""),
      pageviews: num(item.pageviews),
      active_seconds: num(item.active_seconds),
      suspicious: Boolean(item.suspicious),
    })),
    signals: {
      bot_sessions: num(row.signals?.bot_sessions),
      bot_share: num(row.signals?.bot_share),
      previous_bot_share: num(row.signals?.previous_bot_share),
      last_bucket_bots: num(row.signals?.last_bucket_bots),
      median_bucket_bots: num(row.signals?.median_bucket_bots),
      bot_spike: Boolean(row.signals?.bot_spike),
      suspicious_sessions: num(row.signals?.suspicious_sessions),
    },
  };
}

function parsePeriod(value: Partial<PeriodStats> | undefined): PeriodStats {
  return {
    sessions: num(value?.sessions),
    pageviews: num(value?.pageviews),
    human_sessions: num(value?.human_sessions),
    bot_sessions: num(value?.bot_sessions),
    admin_sessions: num(value?.admin_sessions),
    avg_active_seconds: num(value?.avg_active_seconds),
    avg_scroll_percent: value?.avg_scroll_percent == null ? null : num(value.avg_scroll_percent),
    measured_pages: num(value?.measured_pages),
    bounce_sessions: num(value?.bounce_sessions),
    bounce_rate: num(value?.bounce_rate),
    engaged_sessions: num(value?.engaged_sessions),
    suspicious_sessions: num(value?.suspicious_sessions),
  };
}

function parseMix(value: Partial<TrafficCounts> | undefined): TrafficCounts {
  return { human: num(value?.human), bot: num(value?.bot), admin: num(value?.admin) };
}

function parsePage(row: Partial<PageStat>): PageStat {
  return {
    path: String(row.path ?? ""),
    section: String(row.section ?? ""),
    pageviews: num(row.pageviews),
    sessions: num(row.sessions),
    active_seconds: row.active_seconds == null ? null : num(row.active_seconds),
    scroll_percent: row.scroll_percent == null ? null : num(row.scroll_percent),
  };
}

function num(value: unknown): number {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}
