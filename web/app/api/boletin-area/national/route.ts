import { NextResponse } from "next/server";
import { loadNationalArea } from "@/lib/load-national-area";
import { isSpainLocation } from "@/lib/address-search";
export const maxDuration = 30;
export async function GET(req: Request) {
  const p = new URL(req.url).searchParams, lat = Number(p.get("lat")), lng = Number(p.get("lng"));
  const radius = Number(p.get("radiusM") || 500), months = Number(p.get("months") || 12);
  const name = (p.get("municipality") || "").trim(), label = (p.get("label") || name).trim();
  if (!p.get("lat") || !p.get("lng") || !isSpainLocation({lat,lng}) || !name || name.length > 150 || label.length > 500 || !Number.isInteger(radius) || radius < 100 || radius > 3000 || !Number.isInteger(months) || months < 6 || months > 120) return NextResponse.json({error:"Dirección, municipio o filtros no válidos"},{status:400});
  try { return NextResponse.json(await loadNationalArea(lat,lng,name,label,radius,months), {headers:{"Cache-Control":"public, s-maxage=300, stale-while-revalidate=600"}}); }
  catch { return NextResponse.json({error:"No se pudo consultar la información del municipio. Vuelve a intentarlo."},{status:503}); }
}
