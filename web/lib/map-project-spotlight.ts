import { expedienteGrupoKeyFromVariant } from "@/lib/madrid-expediente";
import type { SigmaClassification } from "@/lib/sigma-classification";
import type { SigmaObraIconKey } from "@/lib/sigma-classification-icon";
import { sigmaFichaPath } from "@/lib/sigma-ficha-path";
import type { SigmaExpedienteMetric } from "@/lib/sigma-metrics";
import type { SigmaVisorFicha } from "@/lib/types";

export type MapProjectSpotlightItem = {
  id: string;
  href: string;
  tag: string;
  categoryLabel: string;
  categoriaProyecto: string | null;
  tipoObra: string | null;
  iconKey: SigmaObraIconKey;
  locationLine: string | null;
  resumen: string;
  dateLabel: string;
  title: string;
  dek: string;
  numViviendas: number | null;
  supM2: number | null;
  fase: string | null;
  expedienteGrupo: string;
};

export type SigmaMapCardSlice = {
  distrito: string | null;
  ambitoLabel: string | null;
  resumen: string;
};

const CATEGORY_LABELS: Record<string, string> = {
  gran_desarrollo_residencial: "Gran desarrollo residencial",
  residencial_o_vivienda: "Residencial / vivienda",
  urbanizacion_infraestructuras: "Urbanización e infraestructuras",
  gestion_reparcelacion: "Gestión o reparcelación",
  proteccion_catalogo: "Protección patrimonial",
  equipamiento_dotacional: "Equipamiento público",
  terciario_comercial_hotelero: "Terciario o comercial",
  plan_especial_uso_actividad: "Uso en edificio existente",
  modificacion_planeamiento_general: "Modificación del Plan General",
  ordenacion_parcela_manzana: "Ordenación de parcela",
  ajuste_administrativo: "Ajuste administrativo",
  planeamiento_otros: "Planeamiento urbanístico",
};

const CATEGORY_PLAIN: Record<string, string> = {
  gran_desarrollo_residencial:
    "Es un gran desarrollo residencial con muchas viviendas o un ámbito amplio.",
  residencial_o_vivienda: "Es un proyecto centrado en vivienda o uso residencial.",
  urbanizacion_infraestructuras: "Organiza urbanización, calles o infraestructuras del ámbito.",
  gestion_reparcelacion: "Trata la gestión del suelo y la reparcelación entre propietarios.",
  proteccion_catalogo: "Incide en protección patrimonial o catalogación de edificios.",
  equipamiento_dotacional: "Busca crear o ampliar equipamiento público o dotacional.",
  terciario_comercial_hotelero: "Afecta a usos comerciales, hoteleros u oficinas.",
  plan_especial_uso_actividad: "Regula un uso o actividad concreta en edificio existente.",
  modificacion_planeamiento_general: "Modifica el planeamiento general de la ciudad.",
  ordenacion_parcela_manzana: "Ordena una parcela o manzana: volúmenes, usos o condiciones.",
  ajuste_administrativo: "Es un ajuste técnico o administrativo del planeamiento.",
  planeamiento_otros: "Es un expediente de planeamiento urbanístico sin categoría más específica.",
};

