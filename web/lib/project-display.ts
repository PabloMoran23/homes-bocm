import type { Project } from "./types";

export function projectPath(id: string): string {
  return `/proyecto/${encodeURIComponent(id)}`;
}

export function relevanciaLabel(esRelevante: boolean | null | undefined): string {
  if (esRelevante === true) return "Relevante";
  if (esRelevante === false) return "No relevante";
  return "Sin clasificar";
}

export function relevanciaBadgeClass(esRelevante: boolean | null | undefined): string {
  if (esRelevante === true) return "bg-emerald-50 text-emerald-800 ring-emerald-200";
  if (esRelevante === false) return "bg-slate-100 text-slate-600 ring-slate-200";
  return "bg-amber-50 text-amber-900 ring-amber-200";
}

export function sigmaMatchLabel(type: string | null | undefined): string {
  if (type === "expediente_numero") return "Número de expediente (verificado)";
  if (type === "denominacion_fuzzy") return "Denominación (aprox.)";
  if (type === "denominacion_estricta" || type === "denominacion_sector") {
    return "Denominación (aprox.)";
  }
  return type ?? "";
}

export function coordSourceLabel(source: string | null | undefined): string {
  switch (source) {
    case "municipio_cache":
      return "Centro del municipio (caché Madrid)";
    case "sector_geometry":
      return "Geometría del sector (sector_geometry)";
    case "sector_geometry_municipio":
      return "Centroide municipal (fallback sector_geometry)";
    case "sigma_madrid_ip":
      return "Ubicación SIGMA (información pública, Ayto. Madrid)";
    case "sigma_madrid_ad":
      return "Ubicación SIGMA (catálogo planeamiento AD, polígono expediente)";
    case "sigma_madrid_gestion":
      return "Ubicación SIGMA (gestión, polígono expediente)";
    case "sigma_madrid_urbanizacion":
      return "Ubicación SIGMA (urbanización, polígono expediente)";
    default:
      return source ?? "Sin coordenadas";
  }
}

export function sigmaCatalogSourceLabel(source: string | null | undefined): string | null {
  if (!hasValue(source)) return null;
  const s = source.trim();
  if (s === "informacion_publica") return "Información pública (SIGMA)";
  if (s === "tramitados_ad") return "Planeamiento — expedientes tramitados (SIGMA)";
  if (s === "tramitados_gestion") return "Gestión — expedientes tramitados (SIGMA)";
  if (s === "tramitados_urbanizacion") return "Urbanización — expedientes tramitados (SIGMA)";
  return s;
}

export function sigmaLayerKindLabel(kind: string | null | undefined): string | null {
  if (!hasValue(kind)) return null;
  const k = kind.trim();
  const map: Record<string, string> = {
    planeamiento: "Planeamiento",
    gestion: "Gestión",
    urbanizacion: "Urbanización",
    tramitados_ad: "Tramitados (catálogo AD)",
    tramitados_gestion: "Gestión (tramitados)",
    tramitados_urbanizacion: "Urbanización (tramitados)",
  };
  return map[k] || k;
}

/** Fechas SIGMA/ArcGIS en milisegundos epoch → texto localizado. */
export function formatSigmaArcgisMs(ms: unknown): string | null {
  const n = Number(ms);
  if (ms === null || ms === undefined || ms === "" || Number.isNaN(n)) return null;
  try {
    return new Intl.DateTimeFormat("es-ES", { dateStyle: "medium", timeZone: "UTC" }).format(
      new Date(n),
    );
  } catch {
    return null;
  }
}

/** Fechas ArcGIS sincronizadas como yyyy-mm-dd (UTC). */
export function formatSigmaDateYmdUTC(ymd: string | null | undefined): string | null {
  if (!hasValue(ymd) || ymd.length < 10) return null;
  const t = Date.parse(`${ymd.slice(0, 10)}T12:00:00.000Z`);
  if (Number.isNaN(t)) return ymd;
  return new Intl.DateTimeFormat("es-ES", { dateStyle: "medium", timeZone: "UTC" }).format(t);
}

export function formatEur(n: number | null | undefined): string | null {
  if (n == null || Number.isNaN(n)) return null;
  return new Intl.NumberFormat("es-ES", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(n);
}

export function hasValue(v: string | null | undefined): v is string {
  return Boolean(v && String(v).trim());
}

export function projectHeadline(p: Project): string {
  return p.title.trim() || p.nombreSector || p.tipoInstrumento || "Anuncio urbanístico";
}
