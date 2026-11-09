import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import React from 'react';
import { create, act } from 'react-test-renderer';
const require = createRequire(import.meta.url);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const modules = new Map();
const point = [-3.7, 40.42];
const square = (x, y, delta) => [[x-delta,y-delta],[x+delta,y-delta],[x+delta,y+delta],[x-delta,y+delta],[x-delta,y-delta]];
const feature = (group, geometry, properties = {}) => ({ type: 'Feature', geometry, properties: { EXP_TX_NUMERO: group, EXP_TX_DENOM: `Proyecto ${group}`, FAS_TX_DENOM: 'Aprobación Definitiva', ...properties } });
const large = feature('135/2000/00001', { type: 'Polygon', coordinates: [square(point[0] + .015, point[1], .02)] }, { FEX_DT_APROB: Date.UTC(2001,0,1) });
const undated = feature('135/2026/00002', { type: 'Point', coordinates: point });
const future = feature('135/2099/00003', { type: 'Point', coordinates: point }, { FEX_DT_APROB: Date.UTC(2099,0,1) });
let live = { features: [] }, offline = false;
let requests = [];
const staticFeatures = [large, undated, future, undated];
function load(file) {
  if (modules.has(file)) return modules.get(file).exports;
  const module = { exports: {} }; modules.set(file, module);
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 } }).outputText;
  const localRequire = name => {
    if (name.endsWith('.module.css')) return { default: {} };
    if (name === './fetch-static-json') return { fetchStaticJson: async url => url.includes('ambitos.geojson') ? { features: staticFeatures } : url.includes('visor-slim') ? { byGrupoExpediente: { '135/2026/00002': { tramitacion: [{ fecha: '2026', tramite: 'Aprobación Inicial', organo: null }] } } } : { byExpediente: {} } };
    if (name === './project-directory') return { getDirectoryProject: group => group === '135/2000/00001' ? { id: 'canonical', title: 'Nombre público de la ficha', summary: 'Resumen compartido con la ficha', researched: true } : null, directoryProjectPath: record => `/proyecto/${record.id}` };
    if (name === './supabase/server') return { getSupabaseServer: () => ({ rpc: async () => { if (offline) throw new Error('offline'); return { data: live, error: null }; } }) };
    if (name === 'next/dynamic') return { default: () => () => null };
    if (name === 'next/link') return { default: ({ children }) => children };
    if (!name.startsWith('@/') && !name.startsWith('.')) return require(name);
    const base = name.startsWith('.') ? path.resolve(path.dirname(file), name) : path.join(root, name.slice(2));
    return load(fs.existsSync(base) ? base : fs.existsSync(base + '.ts') ? base + '.ts' : base + '.tsx');
  };
  vm.runInThisContext(`(function(require,module,exports){${code}\n})`)(localRequire, module, module.exports);
  return module.exports;
}
const { summarizeMonthlyLicenses } = load(path.join(root, 'lib/area-monthly.ts'));
const monthlyFeature = (date, code, coords = point) => ({ geometry: { coordinates: coords }, properties: { fecha_concesion: date, actuacion_que: code } });
const monthly = summarizeMonthlyLicenses([
  monthlyFeature('2026-10-02', 'local_obra'), monthlyFeature('2026-10-31', 'vivienda_obra'),
  monthlyFeature('2026-09-30', 'local_obra'), monthlyFeature('2026-10-15', 'local_obra', [-3,41]),
  monthlyFeature('2026-11-02', 'local_obra'), monthlyFeature('2027-01-01', 'local_obra'),
  monthlyFeature('2026', 'local_obra'),
], point[1], point[0], 500, '2026-11-03',1);
assert.equal(monthly.periodMonths,1);
assert.equal(monthly.total, 2, 'Use rolling dates, exact radius, and concession dates only');
assert.deepEqual(monthly.categories.map(row => row.label).sort(), ['Obras en locales', 'Obras en viviendas']);
const delayed = summarizeMonthlyLicenses([monthlyFeature('2026-04-30', 'local_obra')], point[1], point[0], 500, '2026-11-03');
assert.equal(delayed.periodMonths,12);
assert.equal(delayed.latestDate,'2026-04-30','Keep source freshness separate from the chosen time window');
assert.equal(delayed.total, 1);
const repeated = (date, count) => Array.from({length:count}, () => monthlyFeature(date,'local_obra'));
const adaptive = (older, limit=12) => summarizeMonthlyLicenses([monthlyFeature('2026-10-20','vivienda_obra'),...repeated(older,19)],point[1],point[0],500,'2026-11-03',limit);
assert.equal(adaptive('2026-10-21').periodMonths,1,'Dense areas keep the last month');
assert.equal(adaptive('2026-09-20').periodMonths,3);
assert.equal(adaptive('2026-06-20').periodMonths,6);
assert.equal(adaptive('2026-02-20').periodMonths,12);
assert.equal(adaptive('2025-02-20',24).periodMonths,24);
assert.equal(adaptive('2024-02-20',36).periodMonths,36);
const capped = adaptive('2026-02-20',6);
assert.equal(capped.periodMonths,6,'Never exceed the search period');
assert.equal(capped.total,1,'Older records must not inflate the capped count');
assert.equal(adaptive('2025-02-20',12).total,1,'The 12-month filter excludes older concessions');
const empty = summarizeMonthlyLicenses([monthlyFeature('2024-01-01','local_obra')],point[1],point[0],500,'2026-11-03',12);
assert.equal(empty.total,0); assert.deepEqual(empty.categories,[],'Do not move the time window backwards to manufacture activity');
assert.equal(empty.periodMonths,12);

