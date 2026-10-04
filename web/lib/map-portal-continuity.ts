import type { CmPortalGeoJson, CmPortalProyectoProps } from "@/lib/cm-portal-geo";
import { featureCollectionBounds } from "@/lib/cm-portal-geo";
import type { MapBounds } from "@/lib/map-viewport";

type Collection = CmPortalGeoJson<CmPortalProyectoProps>;
export type PortalSeen = { points: Collection; polygons: Collection; approx?: Collection; updatedAt: number };
export const PORTAL_SEEN_LIMIT = 1000;
export function portalZoomLevel(zoom: number | undefined) { return Math.round(zoom ?? 13); }

/** Fresh geometry wins; a project can never be both a point and a polygon. */
export function rememberPortalProjects(previous: PortalSeen | undefined, incoming: { points?: Collection; polygons?: Collection; approx?: Collection }, now = Date.now()): PortalSeen {
  const features = new Map<string, Collection["features"][number]>();
  for (const f of [...(previous?.points.features ?? []), ...(previous?.polygons.features ?? []), ...(incoming.points?.features ?? []), ...(incoming.polygons?.features ?? [])]) {
    features.delete(f.properties.id);
    features.set(f.properties.id, f);
  }
  const bounded = [...features.values()].slice(-PORTAL_SEEN_LIMIT);
  const approximate = new Map<string, Collection["features"][number]>();
  for (const f of [...(previous?.approx?.features ?? []), ...(incoming.approx?.features ?? [])]) if (!features.has(f.properties.id)) approximate.set(f.properties.id, f);
  return {
    points: { type: "FeatureCollection", features: bounded.filter(f => f.geometry.type === "Point") },
    polygons: { type: "FeatureCollection", features: bounded.filter(f => f.geometry.type !== "Point") },
    approx: { type: "FeatureCollection", features: [...approximate.values()].slice(-100) },
    updatedAt: now,
  };
}

export function portalSeenInView(seen: PortalSeen | undefined, bounds: MapBounds | null): { points: Collection | null; polygons: Collection | null } {
  if (!seen || !bounds) return { points: null, polygons: null };
  const visible = (f: Collection["features"][number]) => {
    if (f.geometry.type === "Point") {
      const [lng, lat] = f.geometry.coordinates;
      return lng >= bounds.west && lng <= bounds.east && lat >= bounds.south && lat <= bounds.north;
    }
    const b = featureCollectionBounds({ features: [f] });
    return b && b.west <= bounds.east && b.east >= bounds.west && b.south <= bounds.north && b.north >= bounds.south;
  };
  return {
    points: { ...seen.points, features: seen.points.features.filter(visible) },
    polygons: { ...seen.polygons, features: seen.polygons.features.filter(visible) },
  };
}
