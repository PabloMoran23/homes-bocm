import { dominioError, dominioJson, rpcDominio } from "@/lib/dominio-cache";
import type { CmMunicipioOption } from "@/lib/cm-portal-geo";

export const revalidate = 900;

type Payload = { municipios?: CmMunicipioOption[] };

export async function GET() {
  const { data, error, missing } = await rpcDominio<Payload>("map_cm_municipios");
  if (missing) return dominioError(error || "Supabase no configurado", 503);
  if (error) return dominioError(error, 500);
  const municipios = Array.isArray(data?.municipios) ? data.municipios : [];
  municipios.sort((a, b) => b.n - a.n || a.nombre.localeCompare(b.nombre, "es"));
  return dominioJson({ municipios });
}
