import { dominioError, dominioJson, rpcDominio } from "@/lib/dominio-cache";
import type { MadridDashboardStats } from "@/lib/types";

export const revalidate = 3600;
export const maxDuration = 15;

export async function GET() {
  const { data, error, missing } = await rpcDominio<MadridDashboardStats>("madrid_dashboard_stats");
  if (missing) return dominioError(error || "Supabase no configurado", 503);
  if (error) return dominioError(error, 500);
  if (!data?.sigma) return dominioError("Stats vacías", 500);
  return dominioJson(data, 3600);
}
