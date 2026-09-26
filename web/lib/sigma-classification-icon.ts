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

const S = `fill="none" stroke="#fff" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round"`;

const SVG = {
  vivienda: `<svg viewBox="0 0 24 24" ${S}><path d="M4.2 11.4 12 4.6l7.8 6.8"/><path d="M6.4 10.6V19.6h11.2V10.6"/><path d="M10.2 19.6v-5.1h3.6v5.1"/><path d="M16.6 8.4V5.8h2.1"/></svg>`,
  edificio: `<svg viewBox="0 0 24 24" ${S}><rect x="5.2" y="3.6" width="13.6" height="16.8" rx="0.4"/><path d="M8 7.2h1.4M12 7.2h1.4M16 7.2h1.4M8 11h1.4M12 11h1.4M16 11h1.4M8 14.8h1.4M12 14.8h1.4M16 14.8h1.4"/><path d="M10.6 20.4v-3h2.8v3"/></svg>`,
  garaje: `<svg viewBox="0 0 24 24" ${S}><path d="M4.4 19.4h15.2"/><path d="M5.4 19.4V13L8.2 8.6h7.6L18.6 13v6.4"/><circle cx="8.4" cy="16.4" r="1.15"/><circle cx="15.6" cy="16.4" r="1.15"/><path d="M8 8.6h8"/></svg>`,
  terciario: `<svg viewBox="0 0 24 24" ${S}><path d="M4.4 10.4h15.2V19.8H4.4z"/><path d="M4.2 10.4 12 5.6l7.8 4.8"/><path d="M10.4 19.8v-5h3.2v5"/><path d="M7.2 13.6h1.6M11.2 13.6h1.6M15.2 13.6h1.6"/></svg>`,
  viario: `<svg viewBox="0 0 24 24" ${S}><path d="M8.4 3.6 5.6 20.4"/><path d="M15.6 3.6 18.4 20.4"/><path d="M12 5.4v1.8M12 10.2v1.8M12 15.2v1.8"/></svg>`,
  urbanizacion: `<svg viewBox="0 0 24 24" ${S}><rect x="4" y="4" width="16" height="16" rx="0.4"/><path d="M12 4v16M4 12h16"/><path d="M12 2.6v1.4M11.2 3.4 12 2.4 12.8 3.4"/></svg>`,
  equipamiento: `<svg viewBox="0 0 24 24" ${S}><rect x="4.4" y="8.4" width="15.2" height="11.4" rx="0.5"/><path d="M8.2 8.4V5.8h7.6V8.4"/><path d="M12 11.4v5.4M9.2 14.1h5.6"/></svg>`,
  patrimonio: `<svg viewBox="0 0 24 24" ${S}><path d="M4.4 9.2 12 4.8l7.6 4.4"/><path d="M6.6 9.2v8.2M12 9.2v8.2M17.4 9.2v8.2"/><path d="M4.4 17.4h15.2M5.2 20.2h13.6"/></svg>`,
  usos: `<svg viewBox="0 0 24 24" ${S}><circle cx="12" cy="12" r="7.2"/><path d="M12 4.8v14.4M4.8 12h14.4"/><path d="m7.4 7.4 9.2 9.2"/></svg>`,
  gestion: `<svg viewBox="0 0 24 24" ${S}><path d="M4.4 4.4h7.2v7.2H4.4zM12.4 4.4h7.2v7.2h-7.2zM4.4 12.4h7.2v7.2H4.4z"/><path d="M14.2 14.2h5.4v5.4h-5.4z"/></svg>`,
  planeamiento: `<svg viewBox="0 0 24 24" ${S}><path d="M5.2 6.4 12 3.8l6.8 2.6v10.8L12 20.2 5.2 17.4z"/><path d="M12 3.8v16.4"/><path d="M8.2 8.8h2.8M8.2 12.2h2.8M13.6 10.4h2.4"/></svg>`,
  generico: `<svg viewBox="0 0 24 24" ${S}><rect x="5.4" y="6.6" width="13.2" height="12.8" rx="0.4"/><path d="M12 3.4v3.2M11.2 4.4 12 3.4 12.8 4.4"/></svg>`,
} as const;

export const SIGMA_OBRA_ICON_CONFIG: Record<SigmaObraIconKey, SigmaObraIconConfig> = {
  vivienda: { key: "vivienda", bg: "#6b8f54", ring: "#4d6a3c", svg: SVG.vivienda },
  edificio: { key: "edificio", bg: "#4a5556", ring: "#2f3a3b", svg: SVG.edificio },
  garaje: { key: "garaje", bg: "#c4853a", ring: "#8a5a1e", svg: SVG.garaje },
  terciario: { key: "terciario", bg: "#c07f6c", ring: "#8f5748", svg: SVG.terciario },
  viario: { key: "viario", bg: "#b86f5e", ring: "#8a4d40", svg: SVG.viario },
  urbanizacion: { key: "urbanizacion", bg: "#1f4f53", ring: "#16383b", svg: SVG.urbanizacion },
  equipamiento: { key: "equipamiento", bg: "#5f7a4a", ring: "#3f5232", svg: SVG.equipamiento },
  patrimonio: { key: "patrimonio", bg: "#7a5c58", ring: "#5a403c", svg: SVG.patrimonio },
  usos: { key: "usos", bg: "#b88980", ring: "#8a6560", svg: SVG.usos },
  gestion: { key: "gestion", bg: "#a67c3a", ring: "#7a5a28", svg: SVG.gestion },
  planeamiento: { key: "planeamiento", bg: "#5a5850", ring: "#3d3b36", svg: SVG.planeamiento },
  generico: { key: "generico", bg: "#7a7268", ring: "#5a544c", svg: SVG.generico },
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
    teal: "text-[var(--portal-accent)]",
    violet: "text-[#6b534e]",
    amber: "text-[#9a5c28]",
    sky: "text-[#2a5c60]",
    slate: "text-[var(--portal-ink)]",
  }[tone];
}
