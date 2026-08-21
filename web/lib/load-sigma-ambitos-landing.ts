import { rpcDominio } from "@/lib/dominio-cache";
import { fetchStaticJson } from "@/lib/fetch-static-json";
import { MADRID_PREVIEW_BBOX, sigmaPolygonLimit } from "@/lib/map-live-urls";
import { approximateBBoxAreaKm2 } from "@/lib/sigma-map-geometry";
import type { SectorFeatureCollection } from "@/lib/sector-geo";

const LANDING_LIMIT = sigmaPolygonLimit(12);

function topFeaturesByArea(
  fc: SectorFeatureCollection,
  limit: number,
): SectorFeatureCollection {
  const scored = (fc.features || []).map((feature) => ({
    feature,
    area: approximateBBoxAreaKm2(feature.geometry as { type?: string; coordinates?: unknown }) ?? 0,
  }));
  scored.sort((a, b) => b.area - a.area);
  return {
    type: "FeatureCollection",
    features: scored.slice(0, limit).map((row) => row.feature),
  };
}

/** Mapa de inicio: snapshot local recortado; RPC solo si no hay fichero. */
export async function loadSigmaAmbitosLandingGeo(): Promise<SectorFeatureCollection | null> {
  const staticFc = await fetchStaticJson<SectorFeatureCollection>(
    "/data/madrid-sigma-ambitos-landing.geojson",
  );
  if (staticFc?.features?.length) {
    return topFeaturesByArea(staticFc, LANDING_LIMIT);
  }

  const { data } = await rpcDominio<SectorFeatureCollection>("map_sigma_geojson", {
    p_zoom: 12,
    p_min_lng: MADRID_PREVIEW_BBOX.west,
    p_min_lat: MADRID_PREVIEW_BBOX.south,
    p_max_lng: MADRID_PREVIEW_BBOX.east,
    p_max_lat: MADRID_PREVIEW_BBOX.north,
    p_layer: "landing",
    p_limit: LANDING_LIMIT,
  });
  if (data?.features?.length) return data;
  return null;
}
