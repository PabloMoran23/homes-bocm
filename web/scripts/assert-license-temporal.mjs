/** Reject stale temporal artifacts even when production skips data regeneration. */
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { DATE_RULE_VERSION } from './lib/license-dates.mjs';
import { commonCompleteMonths, periodCoverage } from './lib/period-coverage.mjs';
export function assertLicenseTemporal(outDir) {
  const read = name => JSON.parse(readFileSync(join(outDir, name), 'utf8'));
  const filters = read('madrid-licencias-filter-rows.json');
  const index = read('madrid-licencias-index.json');
  const presentation = read('madrid-presentacion.json');
  const stats = read('madrid-dashboard-stats.json');
  if (filters.temporal?.ruleVersion !== DATE_RULE_VERSION || !/^[a-f0-9]{64}$/.test(filters.temporal.inputDigest || ''))
    throw new Error('Licencias requieren reproceso temporal acreditado');
  if (filters.rows.length !== filters.totalRows || filters.totalRows > index.totalRows || stats.licencias?.totalRows !== index.totalRows || presentation.licencias.total !== filters.totalRows)
    throw new Error('Totales temporales no reconcilian');
  const hash = createHash('sha256').update(DATE_RULE_VERSION);
  const files = readdirSync(outDir).filter(n => /^madrid-licencias-\d{4}\.json$/.test(n)).sort();
  for (const name of files) hash.update(readFileSync(join(outDir, name), 'utf8'));
  if (!files.length) hash.update(readFileSync(join(outDir, 'madrid-licencias-index.json'), 'utf8'));
  if (hash.digest('hex') !== filters.temporal.inputDigest)
    throw new Error('Snapshot temporal cambiado sin reconstruir derivados');
  const coverage = filters.periodCoverage || {};
  const evidencePath = join(outDir, 'madrid-period-coverage.json');
  const evidence = existsSync(evidencePath) ? read('madrid-period-coverage.json') : {};
  const expectedCoverage = periodCoverage(filters.rows.map(r => r.m), evidence, { inputDigest: filters.temporal.inputDigest, asOf: filters.temporal.asOf });
  if (JSON.stringify(coverage) !== JSON.stringify(expectedCoverage))
    throw new Error('Cobertura temporal sin evidencia concordante del snapshot');
  if (filters.rows.some(r => !/^\d{4}-(0[1-9]|1[0-2])$/.test(r.m) || r.m > filters.temporal.asOf.slice(0,7) || !coverage[r.m]))
    throw new Error('Serie mensual inválida o sin cobertura temporal');
  const complete = Object.keys(coverage).filter(m => coverage[m].status === 'complete').sort();
  if (presentation.lastCompleteMonth !== (complete.at(-1) || null))
    throw new Error('Último mes completo sin evidencia concordante');
  if (complete.some(m => m >= filters.temporal.asOf.slice(0,7) || !coverage[m].evidence))
    throw new Error('Cierre temporal sin evidencia o mes abierto');
  const years = presentation.licencias.comparativa.map(r => r.year);
  const common = years.length ? commonCompleteMonths(years, coverage) : [];
  if (years.length && (!common.length || JSON.stringify(common) !== JSON.stringify(presentation.licencias.comparisonMonths)))
    throw new Error('Comparativa sin meses comunes cerrados');
  for (const row of presentation.licencias.comparativa) {
    if (row.total !== filters.rows.filter(r => r.m.startsWith(`${row.year}-`) && common.includes(r.m.slice(5,7))).length)
      throw new Error('Comparativa temporal desajustada');
  }
  for (const derivative of [filters, stats.licencias, presentation.licencias]) {
    if (JSON.stringify(derivative.sourceSnapshot ?? null) !== JSON.stringify(index.sourceSnapshot ?? null))
      throw new Error('Procedencia factual temporal discordante');
  }
  if (!complete.length && (presentation.licencias.coverageStatus !== 'partial' || presentation.licencias.comparativa.length))
    throw new Error('Sin cierre acreditado debe publicarse parcial');
  return { totalRows: index.totalRows, monthlyRows: filters.totalRows, lastCompleteMonth: presentation.lastCompleteMonth };
}
if (process.argv[1] === fileURLToPath(import.meta.url))
  console.log('license-temporal OK:', assertLicenseTemporal(process.argv[2] || fileURLToPath(new URL('../public/data', import.meta.url))));
