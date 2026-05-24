/**
 * Normaliza «qué se va a hacer» en un edificio a partir del open data de licencias Madrid:
 * objeto, tipo_expediente, uso y procedimiento → código estable + etiqueta + categoría de mapa.
 */

import {
  clasificarLicenciaMapa,
  licenciaTituloDesdeTipo,
  normTipoExpediente,
  type LicenciaMapaCategoria,
} from "@/lib/licencia-tipos";

export type ActuacionQueCodigo =
  | "vivienda_obra_menor"
  | "vivienda_obra"
  | "vivienda_uso"
  | "local_actividad"
  | "local_obra"
  | "local_a_vivienda"
  | "edificio_obra_grande"
  | "edificio_reforma_conservacion"
  | "edificio_demolicion"
  | "edificio_primera_ocupacion"
  | "obra_exterior"
  | "consulta"
  | "tramite_generico"
  | "otro";

export type ActuacionConfianza = "alta" | "media" | "baja";

export type ActuacionEdificioInput = {
  tipo_expediente?: string | null;
  objeto?: string | null;
  uso?: string | null;
  procedimiento?: string | null;
};

export type ActuacionEdificioNorm = {
  codigo: ActuacionQueCodigo;
  etiqueta: string;
  detalle: string | null;
  mapaCategoria: LicenciaMapaCategoria;
  confianza: ActuacionConfianza;
};

export const ACTUACION_QUE_LABELS: Record<ActuacionQueCodigo, string> = {
  vivienda_obra_menor: "Obras menores en vivienda",
  vivienda_obra: "Obra en vivienda",
  vivienda_uso: "Uso o apertura en vivienda",
  local_actividad: "Apertura o cambio en local",
  local_obra: "Obra en local comercial",
  local_a_vivienda: "Local convertido en vivienda",
  edificio_obra_grande: "Obra de nueva planta o ampliación",
  edificio_reforma_conservacion: "Reforma o conservación del edificio",
  edificio_demolicion: "Demolición",
  edificio_primera_ocupacion: "Edificio listo para ocupar",
  obra_exterior: "Obra en patio o exterior",
  consulta: "Consulta urbanística",
  tramite_generico: "Actuación urbanística registrada",
  otro: "Tramitación urbanística",
};

/** Icono/color del mapa asociado a cada código normalizado. */
export const ACTUACION_QUE_MAPA_CATEGORIA: Record<ActuacionQueCodigo, LicenciaMapaCategoria> = {
  vivienda_obra_menor: "dr_residencial",
  vivienda_obra: "lu_residencial",
  vivienda_uso: "funcionamiento_residencial",
  local_actividad: "dr_actividad",
  local_obra: "lu_actividad",
  local_a_vivienda: "obra_local_vivienda",
  edificio_obra_grande: "obra_edificio",
  edificio_reforma_conservacion: "obra_edificio",
  edificio_demolicion: "obra_edificio",
  edificio_primera_ocupacion: "primera_ocupacion",
  obra_exterior: "obra_edificio",
  consulta: "consulta",
  tramite_generico: "dr_otra",
  otro: "otra",
};

function esResidencial(uso: string): boolean {
  return (
    uso.includes("residencial") ||
    uso.includes("vivienda") ||
    uso.includes("viviendas") ||
    uso.includes("hotel") ||
    uso.includes("alojamiento")
  );
}

function esActividad(uso: string): boolean {
  return (
    uso.includes("actividad") ||
    uso.includes("comercial") ||
    uso.includes("industrial") ||
    uso.includes("servicios") ||
    uso.includes("dotacional") ||
    uso.includes("equipamiento")
  );
}

function esDeclaracionResponsable(procedimiento: string, tipo: string): boolean {
  return procedimiento.includes("declaracion responsable") || tipo.includes("declaracion responsable");
}

type ReglaObjeto = {
  when: (o: string) => boolean;
  codigo: ActuacionQueCodigo;
  confianza: ActuacionConfianza;
};

