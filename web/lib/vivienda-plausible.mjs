/**
 * Coherencia viviendas ↔ m² (ámbito / edificabilidad). Compartido build-data y UI.
 */

export const M2_AMBITO_MIN_POR_VIVIENDA = 55;
export const M2_EDIFICABLE_MIN_POR_VIVIENDA = 42;
export const MAX_VIVIENDAS_SIN_SUPERFICIE = 400;

/**
 * @param {number | null | undefined} supTotalM2
 * @param {number | null | undefined} [supEdificableM2]
 * @returns {number | null}
 */
export function capViviendasPorSuperficie(supTotalM2, supEdificableM2) {
  const caps = [];
  if (supEdificableM2 != null && supEdificableM2 >= 100) {
    caps.push(Math.floor(supEdificableM2 / M2_EDIFICABLE_MIN_POR_VIVIENDA));
  }
  if (supTotalM2 != null && supTotalM2 >= 200) {
    caps.push(Math.floor(supTotalM2 / M2_AMBITO_MIN_POR_VIVIENDA));
  }
  if (!caps.length) return null;
  return Math.max(1, Math.min(...caps));
}

/**
 * @param {number | null | undefined} numViviendas
 * @param {number | null | undefined} supTotalM2
 * @param {number | null | undefined} [supEdificableM2]
 */
export function viviendasCoherentesConSuperficie(numViviendas, supTotalM2, supEdificableM2) {
  const n = Number(numViviendas);
  if (!Number.isFinite(n) || n < 1) return false;

  const cap = capViviendasPorSuperficie(supTotalM2, supEdificableM2);
  if (cap != null) return n <= cap;
  return n <= MAX_VIVIENDAS_SIN_SUPERFICIE;
}

/**
 * @param {string | null | undefined} familia
 * @param {string | null | undefined} genera
 */
function adjustGeneraTrasDescartarViviendas(familia, genera) {
  const fam = familia || "";
  if (fam === "pecuau" || fam === "catalogacion") return "no";
  if (fam === "plan_especial") return "stock_existente_o_rehabilitacion";
  if (genera === "si" || genera === "probable_si") {
    if (fam === "plan_parcial" || fam === "modificacion_pgou") return "probable_sin_cifra";
    return "desconocido";
  }
  return genera ?? null;
}

/**
 * @param {Record<string, unknown> | null | undefined} metric
 * @returns {Record<string, unknown> | null}
 */
export function sanitizeSigmaExpedienteMetric(metric) {
  if (!metric || typeof metric !== "object") return metric ?? null;

  const viv = metric.num_viviendas_max;
  if (viv == null) return metric;

  const sup = metric.sup_total_m2;
  const edif = metric.sup_edificable_m2;
  if (
    viviendasCoherentesConSuperficie(
      viv,
      sup != null ? Number(sup) : null,
      edif != null ? Number(edif) : null,
    )
  ) {
    return metric;
  }

  const hechos = Array.isArray(metric.hechos)
    ? metric.hechos.filter((h) => {
        const key = h?.metric ?? h?.metrica;
        return key !== "num_viviendas_max";
      })
    : metric.hechos;

  return {
    ...metric,
    num_viviendas_max: null,
    genera_vivienda_nueva: adjustGeneraTrasDescartarViviendas(
      /** @type {string | null | undefined} */ (metric.familia_expediente),
      /** @type {string | null | undefined} */ (metric.genera_vivienda_nueva),
    ),
    hechos,
  };
}

/**
 * @param {Record<string, { num_viviendas_max?: number | null, sup_total_m2?: number | null }>} byExpediente
 */
export function sanitizeMetricsByExpediente(byExpediente) {
  const out = {};
  for (const [grupo, row] of Object.entries(byExpediente || {})) {
    out[grupo] = sanitizeSigmaExpedienteMetric(row);
  }
  return out;
}
