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
const cache = new Map();
function load(file) {
  if (cache.has(file)) return cache.get(file).exports;
  const record = { exports: {} }; cache.set(file, record);
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const localRequire = name => {
    if (!name.startsWith('@/')) return require(name);
    const base = path.join(root, name.slice(2));
    return load(fs.existsSync(base + '.ts') ? base + '.ts' : base + '.tsx');
  };
  vm.runInThisContext(`(function(require,module,exports){${code}\n})`)(localRequire, record, record.exports);
  return record.exports;
}
global.IS_REACT_ACT_ENVIRONMENT = true;
const { MapCatalogPanel } = load(path.join(root, 'components/map/MapCatalogPanel.tsx'));
const { buildPortalMapSpotlightItem, buildLicenseMapSpotlightItem } = load(path.join(root, 'lib/map-project-spotlight.ts'));
const events = [];
const item = buildPortalMapSpotlightItem({ approx: true, id: 'project-1', municipio: 'Madrid', titulo: 'Parque de prueba', resumen: 'Resumen del proyecto', supM2: 1200, fecha: '2024-10-02' });
const callback = name => value => events.push([name, value]);
const props = {
  open: true, onOpen: callback('open'), onClose: callback('close'), municipality: 'Madrid', onChangeMunicipality: callback('municipality'),
  items: [item], selectedId: item.id, onSelect: callback('select'), query: '', onQuery: callback('query'),
  category: '', onCategory: callback('category'), categories: [item.categoryLabel], totalLoaded: 100,
  meta: { proyectosEnRango: 1240 }, loading: false, error: null, showProjects: true, onToggleProjects: callback('projects'),
  showLicenses: false, onToggleLicenses: callback('licenses'), from: '', to: '', onFrom: callback('from'), onTo: callback('to'), others: [],
};
let renderer;
await act(async () => { renderer = create(React.createElement(MapCatalogPanel, props)); });
assert.ok(JSON.stringify(renderer.toJSON()).includes((1240).toLocaleString('es-ES')));
assert.ok(JSON.stringify(renderer.toJSON()).includes('100'));
assert.ok(JSON.stringify(renderer.toJSON()).includes('Ubicación aproximada'), 'approximate projects are visible and labelled in the main catalog');
const buttons = () => renderer.root.findAllByType('button');
const text = node => node.children.filter(c => typeof c === 'string').join('');
const resizeHandle = () => buttons().find(b => ["Ampliar panel", "Reducir panel"].includes(b.props['aria-label']));
assert.equal(resizeHandle().props['aria-expanded'], false);
await act(async () => resizeHandle().props.onClick());
assert.equal(resizeHandle().props['aria-expanded'], true);
await act(async () => {
  resizeHandle().props.onPointerDown({ clientY: 300, pointerId: 1, currentTarget: { setPointerCapture() {} } });
  resizeHandle().props.onPointerUp({ clientY: 420 });
});
assert.equal(resizeHandle().props['aria-expanded'], false, 'drag down reduces the sheet');
await act(async () => resizeHandle().props.onClick());
assert.equal(resizeHandle().props['aria-expanded'], false, 'click after drag must not reopen the sheet');
const projectButton = buttons().find(b => b.findAllByType('h4').length);
assert.equal(projectButton.props['aria-pressed'], true);
await act(async () => projectButton.props.onClick());
assert.deepEqual(events.pop(), ['select', item.id]);
await act(async () => buttons().find(b => text(b).startsWith('Filtros')).props.onClick());
assert.equal(renderer.root.findAllByType('input').filter(i => i.props.type === 'date').length, 2);
await act(async () => renderer.root.findByType('select').props.onChange({ target: { value: item.categoryLabel } }));
assert.deepEqual(events.pop(), ['category', item.categoryLabel]);
await act(async () => renderer.update(React.createElement(MapCatalogPanel, { ...props, open: false })));
assert.equal(renderer.root.findAllByType('aside').length, 0);
await act(async () => renderer.root.findByType('button').props.onClick());
assert.equal(events.pop()[0], 'open');
await act(async () => renderer.update(React.createElement(MapCatalogPanel, { ...props, items: [], query: 'missing' })));
assert.ok(JSON.stringify(renderer.toJSON()).includes('No hay proyectos para estos filtros'));
await act(async () => renderer.update(React.createElement(MapCatalogPanel, { ...props, municipality: 'Alcobendas', showLayerControls: false })));
assert.equal(buttons().filter(b => ['Proyectos', 'Licencias'].includes(text(b).replace('✓ ', ''))).length, 0);
const license = buildLicenseMapSpotlightItem({ ndp: '123/45', direccion: 'Calle de prueba 4', distrito: 'Centro', barrio: 'Sol', licencias: 3, sigma: 2, ultimaLicenciaTipo: 'Licencia urbanística', ultimaLicenciaObjeto: 'Reforma de edificio', ultimaLicenciaUso: 'Residencial', ultimaLicenciaFecha: '2024-10-02' });
assert.equal(license.href, '/ubicacion/123%2F45');
assert.equal(license.title, 'Calle de prueba 4');
assert.equal(license.dateMetricLabel, 'Última licencia');
assert.equal(license.extraMetrics.length, 2);
assert.ok(license.resumen.includes('Reforma de edificio'));
assert.ok(license.badgeIcon.svg.includes('<svg'));
const { raisedMapIconSvg } = load(path.join(root, 'lib/map-raised-project-icon.ts'));
const glyph = raisedMapIconSvg({ ...license.badgeIcon, ring: '#123456' });
assert.ok(glyph.includes('stroke-width="1.7"'), 'preserve glyph stroke widths');
assert.ok(glyph.includes('translate(13 11) scale(.91667)'), 'glyph has an explicit readable size');
const { approximateProjectIconSvg } = load(path.join(root, 'lib/map-raised-project-icon.ts'));
const compact = approximateProjectIconSvg('generico');
assert.ok(compact.includes('width="80" height="104"'));
assert.ok(compact.includes('stroke-dasharray="3 2"'), 'approximate badge is visibly distinct');
await act(async () => renderer.unmount());
console.log('PASS: catalog selection and filters, Madrid-only layer controls, license card data and raised icons.');
