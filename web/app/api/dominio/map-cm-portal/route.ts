import { dominioError, dominioJson, rpcDominio } from "@/lib/dominio-cache";
import type { CmPortalGeoJson, CmPortalMapMeta, CmPortalProyectoProps } from "@/lib/cm-portal-geo";

export const revalidate = 900;

type Payload = {
  generatedAt?: string;
  points?: CmPortalGeoJson<CmPortalProyectoProps>;
  polygons?: CmPortalGeoJson<CmPortalProyectoProps>;
  approx?: CmPortalGeoJson<CmPortalProyectoProps>;
  meta?: CmPortalMapMeta;
};

const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

function parseCoord(raw: string | null): number | null {
  if (raw == null || raw.trim() === "") return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const slug = url.searchParams.get("municipio")?.trim() ?? "";
  const from = url.searchParams.get("from")?.trim() ?? "";
  const to = url.searchParams.get("to")?.trim() ?? "";
  const minLng = parseCoord(url.searchParams.get("minLng"));
  const minLat = parseCoord(url.searchParams.get("minLat"));
  const maxLng = parseCoord(url.searchParams.get("maxLng"));
  const maxLat = parseCoord(url.searchParams.get("maxLat"));
  const bboxOk =
    minLng != null &&
    minLat != null &&
    maxLng != null &&
    maxLat != null &&
    minLng < maxLng &&
    minLat < maxLat;

  if (!SLUG.test(slug) || (from && !DATE.test(from)) || (to && !DATE.test(to)) || (from && to && from > to)) {
    return dominioError("Elige un municipio y un rango de fechas válido", 400);
  }

  const { data, error, missing } = await rpcDominio<Payload>("map_cm_portal_municipio", {
    p_slug: slug,
    p_from: from || null,
    p_to: to || null,
    p_min_lng: bboxOk ? minLng : null,
    p_min_lat: bboxOk ? minLat : null,
    p_max_lng: bboxOk ? maxLng : null,
    p_max_lat: bboxOk ? maxLat : null,
  });
  if (missing) return dominioError(error || "Supabase no configurado", 503);
  if (error) return dominioError(error, 500);
  return dominioJson(
    data ?? {
      points: { type: "FeatureCollection", features: [] },
      polygons: { type: "FeatureCollection", features: [] },
    },
  );
}
