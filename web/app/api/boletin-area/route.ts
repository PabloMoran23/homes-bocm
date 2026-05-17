import { NextResponse } from "next/server";
import type { BoletinAreaResult } from "@/lib/boletin-area";
import { getSupabaseServer } from "@/lib/supabase/server";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const ndp = url.searchParams.get("ndp");
  const latParam = url.searchParams.get("lat");
  const lngParam = url.searchParams.get("lng");
  const radiusM = Number(url.searchParams.get("radiusM") || "600");
  const months = Number(url.searchParams.get("months") || "24");

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
      p_ndp: ndp.trim(),
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

  const { data, error } = await supabase.rpc("boletin_area", {
    p_lat: lat,
    p_lng: lng,
    p_radius_m: radiusM,
    p_months: months,
  });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const result = data as BoletinAreaResult | null;
  if (!result) {
    return NextResponse.json({ error: "Sin resultados" }, { status: 404 });
  }
  if ("error" in result && result.error) {
    return NextResponse.json(result, { status: 422 });
  }

  return NextResponse.json(result);
}
