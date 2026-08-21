import { dominioError, dominioJson, rpcDominio } from "@/lib/dominio-cache";
import type { MadridSigmaMetricsFile } from "@/lib/sigma-metrics";

export const revalidate = 3600;

export async function GET() {
  const { data, error, missing } = await rpcDominio<MadridSigmaMetricsFile>("list_sigma_metrics");
  if (missing) return dominioError(error || "Supabase no configurado", 503);
  if (error) return dominioError(error, 500);
  return dominioJson(
    data ?? { generatedAt: new Date().toISOString(), count: 0, byExpediente: {} },
    3600,
  );
}
