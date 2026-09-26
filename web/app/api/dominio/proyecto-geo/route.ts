import { dominioError, dominioJson, rpcDominio } from "@/lib/dominio-cache";
import type { SectorFeatureCollection } from "@/lib/sector-geo";

export const revalidate = 900;

export async function GET(req: Request) {
  const id = new URL(req.url).searchParams.get("id")?.trim() ?? "";
  if (id.length < 3 || id.length > 80) {
    return dominioError("Falta el proyecto", 400);
  }
  const { data, error, missing } = await rpcDominio<SectorFeatureCollection>("proyecto_mapa_feature", {
    p_id: id,
  });
  if (missing) return dominioError(error || "Supabase no configurado", 503);
  if (error) return dominioError(error, 500);
  return dominioJson(data ?? { type: "FeatureCollection", features: [] }, 900);
}
