import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import type { MadridSigmaMetricsFile, SigmaExpedienteMetric } from "@/lib/sigma-metrics";

const DATA = join(process.cwd(), "public/data");

let cached: MadridSigmaMetricsFile | null = null;

export function loadSigmaMetricsFile(): MadridSigmaMetricsFile | null {
  if (cached) return cached;
  const path = join(DATA, "madrid-sigma-metrics.json");
  if (!existsSync(path)) return null;
  cached = JSON.parse(readFileSync(path, "utf-8")) as MadridSigmaMetricsFile;
  return cached;
}

export function getSigmaMetricForGrupo(expedienteGrupo: string): SigmaExpedienteMetric | null {
  const file = loadSigmaMetricsFile();
  if (!file?.byExpediente) return null;
  return file.byExpediente[expedienteGrupo] ?? null;
}
