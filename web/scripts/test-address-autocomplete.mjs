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
const modules = new Map(), navigations = [];
function load(file) {
  if (modules.has(file)) return modules.get(file).exports;
  const module = { exports: {} };
  modules.set(file, module);
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const localRequire = name => {
    if (name === 'next/navigation') return { useRouter: () => ({ push: url => navigations.push(url) }) };
    if (name === 'next/link') return { default: ({ children }) => children };
    if (!name.startsWith('@/') && !name.startsWith('.')) return require(name);
    const base = name.startsWith('.') ? path.resolve(path.dirname(file), name) : path.join(root, name.slice(2));
    return load(fs.existsSync(base) ? base : fs.existsSync(base + '.ts') ? base + '.ts' : base + '.tsx');
  };
  vm.runInThisContext(`(function(require,module,exports){${code}\n})`)(localRequire, module, module.exports);
  return module.exports;
}
const { suggestAddresses, resolveAddress } = load(path.join(root, 'lib/cartociudad.ts'));
if (process.argv.includes('--live')) {
  const cases = [
    ['gran via madrid', /CALLE GRAN VIA, Madrid/i],
    ['gran via 28 madrid', /CALLE GRAN VIA 28, Madrid/i],
    ['passeig de gracia barcelona', /PASEO GRACIA, Barcelona/i],
    ['mantuano 20 madrid', /CALLE MANTUANO 20, Madrid/i],
  ];
  for (const [query, expected] of cases) {
    const items = await suggestAddresses(query);
    assert.match(items[0]?.label || '', expected);
    const location = await resolveAddress(items[0].id, items[0].type);
    assert.ok(location.lat > 27 && location.lng < 5);
    console.log(`${query} → ${items[0].label} (${location.lat.toFixed(5)}, ${location.lng.toFixed(5)})`);
  }
  process.exit(0);
}
const candidate = (id, address, muni = 'Madrid', type = 'portal') => ({ id, type, address, muni, muniCode: muni === 'Madrid' ? '28079' : '30029', postalCode: '28013' });
const originalFetch = global.fetch;
global.fetch = async url => {
  const q = new URL(url).searchParams.get('q');
  const wrong = candidate('wrong', 'GRAN VIA GRAN VIA 27, Mula', 'Mula');
  const exact = candidate('exact', 'CALLE GRAN VIA 28, Madrid');
  return { ok: true, json: async () => q.startsWith('calle ') ? [exact, exact, candidate('other', 'CALLE GRAN VIA 27, Madrid')] : [wrong, candidate('city', 'Madrid', 'Madrid', 'municipio')] };
};
const suggestions = await suggestAddresses('gran via 28 madrid');
assert.equal(suggestions[0].id, 'exact', 'Match both the number and city before fuzzy matches');
assert.equal(suggestions.filter(item => item.id === 'exact').length, 1, 'Deduplicate both query variants');
assert.ok(!suggestions.some(item => item.type === 'municipio'));
global.fetch = async () => ({ ok: true, json: async () => ({ ...candidate('street', 'GRAN VIA', 'Madrid', 'callejero'), lat: 0, lng: 0 }) });
await assert.rejects(() => resolveAddress('street', 'callejero'), /localizar/, 'Unresolved street coordinates must never become 0,0');
global.fetch = async () => ({ ok: false });
await assert.rejects(() => suggestAddresses('gran via madrid'), /disponible/);

// Reproduce old suggestions and selection requests completing after another edit.
global.IS_REACT_ACT_ENVIRONMENT = true;
global.window = { setTimeout, clearTimeout };
const requests = [], selections = [];
global.fetch = (url, options) => new Promise(resolve => requests.push({ url, signal: options.signal, resolve }));
const { AddressAutocomplete } = load(path.join(root, 'components/AddressAutocomplete.tsx'));
function Harness() {
  const [value, setValue] = React.useState('');
  return React.createElement(AddressAutocomplete, { value, onChange: setValue, onSelect: location => { selections.push(location); setValue(location.label); } });
}
let renderer;
await act(async () => { renderer = create(React.createElement(Harness)); });
const input = () => renderer.root.findByType('input');
const type = value => act(async () => input().props.onChange({ target: { value } }));
const settle = () => act(async () => new Promise(resolve => setTimeout(resolve, 380)));
const respond = (request, data, ok = true) => act(async () => request.resolve({ ok, json: async () => data }));
const key = value => act(async () => input().props.onKeyDown({ key: value, nativeEvent: {}, preventDefault() {} }));
await type('gran via madrid'); await settle();
await type('mantuano 20 madrid'); await settle();
assert.equal(requests[0].signal.aborted, true);
await respond(requests[1], [{ id: 'new', type: 'portal', label: 'CALLE MANTUANO 20, Madrid', municipality: 'Madrid', postalCode: '28002' }]);
await respond(requests[0], [{ id: 'old', type: 'callejero', label: 'Resultado obsoleto', municipality: 'Madrid', postalCode: '' }]);
assert.ok(!JSON.stringify(renderer.toJSON()).includes('Resultado obsoleto'));
await key('ArrowDown'); await key('Enter');
assert.ok(requests[2].url.includes('/resolve?'));
await type('calle mayor madrid');
assert.equal(requests[2].signal.aborted, true);
await respond(requests[2], { lat: 40.4, lng: -3.7, label: 'Obsoleto' });
assert.equal(selections.length, 0, 'A stale resolved location must not overwrite the next edit');
await settle();
await respond(requests[3], [{ id: 'mayor', type: 'callejero', label: 'CALLE MAYOR, Madrid', municipality: 'Madrid', postalCode: '' }]);
await key('Enter');
await respond(requests[4], { lat: 40.415, lng: -3.707, municipality: 'Madrid' });
assert.equal(selections[0].label, 'CALLE MAYOR, Madrid');
assert.equal(input().props['aria-expanded'], false);
await act(async () => renderer.unmount());

// Landing consults only selected coordinates and invalidates them after any edit.
const { LandingAddressForm } = load(path.join(root, 'components/LandingAddressForm.tsx'));
await act(async () => { renderer = create(React.createElement(LandingAddressForm)); });
const field = () => renderer.root.findByType(AddressAutocomplete);
const submit = () => renderer.root.findAllByType('button').find(button => button.props.type === 'submit');
assert.equal(submit().props.disabled, true);
await act(async () => field().props.onSelect({ label: 'PASEO GRACIA 43, Barcelona', lat: 41.39, lng: 2.16, municipality: 'Barcelona' }));
await act(async () => renderer.root.findByType('form').props.onSubmit({ preventDefault() {} }));
const url = new URL(navigations[0], 'http://test');
assert.equal(url.pathname,'/boletin/resultados');
assert.equal(url.searchParams.get('lat'), '41.39');
assert.equal(url.searchParams.get('lng'), '2.16');
assert.equal(url.searchParams.get('localidad'), 'Barcelona');
await act(async () => field().props.onChange('Otra dirección'));
assert.equal(submit().props.disabled, true);
await act(async () => renderer.unmount());
global.fetch = originalFetch;
console.log('Address autocomplete: matching, deduplication, errors, stale requests, keyboard selection and landing coordinates passed.');