const TIPO_OBRA_PLAIN: Record<string, string> = {
  vivienda_residencial:
    "El proyecto prevé viviendas nuevas o un desarrollo residencial en el ámbito afectado.",
  edificio_ampliacion:
    "Afecta a un edificio concreto: ampliación, reforma o nueva edificabilidad.",
  urbanizacion_redes:
    "Es una urbanización o actuación sobre redes, servicios o infraestructuras del suelo.",
  equipamiento_publico:
    "Destina el ámbito a equipamiento público: colegio, sanidad, dotacional o deportivo.",
  proteccion_patrimonio:
    "Protege o regula un bien patrimonial, edificio catalogado o entorno con valor histórico.",
  reparcelacion_gestion:
    "Es una actuación de gestión urbanística: reparcelación o redistribución de suelo.",
  modificacion_planeamiento: "Cambia normas del plan general de Madrid para este ámbito.",
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

function shortDenom(text: string, max = 58): string {
  const s = String(text || "")
    .trim()
    .replace(/\s+/g, " ");
  if (!s) return "Expediente urbanístico";
  return s.length <= max ? s : `${s.slice(0, max - 1)}…`;
}

function yearFromExpedienteNum(num: string | null | undefined): number | null {
  const parts = String(num || "").split("/");
  if (parts.length < 2) return null;
  const y = Number(parts[1]);
  return Number.isFinite(y) && y >= 1990 && y <= 2100 ? y : null;
}

function dateLabelForExpediente(num: string): string {
  const y = yearFromExpedienteNum(num);
  if (!y) return "Madrid";
  if (y >= 2024) return "Reciente";
  return String(y);
}

function trimResumen(text: string | null | undefined, max = 140): string | null {
  const s = String(text || "")
    .replace(/\s+/g, " ")
    .trim();
  if (!s) return null;
  if (s.length <= max) return s;
  const cut = s.slice(0, max);
  const lastSpace = cut.lastIndexOf(" ");
  return `${(lastSpace > 80 ? cut.slice(0, lastSpace) : cut).trim()}…`;
}

function titleCaseDistrito(name: string | null | undefined): string | null {
  if (!name) return null;
  const lower = String(name).toLowerCase().replace(/_/g, " ");
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

export function spotlightCategoryLabel(
  clas: Pick<SigmaClassification, "categoriaProyecto"> | null | undefined,
): string {
  if (!clas?.categoriaProyecto) return "Planeamiento urbanístico";
  return (
    CATEGORY_LABELS[clas.categoriaProyecto] ||
    clas.categoriaProyecto.replace(/_/g, " ")
  );
}

export function spotlightIconKey(
  clas: Pick<SigmaClassification, "categoriaProyecto" | "tipoObra"> | null | undefined,
): SigmaObraIconKey {
  if (!clas) return "generico";
  if (clas.tipoObra && clas.tipoObra !== "sin_determinar") {
    return TIPO_OBRA_TO_ICON[clas.tipoObra] ?? "generico";
  }
  if (clas.categoriaProyecto) {
    return CATEGORIA_TO_ICON[clas.categoriaProyecto] ?? "generico";
  }
  return "generico";
}

export function spotlightAmbitoLabel(
  catalog: { EXP_TX_DENOM?: string | null } | null | undefined,
  visorFicha: SigmaVisorFicha | null | undefined,
): string | null {
  const vf = visorFicha || {};
  for (const raw of [vf.denominacionVisor, vf.ambitoOrdenacion, catalog?.EXP_TX_DENOM]) {
    if (!raw) continue;
    const s = shortDenom(String(raw), 44);
    if (s && s !== "Expediente urbanístico") return s;
  }
  return null;
}

export function spotlightLocationLine(
  distrito: string | null | undefined,
  ambitoLabel: string | null | undefined,
): string | null {
  const d = titleCaseDistrito(distrito);
  if (d && ambitoLabel) return `${d} · ${ambitoLabel}`;
  return d || ambitoLabel || null;
}

export function spotlightResumenForCard(
  clas: Pick<SigmaClassification, "categoriaProyecto" | "tipoObra"> | null | undefined,
  visorFicha: SigmaVisorFicha | null | undefined,
  cardSlice?: SigmaMapCardSlice | null,
): string {
  if (cardSlice?.resumen) return cardSlice.resumen;
  const fromVisor = trimResumen(visorFicha?.resumenContenido);
  if (fromVisor) return fromVisor;
  if (clas?.tipoObra && clas.tipoObra !== "sin_determinar") {
    const plain = trimResumen(TIPO_OBRA_PLAIN[clas.tipoObra], 160);
    if (plain) return plain;
  }
  if (clas?.categoriaProyecto) {
    const plain = trimResumen(CATEGORY_PLAIN[clas.categoriaProyecto], 160);
    if (plain) return plain;
  }
  return "Actuación de planeamiento urbanístico registrada por el Ayuntamiento de Madrid.";
}

export function buildMapProjectSpotlightItem(input: {
  expedienteGrupo: string;
  catalog?: {
    EXP_TX_DENOM?: string | null;
    FAS_TX_DENOM?: string | null;
    EXP_TX_NUMERO?: string | null;
  } | null;
  clasificacion?: SigmaClassification | null;
  metric?: SigmaExpedienteMetric | null;
  cardSlice?: SigmaMapCardSlice | null;
  visorFicha?: SigmaVisorFicha | null;
}): MapProjectSpotlightItem {
  const grupo = expedienteGrupoKeyFromVariant(input.expedienteGrupo);
  const clas = input.clasificacion ?? null;
  const metric = input.metric ?? null;
  const visorFicha = input.visorFicha ?? null;
  const slice = input.cardSlice ?? null;
  const categoryLabel = spotlightCategoryLabel(clas);
  const ambitoLabel =
    slice?.ambitoLabel ?? spotlightAmbitoLabel(input.catalog, visorFicha);
  const locationLine = spotlightLocationLine(slice?.distrito ?? visorFicha?.distrito, ambitoLabel);
  const resumen = spotlightResumenForCard(clas, visorFicha, slice);
  const n = metric?.num_viviendas_max ?? null;
  const slug = grupo.replace(/\//g, "-");

  return {
    id: `sigma-${slug}`,
    href: sigmaFichaPath(grupo),
    tag: categoryLabel,
    categoryLabel,
    categoriaProyecto: clas?.categoriaProyecto ?? null,
    tipoObra: clas?.tipoObra ?? null,
    iconKey: spotlightIconKey(clas),
    locationLine,
    resumen,
    dateLabel: dateLabelForExpediente(input.catalog?.EXP_TX_NUMERO || grupo),
    title: shortDenom(input.catalog?.EXP_TX_DENOM || ambitoLabel || grupo, 50),
    dek: resumen,
    numViviendas: n != null && n > 0 ? n : null,
    supM2:
      metric?.sup_total_m2 != null && metric.sup_total_m2 > 0
        ? Math.round(metric.sup_total_m2)
        : null,
    fase: input.catalog?.FAS_TX_DENOM ? String(input.catalog.FAS_TX_DENOM) : null,
    expedienteGrupo: grupo,
  };
}
