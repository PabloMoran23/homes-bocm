import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import type { MadridDashboardMapaMonth, MadridDashboardStats } from "@/lib/types";

export type LandingNewsSpotlight = {
  id: string;
  href: string;
  tag: string;
  dateLabel: string;
  title: string;
  dek: string;
  featured?: boolean;
  ctaLabel?: string;
  valueLabel?: string;
  trendLabel?: string;
  numViviendas?: number;
  expedienteGrupo?: string;
};

export type LandingNewsFile = {
  generatedAt: string;
  source?: string;
  criteria?: string;
  items: LandingNewsSpotlight[];
};

const FALLBACK: LandingNewsSpotlight[] = [
  {
    id: "fallback-explore",
    featured: true,
    href: "/explore",
    tag: "Madrid",
    dateLabel: "Explorar",
    title: "Descubre qué se está planeando cerca de ti",
    dek: "Mapa unificado de proyectos urbanísticos y licencias por dirección.",
  },
];

let cached: LandingNewsFile | null = null;

function readJson<T>(path: string): T | null {
  if (!existsSync(path)) return null;
  try {
    return JSON.parse(readFileSync(path, "utf-8")) as T;
  } catch {
    return null;
  }
}

function formatInt(n: number) {
  return n.toLocaleString("es-ES");
}

function formatMonth(month: string) {
  const [year, mm] = month.split("-");
  const d = new Date(Number(year), Number(mm) - 1, 1);
  return d.toLocaleDateString("es-ES", { month: "long", year: "numeric" });
}

