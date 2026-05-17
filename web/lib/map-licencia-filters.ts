import { clasificarLicenciaMapa, type LicenciaMapaCategoria } from "@/lib/licencia-tipos";
import { LICENCIA_MAPA_LEYENDA } from "@/lib/licencia-mapa-config";

export const LICENCIA_TIPOS_FILTRABLES: readonly LicenciaMapaCategoria[] = LICENCIA_MAPA_LEYENDA;

export function allLicenciaTiposEnabled(): Set<LicenciaMapaCategoria> {
  return new Set(LICENCIA_TIPOS_FILTRABLES);
}

export function passesLicenciaTipoFilter(
  ultimaLicenciaTipo: string | null | undefined,
  enabled: Set<LicenciaMapaCategoria>,
): boolean {
  if (enabled.size >= LICENCIA_TIPOS_FILTRABLES.length) return true;
  if (enabled.size === 0) return false;
  return enabled.has(clasificarLicenciaMapa(ultimaLicenciaTipo));
}
