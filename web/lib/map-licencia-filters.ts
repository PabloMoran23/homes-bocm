import { normalizarActuacionEdificio, type ActuacionQueCodigo } from "@/lib/actuacion-edificio";
import { ACTUACION_QUE_LEYENDA } from "@/lib/actuacion-que-config";
import type { UbicacionMapProperties } from "@/lib/ubicacion";
import { actuacionDesdeMapProps } from "@/lib/ubicacion";

export const ACTUACION_QUE_FILTRABLES: readonly ActuacionQueCodigo[] = ACTUACION_QUE_LEYENDA;

export function allActuacionQueEnabled(): Set<ActuacionQueCodigo> {
  return new Set(ACTUACION_QUE_FILTRABLES);
}

export function actuacionQueDeProps(
  props: UbicacionMapProperties,
): ActuacionQueCodigo {
  if (props.actuacionQue && ACTUACION_QUE_FILTRABLES.includes(props.actuacionQue as ActuacionQueCodigo)) {
    return props.actuacionQue as ActuacionQueCodigo;
  }
  return normalizarActuacionEdificio(actuacionDesdeMapProps(props)).codigo;
}

export function passesActuacionQueFilter(
  props: UbicacionMapProperties,
  enabled: Set<ActuacionQueCodigo>,
): boolean {
  if (enabled.size >= ACTUACION_QUE_FILTRABLES.length) return true;
  if (enabled.size === 0) return false;
  return enabled.has(actuacionQueDeProps(props));
}
