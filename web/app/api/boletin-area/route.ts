import { NextResponse } from "next/server";
import {
  BOLETIN_DEFAULT_MONTHS,
  BOLETIN_DEFAULT_RADIUS_M,
  type BoletinAreaResult,
} from "@/lib/boletin-area";
import {
  BOLETIN_AREA_CACHE_HEADERS,
  boletinAreaCacheKey,
  readBoletinAreaCache,
  writeBoletinAreaCache,
} from "@/lib/boletin-area-cache";
import { normalizeDireccion } from "@/lib/direccion";
import { getSupabaseServer } from "@/lib/supabase/server";

export const maxDuration = 15;

const RADIUS_MIN = 100;
const RADIUS_MAX = 3000;
const MONTHS_MIN = 6;
const MONTHS_MAX = 120;

function clampInt(value: number, min: number, max: number, fallback: number) {
  if (!Number.isFinite(value)) return fallback;
  return Math.min(max, Math.max(min, Math.round(value)));
}

function normalizeBoletinResult(
  result: BoletinAreaResult,
  opts: { ndp?: string | null; label?: string | null },
): BoletinAreaResult {
  if (!opts.ndp && opts.label) {
    result.center.direccion = opts.label;
  } else if (result.center.direccion) {
    result.center.direccion = normalizeDireccion(result.center.direccion);
  }
  for (const ev of [...result.licencias, ...result.expedientesSigma, ...result.timeline]) {
    if (ev.direccion) ev.direccion = normalizeDireccion(ev.direccion);
  }
  return result;
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const ndp = url.searchParams.get("ndp")?.trim() || null;
  const latParam = url.searchParams.get("lat");
  const lngParam = url.searchParams.get("lng");
  const labelParam = url.searchParams.get("label")?.trim() || null;
  const radiusM = clampInt(
    Number(url.searchParams.get("radiusM") || String(BOLETIN_DEFAULT_RADIUS_M)),
    RADIUS_MIN,
    RADIUS_MAX,
    BOLETIN_DEFAULT_RADIUS_M,
  );
  const months = clampInt(
    Number(url.searchParams.get("months") || String(BOLETIN_DEFAULT_MONTHS)),
    MONTHS_MIN,
    MONTHS_MAX,
    BOLETIN_DEFAULT_MONTHS,
  );

  const supabase = getSupabaseServer();
  if (!supabase) {
    return NextResponse.json(
      { error: "Supabase no configurado (variables de entorno)" },
      { status: 503 },
    );
  }

  let lat: number;
  let lng: number;

  if (ndp) {
    const { data: rows, error } = await supabase.rpc("resolve_ndp_coords", {
      p_ndp: ndp,
    });

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
    const inv = Array.isArray(rows) ? rows[0] : rows;
    if (!inv?.lat || !inv?.lng) {
      return NextResponse.json({ error: "NDP sin coordenadas válidas" }, { status: 422 });
    }
    lat = Number(inv.lat);
    lng = Number(inv.lng);
  } else if (latParam != null && lngParam != null) {
    lat = Number(latParam);
    lng = Number(lngParam);
  } else {
    return NextResponse.json({ error: "Indica dirección (ndp) o lat/lng" }, { status: 400 });
  }

  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    return NextResponse.json({ error: "Coordenadas inválidas" }, { status: 400 });
  }

  const cacheKey = boletinAreaCacheKey({ lat, lng, radiusM, months, ndp });
  const cached = readBoletinAreaCache(cacheKey);
  if (cached) {
    return NextResponse.json(
      normalizeBoletinResult(structuredClone(cached), { ndp, label: labelParam }),
      { headers: BOLETIN_AREA_CACHE_HEADERS },
    );
  }

  const { data, error } = await supabase.rpc("boletin_area", {
    p_lat: lat,
    p_lng: lng,
    p_radius_m: radiusM,
    p_months: months,
  });

  if (error) {
    const msg = error.message.includes("statement timeout")
      ? "La consulta tardó demasiado. Prueba un radio o un periodo más cortos."
      : error.message;
    return NextResponse.json({ error: msg }, { status: error.message.includes("statement timeout") ? 504 : 500 });
  }

  const result = data as BoletinAreaResult | null;
  if (!result) {
    return NextResponse.json({ error: "Sin resultados" }, { status: 404 });
  }
  if ("error" in result && result.error) {
    return NextResponse.json(result, { status: 422 });
  }

  writeBoletinAreaCache(cacheKey, structuredClone(result));
  return NextResponse.json(
    normalizeBoletinResult(result, { ndp, label: labelParam }),
    { headers: BOLETIN_AREA_CACHE_HEADERS },
  );
}
