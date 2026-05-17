import { readFile } from "node:fs/promises";
import { join } from "node:path";
import type { DataSummary } from "./types";

export async function loadSummary(): Promise<DataSummary | null> {
  try {
    const path = join(process.cwd(), "public/data/summary.json");
    const raw = await readFile(path, "utf-8");
    return JSON.parse(raw) as DataSummary;
  } catch {
    return null;
  }
}
