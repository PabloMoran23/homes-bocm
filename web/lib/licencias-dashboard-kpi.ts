import type { ActuacionQueCodigo } from "@/lib/actuacion-edificio";
import type { MadridDashboardMapaMonth, MadridDashboardStats } from "@/lib/types";

export type LicenciasKpiPeriod = "1M" | "1Y";

export type LicenciasKpiMetricId = "volumen" | "obras" | "vivienda";

/** Licencias que implican obra física (excluye uso, consultas y trámites genéricos). */
export const LICENCIAS_OBRA_TIPOS: ActuacionQueCodigo[] = [
  "vivienda_obra",
  "vivienda_obra_menor",
  "local_obra",
  "local_a_vivienda",
  "edificio_obra_grande",
  "edificio_reforma_conservacion",
  "edificio_demolicion",
  "obra_exterior",
];

/** Señal de vivienda nueva o uso residencial relevante (alineado con landing-news). */
export const LICENCIAS_VIVIENDA_TIPOS: ActuacionQueCodigo[] = [
  "vivienda_obra",
  "vivienda_obra_menor",
  "vivienda_uso",
  "local_a_vivienda",
  "edificio_primera_ocupacion",
];

export type LicenciasKpiSnapshot = {
  value: number;
  previous: number;
  pctChange: number | null;
  periodLabel: string;
  compareLabel: string;
  comparisonAvailable: boolean;
};

function sortedMonthly(lic: NonNullable<MadridDashboardStats["licencias"]>): MadridDashboardMapaMonth[] {
  return [...(lic.seriesByMonthActuacionQue ?? lic.seriesByMonthMapaTipo ?? [])].sort((a, b) =>
    a.month.localeCompare(b.month),
  );
}

function monthTypeCount(row: MadridDashboardMapaMonth | undefined, ids: readonly string[]) {
  if (!ids.length) {
    return row?.tipos.reduce((sum, t) => sum + t.count, 0) ?? 0;
  }
  return ids.reduce((sum, id) => sum + (row?.tipos.find((t) => t.id === id)?.count ?? 0), 0);
}

function yearToDateCount(
  rows: MadridDashboardMapaMonth[],
  year: string,
  untilMonth: number,
  ids: readonly string[],
) {
  return rows
    .filter((row) => row.month.startsWith(`${year}-`) && Number(row.month.slice(5, 7)) <= untilMonth)
    .reduce((sum, row) => sum + monthTypeCount(row, ids), 0);
}

function formatMonthShort(monthKey: string): string {
  const [y, m] = monthKey.split("-");
  const d = new Date(Number(y), Number(m) - 1, 1);
  return d.toLocaleDateString("es-ES", { month: "short", year: "numeric" });
}

function formatMonthRange(fromKey: string, toKey: string): string {
  const from = formatMonthShort(fromKey);
  const to = formatMonthShort(toKey);
  const [y1] = fromKey.split("-");
  const [y2] = toKey.split("-");
  if (y1 === y2 && fromKey.slice(5, 7) === toKey.slice(5, 7)) return from;
  if (y1 === y2) {
    const fromMonth = new Date(Number(y1), Number(fromKey.slice(5, 7)) - 1, 1).toLocaleDateString(
      "es-ES",
      { month: "short" },
    );
    const toMonth = new Date(Number(y2), Number(toKey.slice(5, 7)) - 1, 1).toLocaleDateString(
      "es-ES",
      { month: "short", year: "numeric" },
    );
    return `${fromMonth}–${toMonth}`;
  }
  return `${from} – ${to}`;
}

export function percentChangeValue(current: number, previous: number): number | null {
  if (!Number.isFinite(current) || !Number.isFinite(previous) || previous === 0) return null;
  return ((current - previous) / previous) * 100;
}

export function formatPctChange(pct: number | null): string {
  if (pct == null || !Number.isFinite(pct)) return "—";
  const sign = pct > 0 ? "+" : "";
  return `${sign}${Math.round(pct).toLocaleString("es-ES")}%`;
}

function tipoIdsForMetric(metric: LicenciasKpiMetricId): readonly string[] {
  if (metric === "volumen") return [];
  if (metric === "obras") return LICENCIAS_OBRA_TIPOS;
  return LICENCIAS_VIVIENDA_TIPOS;
}

export function computeLicenciasKpi(
  lic: NonNullable<MadridDashboardStats["licencias"]>,
  metric: LicenciasKpiMetricId,
  period: LicenciasKpiPeriod,
): LicenciasKpiSnapshot | null {
  const monthly = sortedMonthly(lic);
  const latest = monthly.at(-1);
  const coverage = lic.periodCoverage || {};
  const closed = (month: string) => coverage[month]?.status === "complete";
  if (!latest) return null;

  const ids = tipoIdsForMetric(metric);

  if (period === "1M") {
    const value = monthTypeCount(latest, ids);
    const [y, m] = latest.month.split("-").map(Number);
    const prevKey = m === 1 ? `${y - 1}-12` : `${y}-${String(m - 1).padStart(2, "0")}`;
    const previous = monthly.find(row => row.month === prevKey);
    const prevValue = previous ? monthTypeCount(previous, ids) : 0;
    const comparisonAvailable = closed(latest.month) && closed(prevKey);
    return {
      value,
      previous: prevValue,
      pctChange: comparisonAvailable ? percentChangeValue(value, prevValue) : null,
      comparisonAvailable,
      periodLabel: formatMonthShort(latest.month) + (closed(latest.month) ? "" : " · parcial"),
      compareLabel: comparisonAvailable ? formatMonthShort(prevKey) : "Sin comparación: cierre no acreditado",
    };
  }

  const year = latest.month.slice(0, 4);
  const untilMonth = Number(latest.month.slice(5, 7));
  const prevYear = String(Number(year) - 1);
  const common = Array.from({ length: untilMonth }, (_, i) => String(i + 1).padStart(2, "0"))
    .filter(m => closed(`${year}-${m}`) && closed(`${prevYear}-${m}`));
  const comparisonAvailable = common.length > 0;
  const countCommon = (y: string) => common.reduce((sum, m) => sum + monthTypeCount(monthly.find(row => row.month === `${y}-${m}`), ids), 0);
  const value = comparisonAvailable ? countCommon(year) : yearToDateCount(monthly, year, untilMonth, ids);
  const prevValue = comparisonAvailable ? countCommon(prevYear) : 0;
  const ytdStart = `${year}-01`;

  return {
    value,
    previous: prevValue,
    pctChange: comparisonAvailable ? percentChangeValue(value, prevValue) : null,
    comparisonAvailable,
    periodLabel: comparisonAvailable ? `${year} · meses cerrados ${common.join(", ")}` : formatMonthRange(ytdStart, latest.month) + " · parcial",
    compareLabel: comparisonAvailable ? `${prevYear} · mismos meses cerrados` : "Sin comparación: cierre no acreditado",
  };
}

export const LICENCIAS_KPI_LABELS: Record<
  LicenciasKpiMetricId,
  { label: string; hint: string }
> = {
  volumen: {
    label: "Volumen total",
    hint: "Todas las licencias concedidas en el periodo",
  },
  obras: {
    label: "Obras",
    hint: "Obra en vivienda, local, edificio o exterior",
  },
  vivienda: {
    label: "Nuevas viviendas",
    hint: "Licencias con señal de vivienda nueva o uso residencial",
  },
};
