/**
 * Paleta SIGMA sobre el plano de papel: agua, salmón, sage y ocre.
 */
export const SIGMA_MAP_POLYGON = {
  default: {
    color: "#1f4f53",
    weight: 2,
    fillColor: "#7a9a96",
    fillOpacity: 0.22,
  },
  tramitados_ad: {
    color: "#9a5c48",
    weight: 1.5,
    fillColor: "#d4a090",
    fillOpacity: 0.26,
  },
  gestion: {
    color: "#5f7a4a",
    weight: 2,
    fillColor: "#c7d4a8",
    fillOpacity: 0.28,
  },
  urbanizacion: {
    color: "#c07f6c",
    weight: 2,
    fillColor: "#e6c3b4",
    fillOpacity: 0.28,
  },
} as const;

export const SIGMA_MAP_POINT = {
  default: {
    radius: 8,
    color: "#1f4f53",
    weight: 2,
    fillColor: "#4a7578",
    fillOpacity: 0.9,
  },
  tramitados_ad: {
    radius: 7,
    color: "#9a5c48",
    weight: 2,
    fillColor: "#c07f6c",
    fillOpacity: 0.88,
  },
} as const;

/** Leyenda mapa (clases Tailwind, alineadas con SIGMA_MAP_POLYGON). */
export const SIGMA_MAP_LEGEND = {
  planeamiento: "h-2.5 w-4 rounded-sm bg-[#7a9a96] ring-1 ring-[#1f4f53]",
  tramitacion: "h-2.5 w-4 rounded-sm bg-[#d4a090] ring-1 ring-[#9a5c48]",
  gestion: "h-2.5 w-4 rounded-sm bg-[#c7d4a8] ring-1 ring-[#5f7a4a]",
  urbanizacion: "h-2.5 w-4 rounded-sm bg-[#e6c3b4] ring-1 ring-[#c07f6c]",
} as const;
