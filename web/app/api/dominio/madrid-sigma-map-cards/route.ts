import { dominioError, dominioJson, rpcDominio } from "@/lib/dominio-cache";
import type { SigmaMapCardSlice } from "@/lib/map-project-spotlight";

export const revalidate = 3600;

type Payload = {
  generatedAt?: string;
  byExpediente?: Record<string, SigmaMapCardSlice>;
};

export async function GET() {
  const { data, error, missing } = await rpcDominio<Payload>("list_sigma_map_cards");
  if (missing) return dominioError(error || "Supabase no configurado", 503);
  if (error) return dominioError(error, 500);
  return dominioJson(data ?? { generatedAt: new Date().toISOString(), byExpediente: {} }, 3600);
}
