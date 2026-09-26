import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { rpcDominio } from "@/lib/dominio-cache";
import type { DataSummary } from "./types";

export async function loadSummary(): Promise<DataSummary | null> {
  const { data } = await rpcDominio<DataSummary>("web_summary");
  if (data?.total != null) return data;
  try {
    const path = join(process.cwd(), "public/data/summary.json");
    const raw = await readFile(path, "utf-8");
    return JSON.parse(raw) as DataSummary;
  } catch {
    return null;
  }
}
