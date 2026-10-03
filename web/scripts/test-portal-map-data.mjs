// Run with: node scripts/test-portal-map-data.mjs
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import React from "react";
import { create, act } from "react-test-renderer";
const requireDependency = createRequire(import.meta.url);
global.IS_REACT_ACT_ENVIRONMENT = true;
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const modules = new Map();
function load(filename) {
  if (modules.has(filename)) return modules.get(filename).exports;
  const record = { exports: {} }; modules.set(filename, record);
  const code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const localRequire = (name) => name.startsWith('@/')
    ? load(path.join(root, name.slice(2) + '.ts')) : requireDependency(name);
  vm.runInThisContext(`(function(require,module,exports){${code}\n})`, { filename })(localRequire, record, record.exports);
  return record.exports;
}
const { usePortalMapData } = load(path.join(root, 'lib/use-portal-map-data.ts'));
const requests = [];
global.fetch = (url, { signal }) => new Promise((resolve) => requests.push({ url, signal, resolve }));
let output;
function Harness(props) {
  const result = usePortalMapData(true, props.selection, props.bounds);
  React.useLayoutEffect(() => { output = result; });
  return null;
}
const selection = { slug: 'madrid', from: '', to: '' };
const bounds = { west: -3.888, south: 40.352, east: -3.52, north: 40.504, zoom: 12 };
const collection = (id) => ({ type: 'FeatureCollection', features: [{ type: 'Feature', geometry: { type: 'Point', coordinates: [-3.7, 40.4] }, properties: { id } }] });
const full = { points: collection('point'), approx: collection('approx'), polygons: collection('full'), meta: { truncated: true, proyectosEnRango: 4598, proyectosAproxTotal: 718 } };
async function reply(request, payload, ok = true) { await act(async () => request.resolve({ ok, json: async () => payload })); }
async function main() {
  let renderer;
  await act(async () => { renderer = create(React.createElement(Harness, { selection, bounds: null })); });
  assert.equal(requests.length, 1);
  await act(async () => renderer.update(React.createElement(Harness, { selection, bounds })));
  assert.equal(requests.length, 1, 'pan cannot cancel/start over the full municipality request');
  assert.equal(requests[0].signal.aborted, false);
  await reply(requests[0], full);
  assert.equal(requests.length, 2);
  assert.equal(output.points.features[0].properties.id, 'point');
  assert.equal(output.polygons.features[0].properties.id, 'full', 'full polygons remain visible while viewport loads');
  await act(async () => renderer.update(React.createElement(Harness, { selection: { ...selection }, bounds: { ...bounds, west: bounds.west + 0.00001 } })));
  assert.equal(requests.length, 2, 'equivalent quantized bounds do not refetch');
  assert.equal(requests[1].signal.aborted, false);
  const zone = { polygons: collection('zone'), points: { ...collection('ignored'), features: [] }, approx: { ...collection('ignored'), features: [] }, meta: { recorteEnVista: true, proyectosEnRango: 1, proyectosAproxTotal: 0, proyectosPoligonos: 1, truncated: true } };
  await reply(requests[1], zone);
  assert.equal(output.polygons.features[0].properties.id, 'zone');
  assert.equal(output.approx.features[0].properties.id, 'approx');
  assert.equal(output.meta.proyectosEnRango, 4598, 'viewport counts must not overwrite municipality totals');
  assert.equal(output.meta.proyectosAproxTotal, 718);
  await act(async () => renderer.update(React.createElement(Harness, { selection, bounds: { ...bounds, east: -3.4 } })));
  assert.equal(requests.length, 3);
  assert.equal(output.polygons.features[0].properties.id, 'zone', 'keep polygons during pan');
  const benidorm = { ...selection, slug: 'benidorm' };
  await act(async () => renderer.update(React.createElement(Harness, { selection: benidorm, bounds })));
  assert.equal(requests[2].signal.aborted, true);
  assert.equal(output.points, null, 'never show previous municipality data');
  await reply(requests[2], zone); // Simulates a late response despite cancellation.
  assert.equal(output.polygons, null);
  await reply(requests[3], { ...full, polygons: collection('benidorm'), meta: { truncated: false } });
  assert.equal(requests.length, 4, 'complete municipalities need no viewport RPC');
  await act(async () => renderer.update(React.createElement(Harness, { selection, bounds })));
  assert.equal(requests.length, 4, 'returning to a cached municipality and viewport needs no request');
  assert.equal(output.polygons.features[0].properties.id, 'zone');
  await act(async () => renderer.update(React.createElement(Harness, { selection, bounds: { ...bounds, zoom: 9 } })));
  assert.equal(output.polygons.features[0].properties.id, 'full', 'zooming out restores municipality polygons');
  const dated = { ...selection, from: '2025-01-01' };
  await act(async () => renderer.update(React.createElement(Harness, { selection: dated, bounds })));
  assert.equal(requests.length, 5);
  assert.equal(output.points, null, 'date changes cannot reuse unfiltered data');
  await reply(requests[4], null, false);
  assert.ok(output.error);
  assert.equal(output.loading, false);
  await act(async () => renderer.update(React.createElement(Harness, { selection: { ...dated, token: 1 }, bounds })));
  assert.equal(requests.length, 6, 'confirming the same selection retries a failed request');
  assert.equal(output.loading, true);
  await reply(requests[5], { ...full, meta: { truncated: false } });
  assert.equal(output.error, null);
  await act(async () => renderer.unmount());
  console.log('PASS: in-flight pan, URL deduplication, independent data, stale response, cache, zoom out, date isolation and errors.');
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
