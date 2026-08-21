import type { MapBounds } from "@/lib/map-viewport";

export const MAP_SIGMA_API = "/api/dominio/map-sigma";
export const MAP_CM_PORTAL_API = "/api/dominio/map-cm-portal";
export const MAP_UBICACIONES_API = "/api/dominio/map-ubicaciones";
export const SEARCH_UBICACIONES_API = "/api/dominio/search-ubicaciones";
export const SIGMA_METRICS_API = "/api/dominio/madrid-sigma-metrics";
export const SIGMA_MAP_CARDS_API = "/api/dominio/madrid-sigma-map-cards";

export const SIGMA_LAYER_STATIC: Record<string, string> = {
  ambitos: "/data/madrid-sigma-ambitos.geojson",
  ip: "/data/madrid-sigma-ip.geojson",
  ad: "/data/madrid-sigma-ad.geojson",
  gestion: "/data/madrid-sigma-gestion.geojson",
  urbanizacion: "/data/madrid-sigma-urbanizacion.geojson",
  landing: "/data/madrid-sigma-ambitos-landing.geojson",
};

/** Recorte ciudad (explorar). Alineado con MadridUnifiedMap. */
export const MADRID_CITY_BBOX: MapBounds = {
  west: -3.888,
  south: 40.348,
  east: -3.518,
  north: 40.502,
};

/** Recorte portada. Alineado con MADRID_PREVIEW_BOUNDS. */
export const MADRID_PREVIEW_BBOX: MapBounds = {
  west: -3.72,
  south: 40.402,
  east: -3.68,
  north: 40.448,
};

/** Zoom de ciudad: pocos polígonos grandes. Coincide con homes.map_sigma_geojson. */
export function sigmaPolygonLimit(zoom: number | undefined): number {
  const z = Math.round(zoom ?? 11);
  if (z <= 9) return 40;
  if (z <= 11) return 80;
  if (z <= 12) return 120;
  if (z <= 14) return 180;
  return 220;
}

export function ubicacionesPointLimit(zoom: number | undefined): number {
  const z = Math.round(zoom ?? 11);
  if (z <= 11) return 600;
  if (z <= 13) return 1200;
  return 2000;
}

export function shouldLoadSigmaPolygons(
  zoom: number | undefined,
  bounds: MapBounds | null,
): boolean {
  return Boolean(bounds) && Math.round(zoom ?? bounds?.zoom ?? 11) >= 8;
}

function quantizeStep(zoom: number): number {
  if (zoom >= 14) return 0.003;
  if (zoom >= 12) return 0.008;
  return 0.02;
}

/** Redondea el recorte para reutilizar cache CDN / RPC. */
export function quantizeBounds(bounds: MapBounds, zoom?: number): MapBounds {
  const z = Math.round(zoom ?? bounds.zoom ?? 11);
  const step = quantizeStep(z);
  const q = (n: number) => Math.round(n / step) * step;
  return {
    west: q(bounds.west),
    south: q(bounds.south),
    east: q(bounds.east),
    north: q(bounds.north),
    zoom: bounds.zoom ?? z,
  };
}

export function mapSigmaQuery(opts: {
  layer: string;
  zoom?: number;
  bounds?: MapBounds | null;
  limit?: number;
}): string {
  const params = new URLSearchParams();
  params.set("layer", opts.layer);
  const zoom = Math.round(opts.zoom ?? opts.bounds?.zoom ?? 11);
  const bounds = opts.bounds ? quantizeBounds(opts.bounds, zoom) : null;
  params.set("zoom", String(zoom));
  params.set("limit", String(opts.limit ?? sigmaPolygonLimit(zoom)));
  if (bounds) {
    params.set("west", String(bounds.west));
    params.set("south", String(bounds.south));
    params.set("east", String(bounds.east));
    params.set("north", String(bounds.north));
  }
  return `${MAP_SIGMA_API}?${params.toString()}`;
}

export function mapUbicacionesQuery(bounds: MapBounds, limit?: number): string {
  const zoom = Math.round(bounds.zoom ?? 11);
  const q = quantizeBounds(bounds, zoom);
  const params = new URLSearchParams({
    west: String(q.west),
    south: String(q.south),
    east: String(q.east),
    north: String(q.north),
    zoom: String(zoom),
    limit: String(limit ?? ubicacionesPointLimit(zoom)),
  });
  return `${MAP_UBICACIONES_API}?${params.toString()}`;
}

export function bboxFetchKey(bounds: MapBounds | null, zoom: number | undefined, layer: string): string {
  const z = Math.round(zoom ?? bounds?.zoom ?? 11);
  const n = sigmaPolygonLimit(z);
  if (!bounds) return `${layer}:z${z}:n${n}`;
  const q = quantizeBounds(bounds, z);
  return [layer, z, n, q.west, q.south, q.east, q.north].join(":");
}
