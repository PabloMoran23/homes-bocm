import { unstable_cache } from "next/cache";
import { rpcDominio } from "@/lib/dominio-cache";
import { fetchStaticJson } from "@/lib/fetch-static-json";
import type { MadridDashboardStats } from "@/lib/types";

const loadCachedMadridDashboardStats = unstable_cache(
  async (): Promise<MadridDashboardStats | null> => {
    const { data, error, missing } = await rpcDominio<MadridDashboardStats>("madrid_dashboard_stats");
    if (missing) throw new Error("supabase-missing");
    if (error || data?.sigma?.total == null) return null;
    return data;
  },
  ["madrid-dashboard-stats-v1"],
  { revalidate: 600 },
);

export async function loadMadridDashboardStats(): Promise<MadridDashboardStats | null> {
  const filePromise = fetchStaticJson<MadridDashboardStats>("/data/madrid-dashboard-stats.json");
  let live: MadridDashboardStats | null = null;
  try {
    live = await loadCachedMadridDashboardStats();
  } catch {
    live = null;
  }
  const file = await filePromise;
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
