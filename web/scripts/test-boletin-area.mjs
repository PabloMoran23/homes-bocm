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
function load(file) {
  if (modules.has(file)) return modules.get(file).exports;
  const module = { exports: {} };
  modules.set(file, module);
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const localRequire = name => {
    if (name === 'next/navigation') return { useSearchParams: () => searchParams };
    if (name === 'next/dynamic') return { default: () => () => null };
    if (name === 'next/link') return { default: ({ children }) => children };
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
await act(async () => input().props.onKeyDown({ key: 'Enter', preventDefault() {} }));
assert.ok(requests[0].url.startsWith('/api/geocode-address?'));
await respond(requests[0], { lat: 40.4, lng: -3.7, label: 'Calle Mayor, Madrid' });
assert.ok(requests[1].url.startsWith('/api/boletin-area?'));
await act(async () => input().props.onChange({ target: { value: 'Otra dirección' } }));
assert.equal(requests[1].signal.aborted, true);
await respond(requests[1], result('Resultado anterior'));
assert.ok(!JSON.stringify(renderer.toJSON()).includes('Resultado anterior'), 'Cancelled results must not overwrite the new address');
await act(async () => renderer.unmount());
requests.length = 0;
searchParams = new URLSearchParams('ndp=123');
await act(async () => { renderer = create(React.createElement(BoletinAreaApp)); });
assert.equal(requests.length, 1);
assert.ok(requests[0].url.includes('/api/boletin-area?') && requests[0].url.includes('ndp=123'), 'NDP links load without a catalogue or geocoder');
await respond(requests[0], result());
assert.equal(input().props.value, 'Dirección de prueba');
await act(async () => renderer.unmount());
console.log('Boletín: cache, immediate search, cancellation and direct NDP loading passed.');
