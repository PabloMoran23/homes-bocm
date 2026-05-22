/**
 * Título, subtítulo y párrafo introductorio para la ficha de un proyecto SIGMA.
 */

import { hasValue } from "@/lib/project-display";
import {
  formatM2,
  type SigmaExpedienteMetric,
} from "@/lib/sigma-metrics";
import { sigmaFaseShortLabel, sigmaTipoActuacion } from "@/lib/sigma-user-labels";
import type { SigmaVisorFicha, SigmaVisorTramite } from "@/lib/types";

export type SigmaPresentationInput = {
  expedienteGrupo: string;
  source?: string | null;
  denominacion?: string | null;
  visorH1?: string | null;
  visorH2?: string | null;
  fase?: string | null;
  figEtiq?: string | null;
  tfigAbrev?: string | null;
  organo?: string | null;
  metric?: SigmaExpedienteMetric | null;
  tramitacion?: SigmaVisorTramite[];
  bocmCount?: number;
  /** Hay PDFs en visor o descargados (aunque no analizados aún). */
  tieneDocumentos?: boolean;
  /** Ficha HTML del visor (promotor, resumen, m²…). */
  visorFicha?: SigmaVisorFicha | null;
};

export type SigmaQueImplica = {
  title: string;
  body: string;
  source: string;
  confidence: "alta" | "media" | "baja";
  /** Ejemplos del tipo de obra (no afirma que ocurran en este expediente). */
  ejemplos?: string[];
};

export type SigmaDisplayHeadline = {
  title: string;
  subtitle: string | null;
  planRef: string | null;
  figureCode: string | null;
};

/** Títulos del visor que son códigos de plan, no direcciones. */
export function isSigmaPlanCodeTitle(text: string | null | undefined): boolean {
  if (!hasValue(text)) return true;
  const t = text.trim();
  if (/^PGOUM[-\s]?\d+/i.test(t)) return true;
  if (/^PGOU\b/i.test(t)) return true;
  if (/^MPG[.\s]/i.test(t)) return true;
  if (/^PLAN\s+GENERAL/i.test(t)) return true;
  if (t.length <= 20 && /^[A-Z0-9.\-]+$/.test(t.replace(/\s/g, ""))) return true;
  return false;
}

/** ¿Parece una denominación con calles / ámbito territorial? */
export function isSigmaLocationDenom(text: string | null | undefined): boolean {
  if (!hasValue(text)) return false;
  if (isSigmaPlanCodeTitle(text)) return false;
  if (text.length < 12) return false;
  const locationHints =
    /(calle|c\/|avda|avenida|paseo|plaza|pza|glorieta|carretera|camino|ronda|boulevard|bulevar|sector|barrio|finca|parcela|manzana|solar|nº|número|\d{1,4})/i;
  return locationHints.test(text) || (text.includes(",") && text.length > 25);
}

function figureKindFromAbrev(tfig?: string | null, figEtiq?: string | null): string | null {
  const ab = tfig?.trim().toUpperCase();
  const MAP: Record<string, string> = {
    MPG: "Modificación del Plan General de Madrid",
    MP: "Modificación puntual del Plan General",
    ED: "Estudio de detalle",
    PP: "Plan parcial",
    PE: "Plan especial",
    PEC: "Proyecto de actuación en edificios existentes",
    PECUAU: "Control de usos en edificio existente",
    AIR: "Actuación integrada de regeneración urbana",
  };
  if (ab && MAP[ab]) return MAP[ab];
  return sigmaTipoActuacion(figEtiq, tfig);
}

function shortenVisorH2(h2: string): string | null {
  const t = h2.trim();
  if (!t) return null;
  const lower = t.toLowerCase();
  if (lower.includes("modificacion") && lower.includes("plan general")) {
    return "Modificación del Plan General";
  }
  if (lower.includes("planeamiento de desarrollo")) {
    return "Planeamiento y modificaciones del Plan General";
  }
  if (lower.includes("estudio de detalle")) return "Estudio de detalle";
  if (lower.includes("plan parcial")) return "Plan parcial";
  if (lower.includes("plan especial")) return "Plan especial";
  if (lower.includes("informacion publica")) return "En información pública";
  if (t.length > 72) return `${t.slice(0, 69)}…`;
  return t.charAt(0) + t.slice(1).toLowerCase();
}

