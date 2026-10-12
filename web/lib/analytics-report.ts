import { getSupabaseServer } from "@/lib/supabase/server";
export type AnalyticsReport = {
  days: number; source: string;
  overview: { sessions: number; pageviews: number; active_sessions: number; single_page_sessions: number; without_interaction: number; suspicious_sessions: number; avg_active_seconds: number };
  pages: { path: string; pageviews: number; sessions: number; active_seconds: number | null; scroll_percent: number | null }[];
  sources: { source: string; sessions: number; pageviews: number }[];
  actions: { event_name: string; count: number }[];
  journeys: { session_id: string; started_at: string; source: string; entry_path: string; pageviews: number; active_seconds: number; suspicious: boolean; events: { id: string; event_name: string; path: string; occurred_at: string; props: Record<string, string | number> }[] }[];
};
export async function getAnalyticsReport(days: number, source: string): Promise<AnalyticsReport> {
  const supabase = getSupabaseServer();
  const key = process.env.ANALYTICS_RPC_KEY;
  if (!supabase || !key) throw new Error("La recogida de sesiones todavía no está configurada.");
  const { data, error } = await supabase.rpc("homes_analytics_report", { p_key: key, p_days: days, p_source: source });
  if (error) throw new Error("No se ha podido consultar la analítica. Comprueba la migración y la configuración del servidor.");
  return data as AnalyticsReport;
}
