import { sigmaClassificationLabel } from "@/lib/sigma-classification";
import { SIGMA_DASHBOARD_PRIMARY_AXES } from "@/lib/sigma-dashboard-constants";
import type { MadridDashboardCount, MadridDashboardStats } from "@/lib/types";

export type SigmaFilterRow = {
  g: string;
  y: number;
  cp: string;
  to: string;
  tl: string;
  es: string;
  fn: string;
  cf: string;
  d: string;
  i: string;
  tp: string;
  fig: string;
  sa: string;
  ut: string;
  ao: string;
  pr: string;
  sup: string;
  fc: string;
  ly: string;
  vf: number;
  cl: number;
  geo: number;
  tr: number;
};

export type SigmaFilterOption = { id: string; label: string; count: number };

export type SigmaFilterRowsFile = {
  generatedAt: string;
  totalRows: number;
  options: {
    categoriaProyecto: SigmaFilterOption[];
    tipoObra: SigmaFilterOption[];
    tipoLegal: SigmaFilterOption[];
    escala: SigmaFilterOption[];
    faseNormalizada: SigmaFilterOption[];
    confianza: SigmaFilterOption[];
    distritos: SigmaFilterOption[];
    iniciativas: SigmaFilterOption[];
    tipoPlaneamiento: SigmaFilterOption[];
    figuraTipo: SigmaFilterOption[];
    sistemaActuacion: SigmaFilterOption[];
    unidadTramitadora: SigmaFilterOption[];
    ambitoOrdenacion: SigmaFilterOption[];
    promotores: SigmaFilterOption[];
    superficie: SigmaFilterOption[];
    faseCatalogo: SigmaFilterOption[];
    layer: SigmaFilterOption[];
  };
  rows: SigmaFilterRow[];
};

export type SigmaDashboardFilters = {
  anio: string[];
  categoriaProyecto: string[];
  tipoObra: string[];
  tipoLegal: string[];
  escala: string[];
  distrito: string[];
  iniciativa: string[];
};

export const EMPTY_SIGMA_FILTERS: SigmaDashboardFilters = {
  anio: [],
  categoriaProyecto: [],
  tipoObra: [],
  tipoLegal: [],
  escala: [],
  distrito: [],
  iniciativa: [],
};

export function hasActiveSigmaFilters(f: SigmaDashboardFilters): boolean {
  return (
    f.anio.length > 0 ||
    f.categoriaProyecto.length > 0 ||
    f.tipoObra.length > 0 ||
    f.tipoLegal.length > 0 ||
    f.escala.length > 0 ||
    f.distrito.length > 0 ||
    f.iniciativa.length > 0
  );
}

export function countActiveSigmaFilters(f: SigmaDashboardFilters): number {
  return (
    f.anio.length +
    f.categoriaProyecto.length +
    f.tipoObra.length +
    f.tipoLegal.length +
    f.escala.length +
    f.distrito.length +
    f.iniciativa.length
  );
}

/** Opciones de año (incoación del expediente) derivadas de las filas cargadas. */
export function buildSigmaAnioOptions(rows: SigmaFilterRow[]): SigmaFilterOption[] {
  const counts = new Map<number, number>();
  for (const r of rows) {
    if (r.y >= 1990 && r.y <= 2100) counts.set(r.y, (counts.get(r.y) || 0) + 1);
  }
  return [...counts.entries()]
    .sort((a, b) => b[0] - a[0])
    .map(([y, count]) => ({ id: String(y), label: String(y), count }));
}

export function filterSigmaRows(rows: SigmaFilterRow[], f: SigmaDashboardFilters): SigmaFilterRow[] {
  return hasActiveSigmaFilters(f) ? rows.filter((r) => matchesRow(r, f)) : rows;
}

function matchesRow(row: SigmaFilterRow, f: SigmaDashboardFilters): boolean {
  if (f.anio.length > 0 && !f.anio.includes(String(row.y))) return false;
  if (f.categoriaProyecto.length > 0 && !f.categoriaProyecto.includes(row.cp)) return false;
  if (f.tipoObra.length > 0 && !f.tipoObra.includes(row.to)) return false;
  if (f.tipoLegal.length > 0 && !f.tipoLegal.includes(row.tl)) return false;
  if (f.escala.length > 0 && !f.escala.includes(row.es)) return false;
  if (f.distrito.length > 0 && !f.distrito.includes(row.d)) return false;
  if (f.iniciativa.length > 0 && !f.iniciativa.includes(row.i)) return false;
  return true;
}

function topCounts(map: Map<string, number>, labelFn: (id: string) => string, n = 14): MadridDashboardCount[] {
  return [...map.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([id, count]) => ({ name: labelFn(id), count }));
}

function axisLabel(id: string): string {
  return sigmaClassificationLabel(id) ?? id.replace(/_/g, " ");
}

