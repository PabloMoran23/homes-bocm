import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { publishStatisticsScope } from './build-statistics-scope.mjs';
const root=mkdtempSync(join(tmpdir(),'statistics-scope-publish-'));
try {
 const file=join(root,'summary.json');
 const original=JSON.parse(readFileSync(new URL('../public/data/summary.json',import.meta.url),'utf8'));
 delete original.statisticsScope;
 writeFileSync(file,JSON.stringify(original));
 const result=publishStatisticsScope(file), upgraded=JSON.parse(readFileSync(file,'utf8'));
 assert.equal(result.upgraded,true);
 assert.equal(upgraded.statisticsScope.checkedAt,original.generatedAt);
 delete upgraded.statisticsScope;assert.deepEqual(upgraded,original);
 const first=readFileSync(file,'utf8');assert.equal(publishStatisticsScope(file).upgraded,false);assert.equal(readFileSync(file,'utf8'),first);
 const contradictory=JSON.parse(first);contradictory.statisticsScope.denominator.count++;
 writeFileSync(file,JSON.stringify(contradictory));const bad=readFileSync(file,'utf8');
 assert.throws(()=>publishStatisticsScope(file),/denominator mismatch/);assert.equal(readFileSync(file,'utf8'),bad);
 const unknown={...original,buildScope:'unknown'};writeFileSync(file,JSON.stringify(unknown));
 assert.throws(()=>publishStatisticsScope(file),/unknown buildScope/);
 console.log('statistics-scope publication: cached export transition, unchanged source date/counts, idempotence and rejection OK');
}finally{rmSync(root,{recursive:true,force:true});}
