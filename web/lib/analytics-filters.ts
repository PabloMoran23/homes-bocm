export const ANALYTICS_RANGES = ["24h", "7d", "30d", "90d", "custom"] as const;
export const ANALYTICS_TRAFFIC = ["all", "human", "bot", "admin"] as const;
export const ANALYTICS_SOURCES = ["all", "google", "bing", "direct", "internal", "other"] as const;
export const ANALYTICS_SECTIONS = [
  "all",
  "inicio",
  "proyecto",
  "proyectos",
  "ubicacion",
  "explore",
  "boletin",
  "madrid",
  "admin",
  "otra",
] as const;

export type AnalyticsRange = (typeof ANALYTICS_RANGES)[number];
export type AnalyticsTraffic = (typeof ANALYTICS_TRAFFIC)[number];
export type AnalyticsSource = (typeof ANALYTICS_SOURCES)[number];
export type AnalyticsSection = (typeof ANALYTICS_SECTIONS)[number];
export type AnalyticsGranularity = "hour" | "day";

export type AnalyticsSelection = {
  range: AnalyticsRange;
  fromDate: string;
  toDate: string;
  traffic: AnalyticsTraffic;
  source: AnalyticsSource;
  section: AnalyticsSection;
};

export type ResolvedAnalyticsQuery = AnalyticsSelection & {
  from: Date;
  to: Date;
  previousFrom: Date;
  previousTo: Date;
  granularity: AnalyticsGranularity;
  currentLabel: string;
  previousLabel: string;
};

export type AnalyticsSearch = {
  r?: string;
  from?: string;
  to?: string;
  traffic?: string;
  source?: string;
  section?: string;
  days?: string;
};

const MADRID = "Europe/Madrid";
const DAY_MS = 24 * 60 * 60 * 1000;
const MAX_SPAN_MS = 90 * DAY_MS;

const RANGE_LABELS: Record<AnalyticsRange, string> = {
  "24h": "24 horas",
  "7d": "7 días",
  "30d": "30 días",
  "90d": "90 días",
  custom: "Fechas",
};

export const TRAFFIC_LABELS: Record<AnalyticsTraffic, string> = {
  all: "Todo el tráfico",
  human: "Personas",
  bot: "Bots",
  admin: "Administradores",
};

export const SOURCE_LABELS: Record<AnalyticsSource, string> = {
  all: "Todos los orígenes",
  google: "Google",
  bing: "Bing",
  direct: "Directo",
  internal: "Interno",
  other: "Otras webs",
};

export const SECTION_LABELS: Record<AnalyticsSection, string> = {
  all: "Todas las secciones",
  inicio: "Inicio",
  proyecto: "Fichas de proyecto",
  proyectos: "Directorio",
  ubicacion: "Ubicaciones",
  explore: "Mapa",
  boletin: "Tu zona",
  madrid: "Estadísticas",
  admin: "Administración",
  otra: "Otras rutas",
};

export function rangeLabel(range: AnalyticsRange): string {
  return RANGE_LABELS[range];
}

export function analyticsHref(selection: AnalyticsSelection, preview = false): string {
  const params = new URLSearchParams();
  if (selection.range !== "7d") params.set("r", selection.range);
  if (selection.range === "custom") {
    params.set("from", selection.fromDate);
    params.set("to", selection.toDate);
  }
  if (selection.traffic !== "all") params.set("traffic", selection.traffic);
  if (selection.source !== "all") params.set("source", selection.source);
  if (selection.section !== "all") params.set("section", selection.section);
  if (preview) params.set("muestra", "1");
  const qs = params.toString();
  return qs ? `/admin/analitica?${qs}` : "/admin/analitica";
}

export function requestedAnalyticsHref(search: AnalyticsSearch): string {
  const params = new URLSearchParams();
  for (const key of ["r", "from", "to", "traffic", "source", "section", "days"] as const) {
    const value = search[key];
    if (value) params.set(key, value);
  }
  const qs = params.toString();
  return qs ? `/admin/analitica?${qs}` : "/admin/analitica";
}

export function parseAnalyticsQuery(search: AnalyticsSearch, now = new Date()): ResolvedAnalyticsQuery {
  const traffic = parseTraffic(search.traffic);
  const source = oneOf(search.source, ANALYTICS_SOURCES, "all");
  const section = oneOf(search.section, ANALYTICS_SECTIONS, "all");
  const range = resolveRange(search, now);
  const window = resolveWindow(range, now);
  const span = window.to.getTime() - window.from.getTime();
  const granularity: AnalyticsGranularity = span <= 48 * 60 * 60 * 1000 ? "hour" : "day";
  const previousTo = window.from;
  const previousFrom = new Date(window.from.getTime() - span);
  return {
    range: window.range,
    fromDate: window.fromDate,
    toDate: window.toDate,
    traffic,
    source,
    section,
    from: window.from,
    to: window.to,
    previousFrom,
    previousTo,
    granularity,
    currentLabel: formatWindow(window.from, window.to, granularity),
    previousLabel: formatWindow(previousFrom, previousTo, granularity),
  };
}