const helpers = load(path.join(root, 'lib/area-context.ts'));
assert.equal(helpers.areaDate('2024-02-29'), '2024-02-29');
assert.equal(helpers.areaDate('2025-02-29'), null);
assert.equal(helpers.areaDate('31/11/2026'), null);
assert.equal(helpers.areaDate('2026'), null, 'Reference years must not become dated events');
assert.equal(helpers.areaDate('2/3/2026'), '2026-03-02');
assert.equal(helpers.projectMilestones([{ fecha: '2099-01-01', tramite: 'Aprobación', organo: null }], '2026-11-03').length, 0);
assert.equal(helpers.projectMilestones([{ fecha: '22/07/2026', tramite: 'Aprobación Inicial', organo: null }], '2026-11-03', { date: '2026-07-23', phase: 'Aprobación Inicial' }).length, 1, 'Catalogue and detailed record must not become two changes for a one-day timezone discrepancy');
const research = { datos: [
  { bloque: 'cronologia', etiqueta: 'Aprobación inicial e información pública', valor: 'El plan se aprobó el 29 de enero de 2026. El anuncio del BOCM del 10 de marzo de 2026 abrió la información pública.', fuenteNombre: 'Ayuntamiento', fuenteFecha: '2030-01-01' },
  { bloque: 'cronologia', etiqueta: 'Aprobación definitiva', valor: 'El Pleno aprobó el plan el 30 de junio de 2026; el anuncio se publicó en el BOCM el 1 de septiembre de 2026.', fuenteNombre: 'Ayuntamiento', fuenteFecha: '2026-06-30' },
  { bloque: 'cronologia', etiqueta: 'Actuación prevista', valor: 'Está prevista en 2027.', fuenteNombre: null, fuenteFecha: '2026-11-01' },
] };
const researchedEvents = helpers.researchMilestones(research, '2026-11-03');
assert.ok(researchedEvents.some(event => event.date === '2026-01-29' && /inicial/.test(event.label)));
assert.ok(researchedEvents.some(event => event.date === '2026-09-01' && event.label === 'Publicación en BOCM'));
assert.ok(!researchedEvents.some(event => event.date === '2030-01-01' || event.date === '2026-11-01'), 'Do not turn source dates or year-only plans into current events');
const reconciled = helpers.enrichAreaProject({ title: 'Proyecto', summary: '', researched: false, phase: 'Aprobación Inicial', milestones: [{ date: '2026-03-10', label: 'Aprobación Inicial', authority: null }], recent: true }, { title: 'Título completo', summary: 'Resumen de la ficha', phase: 'Aprobación Inicial', info: research, tramites: [] }, '2026-11-03', '2025-11-03');
assert.equal(reconciled.phase, 'Aprobación definitiva', 'A documented later approval must supersede old map catalogue metadata');
assert.equal(reconciled.phaseDate, '2026-06-30');
assert.equal(reconciled.lastMilestone.date, '2026-09-01');
assert.ok(!reconciled.milestones.some(event => event.date === '2026-03-10' && event.label === 'Aprobación Inicial'), 'Publication date must not masquerade as a second approval date');
const proximity = helpers.geometryProximity(large.geometry, ...point);
assert.equal(proximity.distanceM, 0, 'A containing polygon must be retained even when its centroid is outside the radius');
assert.equal(proximity.containsPoint, true);
const hole = { type: 'Polygon', coordinates: [square(...point, .02), square(...point, .005)] };
const inHole = helpers.geometryProximity(hole, ...point);
assert.equal(inHole.containsPoint, false, 'Polygon holes are not part of an affected scope');
assert.ok(inHole.distanceM > 300);
const multipolygon = { type: 'MultiPolygon', coordinates: [[square(...point, .001)], [square(-3, 41, .001)]] };
const clipped = helpers.areaDisplayGeometry(multipolygon, { lng: point[0], lat: point[1], radius: 500 });
assert.equal(clipped.coordinates.length, 1, 'Only nearby components should be transferred to the browser');
assert.equal(multipolygon.coordinates.length, 2, 'Rendering must not mutate the matching geometry');
const ring = Array.from({ length: 1001 }, (_, i) => [point[0]+.01*Math.cos(i/1000*Math.PI*2),point[1]+.01*Math.sin(i/1000*Math.PI*2)]);
ring[1000] = ring[0];
const simplified = helpers.areaDisplayGeometry({ type: 'Polygon', coordinates: [ring] });
assert.ok(simplified.coordinates[0].length < 100);
assert.deepEqual(simplified.coordinates[0][0], simplified.coordinates[0].at(-1), 'Display rings remain closed');
assert.ok(!helpers.areaPhaseHint('Aprobación Definitiva', true).includes('en marcha'));
const { loadAreaContext } = load(path.join(root, 'lib/load-area-context.ts'));
const context = await loadAreaContext(point[1], point[0], 500, 12);
assert.equal(context.total, 3, 'Duplicate geometries from the same expediente must not inflate project counts');
const historical = context.projects.find(project => project.group === '135/2000/00001');
assert.equal(historical.recent, false);
assert.equal(historical.containsPoint, true);
assert.equal(historical.href, '/proyecto/canonical', 'Use the canonical project ficha');
assert.equal(historical.summary, 'Resumen compartido con la ficha');
assert.ok(context.projects.every(project => project.group !== '135/2099/00003' || !project.recent));
assert.equal(context.projects.find(project => project.group === '135/2026/00002').lastMilestone, null);
offline = true;
assert.equal((await loadAreaContext(point[1], point[0], 500, 12)).snapshot, true, 'A live service outage must preserve available historic context');

