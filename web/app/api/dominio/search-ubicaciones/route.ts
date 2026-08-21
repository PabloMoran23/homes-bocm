import { dominioError, dominioJson, rpcDominio } from "@/lib/dominio-cache";
import type { UbicacionSearchItem } from "@/lib/ubicacion";

export const revalidate = 60;

export async function GET(req: Request) {
  const q = new URL(req.url).searchParams.get("q")?.trim() || "";
  if (q.length < 2) {
    return dominioJson([], 30);
  }

  const { data, error, missing } = await rpcDominio<UbicacionSearchItem[]>("search_ubicaciones", {
    p_q: q,
    p_limit: 12,
  });

  if (missing) return dominioError(error || "Supabase no configurado", 503);
  if (error) return dominioError(error, 500);
  return dominioJson(Array.isArray(data) ? data : [], 60);
}
