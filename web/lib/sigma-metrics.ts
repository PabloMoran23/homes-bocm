/** Métricas agregadas por expediente (PDF pipeline). */

export type SigmaMetricHecho = {
  metric: string | null;
  value: string | number | null;
  confianza: string | null;
  doc_role: string | null;
  pdf_name: string | null;
};

export type SigmaExpedienteMetric = {
  num_viviendas_max: number | null;
  sup_total_m2: number | null;
  sup_edificable_m2: number | null;
  tipo_vivienda: string | null;
  genera_vivienda_nueva: string | null;
  familia_expediente: string | null;
  pdfs_procesados: number | null;
  doc_role_principal: string | null;
  hechos: SigmaMetricHecho[];
};

export type MadridSigmaMetricsFile = {
  generatedAt: string;
  count: number;
  byExpediente: Record<string, SigmaExpedienteMetric>;
};

export type GeneraViviendaNueva =
  | "si"
  | "probable_si"
  | "probable_sin_cifra"
  | "stock_existente_o_rehabilitacion"
  | "no"
  | "desconocido";

const VIVIENDA_LABELS: Record<string, string> = {
  si: "Incluye vivienda nueva",
  probable_si: "Posible obra nueva",
  probable_sin_cifra: "Puede haber obra; sin cifra",
  stock_existente_o_rehabilitacion: "Rehabilitación / stock existente",
  no: "Sin vivienda nueva",
  desconocido: "Viviendas: sin datos",
};

const FAMILIA_MSG: Record<string, string> = {
  estudio_detalle:
    "Ordenación de parcela o edificio; suele ir antes de las licencias de obra.",
  plan_parcial: "Define reglas del sector: usos, alturas y edificabilidad.",
  plan_especial: "Actuación concreta: colonia, catalogación, regeneración…",
  modificacion_pgou: "Cambio puntual del Plan General; puede ser gran escala.",
  pecuau: "Control de usos en edificio existente (locales, aforo…).",
  catalogacion: "Protección o cambio de régimen del edificio; no obra nueva masiva.",
};

export function viviendaNuevaLabel(code: string | null | undefined): string {
  if (!code) return VIVIENDA_LABELS.desconocido;
  return VIVIENDA_LABELS[code] || VIVIENDA_LABELS.desconocido;
}

export function familiaExpedienteMessage(familia: string | null | undefined): string | null {
  if (!familia) return null;
  return FAMILIA_MSG[familia] || null;
}

export function formatM2(n: number | null | undefined): string | null {
  if (n == null || Number.isNaN(n)) return null;
  return `${Math.round(n).toLocaleString("es-ES")} m²`;
}

export function metricCoverageBadge(hasMetrics: boolean): { label: string; tone: "teal" | "slate" } {
  return hasMetrics
    ? { label: "Estimación desde documentos oficiales", tone: "teal" }
    : { label: "Datos del ayuntamiento", tone: "slate" };
}

let metricsCache: MadridSigmaMetricsFile | null = null;
let metricsPromise: Promise<MadridSigmaMetricsFile | null> | null = null;

export async function loadSigmaMetricsBundle(): Promise<MadridSigmaMetricsFile | null> {
  if (metricsCache) return metricsCache;
  if (!metricsPromise) {
    metricsPromise = (async () => {
      try {
        const res = await fetch("/data/madrid-sigma-metrics.json");
        if (!res.ok) return null;
        metricsCache = (await res.json()) as MadridSigmaMetricsFile;
        return metricsCache;
      } catch {
        return null;
      }
    })();
  }
  return metricsPromise;
}

export function lookupSigmaMetric(
  bundle: MadridSigmaMetricsFile | null | undefined,
  expedienteGrupo: string,
): SigmaExpedienteMetric | null {
  if (!bundle?.byExpediente) return null;
  return bundle.byExpediente[expedienteGrupo] ?? null;
}
