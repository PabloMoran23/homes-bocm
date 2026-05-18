/**
 * Etiquetas y textos de ayuda para proyectos SIGMA (Ayto. Madrid) orientados a usuario medio.
 */

import { formatSigmaArcgisMs, formatSigmaDateYmdUTC, hasValue } from "@/lib/project-display";
import { viviendaNuevaLabel } from "@/lib/sigma-metrics";

export type SigmaStatusBadge = {
  label: string;
  className: string;
};

/** Badge principal: información pública vs en tramitación. */
export function sigmaStatusBadge(source: string | null | undefined): SigmaStatusBadge {
  if (source === "informacion_publica") {
    return {
      label: "Periodo de alegaciones abierto",
      className: "bg-violet-100 text-violet-900",
    };
  }
  return {
    label: "En tramitación",
    className: "bg-amber-50 text-amber-900 ring-1 ring-amber-200",
  };
}

/** Tipo de actuación en lenguaje llano (figura / abreviatura del catálogo). */
export function sigmaTipoActuacion(
  figEtiq?: string | null,
  tfigAbrev?: string | null,
): string | null {
  const raw = [figEtiq, tfigAbrev].filter(hasValue).map((s) => s.trim());
  if (!raw.length) return null;

  const key = raw.join(" ").toUpperCase();
  const FIGURA: Record<string, string> = {
    MPG: "Modificación del Plan General de Madrid",
    "MODIFICACIÓN PUNTUAL DEL PGOU": "Modificación puntual del Plan General",
    "MODIFICACION PUNTUAL DEL PGOU": "Modificación puntual del Plan General",
    "MOD. PUNTUAL PGOU": "Modificación puntual del Plan General",
    "ESTUDIO DE DETALLE": "Estudio de detalle (ordenación de parcela o edificio)",
    "ED": "Estudio de detalle",
    "PLAN PARCIAL": "Plan parcial (reglas del sector: usos, alturas…)",
    "PP": "Plan parcial",
    "PLAN ESPECIAL": "Plan especial (actuación concreta en un ámbito)",
    "PE": "Plan especial",
    "PECU": "Control de usos en edificio existente (locales, aforo…)",
    "PECUAU": "Control de usos en edificio existente",
    "CATALOGACIÓN": "Catalogación o protección de edificio",
    "CATALOGACION": "Catalogación o protección de edificio",
    "REPARCELACIÓN": "Reparcelación de suelos",
    "REPARCELACION": "Reparcelación de suelos",
    "ACTUACIÓN INTEGRADA": "Actuación integrada de regeneración urbana",
    "ACTUACION INTEGRADA": "Actuación integrada de regeneración urbana",
    "AIR": "Actuación integrada de regeneración urbana",
    "URBANIZACIÓN": "Urbanización (obras e infraestructuras del sector)",
    "URBANIZACION": "Urbanización (obras e infraestructuras del sector)",
    "GESTIÓN": "Gestión urbanística",
    "GESTION": "Gestión urbanística",
  };

  for (const [pattern, label] of Object.entries(FIGURA)) {
    if (key.includes(pattern)) return label;
  }

  return raw[0];
}

/** Fase administrativa tal como la publica el ayuntamiento (sin alterar el texto oficial). */
export function sigmaFaseLabel(fase: string | null | undefined): string | null {
  if (!hasValue(fase)) return null;
  return fase.trim();
}

/** Una frase de contexto para la fase vigente. */
export function sigmaFaseContext(fase: string | null | undefined): string | null {
  if (!hasValue(fase)) return null;
  const f = fase.toLowerCase();

  if (f.includes("información pública") || f.includes("informacion publica")) {
    return "Cualquier persona puede revisar el proyecto y presentar alegaciones en el plazo indicado.";
  }
  if (f.includes("aprobación inicial") || f.includes("aprobacion inicial")) {
    return "El ayuntamiento ha dado el primer acuerdo formal; el expediente puede seguir con informes, alegaciones o aprobación definitiva.";
  }
  if (f.includes("aprobación definitiva") || f.includes("aprobacion definitiva")) {
    return "Tramitación avanzada en planeamiento; los siguientes pasos suelen ser licencias de obra u obras de urbanización.";
  }
  if (f.includes("aprobación provisional") || f.includes("aprobacion provisional")) {
    return "Acuerdo previo a la aprobación definitiva; puede haber alegaciones o ajustes antes de cerrar el expediente.";
  }
  if (f.includes("inicio") || f.includes("incoado")) {
    return "El expediente está abierto y en curso en el ayuntamiento.";
  }
  if (f.includes("archiv") || f.includes("desist")) {
    return "El expediente no sigue activo en la fase indicada.";
  }
  return "Estado según el registro urbanístico municipal; consulta la cronología para ver hitos concretos.";
}

export type SigmaInfoPublicaPeriod = {
  /** Texto corto para badge o KPI */
  short: string;
  /** Rango legible */
  range: string | null;
  /** Si hoy cae dentro del periodo (UTC, solo fechas día) */
  isOpen: boolean;
};

