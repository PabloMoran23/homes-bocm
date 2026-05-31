#!/usr/bin/env node
/**
 * Falla el build si los GeoJSON del mapa SIGMA están vacíos (p. ej. caché Vercel corrupta).
 */
import { readFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const dataDir = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "data");

const checks = [
  { file: "madrid-sigma-ambitos.geojson", minFeatures: 100 },
  { file: "madrid-sigma-ambitos-landing.geojson", minFeatures: 100 },
];

let failed = 0;

for (const { file, minFeatures } of checks) {
  const path = join(dataDir, file);
  if (!existsSync(path)) {
    console.error(`✗ Falta ${file}`);
    failed += 1;
    continue;
  }
  let n = 0;
  try {
    const fc = JSON.parse(readFileSync(path, "utf8"));
    n = fc?.features?.length ?? 0;
  } catch (e) {
    console.error(`✗ ${file} JSON inválido: ${e.message}`);
    failed += 1;
    continue;
  }
  if (n < minFeatures) {
    console.error(`✗ ${file} tiene ${n} features (mínimo ${minFeatures})`);
    failed += 1;
  } else {
    console.log(`✓ ${file} (${n} features)`);
  }
}

if (failed) {
  console.error(
    "\nMapa SIGMA sin datos en public/data/. Regenera con npm run build-data o restaura los GeoJSON commiteados.",
  );
  process.exit(1);
}
