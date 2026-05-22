import { fetchStaticJson } from "@/lib/fetch-static-json";
import type { MadridDashboardStats } from "@/lib/types";

export async function loadMadridDashboardStats(): Promise<MadridDashboardStats | null> {
  return fetchStaticJson<MadridDashboardStats>("/data/madrid-dashboard-stats.json");
}
