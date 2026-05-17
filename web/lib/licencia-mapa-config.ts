import type { LicenciaMapaCategoria } from "@/lib/licencia-tipos";

export type LicenciaMapaCategoriaConfig = {
  label: string;
  bg: string;
  ring: string;
  svg: string;
};

const ICONS = {
  casa: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.5L12 3l9 7.5V21a1 1 0 01-1 1h-5v-7H9v7H4a1 1 0 01-1-1z"/></svg>`,
  local: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9h18v12H3z"/><path d="M7 9V5h10v4"/><path d="M9 14h.01M15 14h.01"/></svg>`,
  obra: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg>`,
  doc: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/></svg>`,
  aviso: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><path d="M12 9v4M12 17h.01"/></svg>`,
  llave: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 11-7.78 7.78 5.5 5.5 0 017.78-7.78zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>`,
  uso: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/></svg>`,
  punto: `<svg width="10" height="10" viewBox="0 0 24 24" fill="#fff"><circle cx="12" cy="12" r="5"/></svg>`,
} as const;

export const LICENCIA_MAPA_CONFIG: Record<LicenciaMapaCategoria, LicenciaMapaCategoriaConfig> = {
  dr_residencial: {
    label: "Declaración responsable · vivienda",
    bg: "#d97706",
    ring: "#b45309",
    svg: ICONS.casa,
  },
  dr_actividad: {
    label: "Declaración responsable · local",
    bg: "#7c3aed",
    ring: "#6d28d9",
    svg: ICONS.local,
  },
  dr_otra: {
    label: "Declaración responsable",
    bg: "#ca8a04",
    ring: "#a16207",
    svg: ICONS.doc,
  },
  lu_residencial: {
    label: "Licencia urbanística · vivienda",
    bg: "#0f766e",
    ring: "#115e59",
    svg: ICONS.obra,
  },
  lu_actividad: {
    label: "Licencia urbanística · local",
    bg: "#2563eb",
    ring: "#1d4ed8",
    svg: ICONS.local,
  },
  lu_otra: {
    label: "Licencia urbanística",
    bg: "#0891b2",
    ring: "#0e7490",
    svg: ICONS.obra,
  },
  funcionamiento_residencial: {
    label: "Funcionamiento · vivienda",
    bg: "#059669",
    ring: "#047857",
    svg: ICONS.uso,
  },
  funcionamiento_actividad: {
    label: "Funcionamiento · local / actividad",
    bg: "#4f46e5",
    ring: "#4338ca",
    svg: ICONS.local,
  },
  comunicacion_previa: {
    label: "Comunicación previa de obra",
    bg: "#ea580c",
    ring: "#c2410c",
    svg: ICONS.aviso,
  },
  primera_ocupacion: {
    label: "Primera ocupación",
    bg: "#16a34a",
    ring: "#15803d",
    svg: ICONS.llave,
  },
  obra_local_vivienda: {
    label: "Local convertido en vivienda",
    bg: "#c026d3",
    ring: "#a21caf",
    svg: ICONS.casa,
  },
  obra_edificio: {
    label: "Obra en el edificio",
    bg: "#78716c",
    ring: "#57534e",
    svg: ICONS.obra,
  },
  consulta: {
    label: "Consulta o parcelación",
    bg: "#94a3b8",
    ring: "#64748b",
    svg: ICONS.doc,
  },
  otra: {
    label: "Otra actuación",
    bg: "#64748b",
    ring: "#475569",
    svg: ICONS.punto,
  },
};

export const LICENCIA_MAPA_LEYENDA: LicenciaMapaCategoria[] = [
  "dr_residencial",
  "dr_actividad",
  "lu_residencial",
  "lu_actividad",
  "funcionamiento_residencial",
  "funcionamiento_actividad",
  "comunicacion_previa",
  "primera_ocupacion",
  "obra_local_vivienda",
  "obra_edificio",
  "otra",
];
