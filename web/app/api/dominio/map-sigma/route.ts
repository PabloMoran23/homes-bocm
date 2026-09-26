import { dominioError, dominioJson, rpcDominio } from "@/lib/dominio-cache";
import { MADRID_CITY_BBOX, quantizeBounds, sigmaPolygonLimit } from "@/lib/map-live-urls";
import type { SectorFeatureCollection } from "@/lib/sector-geo";

export const revalidate = 900;
export const maxDuration = 12;

function num(v: string | null): number | null {
  if (v == null || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const layer = (url.searchParams.get("layer") || "ambitos").trim();
  const zoom = Math.round(num(url.searchParams.get("zoom")) ?? 11);
  const limit = Math.min(
    sigmaPolygonLimit(zoom),
    Math.round(num(url.searchParams.get("limit")) ?? sigmaPolygonLimit(zoom)),
  );
  const rawWest = num(url.searchParams.get("west"));
  const rawSouth = num(url.searchParams.get("south"));
  const rawEast = num(url.searchParams.get("east"));
  const rawNorth = num(url.searchParams.get("north"));
  const box = quantizeBounds(
    rawWest != null && rawSouth != null && rawEast != null && rawNorth != null
      ? { west: rawWest, south: rawSouth, east: rawEast, north: rawNorth, zoom }
      : { ...MADRID_CITY_BBOX, zoom },
    zoom,
  );

  const { data, error, missing } = await rpcDominio<SectorFeatureCollection>("map_sigma_geojson", {
    p_zoom: zoom,
    p_min_lng: box.west,
    p_min_lat: box.south,
    p_max_lng: box.east,
    p_max_lat: box.north,
    p_layer: layer,
    p_limit: limit,
  });

  if (missing) return dominioError(error || "Supabase no configurado", 503);
  if (error) return dominioError(error, 500);
  if (!data || data.type !== "FeatureCollection") {
    return dominioError("Respuesta de mapa vacía", 500);
  }
  return dominioJson(data);
}
