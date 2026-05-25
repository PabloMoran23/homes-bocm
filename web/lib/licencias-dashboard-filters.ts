import type { ActuacionQueCodigo } from "@/lib/actuacion-edificio";
import { labelActuacionQue } from "@/lib/actuacion-que-config";
import { normDistritoKey } from "@/lib/madrid-distrito";
import type {
  MadridDashboardCount,
  MadridDashboardMapaMonth,
  MadridDashboardMapaTipo,
  MadridDashboardStats,
} from "@/lib/types";

export type LicenciasFilterRow = {
  m: string;
  d: string;
  a: string;
  p: string;
  u: string;
};

export type LicenciasFilterOption = {
  id: string;
  label: string;
  count: number;
};

export type LicenciasFilterRowsFile = {
  generatedAt: string;
  totalRows: number;
  options: {
    distritos: LicenciasFilterOption[];
    actuaciones: LicenciasFilterOption[];
    procedimientos: LicenciasFilterOption[];
    usos: LicenciasFilterOption[];
  };
  rows: LicenciasFilterRow[];
};

export type LicenciasDashboardFilters = {
  distritos: string[];
  actuaciones: string[];
  procedimientos: string[];
  usos: string[];
};

export const EMPTY_LICENCIAS_FILTERS: LicenciasDashboardFilters = {
  distritos: [],
  actuaciones: [],
  procedimientos: [],
  usos: [],
};

export function hasActiveLicenciasFilters(f: LicenciasDashboardFilters): boolean {
  return (
    f.distritos.length > 0 ||
    f.actuaciones.length > 0 ||
    f.procedimientos.length > 0 ||
    f.usos.length > 0
  );
}

export function countActiveLicenciasFilters(f: LicenciasDashboardFilters): number {
  return f.distritos.length + f.actuaciones.length + f.procedimientos.length + f.usos.length;
}

function matchesRow(row: LicenciasFilterRow, f: LicenciasDashboardFilters): boolean {
  if (f.distritos.length > 0 && !f.distritos.includes(row.d)) return false;
  if (f.actuaciones.length > 0 && !f.actuaciones.includes(row.a)) return false;
  if (f.procedimientos.length > 0 && !f.procedimientos.includes(row.p)) return false;
  if (f.usos.length > 0 && !f.usos.includes(row.u)) return false;
  return true;
}

function topCounts(map: Map<string, number>, n = 20): MadridDashboardCount[] {
  return [...map.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([name, count]) => ({ name, count }));
}

const ACTUACION_ORDER = [
  "vivienda_obra_menor",
  "vivienda_obra",
  "vivienda_uso",
  "local_actividad",
  "local_obra",
  "local_a_vivienda",
  "edificio_obra_grande",
  "edificio_reforma_conservacion",
  "edificio_demolicion",
  "edificio_primera_ocupacion",
  "obra_exterior",
  "consulta",
  "tramite_generico",
  "otro",
] as const;

function actuacionLabel(id: string): string {
  return labelActuacionQue(id as ActuacionQueCodigo);
}

/**
 * Agrega filas filtradas al mismo shape que `stats.licencias` (subset usado por el dashboard).
 */
export function aggregateLicenciasFromRows(
  rows: LicenciasFilterRow[],
  filters: LicenciasDashboardFilters,
  base: NonNullable<MadridDashboardStats["licencias"]>,
): NonNullable<MadridDashboardStats["licencias"]> {
  const filtered = hasActiveLicenciasFilters(filters)
    ? rows.filter((r) => matchesRow(r, filters))
    : rows;

  const byMonth = new Map<string, number>();
  const byYear = new Map<number, number>();
  const byMonthActuacion = new Map<string, Map<string, number>>();
  const byYearActuacion = new Map<number, Map<string, number>>();
  const byDistrito = new Map<string, number>();
  const byUso = new Map<string, number>();
  const byProcedimiento = new Map<string, number>();

  for (const r of filtered) {
    byMonth.set(r.m, (byMonth.get(r.m) || 0) + 1);
    const y = Number(r.m.slice(0, 4));
    if (Number.isFinite(y)) byYear.set(y, (byYear.get(y) || 0) + 1);

    if (!byMonthActuacion.has(r.m)) byMonthActuacion.set(r.m, new Map());
    const mm = byMonthActuacion.get(r.m)!;
    mm.set(r.a, (mm.get(r.a) || 0) + 1);

    if (Number.isFinite(y)) {
      if (!byYearActuacion.has(y)) byYearActuacion.set(y, new Map());
      const ym = byYearActuacion.get(y)!;
      ym.set(r.a, (ym.get(r.a) || 0) + 1);
    }

    byDistrito.set(r.d, (byDistrito.get(r.d) || 0) + 1);
    byUso.set(r.u, (byUso.get(r.u) || 0) + 1);
    byProcedimiento.set(r.p, (byProcedimiento.get(r.p) || 0) + 1);
  }

  const months = [...byMonth.keys()].sort();
  const years = [...byYear.keys()].sort((a, b) => a - b);

  const actuacionIds = [
    ...ACTUACION_ORDER.filter((id) =>
      filtered.some((r) => r.a === id) || base.topActuacionQue?.some((t) => t.id === id),
    ),
    ...[...new Set(filtered.map((r) => r.a))].filter(
      (id) => !ACTUACION_ORDER.includes(id as (typeof ACTUACION_ORDER)[number]),
    ),
  ];

  const seriesByMonthActuacionQue: MadridDashboardMapaMonth[] = months.map((month) => ({
    month,
    tipos: actuacionIds.map((id) => ({
      id,
      label: actuacionLabel(id),
      count: byMonthActuacion.get(month)?.get(id) || 0,
    })),
  }));

  const seriesByYearActuacionQue = years.map((year) => ({
    year,
    tipos: actuacionIds.map((id) => ({
      id,
      label: actuacionLabel(id),
      count: byYearActuacion.get(year)?.get(id) || 0,
    })),
  }));

  const topActuacionQue: MadridDashboardMapaTipo[] = actuacionIds
    .map((id) => ({
      id,
      label: actuacionLabel(id),
      count: filtered.filter((r) => r.a === id).length,
    }))
    .filter((x) => x.count > 0)
    .sort((a, b) => b.count - a.count);

  const distCounts = topCounts(byDistrito, 22);
  const countByDistrito = new Map(distCounts.map((d) => [d.name, d.count]));
  const topDistritoMap = (base.topDistritoMap ?? [])
    .map((p) => ({
      ...p,
      count: countByDistrito.get(normDistritoKey(p.name)) ?? 0,
    }))
    .filter((p) => p.count > 0)
    .sort((a, b) => b.count - a.count);

  return {
    generatedAt: base.generatedAt,
    totalRows: filtered.length,
    withCoords: base.withCoords,
    years,
    months,
    seriesByYear: years.map((year) => ({
      year,
      total: byYear.get(year) || 0,
      uso: [],
    })),
    seriesByMonth: months.map((month) => ({
      month,
      total: byMonth.get(month) || 0,
    })),
    seriesByYearActuacionQue,
    seriesByMonthActuacionQue,
    topActuacionQue,
    topUso: topCounts(byUso, 8),
    topDistrito: distCounts,
    topDistritoMap,
    topProcedimiento: topCounts(byProcedimiento, 10),
    topTipoExpediente: base.topTipoExpediente,
  };
}
