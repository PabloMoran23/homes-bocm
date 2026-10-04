import type { Geometry } from "geojson";
import { featureCollectionBounds } from "@/lib/cm-portal-geo";
import type { CmPortalGeoJson, CmPortalProyectoProps, CmPortalHintProps } from "@/lib/cm-portal-geo";
import type { MapBounds } from "@/lib/map-viewport";
import { projectIconAnchor } from "@/lib/map-raised-project-icon";

export type MunicipalityGeometry = Extract<Geometry, { type: "Polygon" | "MultiPolygon" }>;
function random(seed: string) {
  let hash = 2166136261;
  for (const character of seed) { hash ^= character.charCodeAt(0); hash = Math.imul(hash, 16777619); }
  return (hash >>> 0) / 4294967296;
}
function insideRing(point: [number, number], ring: number[][]) {
  const [x, y] = point;
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [ax, ay] = ring[i], [bx, by] = ring[j];
    if ((ay > y) !== (by > y) && x < (bx - ax) * (y - ay) / (by - ay) + ax) inside = !inside;
  }
  return inside;
}
export function insideMunicipality(point: [number, number], geometry: MunicipalityGeometry) {
  const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
  return polygons.some(rings => insideRing(point, rings[0]) && !rings.slice(1).some(ring => insideRing(point, ring)));
}

/** Stable illustrative points, never outside the actual municipal boundary or in holes. */
export function scatterApproximateProjects(collection: CmPortalGeoJson<CmPortalProyectoProps> | null, geometry: MunicipalityGeometry | null, center: [number, number]): CmPortalGeoJson<CmPortalProyectoProps> | null {
  if (!collection || !geometry) return null;
  const origin = insideMunicipality(center, geometry) ? center : projectIconAnchor(geometry);
  if (!origin || !insideMunicipality(origin, geometry)) return null;
  const latitudeScale = Math.max(.2, Math.cos(origin[1] * Math.PI / 180));
  const extent = featureCollectionBounds({ features: [{ geometry }] });
  const spread = extent ? Math.min(.008, (extent.east - extent.west) * latitudeScale * .35, (extent.north - extent.south) * .35) : .001;
  return { ...collection, features: collection.features.map(feature => {
    let coordinates = origin;
    for (let attempt = 0; attempt < 100; attempt++) {
      const key = `${feature.properties.id}:${attempt}`;
      const angle = random(`${key}:angle`) * Math.PI * 2;
      const radius = Math.sqrt(random(`${key}:radius`)) * spread * (attempt < 75 ? 1 : .25);
      const candidate: [number, number] = [origin[0] + Math.cos(angle) * radius / latitudeScale, origin[1] + Math.sin(angle) * radius];
      if (insideMunicipality(candidate, geometry)) { coordinates = candidate; break; }
    }
    return { ...feature, geometry: { type: "Point" as const, coordinates }, properties: { ...feature.properties, approx: true } };
  }) };
}

/** A few stable random navigation cues in areas without displayed project polygons. */
export function uncoveredExplorationHints(bounds: MapBounds, features: CmPortalGeoJson<CmPortalProyectoProps>["features"], geometry: MunicipalityGeometry | null): CmPortalGeoJson<CmPortalHintProps> {
  const polygons = features.flatMap(f => f.geometry.type === "Polygon" || f.geometry.type === "MultiPolygon" ? [f.geometry] : []);
  const dx = Math.max(.0001, 2 ** Math.round(Math.log2((bounds.east - bounds.west) / 5)));
  const dy = Math.max(.0001, 2 ** Math.round(Math.log2((bounds.north - bounds.south) / 4)));
  const candidates: Array<{ score: number; point: [number, number]; x: number; y: number }> = [];
  for (let x = Math.floor(bounds.west / dx); x <= Math.floor(bounds.east / dx); x++) {
    for (let y = Math.floor(bounds.south / dy); y <= Math.floor(bounds.north / dy); y++) {
      const key = `${dx}:${dy}:${x}:${y}`;
      const point: [number, number] = [(x + .2 + .6 * random(`${key}:x`)) * dx, (y + .2 + .6 * random(`${key}:y`)) * dy];
      if (point[0] < bounds.west || point[0] > bounds.east || point[1] < bounds.south || point[1] > bounds.north || (geometry && !insideMunicipality(point, geometry))) continue;
      if (polygons.some(polygon => insideMunicipality(point, polygon))) continue;
      candidates.push({ score: random(key), point, x, y });
    }
  }
  return { type: "FeatureCollection", features: candidates.sort((a, b) => a.score - b.score).slice(0, 6).map(({ point, x, y }) => ({ type: "Feature", geometry: { type: "Point", coordinates: point }, properties: { west: x * dx, east: (x + 1) * dx, south: y * dy, north: (y + 1) * dy } })) };
}
