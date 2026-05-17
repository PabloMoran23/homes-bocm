import { readFile } from "node:fs/promises";
import { join } from "node:path";
import type { AdminCoverage } from "./types";

export async function loadAdminCoverage(): Promise<AdminCoverage | null> {
  try {
    const path = join(process.cwd(), "public/data/admin-coverage.json");
    const raw = await readFile(path, "utf-8");
    return JSON.parse(raw) as AdminCoverage;
  } catch {
    return null;
  }
}
