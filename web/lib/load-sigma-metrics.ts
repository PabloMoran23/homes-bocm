import { fetchStaticJson } from "@/lib/fetch-static-json";
import type { SigmaExpedienteMetric } from "@/lib/sigma-metrics";

type MadridSigmaMetricsFile = {
  generatedAt?: string;
  count?: number;
  byExpediente?: Record<string, SigmaExpedienteMetric>;
};

let metricsPromise: Promise<MadridSigmaMetricsFile | null> | null = null;

async function loadMetricsFile(): Promise<MadridSigmaMetricsFile | null> {
  if (!metricsPromise) {
    metricsPromise = fetchStaticJson<MadridSigmaMetricsFile>("/data/madrid-sigma-metrics.json");
  }
  return metricsPromise;
}

export async function getSigmaMetricForGrupo(
  expedienteGrupo: string,
): Promise<SigmaExpedienteMetric | null> {
  const file = await loadMetricsFile();
  return file?.byExpediente?.[expedienteGrupo] ?? null;
}
