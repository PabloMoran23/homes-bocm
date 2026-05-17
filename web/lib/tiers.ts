export type TierId = "free" | "particular" | "empresa";

export const TIER_STORAGE_KEY = "bocm-tier";
export const TIER_COOKIE_NAME = "bocm-tier";

export function parseTierId(value: string | undefined | null): TierId {
  if (value === "particular" || value === "empresa" || value === "free") return value;
  return "free";
}

export const TIER_LABEL: Record<TierId, string> = {
  free: "Gratis",
  particular: "Particular",
  empresa: "Empresa",
};

export type TierLimits = {
  maxTableRows: number;
  exportFilteredCsv: boolean;
  /** Si no es null, la ficha trunca el resumen a esta longitud */
  resumenPreviewChars: number | null;
  /** Cuántas filas del ranking de municipios se muestran en /estadisticas */
  statsMunicipioRowsVisible: number | null;
  statsTipoRowsVisible: number | null;
};

export function getTierLimits(tier: TierId): TierLimits {
  switch (tier) {
    case "free":
      return {
        maxTableRows: 60,
        exportFilteredCsv: false,
        resumenPreviewChars: 400,
        statsMunicipioRowsVisible: 10,
        statsTipoRowsVisible: 8,
      };
    case "particular":
      return {
        maxTableRows: 400,
        exportFilteredCsv: false,
        resumenPreviewChars: null,
        statsMunicipioRowsVisible: null,
        statsTipoRowsVisible: null,
      };
    case "empresa":
      return {
        maxTableRows: 20_000,
        exportFilteredCsv: true,
        resumenPreviewChars: null,
        statsMunicipioRowsVisible: null,
        statsTipoRowsVisible: null,
      };
  }
}

export const TIER_FEATURES = {
  free: [
    "Mapa y filtros básicos",
    "Hasta 60 filas en tabla por búsqueda",
    "Estadísticas con vista parcial de rankings",
    "Acceso al documento público cuando exista enlace en la ficha",
  ],
  particular: [
    "Todo lo del plan Gratis",
    "Hasta 400 filas en tabla",
    "Fichas con resumen completo",
    "Rankings completos en estadísticas",
    "Alertas cuando cambie tu zona (en roadmap)",
  ],
  empresa: [
    "Todo lo del plan Particular",
    "Tabla sin tope práctico en el dataset actual",
    "Exportación CSV del resultado filtrado",
    "API y equipos (en roadmap)",
  ],
} as const satisfies Record<TierId, readonly string[]>;
