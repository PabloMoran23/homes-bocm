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
assert.match(html, /Relato documentado/);
assert.doesNotMatch(html, /Pendiente de identificar|No se identifica el expediente|pendiente_identificar/);
for (const estado of ["completa", "parcial", "pendiente_identificar"]) {
  const info = lib.parseProyectoInfoExtra({ ...base, estado, huecos: "Carencia interna", razonPendiente: "Motivo interno",
    datos: [{ bloque: "programa", etiqueta: "Uso", valor: "Residencial", confianza: "alta", fuenteTipo: "oficial" }] });
  const markup = ["relato", "datos"].map(tab => renderToStaticMarkup(React.createElement(panel.ProyectoInfoTabPanel, { info, tab }))).join("");
  assert.match(markup, /Relato documentado/);
  assert.match(markup, /Residencial/);
  assert.doesNotMatch(markup, /Carencia interna|Motivo interno|Aún no consta|Pendiente de identificar/);
}
assert.equal(lib.parseProyectoInfoExtra({ ...base, resumen: "", estado: "pendiente_identificar", razonPendiente: "Sin información" }), null);
const onlyNews = lib.parseProyectoInfoExtra({ ...base, resumen: "", hallazgos: [{ titulo: "Acuerdo publicado", cuerpo: "El pleno aprobó el plan" }] });
assert.deepEqual(Array.from(panel.proyectoInfoTabs(onlyNews), tab => tab.id), ["prensa"]);
assert.equal(renderToStaticMarkup(React.createElement(panel.ProyectoInfoTabPanel, { info: onlyNews, tab: "datos" })), "");
const newsHtml = renderToStaticMarkup(React.createElement(panel.ProyectoInfoTabPanel, { info: onlyNews, tab: "prensa" }));
assert.match(newsHtml, /Acuerdo publicado/);
assert.doesNotMatch(newsHtml, /Sin recortes/);
const info = lib.parseProyectoInfoExtra({ ...base, tipoEntrada: "planeamiento", datos: [{ bloque: "programa", etiqueta: "Normas", valor: "Condiciones del plan", confianza: "alta", fuenteTipo: "oficial" }] });
const details = renderToStaticMarkup(React.createElement(panel.ProyectoInfoTabPanel, { info, tab: "datos" }));
assert.match(details, /Contenido y condiciones/);
assert.doesNotMatch(details, /Qué se va a construir/);
console.log("Unified investigation reader: public content renders without internal workflow status or empty sections");

const titled = lib.parseProyectoInfoExtra({ ...base,
  titulo: "Estudio de Detalle para la ordenación de la manzana RU.2 del Sector AR Nuevo Tres Cantos (exp. 19PD0001)",
  municipio: "Tres Cantos" });
assert.equal(lib.proyectoTituloPublico(titled), "Estudio de Detalle para la ordenación de la manzana RU.2 del Sector AR Nuevo Tres Cantos");
assert.equal(lib.proyectoTituloPublico(lib.parseProyectoInfoExtra({ ...base, titulo: "Prolongación de calle Rosa dels Vents, en l’Alfàs del Pi", municipio: "L'Alfàs del Pi" })), "Prolongación de calle Rosa dels Vents, en l’Alfàs del Pi");
assert.equal(lib.proyectoTituloPublico(lib.parseProyectoInfoExtra({ ...base, titulo: "Urbanización de la calle Mayor", municipio: "Madrid" })), "Urbanización de la calle Mayor · Madrid");
assert.equal(lib.proyectoTituloPublico(lib.parseProyectoInfoExtra({ ...base, titulo: "ru2memoria.pdf", municipio: "Tres Cantos" })), null);
assert.equal(lib.proyectoTituloPublico(lib.parseProyectoInfoExtra(base)), null);
assert.equal(lib.proyectoTituloPublico(null), null);
assert.equal(lib.proyectoTituloPublico(lib.parseProyectoInfoExtra({ ...base, titulo: "Título formal", municipio: "Madrid", datos: [{bloque:"situacion",clave:"nombre_publico",etiqueta:"Nombre",valor:"Nombre conocido de Madrid",confianza:"alta",fuenteTipo:"oficial"}] })), "Nombre conocido de Madrid");
console.log("Research titles use the identified subject and municipality, preserving fallbacks and removing file names and expediente references");

const sigma = load("../lib/sigma-presentation.ts", name => name === "@/lib/project-display"
  ? load("../lib/project-display.ts") : {});
assert.equal(sigma.sigmaPickDisplayHeadline({ expedienteGrupo: "135/2020/00001", tfigAbrev: "MPG", visorH1: "PGOUM-97", publicTitle: "Plan General de Madrid: modificación en calle Mayor" }).title,
  "Plan General de Madrid: modificación en calle Mayor");