const REGLAS_OBJETO: ReglaObjeto[] = [
  {
    when: (o) => o.includes("demolicion"),
    codigo: "edificio_demolicion",
    confianza: "alta",
  },
  {
    when: (o) =>
      o.includes("primera ocupacion") || o.includes("ocupacion y funcionamiento"),
    codigo: "edificio_primera_ocupacion",
    confianza: "alta",
  },
  {
    when: (o) =>
      o.includes("sustitucion") ||
      o.includes("ampliacion") ||
      o.includes("nueva planta") ||
      o.includes("incrementar") && o.includes("vivienda"),
    codigo: "edificio_obra_grande",
    confianza: "alta",
  },
  {
    when: (o) =>
      o.includes("restauracion") ||
      o.includes("conservacion") ||
      o.includes("consolidacion") ||
      o.includes("refuerzo") ||
      o.includes("acondicionamiento") ||
      o.includes("rehabilitacion") ||
      o.includes("reestructuracion"),
    codigo: "edificio_reforma_conservacion",
    confianza: "alta",
  },
  {
    when: (o) =>
      o.includes("exterior") ||
      o.includes("cerramiento") ||
      o.includes("vallado") ||
      o.includes("piscina") ||
      o.includes("talas"),
    codigo: "obra_exterior",
    confianza: "alta",
  },
];

function codigoDesdeObjeto(objeto: string): { codigo: ActuacionQueCodigo; confianza: ActuacionConfianza } | null {
  const o = normTipoExpediente(objeto);
  if (!o) return null;
  for (const regla of REGLAS_OBJETO) {
    if (regla.when(o)) return { codigo: regla.codigo, confianza: regla.confianza };
  }
  return null;
}

function codigoDesdeTipo(
  tipo: string,
  procedimiento: string,
): { codigo: ActuacionQueCodigo; confianza: ActuacionConfianza } {
  if (tipo.includes("consulta urbanistica") || tipo.includes("parcelacion")) {
    return { codigo: "consulta", confianza: "alta" };
  }
  if (
    tipo.includes("transformacion") &&
    (tipo.includes("local") || tipo.includes("locales")) &&
    tipo.includes("vivienda")
  ) {
    return { codigo: "local_a_vivienda", confianza: "alta" };
  }
  if (tipo.includes("declaracion responsable residencial") || tipo.includes("declaracion responsable obra")) {
    return { codigo: "vivienda_obra_menor", confianza: "media" };
  }
  if (tipo.includes("declaracion responsable actividad")) {
    return { codigo: "local_actividad", confianza: "media" };
  }
  if (tipo.includes("declaracion responsable") && tipo.includes("primera ocupacion")) {
    return { codigo: "edificio_primera_ocupacion", confianza: "media" };
  }
  if (tipo.includes("declaracion responsable")) {
    return { codigo: "tramite_generico", confianza: "baja" };
  }
  if (tipo.includes("licencia urbanistica") && tipo.includes("residencial")) {
    return { codigo: "vivienda_obra", confianza: "media" };
  }
  if (tipo.includes("licencia urbanistica") && tipo.includes("actividad")) {
    return { codigo: "local_obra", confianza: "media" };
  }
  if (tipo.includes("funcionamiento") && tipo.includes("residencial")) {
    return { codigo: "vivienda_uso", confianza: "media" };
  }
  if (tipo.includes("funcionamiento") || tipo.includes("implantacion")) {
    return { codigo: "local_actividad", confianza: "media" };
  }
  if (tipo.includes("comunicacion previa")) {
    return { codigo: "tramite_generico", confianza: "baja" };
  }
  if (tipo.includes("primera ocupacion")) {
    return { codigo: "edificio_primera_ocupacion", confianza: "alta" };
  }
  if (
    tipo.includes("nueva planta") ||
    tipo.includes("ampliacion") ||
    tipo.includes("sustitucion") ||
    tipo.includes("reestructuracion")
  ) {
    return { codigo: "edificio_obra_grande", confianza: "alta" };
  }
  if (
    tipo.includes("conservacion") ||
    tipo.includes("restauracion") ||
    tipo.includes("refuerzo") ||
    tipo.includes("acondicionamiento") ||
    tipo.includes("demolicion")
  ) {
    return {
      codigo: tipo.includes("demolicion") ? "edificio_demolicion" : "edificio_reforma_conservacion",
      confianza: "alta",
    };
  }
  if (tipo.includes("obra") || procedimiento.includes("ordinario")) {
    return { codigo: "tramite_generico", confianza: "baja" };
  }
  return { codigo: "otro", confianza: "baja" };
}

