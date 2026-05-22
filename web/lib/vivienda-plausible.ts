/** Coherencia viviendas ↔ superficie (reexport para componentes TS). */

export {
  M2_AMBITO_MIN_POR_VIVIENDA,
  M2_EDIFICABLE_MIN_POR_VIVIENDA,
  MAX_VIVIENDAS_SIN_SUPERFICIE,
  capViviendasPorSuperficie,
  viviendasCoherentesConSuperficie,
  sanitizeSigmaExpedienteMetric,
  sanitizeMetricsByExpediente,
} from "./vivienda-plausible.mjs";

import { sanitizeSigmaExpedienteMetric } from "./vivienda-plausible.mjs";
import type { SigmaExpedienteMetric } from "./sigma-metrics";

export function sanitizeSigmaMetric(metric: SigmaExpedienteMetric | null): SigmaExpedienteMetric | null {
  if (!metric) return null;
  return sanitizeSigmaExpedienteMetric(metric) as SigmaExpedienteMetric;
}
