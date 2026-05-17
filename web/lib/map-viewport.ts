import type { LatLngBounds } from "leaflet";
import type { SectorFeatureCollection } from "@/lib/sector-geo";
import { approximateBBoxAreaKm2 } from "@/lib/sigma-map-geometry";

export type MapBounds = {
  south: number;
  west: number;
  north: number;
  east: number;
};

export const VIEWPORT_PAD = 0.08;
export const MAX_POINTS_IN_VIEW = 2500;
export const MAX_POLYGONS_IN_VIEW = 400;

export function boundsFromLeaflet(b: LatLngBounds, padRatio = VIEWPORT_PAD): MapBounds {
  const padded = b.pad(padRatio);
  const sw = padded.getSouthWest();
  const ne = padded.getNorthEast();
  return { south: sw.lat, west: sw.lng, north: ne.lat, east: ne.lng };
}

export function pointInBounds(lng: number, lat: number, box: MapBounds): boolean {
  return lat >= box.south && lat <= box.north && lng >= box.west && lng <= box.east;
}

function geomBbox(geometry: { type?: string; coordinates?: unknown }): MapBounds | null {
  const km2 = approximateBBoxAreaKm2(geometry);
  if (km2 == null) return null;
  const b = { minLat: 90, maxLat: -90, minLng: 180, maxLng: -180 };
  const acc = (coords: unknown, depth: number) => {
    if (!coords || depth > 14) return;
    if (
      Array.isArray(coords) &&
      coords.length >= 2 &&
      typeof coords[0] === "number" &&
      typeof coords[1] === "number"
    ) {
      const lng = coords[0];
      const lat = coords[1];
      b.minLat = Math.min(b.minLat, lat);
      b.maxLat = Math.max(b.maxLat, lat);
      b.minLng = Math.min(b.minLng, lng);
      b.maxLng = Math.max(b.maxLng, lng);
      return;
    }
    if (Array.isArray(coords)) for (const c of coords) acc(c, depth + 1);
  };
  acc(geometry.coordinates, 0);
  if (b.minLat >= b.maxLat) return null;
  return { south: b.minLat, west: b.minLng, north: b.maxLat, east: b.maxLng };
}

function bboxIntersects(a: MapBounds, b: MapBounds): boolean {
  return !(a.east < b.west || a.west > b.east || a.north < b.south || a.south > b.north);
}

function subsample<T>(items: T[], max: number): T[] {
  if (items.length <= max) return items;
  const step = Math.ceil(items.length / max);
  return items.filter((_, i) => i % step === 0);
}

export function filterPointFeaturesInView<
  T extends { geometry: { coordinates: [number, number] } },
>(features: T[], box: MapBounds | null, max = MAX_POINTS_IN_VIEW): T[] {
  if (!box || !boundsLookValid(box)) return subsample(features, max);
  const inView = features.filter((f) => {
    const [lng, lat] = f.geometry.coordinates;
    return pointInBounds(lng, lat, box);
  });
  if (inView.length === 0 && features.length > 0) {
    return subsample(features, max);
  }
  return subsample(inView, max);
}

/** Evita filtrar con bounds degenerados (mapa aún sin tamaño real). */
function boundsLookValid(box: MapBounds): boolean {
  const latSpan = box.north - box.south;
  const lngSpan = box.east - box.west;
  return latSpan > 0.002 && lngSpan > 0.002;
}

export function filterPolygonFeaturesInView(
  fc: SectorFeatureCollection,
  box: MapBounds | null,
  max = MAX_POLYGONS_IN_VIEW,
): SectorFeatureCollection {
  const features = fc.features || [];
  if (!box || !boundsLookValid(box)) {
    return { type: "FeatureCollection", features: subsample(features, max) };
  }
  const inView = features.filter((f) => {
    const geom = f.geometry as { type?: string; coordinates?: unknown } | undefined;
    if (!geom?.type) return false;
    const fb = geomBbox(geom);
    if (!fb) return true;
    if (geom.type === "Point") {
      return pointInBounds(fb.west, fb.south, box);
    }
    return bboxIntersects(fb, box);
  });
  if (inView.length === 0 && features.length > 0) {
    return { type: "FeatureCollection", features: subsample(features, max) };
  }
  return { type: "FeatureCollection", features: subsample(inView, max) };
}
