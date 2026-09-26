import { dominioError, dominioJson, rpcDominio } from "@/lib/dominio-cache";
import type { DataSummary } from "@/lib/types";

export const revalidate = 3600;

export async function GET() {
  const { data, error, missing } = await rpcDominio<DataSummary>("web_summary");
  if (missing) return dominioError(error || "Supabase no configurado", 503);
  if (error) return dominioError(error, 500);
  return dominioJson(data, 3600);
}