function resolveRange(search: AnalyticsSearch, now: Date): { range: AnalyticsRange; fromDate?: string; toDate?: string } {
  const explicit = (ANALYTICS_RANGES as readonly string[]).includes(search.r ?? "") ? (search.r as AnalyticsRange) : undefined;
  if (explicit === "custom" || (search.from && search.to && !search.r)) {
    return { range: "custom", fromDate: search.from, toDate: search.to };
  }
  if (explicit) return { range: explicit };
  if (search.days === "7" || search.days === "30" || search.days === "90") {
    return { range: `${search.days}d` as AnalyticsRange };
  }
  return { range: "7d", fromDate: undefined, toDate: madridDate(now) };
}

function resolveWindow(
  input: { range: AnalyticsRange; fromDate?: string; toDate?: string },
  now: Date,
): { range: AnalyticsRange; from: Date; to: Date; fromDate: string; toDate: string } {
  const today = madridDate(now);
  if (input.range === "24h") {
    const from = new Date(now.getTime() - DAY_MS);
    return { range: "24h", from, to: now, fromDate: madridDate(from), toDate: today };
  }
  if (input.range === "7d" || input.range === "30d" || input.range === "90d") {
    const days = input.range === "7d" ? 6 : input.range === "30d" ? 29 : 89;
    const fromDate = shiftDate(today, -days);
    return { range: input.range, from: madridMidnight(fromDate), to: now, fromDate, toDate: today };
  }

  const fromDate = isIsoDate(input.fromDate) ? input.fromDate : shiftDate(today, -6);
  let toDate = isIsoDate(input.toDate) ? input.toDate : today;
  if (toDate > today) toDate = today;
  let start = fromDate;
  let end = toDate;
  if (start > end) {
    const swap = start;
    start = end;
    end = swap;
  }
  let from = madridMidnight(start);
  const to = end === today ? now : madridMidnight(shiftDate(end, 1));
  if (to.getTime() <= from.getTime()) {
    return resolveWindow({ range: "24h" }, now);
  }
  if (to.getTime() - from.getTime() > MAX_SPAN_MS) {
    from = new Date(to.getTime() - MAX_SPAN_MS);
    start = madridDate(from);
  }
  return { range: "custom", from, to, fromDate: start, toDate: end };
}

function parseTraffic(value: string | undefined): AnalyticsTraffic {
  if (value === "interesting" || value === "unclassified") return "human";
  return oneOf(value, ANALYTICS_TRAFFIC, "all");
}

function oneOf<T extends string>(value: string | undefined, allowed: readonly T[], fallback: T): T {
  return value && (allowed as readonly string[]).includes(value) ? (value as T) : fallback;
}

export function madridDate(date: Date): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: MADRID,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

export function madridMidnight(isoDate: string): Date {
  const utcGuess = new Date(`${isoDate}T00:00:00Z`);
  const first = timeZoneOffsetMs(utcGuess, MADRID);
  const adjusted = new Date(utcGuess.getTime() - first);
  const second = timeZoneOffsetMs(adjusted, MADRID);
  return new Date(utcGuess.getTime() - second);
}

export function shiftDate(isoDate: string, days: number): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  const shifted = new Date(Date.UTC(year, month - 1, day + days));
  const y = shifted.getUTCFullYear();
  const m = String(shifted.getUTCMonth() + 1).padStart(2, "0");
  const d = String(shifted.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function isIsoDate(value: string | undefined): value is string {
  return !!value && /^\d{4}-\d{2}-\d{2}$/.test(value);
}

function timeZoneOffsetMs(date: Date, timeZone: string): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(date);
  const pick = (type: Intl.DateTimeFormatPartTypes) => Number(parts.find((part) => part.type === type)?.value);
  const asUtc = Date.UTC(pick("year"), pick("month") - 1, pick("day"), pick("hour"), pick("minute"), pick("second"));
  return asUtc - date.getTime();
}

function formatWindow(from: Date, to: Date, granularity: AnalyticsGranularity): string {
  const end = new Date(to.getTime() - 1);
  const sameDay = madridDate(from) === madridDate(end);
  if (granularity === "hour") {
    const stamp = new Intl.DateTimeFormat("es-ES", {
      timeZone: MADRID,
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
    return sameDay ? stamp.format(from).replace(",", "") + " – " + new Intl.DateTimeFormat("es-ES", { timeZone: MADRID, hour: "2-digit", minute: "2-digit" }).format(end) : `${stamp.format(from)} – ${stamp.format(end)}`;
  }
  const day = new Intl.DateTimeFormat("es-ES", { timeZone: MADRID, day: "numeric", month: "short" });
  const dayYear = new Intl.DateTimeFormat("es-ES", { timeZone: MADRID, day: "numeric", month: "short", year: "numeric" });
  if (sameDay) return dayYear.format(from);
  return `${day.format(from)} – ${dayYear.format(end)}`;
}

export function formatBucketLabel(iso: string, granularity: AnalyticsGranularity): string {
  const date = new Date(iso);
  if (granularity === "hour") {
    const day = new Intl.DateTimeFormat("es-ES", { timeZone: MADRID, day: "numeric", month: "short" }).format(date);
    const hour = new Intl.DateTimeFormat("es-ES", { timeZone: MADRID, hour: "2-digit", minute: "2-digit" }).format(date);
    return `${day} ${hour}`;
  }
  return new Intl.DateTimeFormat("es-ES", { timeZone: MADRID, day: "numeric", month: "short" }).format(date);
}
