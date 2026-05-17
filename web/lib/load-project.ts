import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { ensureProject } from "./ensure-project";
import { projectPath } from "./project-display";
import type { Project } from "./types";

export { projectPath };

let index: Map<string, Project> | null = null;

async function getIndex(): Promise<Map<string, Project>> {
  if (index) return index;
  const path = join(process.cwd(), "public/data/projects.json");
  const raw = await readFile(path, "utf-8");
  const rows = JSON.parse(raw) as Array<Partial<Project> & { id: string }>;
  index = new Map();
  for (const row of rows) {
    if (!row.id) continue;
    index.set(row.id, ensureProject(row));
  }
  return index;
}

export async function loadProjectById(id: string): Promise<Project | null> {
  const decoded = decodeURIComponent(id);
  const map = await getIndex();
  return map.get(decoded) ?? null;
}
