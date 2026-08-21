import { dominioError, dominioJson, rpcDominio } from "@/lib/dominio-cache";
import type { CmPortalGeoJson, CmPortalMapMeta, CmPortalProyectoProps } from "@/lib/cm-portal-geo";

export const revalidate = 900;

type Payload = {
  generatedAt?: string;
  points?: CmPortalGeoJson<CmPortalProyectoProps>;
  polygons?: CmPortalGeoJson<CmPortalProyectoProps>;
  meta?: CmPortalMapMeta;
};

export async function GET() {
  const { data, error, missing } = await rpcDominio<Payload>("map_cm_portal");
  if (missing) return dominioError(error || "Supabase no configurado", 503);
  if (error) return dominioError(error, 500);
  return dominioJson(data ?? { points: { type: "FeatureCollection", features: [] } });
}
