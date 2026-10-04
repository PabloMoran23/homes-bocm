import { featureCollectionBounds } from "@/lib/cm-portal-geo";
import type { MapBounds } from "@/lib/map-viewport";

export const PORTAL_INITIAL_MAX_ZOOM = 18;
type Frame = Pick<MapBounds, "west" | "south" | "east" | "north">;

/** Fit the loaded polygon footprint, with points and the municipality as fallbacks. */
export function portalInitialFrame(
  fallback: Frame,
  polygons?: Parameters<typeof featureCollectionBounds>[0],
  points?: Parameters<typeof featureCollectionBounds>[0],
): Frame {
  const frame = featureCollectionBounds(polygons ?? null) ?? featureCollectionBounds(points ?? null) ?? fallback;
  if (frame.east - frame.west >= 0.0002 && frame.north - frame.south >= 0.0002) return frame;
  const lng = (frame.west + frame.east) / 2;
  const lat = (frame.south + frame.north) / 2;
  const dx = Math.max(frame.east - frame.west, 0.0002) / 2;
  const dy = Math.max(frame.north - frame.south, 0.0002) / 2;
  return { west: lng - dx, east: lng + dx, south: lat - dy, north: lat + dy };
}


/** Fixed density-based camera, independent from returned projects and dates. */
export function portalDensityCamera(municipality: {
  n: number; west: number | null; east: number | null; south: number | null; north: number | null;
  centerLng?: number | null; centerLat?: number | null;
}) {
  const lng = municipality.centerLng ?? ((municipality.west ?? -3.71) + (municipality.east ?? -3.69)) / 2;
  const lat = municipality.centerLat ?? ((municipality.south ?? 40.39) + (municipality.north ?? 40.41)) / 2;
  const widthKm = Math.max(.5, ((municipality.east ?? lng + .01) - (municipality.west ?? lng - .01)) * 111.32 * Math.cos(lat * Math.PI / 180));
  const heightKm = Math.max(.5, ((municipality.north ?? lat + .01) - (municipality.south ?? lat - .01)) * 111.32);
  const areaKm2 = widthKm * heightKm;
  const density = Math.max(1, municipality.n) / areaKm2;
  const targetAreaKm2 = Math.min(areaKm2, 80 / density);
  const zoom = Math.min(15.5, Math.max(10, 14 + .5 * Math.log2(25 / Math.max(.25, targetAreaKm2))));
  const side = Math.sqrt(Math.max(.25, targetAreaKm2));
  const dx = side / (111.32 * Math.cos(lat * Math.PI / 180)) / 2;
  const dy = side / 111.32 / 2;
  return { west: lng - dx, east: lng + dx, south: lat - dy, north: lat + dy, zoom };
}
