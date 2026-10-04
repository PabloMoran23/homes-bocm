import type { FeatureCollection } from "geojson";
import { dominioError, dominioJson } from "@/lib/dominio-cache";
import { insideMunicipality, type MunicipalityGeometry } from "@/lib/map-municipality-placement";
export const revalidate = 86400;
const aliases: Record<string, string> = { alboraya: "Alboraia", alcoy: "Alcoi", benicasim: "Benicàssim", burriana: "Borriana", castellondelaplana: "Castelló de la Plana", elche: "Elx", javea: "Xàbia", sagunto: "Sagunt", mogente: "Moixent", lacisterniga: "Cistérniga" };
const normalize = (value: string) => value.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]/g, "");

export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  const name = params.get("name")?.trim() || "";
  const lng = Number(params.get("lng")), lat = Number(params.get("lat"));
  if (!name || name.length > 100 || !params.has("lng") || !params.has("lat") || !Number.isFinite(lng) || !Number.isFinite(lat) || lng < -19 || lng > 5 || lat < 27 || lat > 44) return dominioError("Municipio no válido", 400);
  const load = async (filter: Record<string, string>) => {
    const query = new URLSearchParams({ f: "json", limit: "30", nationallevelname: "Municipio", ...filter });
    const response = await fetch(`https://api-features.ign.es/collections/administrativeunit/items?${query}`, { next: { revalidate: 86400 }, signal: AbortSignal.timeout(8000) });
    if (!response.ok) throw new Error("IGN boundary unavailable");
    const data = await response.json() as FeatureCollection;
    return data.features.filter(f => f.geometry.type === "Polygon" || f.geometry.type === "MultiPolygon");
  };
  try {
    const officialName = aliases[normalize(name)] ?? name;
    const candidates = await load({ bbox: `${lng - .05},${lat - .05},${lng + .05},${lat + .05}` });
    let matching = candidates.filter(f => normalize(String(f.properties?.nameunit || "")) === normalize(officialName));
    if (!matching.length) matching = await load({ nameunit: officialName });
    const feature = matching.find(f => insideMunicipality([lng, lat], f.geometry as MunicipalityGeometry)) ?? (matching.length === 1 ? matching[0] : null);
    if (!feature) return dominioError("No se ha encontrado el límite municipal", 404);
    return dominioJson({ geometry: feature.geometry, source: "IGN", name: feature.properties?.nameunit }, 86400);
  } catch { return dominioError("No hemos podido cargar el límite municipal", 503); }
}
