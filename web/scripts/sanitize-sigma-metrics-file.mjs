/**
 * Reescribe madrid-sigma-metrics.json aplicando coherencia viviendas ↔ m².
 * Uso: node scripts/sanitize-sigma-metrics-file.mjs
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { sanitizeMetricsByExpediente } from "../lib/vivienda-plausible.mjs";

const outDir = join(dirname(fileURLToPath(import.meta.url)), "../public/data");
const path = join(outDir, "madrid-sigma-metrics.json");
const raw = JSON.parse(readFileSync(path, "utf-8"));
const before = Object.values(raw.byExpediente || {}).filter((m) => m?.num_viviendas_max > 0).length;

raw.byExpediente = sanitizeMetricsByExpediente(raw.byExpediente);
raw.generatedAt = new Date().toISOString();
raw.sanityNote =
  "num_viviendas_max filtrado por coherencia con sup_total_m2 / sup_edificable_m2 (≥55 m² ámbito o ≥42 m² edificable por vivienda)";

writeFileSync(path, JSON.stringify(raw));

const after = Object.values(raw.byExpediente).filter((m) => m?.num_viviendas_max > 0).length;
console.log(`OK: ${path}`);
console.log(`  Expedientes con viviendas: ${before} → ${after} (descartadas ${before - after})`);
