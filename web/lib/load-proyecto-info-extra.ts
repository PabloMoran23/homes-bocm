import { parseProyectoInfoExtra, type ProyectoInfoExtra } from "@/lib/proyecto-info-extra";
import { getSupabaseServer } from "@/lib/supabase/server";

export async function loadProyectoInfoExtra(
  ...ids: Array<string | null | undefined>
): Promise<ProyectoInfoExtra | null> {
  const supabase = getSupabaseServer();
  if (!supabase) return null;

  const seen = new Set<string>();
  for (const raw of ids) {
    const id = decodeURIComponent(raw || "").trim();
    if (!id || seen.has(id)) continue;
    seen.add(id);
    const { data, error } = await supabase.rpc("get_proyecto_info_extra", { p_id: id });
    if (error) {
      console.warn("get_proyecto_info_extra:", error.message);
      continue;
    }
    const parsed = parseProyectoInfoExtra(data);
    if (parsed) return parsed;
  }
  return null;
}
