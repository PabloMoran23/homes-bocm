import { rpcDominio } from "@/lib/dominio-cache";
import { fetchStaticJson } from "@/lib/fetch-static-json";
import type { MadridDashboardStats } from "@/lib/types";

export async function loadMadridDashboardStats(): Promise<MadridDashboardStats | null> {
  const [{ data: live }, file] = await Promise.all([
    rpcDominio<MadridDashboardStats>("madrid_dashboard_stats"),
    fetchStaticJson<MadridDashboardStats>("/data/madrid-dashboard-stats.json"),
  ]);
  if (live?.sigma?.total != null) {
    return {
      generatedAt: live.generatedAt || new Date().toISOString(),
      distritoCentroids: file?.distritoCentroids,
      licencias: file?.licencias ?? live.licencias,
      sigma: live.sigma,
    };
  }
  return file;
}
