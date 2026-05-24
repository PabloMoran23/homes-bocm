import type { SigmaClassification } from "@/lib/sigma-classification";
import {
  sigmaClassificationLabel,
  sigmaClassificationPlainText,
  sigmaClassificationResumen,
  sigmaClassificationTone,
  sigmaTipoObraLabel,
} from "@/lib/sigma-classification";

export type SigmaObraIconKey =
  | "vivienda"
  | "edificio"
  | "garaje"
  | "terciario"
  | "viario"
  | "urbanizacion"
  | "equipamiento"
  | "patrimonio"
  | "usos"
  | "gestion"
  | "planeamiento"
  | "generico";

export type SigmaObraIconConfig = {
  key: SigmaObraIconKey;
  bg: string;
  ring: string;
  svg: string;
};

const SVG = {
  vivienda: `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.5 12 3l9 7.5V21a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/></svg>`,
  edificio: `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="1"/><path d="M9 9h.01M15 9h.01M9 15h.01M15 15h.01M12 12h.01"/></svg>`,
  garaje: `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 17h14v-5l-2-4H7l-2 4z"/><circle cx="7.5" cy="17.5" r="1.5"/><circle cx="16.5" cy="17.5" r="1.5"/></svg>`,
  terciario: `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9h18v12H3z"/><path d="M7 9V5h10v4"/></svg>`,
  viario: `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19h16"/><path d="M4 15h16"/><path d="M12 3v16"/><circle cx="12" cy="7" r="2"/></svg>`,
  urbanizacion: `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20M2 12h20"/><circle cx="12" cy="12" r="3"/></svg>`,
  equipamiento: `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c0 1 2 3 6 3s6-2 6-3v-5"/></svg>`,
  patrimonio: `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 4v6c0 5-4 8-8 8s-8-3-8-8V7z"/></svg>`,
  usos: `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg>`,
  gestion: `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>`,
  planeamiento: `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6l9-3 9 3-9 3-9-3z"/><path d="M3 6v12l9 3 9-3V6"/></svg>`,
  generico: `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2 2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5M2 12l10 5 10-5"/></svg>`,
} as const;

export const SIGMA_OBRA_ICON_CONFIG: Record<SigmaObraIconKey, SigmaObraIconConfig> = {
  vivienda: { key: "vivienda", bg: "#0d9488", ring: "#115e59", svg: SVG.vivienda },
  edificio: { key: "edificio", bg: "#0891b2", ring: "#155e75", svg: SVG.edificio },
  garaje: { key: "garaje", bg: "#d97706", ring: "#92400e", svg: SVG.garaje },
  terciario: { key: "terciario", bg: "#ea580c", ring: "#9a3412", svg: SVG.terciario },
  viario: { key: "viario", bg: "#0284c7", ring: "#075985", svg: SVG.viario },
  urbanizacion: { key: "urbanizacion", bg: "#2563eb", ring: "#1e40af", svg: SVG.urbanizacion },
  equipamiento: { key: "equipamiento", bg: "#059669", ring: "#047857", svg: SVG.equipamiento },
  patrimonio: { key: "patrimonio", bg: "#7c3aed", ring: "#5b21b6", svg: SVG.patrimonio },
  usos: { key: "usos", bg: "#db2777", ring: "#9d174d", svg: SVG.usos },
  gestion: { key: "gestion", bg: "#ca8a04", ring: "#854d0e", svg: SVG.gestion },
  planeamiento: { key: "planeamiento", bg: "#4f46e5", ring: "#3730a3", svg: SVG.planeamiento },
  generico: { key: "generico", bg: "#64748b", ring: "#334155", svg: SVG.generico },
};

const TIPO_OBRA_TO_ICON: Record<string, SigmaObraIconKey> = {
  vivienda_residencial: "vivienda",
  edificio_ampliacion: "edificio",
  garaje_aparcamiento: "garaje",
  uso_terciario: "terciario",
  infraestructura_viaria: "viario",
  urbanizacion_redes: "urbanizacion",
  equipamiento_publico: "equipamiento",
  proteccion_patrimonio: "patrimonio",
  ordenacion_usos_actividad: "usos",
  reparcelacion_gestion: "gestion",
  modificacion_planeamiento: "planeamiento",
  sin_determinar: "generico",
};

const CATEGORIA_TO_ICON: Record<string, SigmaObraIconKey> = {
  gran_desarrollo_residencial: "vivienda",
  residencial_o_vivienda: "vivienda",
  urbanizacion_infraestructuras: "urbanizacion",
  gestion_reparcelacion: "gestion",
  proteccion_catalogo: "patrimonio",
  equipamiento_dotacional: "equipamiento",
  terciario_comercial_hotelero: "terciario",
  plan_especial_uso_actividad: "usos",
  modificacion_planeamiento_general: "planeamiento",
  ordenacion_parcela_manzana: "edificio",
  ajuste_administrativo: "generico",
  planeamiento_otros: "generico",
};

export function resolveSigmaObraIconKey(
  clasificacion?: Pick<SigmaClassification, "tipoObra" | "categoriaProyecto"> | null,
): SigmaObraIconKey {
  if (!clasificacion) return "generico";
  if (clasificacion.tipoObra && clasificacion.tipoObra !== "sin_determinar") {
    return TIPO_OBRA_TO_ICON[clasificacion.tipoObra] ?? "generico";
  }
  if (clasificacion.categoriaProyecto) {
    return CATEGORIA_TO_ICON[clasificacion.categoriaProyecto] ?? "generico";
  }
  return "generico";
}

export function sigmaObraIconConfig(
  clasificacion?: Pick<SigmaClassification, "tipoObra" | "categoriaProyecto"> | null,
): SigmaObraIconConfig {
  return SIGMA_OBRA_ICON_CONFIG[resolveSigmaObraIconKey(clasificacion)];
}

export function sigmaHeroClassificationHeadline(
  clasificacion?: SigmaClassification | null,
): { title: string; summary: string | null } | null {
  if (!clasificacion) return null;
  const resumen = sigmaClassificationResumen(clasificacion);
  const title =
    (clasificacion.tipoObra && clasificacion.tipoObra !== "sin_determinar"
      ? sigmaTipoObraLabel(clasificacion.tipoObra)
      : null) ??
    sigmaClassificationLabel(clasificacion.categoriaProyecto) ??
    "Proyecto de planeamiento";
  const summary =
    resumen?.headline ??
    sigmaClassificationPlainText(clasificacion.tipoObra, "tipoObra") ??
    sigmaClassificationPlainText(clasificacion.categoriaProyecto, "categoria");
  return { title, summary };
}

export function sigmaClassificationHeroToneClass(
  clasificacion?: Pick<SigmaClassification, "tipoObra" | "categoriaProyecto"> | null,
): string {
  const tone = sigmaClassificationTone(
    clasificacion?.tipoObra ?? clasificacion?.categoriaProyecto ?? null,
  );
  return {
    teal: "text-teal-900",
    violet: "text-violet-900",
    amber: "text-amber-900",
    sky: "text-sky-900",
    slate: "text-slate-800",
  }[tone];
}