function refinarConUso(
  codigo: ActuacionQueCodigo,
  confianza: ActuacionConfianza,
  uso: string,
): { codigo: ActuacionQueCodigo; confianza: ActuacionConfianza } {
  if (!uso) return { codigo, confianza };
  if (codigo !== "tramite_generico" && codigo !== "otro") return { codigo, confianza };

  if (esResidencial(uso)) {
    return {
      codigo: codigo === "otro" ? "vivienda_obra" : "vivienda_obra_menor",
      confianza: confianza === "baja" ? "media" : confianza,
    };
  }
  if (esActividad(uso)) {
    return {
      codigo: "local_actividad",
      confianza: confianza === "baja" ? "media" : confianza,
    };
  }
  return { codigo, confianza };
}

function detalleLinea(input: ActuacionEdificioInput, procedimiento: string): string | null {
  const partes: string[] = [];
  const uso = (input.uso || "").trim();
  const objeto = (input.objeto || "").trim();
  if (uso) partes.push(uso);
  if (objeto && objeto.length <= 120) partes.push(objeto);
  if (procedimiento.includes("declaracion responsable")) {
    partes.push("Trámite rápido municipal");
  } else if (procedimiento.includes("comunicacion previa")) {
    partes.push("Obra comunicada al Ayuntamiento");
  } else if (procedimiento.includes("ordinario abreviado")) {
    partes.push("Licencia ordinaria abreviada");
  } else if (procedimiento.includes("ordinario comun")) {
    partes.push("Licencia ordinaria");
  }
  return partes.length ? partes.join(" · ") : null;
}

/** Variable normalizada «qué se va a hacer» para UI y mapas. */
export function normalizarActuacionEdificio(input: ActuacionEdificioInput): ActuacionEdificioNorm {
  const tipo = normTipoExpediente(input.tipo_expediente || "");
  const objetoRaw = (input.objeto || "").trim();
  const uso = normTipoExpediente(input.uso || "");
  const procedimiento = normTipoExpediente(input.procedimiento || "");

  let codigo: ActuacionQueCodigo = "otro";
  let confianza: ActuacionConfianza = "baja";

  const desdeObjeto = objetoRaw ? codigoDesdeObjeto(objetoRaw) : null;
  if (desdeObjeto) {
    codigo = desdeObjeto.codigo;
    confianza = desdeObjeto.confianza;
  } else if (tipo) {
    const desdeTipo = codigoDesdeTipo(tipo, procedimiento);
    codigo = desdeTipo.codigo;
    confianza = desdeTipo.confianza;
  }

  const refinado = refinarConUso(codigo, confianza, uso);
  codigo = refinado.codigo;
  confianza = refinado.confianza;

  if (esDeclaracionResponsable(procedimiento, tipo)) {
    if (esActividad(uso)) codigo = "local_actividad";
    else if (codigo === "tramite_generico" || codigo === "vivienda_obra") {
      codigo = "vivienda_obra_menor";
    }
  }

  const etiqueta =
    ACTUACION_QUE_LABELS[codigo] !== ACTUACION_QUE_LABELS.otro
      ? ACTUACION_QUE_LABELS[codigo]
      : licenciaTituloDesdeTipo(input.tipo_expediente);

  const mapaCategoria =
    confianza === "baja" && tipo
      ? clasificarLicenciaMapa(input.tipo_expediente)
      : ACTUACION_QUE_MAPA_CATEGORIA[codigo];

  return {
    codigo,
    etiqueta,
    detalle: detalleLinea(input, procedimiento),
    mapaCategoria,
    confianza,
  };
}

export function actuacionQueCodigo(input: ActuacionEdificioInput): ActuacionQueCodigo {
  return normalizarActuacionEdificio(input).codigo;
}