export function sigmaInfoPublicaFromArcgis(
  iniMs: unknown,
  finMs: unknown,
): SigmaInfoPublicaPeriod | null {
  const ini = formatSigmaArcgisMs(iniMs);
  const fin = formatSigmaArcgisMs(finMs);
  if (!ini && !fin) return null;

  const now = Date.now();
  const tIni = Number(iniMs);
  const tFin = Number(finMs);
  const isOpen =
    !Number.isNaN(tIni) &&
    !Number.isNaN(tFin) &&
    now >= tIni &&
    now <= tFin + 86_400_000;

  const range = [ini, fin ? `hasta ${fin}` : null].filter(Boolean).join(" · ");
  return {
    short: isOpen ? "Alegaciones abiertas" : "Periodo de información pública",
    range: range || null,
    isOpen,
  };
}

export function sigmaInfoPublicaFromYmd(
  iniYmd: string | null | undefined,
  finYmd: string | null | undefined,
): SigmaInfoPublicaPeriod | null {
  const ini = formatSigmaDateYmdUTC(iniYmd ?? null);
  const fin = formatSigmaDateYmdUTC(finYmd ?? null);
  if (!ini && !fin) return null;

  const parse = (ymd: string | null | undefined) => {
    if (!hasValue(ymd) || ymd.length < 10) return NaN;
    return Date.parse(`${ymd.slice(0, 10)}T12:00:00.000Z`);
  };
  const tIni = parse(iniYmd);
  const tFin = parse(finYmd);
  const now = Date.now();
  const isOpen =
    !Number.isNaN(tIni) && !Number.isNaN(tFin) && now >= tIni && now <= tFin + 86_400_000;

  const range = [ini, fin ? `hasta ${fin}` : null].filter(Boolean).join(" · ");
  return {
    short: isOpen ? "Alegaciones abiertas" : "Periodo de información pública",
    range: range || null,
    isOpen,
  };
}

/** Origen del dato (versión usuario). */
export function sigmaCatalogSourceUserLabel(source: string | null | undefined): string | null {
  if (!hasValue(source)) return null;
  const map: Record<string, string> = {
    informacion_publica: "Registro en periodo de información pública",
    tramitados_ad: "Planeamiento en curso",
    tramitados_gestion: "Gestión urbanística",
    tramitados_urbanizacion: "Urbanización",
  };
  return map[source.trim()] || source;
}

/** Capa GIS (versión usuario; detalle técnico). */
export function sigmaLayerKindUserLabel(kind: string | null | undefined): string | null {
  if (!hasValue(kind)) return null;
  const map: Record<string, string> = {
    planeamiento: "Planeamiento",
    gestion: "Gestión urbanística",
    urbanizacion: "Urbanización",
    tramitados_ad: "Planeamiento en curso",
    tramitados_gestion: "Gestión urbanística",
    tramitados_urbanizacion: "Urbanización",
  };
  return map[kind.trim()] || kind;
}

/** Etiqueta de capa para popups del mapa. */
export function sigmaMapPopupLayerHint(layerKind: string | null | undefined): string | null {
  if (!hasValue(layerKind)) return null;
  if (layerKind === "tramitados_ad") {
    return "Planeamiento en curso · ámbito del proyecto";
  }
  const labels: Record<string, string> = {
    planeamiento: "En información pública · planeamiento",
    gestion: "En información pública · gestión urbanística",
    urbanizacion: "En información pública · urbanización",
  };
  return labels[layerKind] || `Proyecto · ${sigmaLayerKindUserLabel(layerKind)}`;
}

export function metricCoverageUserBadge(hasMetrics: boolean): { label: string; tone: "teal" | "slate" } {
  return hasMetrics
    ? { label: "Estimación desde documentos oficiales", tone: "teal" }
    : { label: "Datos del ayuntamiento", tone: "slate" };
}

export function generaViviendaUserLabel(code: string | null | undefined): string {
  return viviendaNuevaLabel(code);
}

export function sigmaDocumentosLabel(count: number, localCount?: number): string {
  if (count <= 0) return "Documentos oficiales";
  const base = count === 1 ? "1 documento" : `${count.toLocaleString("es-ES")} documentos`;
  if (localCount != null && localCount > 0) {
    return `${base} (${localCount} descargados)`;
  }
  return base;
}

export function bocmAnunciosTabLabel(count: number): string {
  return count === 1 ? "1 anuncio en el Boletín" : `${count} anuncios en el Boletín`;
}

export const SIGMA_AYTO_TAB_LABEL = "Proyecto (Ayuntamiento)";

export const SIGMA_DOCUMENTOS_TAB_LABEL = "Documentos oficiales";

export const SIGMA_METRICS_EMPTY_COPY =
  "Todavía no hemos extraído cifras de viviendas o superficie de los PDFs de este expediente. Puedes ver el estado y la tramitación en las otras pestañas.";

export const SIGMA_AYTO_INTRO =
  "Datos del registro urbanístico del Ayuntamiento de Madrid: qué se tramita, en qué fase está y qué documentos hay disponibles.";

export const SIGMA_TRAMITACION_INTRO =
  "Hitos publicados en el visor de seguimiento del ayuntamiento (fechas y órganos que intervienen).";

export const SIGMA_TRAMITACION_EMPTY =
  "No hay pasos detallados en el visor para este expediente. El estado actual refleja el catálogo municipal.";

export const SIGMA_DOCUMENTOS_INTRO =
  "Memorias, informes y anexos del expediente en el archivo electrónico del ayuntamiento.";

export const SIGMA_BOCM_SECTION_INTRO =
  "Anuncios oficiales en el Boletín de la Comunidad de Madrid que mencionan este mismo expediente.";
