import type { Geometry } from "geojson";
import { geometrySurfaceM2, geometryExtentM2 } from "@/lib/area-context";

/** Large municipal regulations remain in the catalogue, without map outlines or pins. */
export function hasBroadMapExtent(value: unknown): boolean {
  if (!value || typeof value !== "object") return false;
  const geometry = value as Geometry;
  if (!geometry || (geometry.type !== "Polygon" && geometry.type !== "MultiPolygon")) return false;
  if (!Array.isArray(geometry.coordinates)) return false;
  const first = geometry.type === "Polygon" ? geometry.coordinates[0]?.[0] : geometry.coordinates[0]?.[0]?.[0];
  if (!first || !Number.isFinite(first[1])) return false;
  return geometrySurfaceM2(geometry, first[1]) > 15_000_000 || geometryExtentM2(geometry, first[1]) > 25_000_000;
}
