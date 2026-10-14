import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import ts from "typescript";
const source = readFileSync(new URL("../lib/licencias-dashboard-kpi.ts", import.meta.url), "utf8");
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const mod = { exports: {} }; new Function("exports", code)(mod.exports);
const { computeLicenciasKpi } = mod.exports;
const lic = { seriesByMonthActuacionQue: [
  { month: "2025-01", tipos: [{ id: "local_actividad", count: 10 }] },
  { month: "2026-01", tipos: [{ id: "local_actividad", count: 12 }] },
  { month: "2026-03", tipos: [{ id: "local_actividad", count: 300 }] },
] };
assert.equal(computeLicenciasKpi(lic, "volumen", "1M").pctChange, null);
assert.equal(computeLicenciasKpi(lic, "volumen", "1Y").comparisonAvailable, false);
lic.periodCoverage = Object.fromEntries(["2025-01", "2026-01", "2026-03"].map(m => [m, { status: "complete" }]));
// February is missing: don't compare March with January.
assert.equal(computeLicenciasKpi(lic, "volumen", "1M").pctChange, null);
const ytd = computeLicenciasKpi(lic, "volumen", "1Y");
assert.equal(ytd.value, 12); assert.equal(ytd.previous, 10); assert.equal(ytd.pctChange, 20);
assert.match(ytd.periodLabel, /meses cerrados 01/);
console.log("OK temporal KPI: partial suppression, calendar previous month, matched closed months");
// Render the actual card: partial data has a label and no misleading percentage/vs.
const { createRequire } = await import("node:module");
const require = createRequire(import.meta.url);
const { renderToStaticMarkup } = require("react-dom/server");
const React = require("react");
const cardSource = readFileSync(new URL("../components/madrid/dashboard/LicenciasKpiCard.tsx", import.meta.url), "utf8");
const cardCode = ts.transpileModule(cardSource, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
const cardModule = { exports: {} };
const localRequire = name => name.includes("PeriodToggle") ? { PeriodToggle: () => null } : name.includes("licencias-dashboard-kpi") ? mod.exports : require(name);
new Function("require", "exports", cardCode)(localRequire, cardModule.exports);
const partial = computeLicenciasKpi({ ...lic, periodCoverage: {} }, "volumen", "1M");
const html = renderToStaticMarkup(React.createElement(cardModule.exports.LicenciasKpiCard, { label: "Volumen", hint: "Observado", snapshot: partial, period: "1M", onPeriodChange: () => {} }));
assert.match(html, /parcial/);
assert.match(html, /Sin comparación: cierre no acreditado/);
assert.equal(html.includes("vs "), false);
assert.equal(html.includes("%"), false);
console.log("OK partial KPI UI rendered");
