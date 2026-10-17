import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
function load(path, customRequire = require) {
  const source = ts.transpileModule(fs.readFileSync(new URL(path, import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const exports = {};
  vm.runInNewContext(source, { exports, require: customRequire }, { filename: path });
  return exports;
}
const lib = load("../lib/proyecto-info-extra.ts");
const base = { id: 1, proyectoId: "p1", resumen: "Relato documentado", estado: "completa", datos: [], hallazgos: [] };
assert.equal(lib.parseProyectoInfoExtra(base).estado, "completa");
assert.equal(lib.parseProyectoInfoExtra({ ...base, estado: "parcial" }).estado, "parcial");
const pending = lib.parseProyectoInfoExtra({ ...base, estado: "pendiente_identificar", tipoEntrada: "documento", razonPendiente: "No se identifica el expediente" });
assert.equal(pending.estado, "pendiente_identificar");
assert.equal(pending.razonPendiente, "No se identifica el expediente");
assert.equal(lib.parseProyectoInfoExtra({ ...base, estado: "invalid" }), null);
const panel = load("../components/project-detail/ProyectoInfoExtraPanel.tsx", name => {
  if (name === "@/lib/proyecto-info-extra") return lib;
  if (name.endsWith("TramitacionTimeline")) return { TramitacionTimeline: () => null };
  return require(name);
});
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const html = renderToStaticMarkup(React.createElement(panel.ProyectoInfoTabPanel, { info: pending, tab: "relato" }));
assert.match(html, /Pendiente de identificar/);
assert.match(html, /No se identifica el expediente/);
const info = lib.parseProyectoInfoExtra({ ...base, tipoEntrada: "planeamiento", datos: [{ bloque: "programa", etiqueta: "Normas", valor: "Condiciones del plan", confianza: "alta", fuenteTipo: "oficial" }] });
const details = renderToStaticMarkup(React.createElement(panel.ProyectoInfoTabPanel, { info, tab: "datos" }));
assert.match(details, /Contenido y condiciones/);
assert.doesNotMatch(details, /Qué se va a construir/);
console.log("Unified investigation reader: legacy states, persistent fallback and territorial content render correctly");
