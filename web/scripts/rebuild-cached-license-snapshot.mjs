/** Rebuild the public 2022+ license cut through the normal source-backed builders.
 * Run the XLSX downloader --skip-download first. No DB or credentials are used.
 */
import { fileURLToPath } from 'node:url';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { buildMadridLicenciasWeb } from './build-madrid-licencias.mjs';
import { buildMadridDashboardStats } from './build-madrid-dashboard-stats.mjs';
import { buildMadridLicenciasFilterRows } from './build-madrid-licencias-filter-rows.mjs';
import { buildMadridPresentacion } from './build-madrid-presentacion.mjs';
import { assertLicenseTerritory } from './assert-license-territory.mjs';
const root = fileURLToPath(new URL('../../', import.meta.url));
const outDir = join(root, 'web/public/data');
const summary = JSON.parse(readFileSync(join(root, 'output/madrid_licencias_summary.json'), 'utf8'));
if (summary.sourceSnapshot?.mode !== 'cached-xlsx-replay')
  throw new Error('Regenerar primero evidencia mediante el descargador --skip-download');
const index = await buildMadridLicenciasWeb({
  jsonlPath: join(root, 'output/madrid_licencias.jsonl'), outDir, minYear: 2022,
});
if (!index?.sourceSnapshot || index.sourceSnapshot.mode !== 'cached-xlsx-replay')
  throw new Error('Se requiere evidencia de replay desde los XLSX originales cacheados');
assertLicenseTerritory(outDir);
buildMadridDashboardStats({outDir});
buildMadridLicenciasFilterRows({outDir});
buildMadridPresentacion({outDir});
console.log(JSON.stringify({municipioCode:index.municipioCode, years:index.years,
  totalRows:index.totalRows, withCoords:index.withCoords, sourceMode:index.sourceSnapshot.mode}));
