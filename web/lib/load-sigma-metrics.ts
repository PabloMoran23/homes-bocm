import { rpcDominio } from "@/lib/dominio-cache";
import { fetchStaticJson } from "@/lib/fetch-static-json";
import type { SigmaExpedienteMetric } from "@/lib/sigma-metrics";
import { sanitizeSigmaMetric } from "@/lib/vivienda-plausible";

type MadridSigmaMetricsFile = {
  generatedAt?: string;
  count?: number;
  byExpediente?: Record<string, SigmaExpedienteMetric>;
};

let metricsPromise: Promise<MadridSigmaMetricsFile | null> | null = null;

async function loadMetricsFile(): Promise<MadridSigmaMetricsFile | null> {
  if (!metricsPromise) {
    metricsPromise = (async () => {
      const { data } = await rpcDominio<MadridSigmaMetricsFile>("list_sigma_metrics");
      if (data?.byExpediente) return data;
      return fetchStaticJson<MadridSigmaMetricsFile>("/data/madrid-sigma-metrics.json");
    })();
  }
  return metricsPromise;
}

export async function getSigmaMetricForGrupo(
  expedienteGrupo: string,
): Promise<SigmaExpedienteMetric | null> {
  const file = await loadMetricsFile();
  return sanitizeSigmaMetric(file?.byExpediente?.[expedienteGrupo] ?? null);
}