// Independently loaded context must survive missing data and expose separate license and project views.
global.IS_REACT_ACT_ENVIRONMENT = true;
global.window = { setTimeout, clearTimeout };
global.fetch = (url, options = {}) => new Promise(resolve => requests.push({ url, signal: options.signal, resolve }));
const { AreaExperience } = load(path.join(root, 'components/area/AreaExperience.tsx'));
const data = { center: { lat: point[1], lng: point[0], direccion: 'Dirección de prueba' }, params: { radiusM: 500, months: 12 }, stats: { licencias: 0, expedientesSigma: 0, eventos: 0 }, licencias: [], expedientesSigma: [], timeline: [] };
let renderer;
await act(async () => { renderer = create(React.createElement(AreaExperience, { data })); });
assert.ok(requests[0].url.startsWith('/api/boletin-area/context?'));
await act(async () => requests[0].resolve({ ok: true, json: async () => context }));
assert.ok(JSON.stringify(renderer.toJSON()).includes('Nombre público de la ficha'), 'Historical projects are visible when there are no recent licenses');
const monthlyRequest = requests.find(request => request.url.startsWith('/api/boletin-area/monthly?'));
await act(async () => monthlyRequest.resolve({ ok: true, json: async () => delayed }));
const summaryText = JSON.stringify(renderer.toJSON());
assert.ok(!summaryText.includes('Sin más novedades'), 'Omit cards without real news');
assert.equal(renderer.root.findAll(node => node.props.className === 'area-news-card area-news-license').length, 1, 'Each license category has its own compact card');
assert.ok(summaryText.includes('Obras en locales'));
assert.ok(summaryText.includes('Periodo ampliado automáticamente'));
assert.ok(summaryText.includes('Último año'));
assert.equal(new URL(monthlyRequest.url,'http://test').searchParams.get('months'),'12','Send the search filter to the adaptive summary');
assert.ok(!summaryText.includes('proyectos y expedientes del entorno'), 'Do not lead with opaque catalogue counters');
const tabs = renderer.root.findAll(node => node.props.role === 'tab');
await act(async () => tabs.find(node => node.props.id.endsWith('-licencias-tab')).props.onClick());
assert.ok(JSON.stringify(renderer.toJSON()).includes('No hay licencias recuperadas'));
await act(async () => tabs.find(node => node.props.id.endsWith('-cambios-tab')).props.onClick());
assert.ok(JSON.stringify(renderer.toJSON()).includes('No hay movimientos fechados'));
await act(async () => renderer.unmount());
assert.equal(requests[0].signal.aborted, true);
console.log('Area context: polygon proximity, holes, historical plans, genuine event dates, canonical fichas, lightweight map geometry, fallback and UX views passed.');
