import { fetchStaticJson } from "@/lib/fetch-static-json";
import type { LandingMapSpotlightFile } from "@/lib/landing-map-spotlight";
import type { SectorFeatureCollection } from "@/lib/sector-geo";

export async function loadLandingMapSpotlight(): Promise<LandingMapSpotlightFile | null> {
  const data = await fetchStaticJson<LandingMapSpotlightFile>("/data/landing-map-spotlight.json");
  if (!data?.items?.length) return null;
  return data;
}

export async function loadLandingMapSpotlightGeo(): Promise<SectorFeatureCollection | null> {
  const fc = await fetchStaticJson<SectorFeatureCollection>("/data/landing-map-spotlight.geojson");
  if (!fc?.features?.length) return null;
  return fc;
}