export function sigmaPickDisplayHeadline(input: SigmaPresentationInput): SigmaDisplayHeadline {
  const denom = input.denominacion?.trim() || null;
  const h1 = input.visorH1?.trim() || null;
  const h2 = input.visorH2?.trim() || null;
  const planRef = h1 && isSigmaPlanCodeTitle(h1) ? h1 : null;
  const figureCode = hasValue(input.figEtiq) ? input.figEtiq!.trim() : null;

  const tipo =
    figureKindFromAbrev(input.tfigAbrev, input.figEtiq) ||
    (h2 ? shortenVisorH2(h2) : null);

  let title: string;
  if (isSigmaLocationDenom(denom)) {
    title = denom!;
  } else if (tipo && denom && !isSigmaPlanCodeTitle(denom)) {
    title = denom;
  } else if (h2 && !isSigmaPlanCodeTitle(h2)) {
    title = shortenVisorH2(h2) || h2;
  } else if (tipo) {
    title = tipo;
  } else if (h1 && !isSigmaPlanCodeTitle(h1)) {
    title = h1;
  } else {
    title = input.expedienteGrupo;
  }

  const subtitleParts: string[] = [];
  if (isSigmaLocationDenom(denom) && tipo && title !== tipo) {
    subtitleParts.push(tipo);
  }
  if (planRef) subtitleParts.push(planRef);

  const subtitle =
    subtitleParts.length > 0
      ? subtitleParts.join(" · ")
      : figureCode && !title.includes(figureCode)
        ? `Figura ${figureCode}`
        : null;

  return { title, subtitle, planRef, figureCode };
}

export function buildSigmaProjectLead(input: SigmaPresentationInput): string {
  const fase = sigmaFaseShortLabel(input.fase);
  const tipo = figureKindFromAbrev(input.tfigAbrev, input.figEtiq);
  const { planRef } = sigmaPickDisplayHeadline(input);
  const metric = input.metric;

  const sentences: string[] = [];

  if (tipo && planRef) {
    sentences.push(`${tipo} en el marco del plan urbanístico ${planRef} de Madrid.`);
  } else if (tipo) {
    sentences.push(`${tipo} tramitado en la ciudad de Madrid.`);
  } else {
    sentences.push(
      "Actuación de planeamiento o gestión urbanística registrada por el Ayuntamiento de Madrid.",
    );
  }

  if (fase) sentences.push(`Estado actual: ${fase.toLowerCase()}.`);

  if (metric?.num_viviendas_max != null && metric.num_viviendas_max > 0) {
    sentences.push(
      `En la documentación aparecen hasta ${metric.num_viviendas_max.toLocaleString("es-ES")} viviendas.`,
    );
  } else if (formatM2(metric?.sup_total_m2)) {
    sentences.push(`El ámbito afectado ronda los ${formatM2(metric!.sup_total_m2)}.`);
  }

  const bocmN = input.bocmCount ?? 0;
  if (bocmN > 0) {
    sentences.push(
      bocmN === 1
        ? "Hay un anuncio en el Boletín oficial relacionado con este expediente."
        : `Hay ${bocmN} anuncios en el Boletín oficial relacionados con este expediente.`,
    );
  }

  return sentences.join(" ");
}

const QUE_IMPLICA_POR_FAMILIA: Record<
  string,
  { title: string; body: string; ejemplos: string[] }
> = {
  plan_especial: {
    title: "Plan especial en un ámbito concreto",
    body:
      "Fija qué puede ocurrir en esa zona: usos permitidos, rehabilitación, protección o infraestructuras. No indica por sí solo si habrá alcantarillado, tendido eléctrico u obras de locales; eso está en la memoria técnica del expediente.",
    ejemplos: ["Rehabilitación", "Cambio de usos", "Protección", "Infraestructuras"],
  },
  plan_parcial: {
    title: "Plan parcial (reglas del sector)",
    body:
      "Establece alturas, usos y edificabilidad de un barrio o sector. Las obras concretas (redes, locales, vivienda nueva) se desprenden de la documentación y de licencias posteriores.",
    ejemplos: ["Nueva edificación", "Dotaciones", "Reordenación de usos"],
  },
  modificacion_pgou: {
    title: "Modificación del Plan General",
    body:
      "Cambia las normas urbanísticas en un ámbito acotado. El impacto concreto (viviendas, equipamientos, redes) hay que leerlo en memoria e informes.",
    ejemplos: ["Más vivienda", "Suelo dotacional", "Cambio de calificación"],
  },
  estudio_detalle: {
    title: "Estudio de detalle (una parcela o edificio)",
    body:
      "Ordena un solar o edificio antes de las licencias de obra. Suele detallar volumen, usos y a veces obras previstas en la memoria.",
    ejemplos: ["Obra nueva", "Reforma", "Ampliación"],
  },
  pecuau: {
    title: "Control de usos en edificio existente",
    body:
      "Afecta sobre todo a locales, terrazas, aparcamientos o aforos en un inmueble ya construido, no a una urbanización completa.",
    ejemplos: ["Locales comerciales", "Hostelería", "Plazas de garaje"],
  },
  catalogacion: {
    title: "Catalogación o protección",
    body:
      "Cambia el régimen de protección de un edificio o entorno. No implica por sí mismo una gran obra nueva en el ámbito.",
    ejemplos: ["Protección patrimonial", "Límites de reforma"],
  },
  planeamiento_otro: {
    title: "Actuación de planeamiento",
    body:
      "Tramitación urbanística del ayuntamiento. Para saber si hay obras de red, edificación o cambios de uso hace falta la memoria del expediente.",
    ejemplos: ["Consultar memoria técnica", "Informes sectoriales"],
  },
};

