import {
  ACTUACION_QUE_LABELS,
  ACTUACION_QUE_MAPA_CATEGORIA,
  type ActuacionQueCodigo,
} from "@/lib/actuacion-edificio";
import { LICENCIA_MAPA_CONFIG } from "@/lib/licencia-mapa-config";

/** Orden de leyenda (filtro mapa + gráfico estadísticas). */
export const ACTUACION_QUE_LEYENDA: ActuacionQueCodigo[] = [
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

export type ActuacionQueMapStyle = {
  label: string;
  bg: string;
  ring: string;
};

export function getActuacionQueMapStyle(codigo: ActuacionQueCodigo): ActuacionQueMapStyle {
  const mapaCat = ACTUACION_QUE_MAPA_CATEGORIA[codigo];
  const cfg = LICENCIA_MAPA_CONFIG[mapaCat];
  return {
    label: ACTUACION_QUE_LABELS[codigo],
    bg: cfg.bg,
    ring: cfg.ring,
  };
}

export function labelActuacionQue(codigo: string): string {
  return ACTUACION_QUE_LABELS[codigo as ActuacionQueCodigo] ?? codigo;
}
