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
  tipoObra: string | null;
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

const TIPO_OBRA_LABELS: Record<string, string> = {
  vivienda_residencial: "Vivienda / residencial",
  edificio_ampliacion: "Edificio / ampliación / reforma",
  garaje_aparcamiento: "Garaje / aparcamiento",
  uso_terciario: "Uso terciario (bar, hotel, oficina…)",
  infraestructura_viaria: "Infraestructura viaria (aceras, calzada…)",
  urbanizacion_redes: "Urbanización / redes",
  equipamiento_publico: "Equipamiento público",
  proteccion_patrimonio: "Protección patrimonial",
  ordenacion_usos_actividad: "Ordenación de usos / actividad",
  reparcelacion_gestion: "Reparcelación / gestión",
  modificacion_planeamiento: "Modificación del planeamiento",
  sin_determinar: "Tipo de obra sin determinar",
};

const TIPO_OBRA_PLAIN: Record<string, string> = {
  vivienda_residencial:
    "El proyecto prevé viviendas nuevas o un desarrollo residencial en el ámbito afectado.",
  edificio_ampliacion:
    "Afecta a un edificio concreto: ampliación, reforma, nueva edificabilidad u ordenación de volúmenes.",
  garaje_aparcamiento:
    "Tiene que ver con plazas de garaje, aparcamiento o estacionamiento en un edificio o parcela.",
  uso_terciario:
    "Regula o autoriza un uso terciario: bar, restaurante, hotel, oficina, comercio u hospedaje.",
  infraestructura_viaria:
    "Interviene en la calle o el espacio público: aceras, calzada, viario o accesibilidad peatonal.",
  urbanizacion_redes:
    "Es una urbanización o actuación sobre redes, servicios o infraestructuras del suelo.",
  equipamiento_publico:
    "Destina el ámbito a equipamiento público: colegio, sanidad, dotacional, cultural o deportivo.",
  proteccion_patrimonio:
    "Protege o regula un bien patrimonial, edificio catalogado o entorno con valor histórico.",
  ordenacion_usos_actividad:
    "Ordena usos en un edificio existente: terrazas, locales, actividad, PECUAU o compatibilidades.",
  reparcelacion_gestion:
    "Es una actuación de gestión urbanística: reparcelación, compensación o redistribución de suelo.",
  modificacion_planeamiento:
    "Cambia normas del plan general de Madrid para este ámbito o para toda la ciudad.",
  sin_determinar:
    "No hemos podido concretar qué tipo de obra plantea; conviene leer el resumen del visor.",
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

const AXIS_PLAIN: Record<string, string> = {
  modificacion_pgou: "Instrumento: modificación del Plan General (PGOU).",
  estudio_detalle: "Instrumento: estudio de detalle sobre una parcela o manzana.",
  plan_parcial: "Instrumento: plan parcial de ordenación.",
  plan_especial: "Instrumento: plan especial para este ámbito concreto.",
  proyecto_urbanizacion: "Instrumento: proyecto de urbanización.",
  gestion_reparcelacion: "Instrumento: gestión o reparcelación.",
  catalogacion_proteccion: "Instrumento: catalogación o protección.",
  ajuste_administrativo: "Instrumento: subsanación o ajuste administrativo.",
  otro_instrumento: "Instrumento urbanístico no clasificado con más detalle.",
  micro_parcela: "Escala: una parcela muy pequeña.",
  parcela: "Escala: una parcela.",
  manzana_o_ambito_pequeno: "Escala: manzana o ámbito de barrio pequeño.",
  ambito_medio: "Escala: ámbito medio (varias manzanas).",
  gran_ambito: "Escala: gran ámbito o desarrollo extenso.",
  sin_escala: "Escala: sin dato fiable de tamaño.",
  informacion_publica: "Estado: en periodo de información pública.",
  aprobacion_inicial: "Estado: aprobación inicial.",
  aprobacion_provisional: "Estado: aprobación provisional.",
  aprobacion_definitiva: "Estado: aprobación definitiva.",
  gestion: "Estado: fase de gestión urbanística.",
  urbanizacion: "Estado: fase de urbanización.",
  archivado_o_detenido: "Estado: archivado, desistido o detenido.",
  expediente_abierto: "Estado: expediente recién incoado.",
  en_tramitacion: "Estado: en tramitación.",
};

export type SigmaClassificationTag = {
  id: string;
  label: string;
  hint: string;
  tone: ReturnType<typeof sigmaClassificationTone>;
};

export function sigmaClassificationPlainText(
  code: string | null | undefined,
  kind: "tipoObra" | "categoria" | "axis" = "axis",
): string | null {
  if (!code) return null;
  if (kind === "tipoObra") return TIPO_OBRA_PLAIN[code] ?? null;
  if (kind === "categoria") return CATEGORY_PLAIN[code] ?? null;
  return AXIS_PLAIN[code] ?? null;
}

/** Resumen en lenguaje llano + etiquetas para la ficha del proyecto. */
export function sigmaClassificationResumen(value?: SigmaClassification | null): {
  headline: string;
  tags: SigmaClassificationTag[];
} | null {
  if (!value?.categoriaProyecto && !value?.tipoObra) return null;

  const parts: string[] = [];
  const tipoObraPlain = sigmaClassificationPlainText(value.tipoObra, "tipoObra");
  const categoriaPlain = sigmaClassificationPlainText(value.categoriaProyecto, "categoria");
  const fasePlain = sigmaClassificationPlainText(value.faseNormalizada, "axis");
  const escalaPlain = sigmaClassificationPlainText(value.escala, "axis");

  if (tipoObraPlain) parts.push(tipoObraPlain);
  else if (categoriaPlain) parts.push(categoriaPlain);

  if (escalaPlain && value.escala !== "sin_escala") parts.push(escalaPlain);
  if (fasePlain) parts.push(fasePlain);

  const headline =
    parts.join(" ").trim() ||
    "Proyecto de planeamiento urbanístico del Ayuntamiento de Madrid en tramitación o consulta.";

  const tags: SigmaClassificationTag[] = [];

  if (value.tipoObra && value.tipoObra !== "sin_determinar") {
    tags.push({
      id: "tipoObra",
      label: sigmaTipoObraLabel(value.tipoObra) ?? value.tipoObra,
      hint: tipoObraPlain ?? "Qué se quiere construir o autorizar.",
      tone: sigmaClassificationTone(value.tipoObra),
    });
  }

  if (value.tipoLegal) {
    tags.push({
      id: "tipoLegal",
      label: sigmaClassificationLabel(value.tipoLegal) ?? value.tipoLegal,
      hint: sigmaClassificationPlainText(value.tipoLegal, "axis") ?? "Cómo se tramita urbanísticamente.",
      tone: "slate",
    });
  }

  if (value.escala && value.escala !== "sin_escala") {
    tags.push({
      id: "escala",
      label: sigmaClassificationLabel(value.escala) ?? value.escala,
      hint: escalaPlain ?? "Tamaño del ámbito afectado.",
      tone: "slate",
    });
  }

  if (value.faseNormalizada) {
    tags.push({
      id: "fase",
      label: sigmaClassificationLabel(value.faseNormalizada) ?? value.faseNormalizada,
      hint: fasePlain ?? "En qué punto del procedimiento está.",
      tone: "sky",
    });
  }

  if (value.categoriaProyecto) {
    tags.push({
      id: "categoria",
      label: sigmaClassificationLabel(value.categoriaProyecto) ?? value.categoriaProyecto,
      hint: categoriaPlain ?? "Resumen temático del proyecto.",
      tone: sigmaClassificationTone(value.categoriaProyecto),
    });
  }

  return { headline, tags };
}

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
  return CATEGORY_LABELS[value] || TIPO_OBRA_LABELS[value] || AXIS_LABELS[value] || value.replace(/_/g, " ");
}

export function sigmaTipoObraLabel(value: string | null | undefined): string | null {
  if (!value) return null;
  return TIPO_OBRA_LABELS[value] || value.replace(/_/g, " ");
}

export function sigmaClassificationTone(
  category: string | null | undefined,
): "teal" | "violet" | "amber" | "sky" | "slate" {
  if (!category) return "slate";
  if (category.includes("residencial") || category.includes("vivienda")) return "teal";
  if (
    category.includes("urbanizacion") ||
    category.includes("infraestructura") ||
    category.includes("viaria") ||
    category.includes("redes")
  )
    return "sky";
  if (category.includes("proteccion") || category.includes("catalogo") || category.includes("patrimonio"))
    return "violet";
  if (
    category.includes("gestion") ||
    category.includes("administrativo") ||
    category.includes("reparcelacion")
  )
    return "amber";
  if (category.includes("garaje") || category.includes("terciario") || category.includes("ordenacion_usos"))
    return "amber";
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
