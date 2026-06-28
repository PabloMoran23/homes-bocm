export const CM_PORTAL_PROYECTOS_URL = "/data/cm-portal-proyectos.geojson";
export const CM_PORTAL_PROYECTOS_POLIGONOS_URL = "/data/cm-portal-proyectos-poligonos.geojson";
export const CM_PORTAL_LICENCIAS_URL = "/data/cm-portal-licencias.geojson";
export const CM_PORTAL_META_URL = "/data/cm-portal-meta.json";

export type CmPortalMapMeta = {
  generatedAt?: string;
  proyectosTotal?: number;
  proyectosEnMapa?: number;
  proyectosPoligonos?: number;
  proyectosPuntosReales?: number;
  proyectosSinUbicacion?: number;
  licenciasEnMapa?: number;
};

export type CmPortalProyectoProps = {
  id: string;
  municipio: string;
  titulo: string;
  fecha?: string;
  tipo?: string;
  url?: string;
  coordSource?: string;
  sectorKey?: string;
  catalogSource?: string;
};

export type CmPortalLicenciaProps = {
  id: string;
  municipio: string;
  titulo: string;
  fecha?: string;
  tipo?: string;
  distrito?: string;
  catalogSource?: string;
};

export type CmPortalGeoJson<P> = {
  type: "FeatureCollection";
  generatedAt?: string;
  features: Array<{
    type: "Feature";
    geometry:
      | { type: "Point"; coordinates: [number, number] }
      | { type: "Polygon"; coordinates: number[][][] }
      | { type: "MultiPolygon"; coordinates: number[][][][] };
    properties: P;
  }>;
};

export function portalProyectoPopupHtml(p: CmPortalProyectoProps): string {
  const title = p.titulo || p.id;
  const meta = [p.municipio, p.fecha, p.tipo].filter(Boolean).join(" · ");
  const link = p.id
    ? `<a href="/proyecto/${encodeURIComponent(p.id)}" class="font-semibold text-[var(--portal-accent)] hover:underline">Ver ficha</a>`
    : "";
  const ext = p.url
    ? ` · <a href="${p.url}" target="_blank" rel="noopener noreferrer" class="text-slate-600 hover:underline">Portal</a>`
    : "";
  return `<div class="text-sm leading-snug"><div class="font-semibold text-slate-900">${escapeHtml(title)}</div>${meta ? `<div class="mt-1 text-slate-600">${escapeHtml(meta)}</div>` : ""}<div class="mt-2">${link}${ext}</div></div>`;
}

export function portalLicenciaPopupHtml(p: CmPortalLicenciaProps): string {
  const title = p.titulo || p.id;
  const meta = [p.municipio, p.fecha, p.tipo, p.distrito].filter(Boolean).join(" · ");
  return `<div class="text-sm leading-snug"><div class="font-semibold text-slate-900">${escapeHtml(title)}</div>${meta ? `<div class="mt-1 text-slate-600">${escapeHtml(meta)}</div>` : ""}</div>`;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
