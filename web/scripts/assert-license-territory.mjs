import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { TERRITORIAL_POLICY } from './lib/license-territory.mjs';

export function assertLicenseTerritory(outDir) {
  const indexPath = join(outDir, 'madrid-licencias-index.json');
  const names = readdirSync(outDir);
  const files = names.filter(n => /^madrid-licencias-\d{4}\.json$/.test(n));
  const geoFiles = names.filter(n => /^madrid-licencias-\d{4}\.geojson$/.test(n));
  if (!existsSync(indexPath)) {
    if (files.length || geoFiles.length) throw new Error('Licencias sin índice territorial');
    return;
  }
  const idx = JSON.parse(readFileSync(indexPath));
  if (idx.municipioCode !== '28079' || idx.territorialPolicy !== TERRITORIAL_POLICY)
    throw new Error('Licencias requieren reproceso territorial acreditado');
  let total = 0, mapped = 0;
  const years = new Set((idx.years || []).map(String));
  if (files.length !== years.size || geoFiles.length !== years.size || Object.values(idx.byYear || {}).reduce((a,b)=>a+b,0) !== idx.totalRows) throw new Error('Particiones territoriales obsoletas');
  for (const name of files) {
    const year = name.match(/(\d{4})/)[1];
    const rows = JSON.parse(readFileSync(join(outDir, name)));
    const geo = JSON.parse(readFileSync(join(outDir, name.replace('.json', '.geojson'))));
    if (!years.has(year) || rows.length !== idx.byYear[year] || rows.some(r => r.municipioCode !== '28079'))
      throw new Error(`Contaminación o descuadre territorial: ${name}`);
    if (geo.features.some(f => f.properties.municipioCode !== '28079') || geo.features.length > rows.length)
      throw new Error(`Cobertura territorial inválida: ${name}`);
    total += rows.length;
    mapped += geo.features.length;
  }
  if (total !== idx.totalRows || mapped !== idx.withCoords || total - mapped !== idx.withoutCoords)
    throw new Error('Totales, años y cobertura geográfica no reconcilian');
  return idx;
}
if (process.argv[1] === fileURLToPath(import.meta.url))
  assertLicenseTerritory(process.argv[2] || fileURLToPath(new URL('../public/data', import.meta.url)));
