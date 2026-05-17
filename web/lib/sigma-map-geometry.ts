import type { SectorFeatureCollection } from "./sector-geo";

/**
 * Área aproximada del rectángulo envolvente en km² (WGS84, lat media para cos φ).
 * Suficiente para separar polígonos locales de ámbitos que cubren todo el municipio (~600 km²
 * o fichas que reutilizan el mismo perímetro grande).
 */
export const SIGMA_MAP_DEFAULT_MAX_BBOX_KM2 = 15;

type GeomLike = { type?: string; coordinates?: unknown } | null | undefined;

function accumulateBounds(coords: unknown, depth: number, b: Bounds): void {
  if (!coords || depth > 14) return;
  if (
    typeof coords === "object" &&
    coords !== null &&
    Array.isArray(coords) &&
    coords.length >= 2 &&
    typeof coords[0] === "number" &&
    typeof (coords as number[])[1] === "number"
  ) {
    const lng = coords[0] as number;
    const lat = (coords as number[])[1] as number;
    b.minLat = Math.min(b.minLat, lat);
    b.maxLat = Math.max(b.maxLat, lat);
    b.minLng = Math.min(b.minLng, lng);
    b.maxLng = Math.max(b.maxLng, lng);
    return;
  }
  if (Array.isArray(coords)) {
    for (const c of coords) accumulateBounds(c, depth + 1, b);
  }
}

type Bounds = { minLat: number; maxLat: number; minLng: number; maxLng: number };

/** null si geometría desconocida o vacía → no filtramos. */
export function approximateBBoxAreaKm2(geometry: GeomLike): number | null {
  if (!geometry?.type || geometry.type === "GeometryCollection") return null;
  const t = geometry.type;
  if (t !== "Polygon" && t !== "MultiPolygon") return null;

  const b: Bounds = { minLat: 90, maxLat: -90, minLng: 180, maxLng: -180 };
  accumulateBounds(geometry.coordinates, 0, b);
  if (b.minLat >= b.maxLat || b.minLng >= b.maxLng) return null;

  const latSpan = b.maxLat - b.minLat;
  const lngSpan = b.maxLng - b.minLng;
  const avgLatRad = ((b.minLat + b.maxLat) / 2) * (Math.PI / 180);
  return latSpan * 111 * lngSpan * 111 * Math.cos(avgLatRad);
}

/** Filtra polígonos cuyo bbox supera maxKm²; útil si no hay nueva dependencia (turf). */
export function filterSigmaMapFeaturesByBBox(
  fc: SectorFeatureCollection,
  maxKm2: number,
): { visible: SectorFeatureCollection; excluded: number } {
  const features: SectorFeatureCollection["features"] = [];
  let excluded = 0;

  for (const f of fc.features || []) {
    const geom = f.geometry as GeomLike;
    const km2 = approximateBBoxAreaKm2(geom);
    if (km2 != null && km2 > maxKm2) {
      excluded += 1;
      continue;
    }
    features.push(f);
  }

  return { visible: { type: "FeatureCollection", features }, excluded };
}
