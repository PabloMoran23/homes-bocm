import type { SigmaFilterRow } from "@/lib/sigma-dashboard-filters";
import { formatPctChange, percentChangeValue } from "@/lib/licencias-dashboard-kpi";

export type SigmaKpiPeriod = "1Y" | "5Y";

export type SigmaKpiMetricId = "totales" | "vivienda" | "urbanismo";

/** Categorías con señal clara de vivienda o residencial. */
export const SIGMA_VIVIENDA_CATEGORIAS = new Set([
  "gran_desarrollo_residencial",
  "residencial_o_vivienda",
]);

export const SIGMA_VIVIENDA_TIPOS_OBRA = new Set([
  "vivienda_residencial",
  "edificio_ampliacion",
  "garaje_aparcamiento",
]);

/** Nuevas actuaciones de urbanización (suelo, redes, viario). */
export const SIGMA_URBANISMO_CATEGORIAS = new Set(["urbanizacion_infraestructuras"]);

export const SIGMA_URBANISMO_TIPOS_OBRA = new Set([
  "urbanizacion_redes",
  "infraestructura_viaria",
  "equipamiento_publico",
]);

export const SIGMA_URBANISMO_TIPOS_LEGAL = new Set(["proyecto_urbanizacion"]);

export type SigmaKpiSnapshot = {
  value: number;
  previous: number;
  pctChange: number | null;
  periodLabel: string;
  compareLabel: string;
};

export function sigmaRowIsVivienda(row: SigmaFilterRow): boolean {
  return SIGMA_VIVIENDA_CATEGORIAS.has(row.cp) || SIGMA_VIVIENDA_TIPOS_OBRA.has(row.to);
}

export function sigmaRowIsUrbanismo(row: SigmaFilterRow): boolean {
  return (
    SIGMA_URBANISMO_CATEGORIAS.has(row.cp) ||
    SIGMA_URBANISMO_TIPOS_OBRA.has(row.to) ||
    SIGMA_URBANISMO_TIPOS_LEGAL.has(row.tl)
  );
}

function matchesMetric(row: SigmaFilterRow, metric: SigmaKpiMetricId): boolean {
  if (metric === "totales") return true;
  if (metric === "vivienda") return sigmaRowIsVivienda(row);
  return sigmaRowIsUrbanismo(row);
}

function countInYearRange(rows: SigmaFilterRow[], metric: SigmaKpiMetricId, from: number, to: number) {
  return rows.filter((r) => r.y >= from && r.y <= to && matchesMetric(r, metric)).length;
}

function countsByExpedienteYear(rows: SigmaFilterRow[]): Map<number, number> {
  const map = new Map<number, number>();
  for (const r of rows) {
    if (r.y >= 1990 && r.y <= 2100) map.set(r.y, (map.get(r.y) || 0) + 1);
  }
  return map;
}

/**
 * Año de referencia para KPIs: el último año civil con datos cerrados.
 * Si el año en curso tiene muy pocos expedientes vs el anterior, no se usa (evita 2026 con 2 vs 2025 con 31).
 */
export function sigmaKpiReferenceYear(rows: SigmaFilterRow[]): number | null {
  const byY = countsByExpedienteYear(rows);
  if (!byY.size) return null;

  const calendarYear = new Date().getFullYear();
  const maxInData = Math.max(...byY.keys());

  if (maxInData < calendarYear) return maxInData;

  const cur = byY.get(calendarYear) || 0;
  const prev = byY.get(calendarYear - 1) || 0;

  if (prev > 0 && cur < Math.max(8, prev * 0.4)) return calendarYear - 1;
  return maxInData;
}

export function computeSigmaKpi(
  rows: SigmaFilterRow[],
  metric: SigmaKpiMetricId,
  period: SigmaKpiPeriod,
): SigmaKpiSnapshot | null {
  if (!rows.length) return null;
  const ref = sigmaKpiReferenceYear(rows);
  if (ref == null) return null;

  if (period === "1Y") {
    const value = countInYearRange(rows, metric, ref, ref);
    const prevYear = ref - 1;
    const previous = countInYearRange(rows, metric, prevYear, prevYear);
    return {
      value,
      previous,
      pctChange: percentChangeValue(value, previous),
      periodLabel: String(ref),
      compareLabel: String(prevYear),
    };
  }

  const from5 = ref - 4;
  const to5Prev = ref - 5;
  const from5Prev = ref - 9;
  const value = countInYearRange(rows, metric, from5, ref);
  const previous = countInYearRange(rows, metric, from5Prev, to5Prev);

  return {
    value,
    previous,
    pctChange: percentChangeValue(value, previous),
    periodLabel: `${from5}–${ref}`,
    compareLabel: `${from5Prev}–${to5Prev}`,
  };
}

export { formatPctChange };

export const SIGMA_KPI_LABELS: Record<SigmaKpiMetricId, { label: string; hint: string }> = {
  totales: {
    label: "Proyectos totales",
    hint: "Incoaciones por año del expediente (último año completo en 1Y)",
  },
  vivienda: {
    label: "Con vivienda",
    hint: "Residencial, gran desarrollo o obra en edificio/vivienda",
  },
  urbanismo: {
    label: "Urbanismo nuevo",
    hint: "Urbanización, redes, viario o proyecto de urbanización",
  },
};
