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
let searchParams = new URLSearchParams();
const navigations = [];
const router = { push:url => navigations.push(url), replace:url => navigations.push(url) };
function load(file) {
  if (modules.has(file)) return modules.get(file).exports;
  const module = { exports: {} };
  modules.set(file, module);
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const localRequire = name => {
    if (name === 'next/navigation') return { useSearchParams: () => searchParams, useRouter:() => router };
    if (name === 'next/dynamic') return { default: () => () => null };
    if (name === 'next/link') return { default: ({ children }) => children };
    if (name === '@/components/area/NationalAreaExperience') return { NationalAreaExperience: ({ data }) => React.createElement('section', null, data.municipality?.name || 'Sin cobertura') };
    if (name === '@/components/area/AreaExperience') return { AreaExperience: ({ data }) => React.createElement('section', null, data.center.direccion) };
    if (name === '@/lib/analytics') return { trackEvent() {} };
    if (!name.startsWith('@/') && !name.startsWith('.')) return require(name);
    const base = name.startsWith('.') ? path.resolve(path.dirname(file), name) : path.join(root, name.slice(2));
    return load(fs.existsSync(base) ? base : fs.existsSync(base + '.ts') ? base + '.ts' : base + '.tsx');
  };
  vm.runInThisContext(`(function(require,module,exports){${code}\n})`)(localRequire, module, module.exports);
  return module.exports;
}
const cache = load(path.join(root, 'lib/boletin-area-cache.ts'));
const coords = { lat: 40.41541, lng: -3.7074, radiusM: 500, months: 12 };
assert.notEqual(cache.boletinAreaCacheKey(coords), cache.boletinAreaCacheKey({ ...coords, lat: 40.41549 }), 'Nearby centers must not share results');
for (let i = 0; i <= 200; i++) cache.writeBoletinAreaCache(`test-${i}`, { i });
assert.equal(cache.readBoletinAreaCache('test-0'), null, 'Cache is bounded before entries expire');
assert.equal(cache.readBoletinAreaCache('test-200').i, 200);
// Deferred requests reproduce responses arriving after the user changes address.
global.IS_REACT_ACT_ENVIRONMENT = true;
global.window = { setTimeout, clearTimeout, matchMedia: () => ({ matches: false }) };
const requests = [];
global.fetch = (url, options = {}) => new Promise(resolve => requests.push({ url, signal: options.signal, resolve }));
const result = (direccion = 'Dirección de prueba') => ({
  center: { lat: 40.4, lng: -3.7, direccion, ndp: '123', distrito: '', barrio: '' },
  params: { radiusM: 500, months: 12 },
  stats: { licencias: 0, expedientesSigma: 0, eventos: 0 },
  licencias: [], expedientesSigma: [], timeline: [],
});
const respond = async (request, data) => act(async () => request.resolve({ ok: true, json: async () => data }));
const { BoletinAreaApp } = load(path.join(root, 'components/BoletinAreaApp.tsx'));
let renderer;
await act(async () => { renderer = create(React.createElement(BoletinAreaApp)); });
assert.equal(requests.length, 0, 'Mount must not download the address catalogue');
const input = () => renderer.root.findByType('input');
const searchButton = () => renderer.root.findAllByType('button').find(b => ['Buscar dirección', 'Buscar', 'Buscando…'].includes(b.props.children));
await act(async () => input().props.onChange({ target: { value: 'Calle Mayor 12' } }));
assert.equal(searchButton().props.disabled, false, 'Search does not wait for suggestions');
await act(async () => input().props.onKeyDown({ key: 'Enter', nativeEvent: {}, preventDefault() {} }));
assert.ok(requests[0].url.startsWith('/api/geocode-address?'));
await act(async () => input().props.onChange({ target: { value: 'Otra dirección' } }));
assert.equal(requests[0].signal.aborted, true);
await respond(requests[0], { lat:40.4,lng:-3.7,label:'Resultado anterior' });
assert.equal(navigations.length,0,'Cancelled geocoding must not navigate');
await act(async () => searchButton().props.onClick());
await respond(requests[1], {lat:40.4,lng:-3.7,label:'Calle Mayor, Madrid',municipality:'Madrid'});
assert.ok(navigations[0].startsWith('/boletin/resultados?'),'Search opens a dedicated results page');
assert.equal(new URL(navigations[0],'http://test').searchParams.get('lat'),'40.4');
assert.ok(!requests.some(request => request.url.startsWith('/api/boletin-area?')),'Fetch activity only on the results page');
await act(async () => renderer.unmount());
requests.length = 0;
searchParams = new URLSearchParams('ndp=123');
await act(async () => { renderer = create(React.createElement(BoletinAreaApp,{view:'results'})); });
assert.equal(requests.length, 1);
assert.ok(requests[0].url.includes('/api/boletin-area?') && requests[0].url.includes('ndp=123'), 'NDP links load without a catalogue or geocoder');
await respond(requests[0], result());
assert.equal(renderer.root.findAllByType('input').length,0,'Results omit the address search');
assert.ok(JSON.stringify(renderer.toJSON()).includes('Dirección de prueba'));
assert.ok(renderer.root.findAll(node => node.props.href?.startsWith('/boletin?') && node.props.href.includes('edit=1')).length > 0,'Results breadcrumb returns to edit the search');
assert.ok(!JSON.stringify(renderer.toJSON()).includes('Entiende lo que pasa en tu zona'),'Results omit the introductory heading');
await act(async () => renderer.unmount());
console.log('Boletín: cache, immediate search, cancellation and direct NDP loading passed.');

