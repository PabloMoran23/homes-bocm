/**
 * Paleta SIGMA en mapa: polígonos translúcidos con tonos joya para distinguir
 * planeamiento, tramitación, gestión y urbanización sin ensuciar la base.
 */
export const SIGMA_MAP_POLYGON = {
  /** Ámbitos, IP y planeamiento por defecto */
  default: {
    color: "#4f46e5",
    weight: 2,
    fillColor: "#a5b4fc",
    fillOpacity: 0.28,
  },
  tramitados_ad: {
    color: "#0284c7",
    weight: 1.5,
    fillColor: "#7dd3fc",
    fillOpacity: 0.26,
  },
  gestion: {
    color: "#059669",
    weight: 2,
    fillColor: "#6ee7b7",
    fillOpacity: 0.24,
  },
  urbanizacion: {
    color: "#d97706",
    weight: 2,
    fillColor: "#fbbf24",
    fillOpacity: 0.25,
  },
} as const;

export const SIGMA_MAP_POINT = {
  default: {
    radius: 8,
    color: "#4f46e5",
    weight: 2,
    fillColor: "#818cf8",
    fillOpacity: 0.88,
  },
  tramitados_ad: {
    radius: 7,
    color: "#0284c7",
    weight: 2,
    fillColor: "#38bdf8",
    fillOpacity: 0.85,
  },
} as const;

/** Leyenda mapa (clases Tailwind, alineadas con SIGMA_MAP_POLYGON). */
export const SIGMA_MAP_LEGEND = {
  planeamiento: "h-2.5 w-4 rounded-sm bg-indigo-300/90 ring-1 ring-indigo-700",
  tramitacion: "h-2.5 w-4 rounded-sm bg-sky-300/90 ring-1 ring-sky-700",
  gestion: "h-2.5 w-4 rounded-sm bg-emerald-300/90 ring-1 ring-emerald-700",
  urbanizacion: "h-2.5 w-4 rounded-sm bg-amber-300/90 ring-1 ring-amber-700",
} as const;
