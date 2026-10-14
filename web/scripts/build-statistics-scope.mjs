/** Upgrade cached summary metadata through the same contract as fresh exports.
 * No dates, counts, sources or geography are inferred or rewritten. Existing
 * manifests must validate: regeneration must not repair a contradictory one.
 */
import { readFileSync, writeFileSync, renameSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createStatisticsScope, assertStatisticsScope } from '../lib/statistics-scope.mjs';
export function publishStatisticsScope(path) {
  const text = readFileSync(path, 'utf8');
  const summary = JSON.parse(text);
  if (Object.hasOwn(summary, 'statisticsScope')) {
    assertStatisticsScope(summary);
    return { upgraded: false, checkedAt: summary.statisticsScope.checkedAt };
  }
  const statisticsScope = createStatisticsScope(summary);
  const candidate = { ...summary, statisticsScope };
  assertStatisticsScope(candidate);
  const temporary = path + '.scope.tmp';
  writeFileSync(temporary, JSON.stringify(candidate, null, 2) + '\n');
  renameSync(temporary, path);
  return { upgraded: true, checkedAt: statisticsScope.checkedAt };
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const path = process.argv[2] ? resolve(process.argv[2]) : fileURLToPath(new URL('../public/data/summary.json', import.meta.url));
  console.log('statistics-scope publication: ' + JSON.stringify(publishStatisticsScope(path)));
}