function plainLabel(id: string): string {
  return id
    .split(/\s+/)
    .map((w) => (w.length <= 2 ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
}

const SUP_NAMES: Record<string, string> = {
  lt500: "< 500 m²",
  "500-2k": "500 – 2.000 m²",
  "2k-10k": "2.000 – 10.000 m²",
  gt10k: "> 10.000 m²",
};

export type SigmaDashboardView = MadridDashboardStats["sigma"] & {
  byCategoriaProyecto: MadridDashboardCount[];
  byTipoObra: MadridDashboardCount[];
  byTipoLegal: MadridDashboardCount[];
  byEscala: MadridDashboardCount[];
  byFaseNormalizada: MadridDashboardCount[];
  byConfianza: MadridDashboardCount[];
  bySistemaActuacion: MadridDashboardCount[];
  byUnidadTramitadora: MadridDashboardCount[];
  byAmbitoOrdenacion: MadridDashboardCount[];
  conClasificacion: number;
};

export function aggregateSigmaFromRows(
  rows: SigmaFilterRow[],
  filters: SigmaDashboardFilters,
  base: MadridDashboardStats["sigma"],
): SigmaDashboardView {
  const filtered = hasActiveSigmaFilters(filters) ? rows.filter((r) => matchesRow(r, filters)) : rows;

  const byYear = new Map<number, number>();
  const maps = {
    cp: new Map<string, number>(),
    to: new Map<string, number>(),
    tl: new Map<string, number>(),
    es: new Map<string, number>(),
    fn: new Map<string, number>(),
    cf: new Map<string, number>(),
    d: new Map<string, number>(),
    i: new Map<string, number>(),
    tp: new Map<string, number>(),
    fig: new Map<string, number>(),
    sa: new Map<string, number>(),
    ut: new Map<string, number>(),
    ao: new Map<string, number>(),
    pr: new Map<string, number>(),
    sup: new Map<string, number>(),
    fc: new Map<string, number>(),
    ly: new Map<string, number>(),
  };

  let conVisorFicha = 0;
  let conClasificacion = 0;
  let conGeometry = 0;
  let conTramitacion = 0;

  for (const r of filtered) {
    if (r.y) byYear.set(r.y, (byYear.get(r.y) || 0) + 1);
    if (r.cp) maps.cp.set(r.cp, (maps.cp.get(r.cp) || 0) + 1);
    if (r.to) maps.to.set(r.to, (maps.to.get(r.to) || 0) + 1);
    if (r.tl) maps.tl.set(r.tl, (maps.tl.get(r.tl) || 0) + 1);
    if (r.es) maps.es.set(r.es, (maps.es.get(r.es) || 0) + 1);
    if (r.fn) maps.fn.set(r.fn, (maps.fn.get(r.fn) || 0) + 1);
    if (r.cf) maps.cf.set(r.cf, (maps.cf.get(r.cf) || 0) + 1);
    if (r.d) maps.d.set(r.d, (maps.d.get(r.d) || 0) + 1);
    if (r.i) maps.i.set(r.i, (maps.i.get(r.i) || 0) + 1);
    if (r.tp) maps.tp.set(r.tp, (maps.tp.get(r.tp) || 0) + 1);
    if (r.fig) maps.fig.set(r.fig, (maps.fig.get(r.fig) || 0) + 1);
    if (r.sa) maps.sa.set(r.sa, (maps.sa.get(r.sa) || 0) + 1);
    if (r.ut) maps.ut.set(r.ut, (maps.ut.get(r.ut) || 0) + 1);
    if (r.ao) maps.ao.set(r.ao, (maps.ao.get(r.ao) || 0) + 1);
    if (r.pr) maps.pr.set(r.pr, (maps.pr.get(r.pr) || 0) + 1);
    if (r.sup) maps.sup.set(r.sup, (maps.sup.get(r.sup) || 0) + 1);
    if (r.fc) maps.fc.set(r.fc, (maps.fc.get(r.fc) || 0) + 1);
    if (r.ly) maps.ly.set(r.ly, (maps.ly.get(r.ly) || 0) + 1);
    if (r.vf) conVisorFicha += 1;
    if (r.cl) conClasificacion += 1;
    if (r.geo) conGeometry += 1;
    if (r.tr) conTramitacion += 1;
  }

  const seriesByYear = [...byYear.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([year, count]) => ({ year, count }));

  const baseExt = base as SigmaDashboardView;

  return {
    ...base,
    total: filtered.length,
    conVisorFicha,
    conClasificacion,
    conTramitacion,
    conGeometry,
    seriesByYear,
    byCategoriaProyecto: topCounts(maps.cp, axisLabel, 12),
    byTipoObra: topCounts(maps.to, axisLabel, 12),
    byTipoLegal: topCounts(maps.tl, axisLabel, 10),
    byEscala: topCounts(maps.es, axisLabel, 8),
    byFaseNormalizada: topCounts(maps.fn, axisLabel, 10),
    byConfianza: topCounts(maps.cf, (id) => (id === "alta" ? "Alta" : id === "media" ? "Media" : id === "baja" ? "Baja" : id), 4),
    byDistrito: topCounts(maps.d, plainLabel, 22),
    byPromotor: topCounts(maps.pr, (id) => id, 12),
    byFiguraTipo: topCounts(maps.fig, plainLabel, 10),
    byTipoPlaneamiento: topCounts(maps.tp, plainLabel, 8),
    byIniciativa: topCounts(maps.i, plainLabel, 6),
    byTramite: base.byTramite,
    byLayer: topCounts(maps.ly, plainLabel, 6),
    byOrgano: base.byOrgano,
    byFase: topCounts(maps.fc, plainLabel, 12),
    byTipoFiguraAbrev: base.byTipoFiguraAbrev,
    superficieBuckets: topCounts(maps.sup, (id) => SUP_NAMES[id] || id, 4),
    topViviendas: base.topViviendas,
    conMetricasPdf: base.conMetricasPdf,
    viviendasEnMetricas: base.viviendasEnMetricas,
    expedientesConViviendas: base.expedientesConViviendas,
    bySistemaActuacion: topCounts(maps.sa, plainLabel, 8),
    byUnidadTramitadora: topCounts(maps.ut, plainLabel, 8),
    byAmbitoOrdenacion: topCounts(maps.ao, (id) => id.toUpperCase(), 12),
    clasificacionGeneratedAt: baseExt.clasificacionGeneratedAt,
  };
}

export function sigmaFilterOptionsForAxis(
  file: SigmaFilterRowsFile,
  axisId: (typeof SIGMA_DASHBOARD_PRIMARY_AXES)[number]["id"],
): SigmaFilterOption[] {
  return file.options[axisId];
}
