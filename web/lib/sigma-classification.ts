export type SigmaClassificationCode =
  | "gran_desarrollo_residencial"
  | "residencial_o_vivienda"
  | "urbanizacion_infraestructuras"
  | "gestion_reparcelacion"
  | "proteccion_catalogo"
  | "equipamiento_dotacional"
  | "terciario_comercial_hotelero"
  | "plan_especial_uso_actividad"
  | "modificacion_planeamiento_general"
  | "ordenacion_parcela_manzana"
  | "ajuste_administrativo"
  | "planeamiento_otros"
  | string;

export type SigmaClassification = {
  tipoLegal: string | null;
  escala: string | null;
  contenidoPrincipal: string | null;
  faseNormalizada: string | null;
  categoriaProyecto: SigmaClassificationCode | null;
  confianza: "alta" | "media" | "baja" | string | null;
  fuentes?: Record<string, unknown> | null;
};

const CATEGORY_LABELS: Record<string, string> = {
  gran_desarrollo_residencial: "Gran desarrollo residencial",
  residencial_o_vivienda: "Residencial / vivienda",
  urbanizacion_infraestructuras: "Urbanización e infraestructuras",
  gestion_reparcelacion: "Gestión o reparcelación",
  proteccion_catalogo: "Protección patrimonial / catálogo",
  equipamiento_dotacional: "Equipamiento o dotacional",
  terciario_comercial_hotelero: "Terciario, comercial u hotelero",
  plan_especial_uso_actividad: "Uso o actividad en edificio existente",
  modificacion_planeamiento_general: "Modificación del planeamiento general",
  ordenacion_parcela_manzana: "Ordenación de parcela o manzana",
  ajuste_administrativo: "Ajuste administrativo",
  planeamiento_otros: "Planeamiento urbanístico",
};

const AXIS_LABELS: Record<string, string> = {
  modificacion_pgou: "Modificación del PGOU",
  estudio_detalle: "Estudio de detalle",
  plan_parcial: "Plan parcial",
  plan_especial: "Plan especial",
  proyecto_urbanizacion: "Proyecto de urbanización",
  gestion_reparcelacion: "Gestión / reparcelación",
  catalogacion_proteccion: "Catalogación / protección",
  ajuste_administrativo: "Ajuste administrativo",
  otro_instrumento: "Otro instrumento",
  micro_parcela: "Micro parcela",
  parcela: "Parcela",
  manzana_o_ambito_pequeno: "Manzana o ámbito pequeño",
  ambito_medio: "Ámbito medio",
  gran_ambito: "Gran ámbito",
  sin_escala: "Escala sin dato",
  vivienda_residencial: "Vivienda / residencial",
  urbanizacion_infraestructura: "Urbanización / infraestructura",
  proteccion_catalogo: "Protección / catálogo",
  dotacional_equipamiento: "Dotacional / equipamiento",
  terciario_comercial_hotelero: "Terciario / comercial / hotelero",
  uso_actividad_edificio_existente: "Uso o actividad en edificio existente",
  ordenacion_parcela: "Ordenación de parcela",
  sin_clasificar: "Contenido sin clasificar",
  informacion_publica: "Información pública",
  aprobacion_inicial: "Aprobación inicial",
  aprobacion_provisional: "Aprobación provisional",
  aprobacion_definitiva: "Aprobación definitiva",
  gestion: "Gestión",
  urbanizacion: "Urbanización",
  archivado_o_detenido: "Archivado o detenido",
  expediente_abierto: "Expediente abierto",
  en_tramitacion: "En tramitación",
};

export function sigmaClassificationLabel(value: string | null | undefined): string | null {
  if (!value) return null;
  return CATEGORY_LABELS[value] || AXIS_LABELS[value] || value.replace(/_/g, " ");
}

export function sigmaClassificationTone(
  category: string | null | undefined,
): "teal" | "violet" | "amber" | "sky" | "slate" {
  if (!category) return "slate";
  if (category.includes("residencial")) return "teal";
  if (category.includes("urbanizacion") || category.includes("infraestructura")) return "sky";
  if (category.includes("proteccion") || category.includes("catalogo")) return "violet";
  if (category.includes("gestion") || category.includes("administrativo")) return "amber";
  return "slate";
}

export function sigmaConfidenceLabel(value: string | null | undefined): string | null {
  if (value === "alta") return "Confianza alta";
  if (value === "media") return "Confianza media";
  if (value === "baja") return "Confianza baja";
  return value || null;
}

/** Etiquetas legibles para filtros del mapa (exportadas desde los mismos mapas internos). */
export function sigmaClassificationAxisLabel(value: string | null | undefined): string | null {
  return sigmaClassificationLabel(value);
}
