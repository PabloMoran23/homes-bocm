import { fetchStaticJson } from "@/lib/fetch-static-json";
import { rpcDominio } from "@/lib/dominio-cache";
import type { DataSummary } from "./types";

export async function loadSummary(): Promise<DataSummary | null> {
  const { data } = await rpcDominio<DataSummary>("web_summary");
  if (data?.total != null) return data;
  return fetchStaticJson<DataSummary>("/data/summary.json");
}
