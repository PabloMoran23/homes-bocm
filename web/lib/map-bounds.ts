import L from "leaflet";
import type { SectorFeatureCollection } from "./sector-geo";

export function collectMapBounds(
  points: { lat: number; lng: number }[],
  sectorGeoJson?: SectorFeatureCollection | null,
): L.LatLngBounds | null {
  let bounds: L.LatLngBounds | null = null;

  if (sectorGeoJson?.features?.length) {
    const layer = L.geoJSON(sectorGeoJson as never);
    const sectorBounds = layer.getBounds();
    layer.remove();
    if (sectorBounds.isValid()) bounds = sectorBounds;
  }

  for (const p of points) {
    const ll = L.latLng(p.lat, p.lng);
    bounds = bounds ? bounds.extend(ll) : L.latLngBounds([ll, ll]);
  }

  return bounds?.isValid() ? bounds : null;
}
