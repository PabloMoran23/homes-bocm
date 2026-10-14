import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import { spawnSync } from "node:child_process";
import { createStatisticsScope, assertStatisticsScope, nationalStatisticsScope } from "../lib/statistics-scope.mjs";
const fixture = (buildScope = "full") => {
  const s = { buildScope, generatedAt: "2026-10-14T10:00:00Z", total: 3, totalRelevant: 1, byTipo: [{ name: "Plan especial", count: 3 }], byMunicipio: [{ name: "Madrid", count: 2 }], dateRange: { min: "2025", max: "2026" }, byYear: [{ year: "2025", count: 1 }, { year: "2026", count: 2 }], bySource: [{ name: "bocm", count: 2 }, { name: "dogc", count: 1 }], byTerritorio: [{ name: "Madrid", count: 2 }, { name: "Cataluña", count: 1 }] };
  s.statisticsScope = createStatisticsScope(s);
  return s;
};
const summary = fixture();
assert.equal(nationalStatisticsScope(summary).title, "España · cobertura parcial");
assert.equal(nationalStatisticsScope(summary).denominator.count, 3); // all charts use total, never totalRelevant
assert.equal(nationalStatisticsScope(fixture("madrid-public")), null);
for (const change of [
  (s) => delete s.statisticsScope,
  (s) => s.buildScope = "unknown",
  (s) => s.statisticsScope.coverage = "complete",
  (s) => s.statisticsScope.geography = "España completa",
  (s) => s.total++,
  (s) => s.byYear[0].count++,
  (s) => s.byTerritorio[0].count++,
  (s) => s.byTipo[0].count++,
  (s) => s.bySource[0].name = "other",
  (s) => s.dateRange.min = "2000",
  (s) => s.statisticsScope.checkedAt = "invalid",
  (s) => s.statisticsScope.denominator.count = s.totalRelevant,
]) {
  const bad = structuredClone(summary); change(bad);
  assert.throws(() => assertStatisticsScope(bad), /statistics-scope/);
  assert.equal(nationalStatisticsScope(bad), null);
}
for (const bad of [null, {}, { statisticsScope: {} }, { ...summary, byYear: null }]) assert.equal(nationalStatisticsScope(bad), null);
// A new dataset must regenerate its manifest before it can recover.
const updated = structuredClone(summary);
updated.byYear.push({ year: "2027", count: 1 }); updated.dateRange.max = "2027"; updated.total++;
updated.byTerritorio[0].count++; updated.bySource[0].count++;
assert.equal(nationalStatisticsScope(updated), null);
updated.statisticsScope = createStatisticsScope(updated);
assert.equal(nationalStatisticsScope(updated).denominator.count, 4);
assert.deepEqual(createStatisticsScope(updated), updated.statisticsScope);
const python = spawnSync("python3", ["-c", "import json,sys;sys.path.insert(0,'../db');from statistics_scope import create_statistics_scope;print(json.dumps(create_statistics_scope(json.load(sys.stdin))))"], { input: JSON.stringify(summary), encoding: "utf8", cwd: new URL("..", import.meta.url) });
assert.equal(python.status, 0, python.stderr);
assert.deepEqual(JSON.parse(python.stdout), summary.statisticsScope);
// Exercise the real page adapter and rendered national tab with chart/network imports stubbed.
const require = createRequire(import.meta.url);
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const compile = (path, extra, resolver) => {
  const source = readFileSync(new URL(path, import.meta.url), "utf8");
  const output = ts.transpileModule(source + extra, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText;
  const exports = {};
  runInNewContext(output, { exports, require: resolver, console: { warn() {} } });
  return exports;
};
const adapter = compile("../app/madrid/estadisticas/page.tsx", "\nexports.testAdapter = espanaFromSummary;", (name) => {
  if (name.includes("statistics-scope")) return { nationalStatisticsScope };
  if (name.includes("seo")) return { withCanonical: () => ({}) };
  return {};
}).testAdapter;
assert.equal(adapter(fixture("madrid-public")), null);
assert.equal(adapter({ ...summary, total: 999 }), null);
const view = adapter(summary);
assert.equal(view.anuncios, 3);
assert.equal(view.porAno.reduce((n, r) => n + r.count, 0), view.anuncios);
assert.equal([...view.territorios, ...view.territoriosMenores].reduce((n, r) => n + r.count, 0), view.anuncios);
const Presentation = compile("../components/madrid/dashboard/MadridPresentacion.tsx", "", (name) => {
  if (name === "react") return { ...React, useState: () => ["espana", () => {}] };
  if (name === "react/jsx-runtime") return require(name);
  if (name === "next/dynamic") return () => () => null;
  if (name === "next/link") return function TestLink({ children }) { return React.createElement("a", null, children); };
  return new Proxy({}, { get: () => () => null });
}).MadridPresentacion;
const render = (espana) => renderToStaticMarkup(React.createElement(Presentation, { data: { licencias: { comparativa: [] } }, espana, proyectos: [] }));
const html = render(view);
assert.match(html, /España · cobertura parcial/);
for (const label of ["bocm", "dogc", "Madrid", "Cataluña", "2025", "2026", summary.generatedAt, "Denominador: todos los anuncios publicados"]) assert.ok(html.includes(label), label);
const unavailable = render(adapter(fixture("madrid-public")));
assert.match(unavailable, /España · datos no disponibles/);
assert.match(unavailable, /No hay un resumen con alcance nacional validado/);
assert.doesNotMatch(unavailable, /anuncios publicados en las fuentes incluidas/);
console.log("statistics-scope tests OK: Madrid rejected, actual adapter/render title and denominators, drift, failure/recovery, JS/Python parity");
