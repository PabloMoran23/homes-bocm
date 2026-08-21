import { dominioError, dominioJson, rpcDominio } from "@/lib/dominio-cache";
import { quantizeBounds, ubicacionesPointLimit } from "@/lib/map-live-urls";
import type { UbicacionesMapGeoJson } from "@/lib/madrid-ubicaciones-map";

export const revalidate = 300;
export const maxDuration = 12;

function num(v: string | null): number | null {
  if (v == null || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const west = num(url.searchParams.get("west"));
  const south = num(url.searchParams.get("south"));
  const east = num(url.searchParams.get("east"));
  const north = num(url.searchParams.get("north"));
  if (west == null || south == null || east == null || north == null) {
    return dominioError("Indica west, south, east y north", 400);
  }

  const zoom = Math.round(num(url.searchParams.get("zoom")) ?? 11);
  const box = quantizeBounds({ west, south, east, north, zoom }, zoom);
  const cap = ubicacionesPointLimit(zoom);
  const limit = Math.min(cap, Math.round(num(url.searchParams.get("limit")) ?? cap));

  const { data, error, missing } = await rpcDominio<UbicacionesMapGeoJson>("map_ubicaciones_bbox", {
    p_min_lng: box.west,
    p_min_lat: box.south,
    p_max_lng: box.east,
    p_max_lat: box.north,
    p_limit: limit,
  });

  if (missing) return dominioError(error || "Supabase no configurado", 503);
  if (error) return dominioError(error, 500);
  return dominioJson(data ?? { type: "FeatureCollection", features: [] }, 300);
}