function percentChange(current: number, previous: number): string | null {
  if (!Number.isFinite(current) || !Number.isFinite(previous) || previous === 0) return null;
  const pct = ((current - previous) / previous) * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${Math.round(pct).toLocaleString("es-ES")}%`;
}

function monthTypeCount(row: MadridDashboardMapaMonth | undefined, id: string) {
  return row?.tipos.find((x) => x.id === id)?.count ?? 0;
}

function monthTotal(row: MadridDashboardMapaMonth | undefined) {
  return row?.tipos.reduce((sum, x) => sum + x.count, 0) ?? 0;
}

function yearToDateTypeCount(
  rows: MadridDashboardMapaMonth[],
  year: string,
  untilMonth: number,
  id: string,
) {
  return rows
    .filter((row) => row.month.startsWith(`${year}-`) && Number(row.month.slice(5, 7)) <= untilMonth)
    .reduce((sum, row) => sum + monthTypeCount(row, id), 0);
}

function sumMonthTypeCounts(row: MadridDashboardMapaMonth | undefined, ids: string[]) {
  return ids.reduce((sum, id) => sum + monthTypeCount(row, id), 0);
}

function yearToDateTypeCounts(
  rows: MadridDashboardMapaMonth[],
  year: string,
  untilMonth: number,
  ids: string[],
) {
  return ids.reduce((sum, id) => sum + yearToDateTypeCount(rows, year, untilMonth, id), 0);
}

function buildLicenseNews(stats: MadridDashboardStats): LandingNewsSpotlight[] {
  const monthly = [
    ...(stats.licencias?.seriesByMonthActuacionQue ??
      stats.licencias?.seriesByMonthMapaTipo ??
      []),
  ].sort((a, b) =>
    a.month.localeCompare(b.month),
  );
  const latest = monthly.at(-1);
  const previous = monthly.at(-2);
  if (!latest) return [];

  const latestMonth = formatMonth(latest.month);
  const latestYear = latest.month.slice(0, 4);
  const latestMonthNumber = Number(latest.month.slice(5, 7));
  const previousMonth = previous ? formatMonth(previous.month) : "el mes anterior";

  const housingSignalTypes = [
    "vivienda_obra",
    "vivienda_obra_menor",
    "vivienda_uso",
    "local_a_vivienda",
    "edificio_primera_ocupacion",
  ];
  const housingSignal = sumMonthTypeCounts(latest, housingSignalTypes);
  const prevHousingSignal = sumMonthTypeCounts(previous, housingSignalTypes);
  const housingSignalTrend = percentChange(housingSignal, prevHousingSignal);
  const housingSignalYtd = yearToDateTypeCounts(
    monthly,
    latestYear,
    latestMonthNumber,
    housingSignalTypes,
  );
  const prevHousingSignalYtd = yearToDateTypeCounts(
    monthly,
    String(Number(latestYear) - 1),
    latestMonthNumber,
    housingSignalTypes,
  );
  const localToHousing = monthTypeCount(latest, "local_a_vivienda");
  const localYtd = yearToDateTypeCount(monthly, latestYear, latestMonthNumber, "local_a_vivienda");
  const residentialUse = monthTypeCount(latest, "vivienda_uso");
  const prevResidentialUse = monthTypeCount(previous, "vivienda_uso");
  const residentialTrend = percentChange(residentialUse, prevResidentialUse);

  const items: LandingNewsSpotlight[] = [
    {
      id: "stat-vivienda-nueva-pulso",
      href: "/madrid/estadisticas",
      tag: "Vivienda",
      dateLabel: latestMonth,
      title: `La señal de vivienda nueva mueve ${formatInt(housingSignal)} expedientes en ${latestMonth}${housingSignalTrend ? ` (${housingSignalTrend})` : ""}`,
      dek: `Agregado de licencias residenciales, autorizaciones de uso residencial, primera ocupación y transformación local-vivienda. El cambio estricto de local a vivienda marca ${formatInt(localToHousing)} en ${latestMonth} y ${formatInt(localYtd)} en ${latestYear}; la autorización residencial suma ${formatInt(residentialUse)}${residentialTrend ? ` (${residentialTrend} vs ${previousMonth})` : ""}.`,
      featured: true,
      valueLabel: `${formatInt(housingSignal)} expedientes`,
      trendLabel: `${housingSignalTrend ? `${housingSignalTrend} vs ${previousMonth}` : `vs ${previousMonth}`} · ${formatInt(housingSignalYtd)} en ${latestYear} · ${formatInt(prevHousingSignalYtd)} en el mismo tramo de ${Number(latestYear) - 1}`,
      ctaLabel: "Ver estadísticas",
    },
  ];

  const localActivity = monthTypeCount(latest, "local_actividad");
  const prevLocalActivity = monthTypeCount(previous, "local_actividad");
  const localActivityTrend = percentChange(localActivity, prevLocalActivity);
  if (localActivityTrend && localActivity > prevLocalActivity) {
    items.push({
      id: "stat-actividad-locales",
      href: "/madrid/estadisticas",
      tag: "Locales",
      dateLabel: latestMonth,
      title: `Aperturas y cambios en local se aceleran: ${formatInt(localActivity)} expedientes`,
      dek: `La declaración responsable de actividad en local prácticamente duplica ${previousMonth}. Es la señal más viva del último mes en licencias.`,
      valueLabel: `${formatInt(localActivity)} expedientes`,
      trendLabel: `${localActivityTrend} vs ${previousMonth}`,
      ctaLabel: "Ver serie",
    });
  }

  const residentialWorksYtd = yearToDateTypeCount(monthly, latestYear, latestMonthNumber, "vivienda_obra");
  const residentialWorksPrevYtd = yearToDateTypeCount(
    monthly,
    String(Number(latestYear) - 1),
    latestMonthNumber,
    "vivienda_obra",
  );
  const residentialWorksTrend = percentChange(residentialWorksYtd, residentialWorksPrevYtd);
  if (residentialWorksTrend && residentialWorksYtd > residentialWorksPrevYtd) {
    items.push({
      id: "stat-licencia-residencial-ytd",
      href: "/madrid/estadisticas",
      tag: "Residencial",
      dateLabel: `${latestYear} acumulado`,
      title: `Las obras residenciales con licencia suben ${residentialWorksTrend} en el año`,
      dek: `${formatInt(residentialWorksYtd)} licencias urbanísticas residenciales hasta ${latestMonth}, frente a ${formatInt(residentialWorksPrevYtd)} en el mismo tramo del año anterior.`,
      valueLabel: `${formatInt(residentialWorksYtd)} licencias`,
      trendLabel: `${residentialWorksTrend} interanual`,
      ctaLabel: "Ver detalle",
    });
  }

  const latestTotal = monthTotal(latest);
  const prevTotal = monthTotal(previous);
  const totalTrend = percentChange(latestTotal, prevTotal);
  items.push({
    id: "stat-volumen-licencias",
    href: "/madrid/estadisticas",
    tag: "Pulso urbano",
    dateLabel: latestMonth,
    title: `${formatInt(latestTotal)} licencias urbanísticas en el último mes disponible`,
    dek: `El volumen total se mantiene alto tras el pico de marzo; ayuda a distinguir ruido administrativo de señales realmente útiles por uso.`,
    valueLabel: `${formatInt(latestTotal)} trámites`,
    trendLabel: totalTrend ? `${totalTrend} vs ${previousMonth}` : undefined,
    ctaLabel: "Abrir panel",
  });

  return items;
}

function expedienteGrupoKey(value: string | null | undefined) {
  const raw = String(value || "").trim();
  const match = raw.match(/(\d+)\s*\/\s*(\d{4})\s*\/\s*([A-Za-z0-9]+)/);
  return match ? `${match[1]}/${match[2]}/${match[3]}` : raw;
}

function yearFromExpediente(value: string | null | undefined) {
  const match = String(value || "").match(/\/(\d{4})\//);
  return match ? Number(match[1]) : null;
}

function sigmaHref(grupo: string) {
  return `/sigma/${encodeURIComponent(grupo.replace(/\//g, "-"))}`;
}

function shortTitle(value: string | null | undefined, max = 58) {
  const s = String(value || "Proyecto urbanístico").replace(/\s+/g, " ").trim();
  return s.length > max ? `${s.slice(0, max - 1).trim()}…` : s;
}

function buildSigmaNews(root: string): LandingNewsSpotlight[] {
  const sigma = readJson<{ expedientes?: Array<Record<string, unknown>> }>(
    join(root, "public/data/madrid-sigma.json"),
  );
  const slim = readJson<{ byGrupoExpediente?: Record<string, { visorFicha?: Record<string, unknown> }> }>(
    join(root, "public/data/madrid-sigma-visor-slim.json"),
  );
  if (!sigma?.expedientes?.length || !slim?.byGrupoExpediente) return [];

  const candidates = sigma.expedientes
    .map((exp) => {
      const grupo = expedienteGrupoKey(String(exp.EXP_TX_NUMERO || ""));
      const year = yearFromExpediente(grupo);
      const ficha = slim.byGrupoExpediente?.[grupo]?.visorFicha;
      const sup = Number(ficha?.superficieAmbitoM2);
      if (!grupo || !year || year < 2024 || !Number.isFinite(sup) || sup < 2_000) return null;
      return {
        grupo,
        year,
        sup,
        fase: String(exp.FAS_TX_DENOM || "").trim(),
        denom: shortTitle(String(exp.EXP_TX_DENOM || ficha?.denominacion || grupo)),
      };
    })
    .filter((x): x is NonNullable<typeof x> => x != null)
    .sort((a, b) => b.year - a.year || b.sup - a.sup)
    .slice(0, 2);

  return candidates.map((item, index) => ({
    id: `sigma-superficie-${item.grupo.replace(/\W+/g, "-")}`,
    href: sigmaHref(item.grupo),
    tag: index === 0 ? "Ámbito reciente" : "m²",
    dateLabel: String(item.year),
    title: `${item.denom}: ${formatInt(Math.round(item.sup))} m² de ámbito`,
    dek: [item.fase, "Sin cifra fiable de viviendas recientes; aquí pesa la superficie y la fase del expediente."]
      .filter(Boolean)
      .join(" · "),
    valueLabel: `${formatInt(Math.round(item.sup))} m²`,
    expedienteGrupo: item.grupo,
    ctaLabel: "Ver ficha",
  }));
}

function buildLandingNewsFromStats(root: string): LandingNewsFile | null {
  const stats = readJson<MadridDashboardStats>(join(root, "public/data/madrid-dashboard-stats.json"));
  if (!stats?.licencias) return null;

  const items = [...buildLicenseNews(stats), ...buildSigmaNews(root)].slice(0, 6);
  if (!items.length) return null;

  return {
    generatedAt: stats.licencias.generatedAt || stats.generatedAt || new Date().toISOString(),
    source: "madrid-dashboard-stats + madrid-sigma",
    criteria:
      "Señales recientes de licencias y, si no hay proyectos de vivienda fiables, expedientes recientes por superficie",
    items,
  };
}

export function loadLandingNews(): LandingNewsFile {
  if (cached) return cached;
  const root = process.cwd();
  cached = buildLandingNewsFromStats(root);
  if (cached) return cached;

  const path = join(root, "public/data/landing-news.json");
  cached = readJson<LandingNewsFile>(path) ?? {
    generatedAt: new Date().toISOString(),
    items: FALLBACK,
  };
  if (!cached.items?.length) cached.items = FALLBACK;
  return cached;
}
