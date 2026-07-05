import { fetchStaticJson } from "./fetch-static-json";
import { loadCmPortalProjectById } from "./load-cm-portal-project";
import { ensureProject } from "./ensure-project";
import { projectFromDominioRow } from "./proyecto-dominio-map";
import { projectPath } from "./project-display";
import { getSupabaseServer } from "./supabase/server";
import type { Project } from "./types";

export { projectPath };

let index: Map<string, Project> | null = null;

async function getIndex(): Promise<Map<string, Project>> {
  if (index) return index;
  index = new Map();
  const rows = await fetchStaticJson<Array<Partial<Project> & { id: string }>>("/data/projects.json");
  if (!rows) return index;
  for (const row of rows) {
    if (!row.id) continue;
    index.set(row.id, ensureProject(row));
  }
  return index;
}

async function loadProjectFromSupabase(id: string): Promise<Project | null> {
  const supabase = getSupabaseServer();
  if (!supabase) return null;

  const { data, error } = await supabase.rpc("get_proyecto_portal", { p_id: id });
  if (error) {
    console.warn("get_proyecto_portal:", error.message);
    return null;
  }
  if (!data || typeof data !== "object") return null;
  return projectFromDominioRow(data as Record<string, unknown>);
}

export async function loadProjectById(id: string): Promise<Project | null> {
  const decoded = decodeURIComponent(id);
  const fromDb = await loadProjectFromSupabase(decoded);
  if (fromDb) return fromDb;
  const map = await getIndex();
  const fromBocm = map.get(decoded);
  if (fromBocm) return fromBocm;
  return loadCmPortalProjectById(decoded);
}
