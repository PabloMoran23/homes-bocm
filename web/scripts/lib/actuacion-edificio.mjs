/** Port de lib/actuacion-edificio.ts para scripts Node (build geojson). */

import { clasificarLicenciaMapa } from "./licencia-mapa-categoria.mjs";

export const ACTUACION_QUE_LABELS = {
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

const MAPA_POR_CODIGO = {
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

function norm(s) {
  return String(s || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function esResidencial(uso) {
  return /residencial|vivienda|hotel|alojamiento/.test(uso);
}

function esActividad(uso) {
  return /actividad|comercial|industrial|servicios|dotacional|equipamiento/.test(uso);
}

function codigoDesdeObjeto(objeto) {
  const o = norm(objeto);
  if (!o) return null;
  if (o.includes("demolicion")) return { codigo: "edificio_demolicion", confianza: "alta" };
  if (o.includes("primera ocupacion") || o.includes("ocupacion y funcionamiento")) {
    return { codigo: "edificio_primera_ocupacion", confianza: "alta" };
  }
  if (o.includes("sustitucion") || o.includes("ampliacion") || o.includes("nueva planta")) {
    return { codigo: "edificio_obra_grande", confianza: "alta" };
  }
  if (
    /restauracion|conservacion|consolidacion|refuerzo|acondicionamiento|rehabilitacion|reestructuracion/.test(
      o,
    )
  ) {
    return { codigo: "edificio_reforma_conservacion", confianza: "alta" };
  }
  if (/exterior|cerramiento|vallado|piscina|talas/.test(o)) {
    return { codigo: "obra_exterior", confianza: "alta" };
  }
  return null;
}

function codigoDesdeTipo(tipo, procedimiento) {
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
  if (tipo.includes("declaracion responsable residencial")) {
    return { codigo: "vivienda_obra_menor", confianza: "media" };
  }
  if (tipo.includes("declaracion responsable actividad")) {
    return { codigo: "local_actividad", confianza: "media" };
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
  if (tipo.includes("primera ocupacion")) {
    return { codigo: "edificio_primera_ocupacion", confianza: "alta" };
  }
  if (tipo.includes("nueva planta") || tipo.includes("ampliacion") || tipo.includes("sustitucion")) {
    return { codigo: "edificio_obra_grande", confianza: "alta" };
  }
  if (
    tipo.includes("conservacion") ||
    tipo.includes("restauracion") ||
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

export function normalizarActuacionEdificio(input) {
  const tipo = norm(input.tipo_expediente || input.tipoExpediente);
  const objetoRaw = String(input.objeto || "").trim();
  const uso = norm(input.uso);
  const procedimiento = norm(input.procedimiento);

  let codigo = "otro";
  let confianza = "baja";

  const desdeObjeto = objetoRaw ? codigoDesdeObjeto(objetoRaw) : null;
  if (desdeObjeto) {
    codigo = desdeObjeto.codigo;
    confianza = desdeObjeto.confianza;
  } else if (tipo) {
    const d = codigoDesdeTipo(tipo, procedimiento);
    codigo = d.codigo;
    confianza = d.confianza;
  }

  if ((codigo === "tramite_generico" || codigo === "otro") && uso) {
    if (esResidencial(uso)) {
      codigo = "vivienda_obra_menor";
      confianza = "media";
    } else if (esActividad(uso)) {
      codigo = "local_actividad";
      confianza = "media";
    }
  }

  if (procedimiento.includes("declaracion responsable") || tipo.includes("declaracion responsable")) {
    if (esActividad(uso)) codigo = "local_actividad";
    else if (codigo === "tramite_generico" || codigo === "vivienda_obra") codigo = "vivienda_obra_menor";
  }

  const etiqueta = ACTUACION_QUE_LABELS[codigo] || ACTUACION_QUE_LABELS.otro;
  const mapaCategoria =
    confianza === "baja" && (input.tipo_expediente || input.tipoExpediente)
      ? clasificarLicenciaMapa(input.tipo_expediente || input.tipoExpediente)
      : MAPA_POR_CODIGO[codigo] || "otra";

  return { codigo, etiqueta, mapaCategoria, confianza };
}
