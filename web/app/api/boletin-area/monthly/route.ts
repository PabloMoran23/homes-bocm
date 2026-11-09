import { NextResponse } from "next/server";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { summarizeMonthlyLicenses, type LicenseFeature } from "@/lib/area-monthly";
import { areaToday, areaCutoff } from "@/lib/area-context";
import { isMadridLocation } from "@/lib/address-search";

type LicenseIndex = { generatedAt:string; years:number[] };
let revision = "";
const files = new Map<number,Promise<LicenseFeature[]>>();
async function loadYear(year:number) {
  if (!files.has(year)) files.set(year,(async () => {
    const data = JSON.parse(await readFile(join(process.cwd(), "public/data", `madrid-licencias-${year}.geojson`), "utf8")) as {features:LicenseFeature[]};
    if (!data?.features) { files.delete(year); throw new Error("Archivo no disponible"); }
    // Keep only the fields needed to count dates, distance and types.
    return data.features.map(({geometry,properties:p}) => ({geometry,properties:{fecha_concesion:p.fecha_concesion,actuacion_que:p.actuacion_que,tipo_expediente:p.tipo_expediente,objeto:p.objeto,uso:p.uso,procedimiento:p.procedimiento}}));
  })().catch(error => { files.delete(year); throw error; }));
  return files.get(year)!;
}
export async function GET(req: Request) {
  const params = new URL(req.url).searchParams;
  const lat = Number(params.get("lat")), lng = Number(params.get("lng")), radius = Number(params.get("radiusM") || 500), months = Number(params.get("months") || 12);
  if (!params.get("lat") || !params.get("lng") || !isMadridLocation({lat,lng}) || !Number.isFinite(radius) || radius < 100 || radius > 3000 || !Number.isInteger(months) || months < 1 || months > 120) return NextResponse.json({error:"Dirección, radio o periodo no válidos"},{status:400});
  try {
    const today = areaToday(), year = Number(today.slice(0,4)), firstYear = Number(areaCutoff(today,months).slice(0,4));
    const index = JSON.parse(await readFile(join(process.cwd(), "public/data/madrid-licencias-index.json"), "utf8")) as LicenseIndex;
    if (!index?.years?.length) throw new Error("Índice no disponible");
    if (revision !== index.generatedAt) { files.clear(); revision = index.generatedAt; }
    const years = index.years.filter(value => value >= firstYear && value <= year);
    if (!years.length) throw new Error("No hay archivos para este periodo");
    const features = (await Promise.all(years.map(loadYear))).flat();
    return NextResponse.json(summarizeMonthlyLicenses(features,lat,lng,radius,today,months),{headers:{"Cache-Control":"public, s-maxage=300"}});
  } catch { return NextResponse.json({error:"No se pudo consultar el resumen de licencias"},{status:503}); }
}
