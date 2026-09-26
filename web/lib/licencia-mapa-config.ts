import type { LicenciaMapaCategoria } from "@/lib/licencia-tipos";

export type LicenciaMapaCategoriaConfig = {
  label: string;
  bg: string;
  ring: string;
  svg: string;
};

const ICONS = {
  casa: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4.2 11.4 12 4.6l7.8 6.8"/><path d="M6.4 10.6V19.6h11.2V10.6"/><path d="M10.2 19.6v-5.1h3.6v5.1"/></svg>`,
  local: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4.4 10.4h15.2V19.8H4.4z"/><path d="M4.2 10.4 12 5.6l7.8 4.8"/><path d="M10.4 19.8v-5h3.2v5"/></svg>`,
  obra: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="5.2" y="3.8" width="13.6" height="16.4" rx="0.4"/><path d="M8 8h1.4M12 8h1.4M16 8h1.4M8 12h1.4M12 12h1.4M16 12h1.4"/><path d="M10.6 20.2v-3h2.8v3"/></svg>`,
  doc: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M5.2 6.4 12 3.8l6.8 2.6v10.8L12 20.2 5.2 17.4z"/><path d="M12 3.8v16.4"/><path d="M8.2 8.8h2.8M13.6 10.4h2.4"/></svg>`,
  aviso: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4.2 20.4 19H3.6z"/><path d="M12 10v4.2M12 16.8h.01"/></svg>`,
  llave: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="8.4" cy="14.2" r="3.2"/><path d="M11.2 12.6 19.4 4.4M16.6 4.4h2.8v2.8"/></svg>`,
  uso: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="7.2"/><path d="M12 4.8v14.4M4.8 12h14.4"/></svg>`,
  punto: `<svg width="10" height="10" viewBox="0 0 24 24" fill="#fff"><circle cx="12" cy="12" r="5"/></svg>`,
} as const;

export const LICENCIA_MAPA_CONFIG: Record<LicenciaMapaCategoria, LicenciaMapaCategoriaConfig> = {
  dr_residencial: {
    label: "Obras menores en vivienda",
    bg: "#6b8f54",
    ring: "#4d6a3c",
    svg: ICONS.casa,
  },
  dr_actividad: {
    label: "Apertura o cambio en local",
    bg: "#c07f6c",
    ring: "#8f5748",
    svg: ICONS.local,
  },
  dr_otra: {
    label: "Trámite rápido de obra o actividad",
    bg: "#c4853a",
    ring: "#8a5a1e",
    svg: ICONS.doc,
  },
  lu_residencial: {
    label: "Obras con licencia en vivienda",
    bg: "#1f4f53",
    ring: "#16383b",
    svg: ICONS.obra,
  },
  lu_actividad: {
    label: "Obras o actividad en local",
    bg: "#9a5c48",
    ring: "#6b3f32",
    svg: ICONS.local,
  },
  lu_otra: {
    label: "Obra o actuación autorizada",
    bg: "#4a7578",
    ring: "#2f4e51",
    svg: ICONS.obra,
  },
  funcionamiento_residencial: {
    label: "Vivienda autorizada para uso",
    bg: "#5f7a4a",
    ring: "#3f5232",
    svg: ICONS.uso,
  },
  funcionamiento_actividad: {
    label: "Local autorizado para abrir",
    bg: "#b86f5e",
    ring: "#8a4d40",
    svg: ICONS.local,
  },
  comunicacion_previa: {
    label: "Obra comunicada al Ayuntamiento",
    bg: "#7a5c58",
    ring: "#5a403c",
    svg: ICONS.aviso,
  },
  primera_ocupacion: {
    label: "Edificio listo para ocupar",
    bg: "#7e9a62",
    ring: "#5a7044",
    svg: ICONS.llave,
  },
  obra_local_vivienda: {
    label: "Local convertido en vivienda",
    bg: "#a67c3a",
    ring: "#7a5a28",
    svg: ICONS.casa,
  },
  obra_edificio: {
    label: "Obra en el edificio",
    bg: "#4a5556",
    ring: "#2f3a3b",
    svg: ICONS.obra,
  },
  consulta: {
    label: "Consulta o parcelación",
    bg: "#5a5850",
    ring: "#3d3b36",
    svg: ICONS.doc,
  },
  otra: {
    label: "Otros trámites",
    bg: "#7a7268",
    ring: "#5a544c",
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
