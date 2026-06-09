import { fetchStaticJson } from "@/lib/fetch-static-json";
import type { SectorFeatureCollection } from "@/lib/sector-geo";

/** GeoJSON simplificado del mapa de inicio (servido en build, sin fetch en cliente). */
export async function loadSigmaAmbitosLandingGeo(): Promise<SectorFeatureCollection | null> {
  const fc = await fetchStaticJson<SectorFeatureCollection>(
    "/data/madrid-sigma-ambitos-landing.geojson",
  );
  if (!fc?.features?.length) return null;
  return fc;
}
