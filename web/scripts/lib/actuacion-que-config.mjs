/** Port de lib/actuacion-que-config.ts para scripts Node. */

import { ACTUACION_QUE_LABELS } from "./actuacion-edificio.mjs";
import { LICENCIA_MAPA_COLORS } from "./licencia-mapa-categoria.mjs";

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

export const ACTUACION_QUE_LEYENDA = [
  "vivienda_obra_menor",
  "vivienda_obra",
  "vivienda_uso",
  "local_actividad",
  "local_obra",
  "local_a_vivienda",
  "edificio_obra_grande",
  "edificio_reforma_conservacion",
  "edificio_demolicion",
  "edificio_primera_ocupacion",
  "obra_exterior",
  "consulta",
  "tramite_generico",
  "otro",
];

export function labelActuacionQue(codigo) {
  return ACTUACION_QUE_LABELS[codigo] || codigo;
}

export function colorActuacionQue(codigo) {
  const cat = MAPA_POR_CODIGO[codigo] || "otra";
  return LICENCIA_MAPA_COLORS[cat] || "#64748b";
}