// A chosen autocomplete result must be used directly, without geocoding its label again.
requests.length = 0;
searchParams = new URLSearchParams();
await act(async () => { renderer = create(React.createElement(BoletinAreaApp)); });
const { AddressAutocomplete } = load(path.join(root, 'components/AddressAutocomplete.tsx'));
await act(async () => renderer.root.findByType(AddressAutocomplete).props.onSelect({ lat: 40.42023, lng: -3.70197, label: 'Gran Vía 28, Madrid', municipality: 'Madrid' }));
await act(async () => searchButton().props.onClick());
assert.equal(requests.length,0,'Chosen coordinates navigate without a redundant request');
assert.equal(new URL(navigations.at(-1),'http://test').pathname,'/boletin/resultados');
assert.equal(new URL(navigations.at(-1),'http://test').searchParams.get('lat'),'40.42023');
await act(async () => renderer.unmount());

// Landing links preserve the actual selected coordinates, not an approximate second lookup.
requests.length = 0;
searchParams = new URLSearchParams({ q: 'Gran Vía 28, Madrid', lat: '40.42023', lng: '-3.70197', localidad: 'Madrid',radiusM:'800',months:'24' });
await act(async () => { renderer = create(React.createElement(BoletinAreaApp,{view:'results'})); });
assert.equal(requests.length, 1);
assert.ok(requests[0].url.startsWith('/api/boletin-area?'));
assert.equal(new URL(requests[0].url,'http://test').searchParams.get('radiusM'),'800');
assert.equal(new URL(requests[0].url,'http://test').searchParams.get('months'),'24');
await act(async () => renderer.unmount());

// National address search must not imply that Madrid-only activity data covers other cities.
requests.length = 0;
searchParams = new URLSearchParams({ q: 'Passeig de Gràcia 43, Barcelona', lat: '41.3917', lng: '2.1649', localidad: 'Barcelona' });
await act(async () => { renderer = create(React.createElement(BoletinAreaApp,{view:'results'})); });
assert.equal(requests.length, 1, 'National search must query municipal coverage');
assert.ok(requests[0].url.startsWith('/api/boletin-area/national?'));
assert.equal(new URL(requests[0].url, 'http://test').searchParams.get('municipality'), 'Barcelona');
await respond(requests[0], { center:{lat:41.39,lng:2.16,label:'Barcelona'}, municipality:{name:'Barcelona'}, radiusM:500, months:12 });
assert.ok(JSON.stringify(renderer.toJSON()).includes('Barcelona'));
await act(async () => renderer.unmount());
console.log('Autocomplete: chosen coordinates, landing handoff and national coverage messaging passed.');

// Returning through the breadcrumb preserves the query without running it again.
requests.length = 0;
searchParams = new URLSearchParams({q:'Gran Vía 28, Madrid',lat:'40.42023',lng:'-3.70197',localidad:'Madrid',edit:'1',radiusM:'800',months:'24'});
await act(async () => { renderer = create(React.createElement(BoletinAreaApp)); });
assert.equal(input().props.value,'Gran Vía 28, Madrid');
assert.equal(requests.length,0);
await act(async () => searchButton().props.onClick());
assert.equal(requests.length,0,'Breadcrumb handoff keeps resolved coordinates');
assert.equal(new URL(navigations.at(-1),'http://test').searchParams.get('radiusM'),'800');
await act(async () => renderer.unmount());
console.log('Area routes: separate results, breadcrumb return, coordinate handoff and filters passed.');
