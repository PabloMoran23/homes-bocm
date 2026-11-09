import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import ts from 'typescript';
const require = createRequire(import.meta.url), root = process.cwd(), modules = new Map();
const municipality = { slug:'ciudad', name:'Ciudad', province:'provincia', center:[-0.12,38.54] };
const archive = { id:'archive', title:'Plan anterior', summary:'Un antecedente sin fecha precisa', status:'Aprobado', researched:false };
let offline = false, features = [];
function load(file) {
  if (modules.has(file)) return modules.get(file).exports;
  const module = {exports:{}}; modules.set(file,module);
  const code = ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
  const localRequire = name => {
    if (name === './project-directory') return {getProjectDirectory:() => ({municipalities:[municipality], generatedAt:'2026-10-01'}), municipalityProjects:() => [archive], municipalityPath:() => '/proyectos/provincia/ciudad', directoryProjectPath:p => `/proyecto/${p.id}`, getDirectoryProject:() => null};
    if (name === './supabase/server') return { getSupabaseServer:() => ({rpc:async name => offline ? {error:{message:'offline'}} : name === 'map_cm_municipios' ? {data:{municipios:[{slug:'pueblo-nuevo',nombre:'Pueblo Nuevo',n:3,centerLng:-.11,centerLat:38.54},{slug:'barcelona',nombre:'Barcelona',n:2026,centerLng:null,centerLat:null,west:2.10,east:2.21,south:41.35,north:41.46}]}} : {data:{points:{features}}}}) };
    if (!name.startsWith('.') && !name.startsWith('@/')) return require(name);
    const base = name.startsWith('.') ? path.resolve(path.dirname(file),name) : path.join(root,name.slice(2));
    return load(fs.existsSync(base) ? base : base+'.ts');
  };
  vm.runInThisContext(`(function(require,module,exports){${code}\n})`)(localRequire,module,module.exports);
  return module.exports;
}
const h = load(path.join(root,'lib/national-area.ts'));
assert.equal(h.resolveAreaMunicipality([municipality], 'Cíudad',38.54,-.12),municipality);
assert.equal(h.resolveAreaMunicipality([municipality], 'Otra ciudad',38.54,-.12),null,'Never assign the nearest municipality when names differ');
assert.equal(h.resolveAreaMunicipality([municipality], 'Ciudad',42,2),null,'Disambiguate distant homonyms');
assert.equal(h.resolveAreaMunicipality([municipality,{...municipality,province:'otra'}], 'Ciudad',38.54,-.12),null,'Do not guess between nearby homonyms');
assert.equal(h.isNationalAreaCard('Plan: memoria.pdf'),false);
assert.equal(h.areaCatalogueText('Plan<br/>del barrio &amp; entorno'), 'Plan del barrio & entorno');
assert.equal(h.isNationalAreaCard('Plan parcial del sector 2'),true);
const point = {type:'Point',coordinates:[-.12,38.54]};
assert.equal(h.hasReliableAreaGeometry({coordSource:'municipio_centroid_jitter'},point),false);
assert.equal(h.hasReliableAreaGeometry({approx:true,coordSource:'portal_geometry_centroid'},point),false);
assert.equal(h.hasReliableAreaGeometry({},point),false);
assert.equal(h.hasReliableAreaGeometry({coordSource:'portal_geometry_centroid'},point),true);
const {loadNationalArea} = load(path.join(root,'lib/load-national-area.ts'));
const uncovered = await loadNationalArea(38.54,-.12,'Sin datos','Dirección',500,12);
assert.equal(uncovered.scope,'uncovered'); assert.equal(uncovered.total,0); assert.equal(uncovered.nearby.length,0);
const barcelona = await loadNationalArea(41.3886,2.1685,'Barcelona','Passeig de Gràcia 4',500,12);
assert.equal(barcelona.scope,'municipal','A municipality with bounds and null centre must remain covered');
assert.equal(barcelona.municipality.name,'Barcelona');
assert.equal(barcelona.municipality.href,'/explore?municipio=barcelona');
assert.equal(barcelona.nearby.length,0,'Municipal bounds must not be presented as project locations');
assert.equal(h.municipalityReference({centerLng:null,centerLat:null,west:null,east:null,south:null,north:null}),null);
const newlyCovered = await loadNationalArea(38.54,-.11,'Pueblo Nuevo','Dirección',500,12);
assert.equal(newlyCovered.municipality.href,'/explore?municipio=pueblo-nuevo','Municipalities added after the static directory remain accessible');
offline = true;
const fallback = await loadNationalArea(38.54,-.12,'Ciudad','Dirección',500,12);
assert.equal(fallback.scope,'municipal'); assert.equal(fallback.liveUnavailable,true);
assert.equal(fallback.history[0].date,null,'Catalogue update is not an event date');
assert.equal(fallback.history[0].href,'/proyecto/archive');
assert.equal(fallback.recent.length,0,'Undated archive does not become recent activity');
offline = false;
const today = new Date().toLocaleDateString('sv-SE',{timeZone:'Europe/Madrid'});
features = [
  {geometry:point,properties:{id:'real',titulo:'Proyecto cercano',municipio:'Ciudad',fecha:today,coordSource:'portal_geometry_centroid'}},
  {geometry:{type:'Polygon',coordinates:[[[-.3,38.3],[.1,38.3],[.1,38.7],[-.3,38.7],[-.3,38.3]]]},properties:{id:'city-rule',titulo:'Regulación municipal',municipio:'Ciudad',fecha:today,coordSource:'portal_geometry_centroid'}},
  {geometry:point,properties:{id:'approx',titulo:'Solo municipal',municipio:'Ciudad',fecha:'2026',coordSource:'municipio_centroid_jitter'}},
];
const near = await loadNationalArea(38.54,-.12,'Ciudad','Dirección',500,12);
assert.equal(near.scope,'nearby'); assert.equal(near.nearby.length,1);
assert.equal(near.nearby[0].id,'real'); assert.equal(near.nearby[0].distanceM,0);
assert.equal(near.recent.length,2,'Keep dated municipal regulations as context, without inventing dates for year-only records');
assert.ok(near.recent.some(p => p.id === 'city-rule' && !p.geometry),'City-wide regulation is preserved without a map outline');
assert.ok(near.history.some(p => p.id === 'approx' && !p.geometry),'Municipal centroids belong only in municipal context');
assert.equal(near.total,3,'Deduplicate multiple queries and respect current eligibility instead of resurrecting static records');
assert.ok(!near.history.some(p => p.id === 'archive'), 'Do not reinsert stale catalogue records after a successful live query');
console.log('National area: municipal resolution, real proximity, undated history, deduplication, coverage and offline fallback passed.');