function inferFamiliaFromInput(input: SigmaPresentationInput): string {
  if (input.metric?.familia_expediente) return input.metric.familia_expediente;
  const ab = input.tfigAbrev?.trim().toUpperCase();
  if (ab === "PE") return "plan_especial";
  if (ab === "PP") return "plan_parcial";
  if (ab === "MPG" || ab === "MP") return "modificacion_pgou";
  if (ab === "ED") return "estudio_detalle";
  const blob = `${input.visorH2 || ""} ${input.figEtiq || ""}`.toLowerCase();
  if (blob.includes("plan especial")) return "plan_especial";
  if (blob.includes("plan parcial")) return "plan_parcial";
  return "planeamiento_otro";
}

function usoPrincipalDesdeMetric(metric: SigmaExpedienteMetric): string | null {
  for (const h of metric.hechos || []) {
    const key = (h as { metric?: string; metrica?: string }).metric ?? (h as { metrica?: string }).metrica;
    if (key === "uso_principal" && h.value != null) {
      const v = String(h.value).replace(/\s+/g, " ").trim();
      if (v.length > 6) return v.slice(0, 220);
    }
  }
  const direct = metric as SigmaExpedienteMetric & { uso_principal?: string };
  if (direct.uso_principal) return String(direct.uso_principal).slice(0, 220);
  return null;
}

/** Respuesta a «¿de qué va?» / «¿qué obras implica?». */
export function buildSigmaQueImplica(input: SigmaPresentationInput): SigmaQueImplica {
  const uso = input.metric ? usoPrincipalDesdeMetric(input.metric) : null;
  const viviendas = input.metric?.num_viviendas_max;
  const sup = formatM2(input.metric?.sup_total_m2);

  if (uso) {
    return {
      title: "Uso y actuación previstos",
      body: `Según memorias e informes analizados: ${uso}.${viviendas ? ` Hasta ${viviendas.toLocaleString("es-ES")} viviendas en el ámbito.` : ""}${sup ? ` Superficie de referencia: ${sup}.` : ""}`,
      source: "Basado en documentos oficiales del expediente",
      confidence: "media",
    };
  }

  const vf = input.visorFicha;
  const resumenVisor = vf?.resumenContenido?.trim();
  if (resumenVisor && resumenVisor.length > 24) {
    const prefijos: string[] = [];
    if (vf?.figuraTipo) prefijos.push(vf.figuraTipo);
    if (vf?.tipoPlaneamiento) prefijos.push(`tipo ${vf.tipoPlaneamiento.toLowerCase()}`);
    const supV = vf?.superficieAmbitoM2;
    const supTxt =
      supV != null && supV > 0
        ? ` Ámbito: ${formatM2(supV)}.`
        : vf?.superficieAmbitoTexto
          ? ` Ámbito: ${vf.superficieAmbitoTexto}.`
          : "";
    return {
      title: prefijos.length ? prefijos.join(" · ") : "Objeto del expediente",
      body: `${resumenVisor}${supTxt}`,
      source: "Basado en la ficha oficial del Ayuntamiento",
      confidence: "alta",
    };
  }

  const familia = inferFamiliaFromInput(input);
  const plantilla = QUE_IMPLICA_POR_FAMILIA[familia] ?? QUE_IMPLICA_POR_FAMILIA.planeamiento_otro;
  let body = plantilla.body;

  if (!input.metric?.pdfs_procesados && !resumenVisor) {
    body +=
      " Homes no ha analizado aún los PDFs de este expediente" +
      (input.tieneDocumentos
        ? "; puedes abrirlos en el visor municipal o en la pestaña Documentos."
        : vf?.descripcionAmbito
          ? ` ${vf.descripcionAmbito}`
          : ". Si hay documentación, suele publicarse en el visor del ayuntamiento.");
  }

  if (viviendas && viviendas > 0) {
    body += ` En documentación relacionada figuran hasta ${viviendas.toLocaleString("es-ES")} viviendas.`;
  }

  return {
    title: plantilla.title,
    body,
    source: input.metric?.pdfs_procesados
      ? "Basado en el tipo de proyecto y documentos oficiales"
      : "Basado en el tipo de proyecto publicado",
    confidence: input.metric?.pdfs_procesados ? "media" : "baja",
    ejemplos: plantilla.ejemplos,
  };
}

export function sigmaPresentationMetaLine(input: SigmaPresentationInput): string | null {
  const { planRef, figureCode } = sigmaPickDisplayHeadline(input);
  const bits: string[] = [`Ref. ${input.expedienteGrupo}`];
  if (figureCode) bits.push(figureCode);
  if (planRef && !bits.some((b) => b.includes(planRef))) bits.push(planRef);
  return bits.join(" · ");
}
