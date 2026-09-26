export const CM_PORTAL_PROYECTOS_URL = "/data/cm-portal-proyectos.geojson";
export const CM_PORTAL_PROYECTOS_POLIGONOS_URL = "/data/cm-portal-proyectos-poligonos.geojson";
export const CM_PORTAL_LICENCIAS_URL = "/data/cm-portal-licencias.geojson";
export const CM_PORTAL_META_URL = "/data/cm-portal-meta.json";

export type CmPortalMapMeta = {
  generatedAt?: string;
  municipio?: string;
  from?: string;
  to?: string;
  proyectosTotal?: number;
  proyectosEnRango?: number;
  proyectosEnMapa?: number;
  proyectosPoligonos?: number;
  proyectosPuntosReales?: number;
  proyectosAprox?: number;
  proyectosAproxTotal?: number;
  centerLng?: number | null;
  centerLat?: number | null;
  proyectosSinUbicacion?: number;
  proyectosSinFecha?: number;
  truncated?: boolean;
  recorteEnVista?: boolean;
  limiteMapa?: number;
  licenciasEnMapa?: number;
};

export type CmMunicipioOption = {
  slug: string;
  nombre: string;
  n: number;
  west: number | null;
  south: number | null;
  east: number | null;
  north: number | null;
};

export type CmPortalProyectoProps = {
  id: string;
  municipio: string;
  titulo: string;
  /** Nombre que entiende la gente, si hay ficha de investigación. */
  nombrePopular?: string | null;
  /** Tiene ficha de investigación: se dibuja encima y con ese nombre. */
  investigado?: boolean;
  fecha?: string;
  tipo?: string;
  url?: string;
  coordSource?: string;
  sectorKey?: string;
  catalogSource?: string;
  /** Sin parcela real: la bandera sale del centro del municipio. */
  approx?: boolean;
  /** Por qué no se dibuja: sin coordenada, o polígono que tapa el municipio. */
  fueraDeMapa?: "sin_coordenada" | "extension";
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

/** Recuadro en grados de una colección, ignorando coordenadas que no son lat/lng. */
export function featureCollectionBounds(
  geo: { features: Array<{ geometry?: { coordinates?: unknown } | null }> } | null,
): { west: number; south: number; east: number; north: number } | null {
  let west = Infinity;
  let south = Infinity;
  let east = -Infinity;
  let north = -Infinity;
  const walk = (node: unknown) => {
    if (!Array.isArray(node) || node.length === 0) return;
    if (typeof node[0] === "number" && typeof node[1] === "number") {
      const lng = node[0];
      const lat = node[1];
      if (lng < -180 || lng > 180 || lat < -90 || lat > 90) return;
      west = Math.min(west, lng);
      east = Math.max(east, lng);
      south = Math.min(south, lat);
      north = Math.max(north, lat);
      return;
    }
    for (const child of node) walk(child);
  };
  for (const feature of geo?.features ?? []) walk(feature.geometry?.coordinates);
  if (!Number.isFinite(west) || east <= west || north <= south) return null;
  return { west, south, east, north };
}

export function portalProyectoLabel(p: CmPortalProyectoProps): string {
  const popular = p.nombrePopular?.trim();
  if (popular) return popular;
  return p.titulo || p.id;
}

export function portalProyectoPopupHtml(p: CmPortalProyectoProps): string {
  const title = portalProyectoLabel(p);
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
