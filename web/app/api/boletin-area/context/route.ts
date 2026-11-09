import { NextResponse } from "next/server";
import { loadAreaContext } from "@/lib/load-area-context";
import { isMadridLocation } from "@/lib/address-search";

export const maxDuration = 30;
export async function GET(req: Request) {
  const params = new URL(req.url).searchParams;
  const lat = Number(params.get("lat")), lng = Number(params.get("lng"));
  const radius = Number(params.get("radiusM") || 500), months = Number(params.get("months") || 12);
  if (!params.get("lat") || !params.get("lng") || !isMadridLocation({ lat, lng }) || !Number.isFinite(radius) || radius < 100 || radius > 3000 || !Number.isInteger(months) || months < 6 || months > 120) {
    return NextResponse.json({ error: "Dirección o filtros no válidos" }, { status: 400 });
  }
  try {
    return NextResponse.json(await loadAreaContext(lat, lng, radius, months), { headers: { "Cache-Control": "public, s-maxage=300, stale-while-revalidate=600" } });
  } catch {
    return NextResponse.json({ error: "No se pudo cargar el contexto urbanístico. Puedes seguir consultando las licencias." }, { status: 503 });
  }
}
