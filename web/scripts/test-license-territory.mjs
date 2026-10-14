import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, readFileSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { licenseTerritory } from './lib/license-territory.mjs';
import { assertLicenseTerritory } from './assert-license-territory.mjs';
import { buildMadridLicenciasWeb } from './build-madrid-licencias.mjs';
assert.equal(licenseTerritory({}).reason, 'missing_municipality_provenance');
assert.equal(licenseTerritory({source: 'madrid-opendata'}).municipioCode, '28079');
assert.equal(licenseTerritory({source: 'portal', municipio_slug: 'valladolid'}).municipioCode, '47186');
const temp = mkdtempSync(join(tmpdir(), 'license-territory-'));
try {
  const input = join(temp, 'input.jsonl');
  writeFileSync(input, [
    {source:'madrid-opendata', anio_dataset: 2024},
    {source:'portal', municipio_slug:'valladolid', anio_dataset: 2024},
    {anio_dataset: 2024},
    {source:'madrid-opendata', anio_dataset: 2019},
  ].map(r=>JSON.stringify(r)).join('\n'));
  const idx = await buildMadridLicenciasWeb({jsonlPath:input,outDir:temp,minYear:2022});
  assert.equal(idx.totalRows, 1);
  assert.equal(idx.excludedTerritory, 2);
  assertLicenseTerritory(temp);
  const path = join(temp,'madrid-licencias-2024.json');
  const good = readFileSync(path);
  writeFileSync(path, JSON.stringify([{municipioCode:'47186'}]));
  assert.throws(()=>assertLicenseTerritory(temp), /Contaminación/);
  writeFileSync(path, good);
  assertLicenseTerritory(temp);
  writeFileSync(input, JSON.stringify({source:'portal',municipio_slug:'valladolid',anio_dataset:2024}));
  await buildMadridLicenciasWeb({jsonlPath:input,outDir:temp,minYear:2022});
  assert.equal(existsSync(path), false);
  assertLicenseTerritory(temp);
} finally { rmSync(temp,{recursive:true,force:true}); }
console.log('Territorial contract, reconciliation, failure and recovery: OK');
