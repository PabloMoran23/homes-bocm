import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { webcrypto } from "node:crypto";
import ts from "typescript";

function load(file, globals = {}) {
  const source = ts.transpileModule(fs.readFileSync(new URL(file, import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const exports = {};
  vm.runInNewContext(source, { exports, URL, ...globals }, { filename: file });
  return exports;
}

const seguir = load("../lib/seguir-proyecto.ts");
assert.equal(seguir.normalizeEmail("  Ana@Ejemplo.es "), "ana@ejemplo.es");
assert.equal(seguir.normalizeEmail("no-es-correo"), null);
assert.equal(seguir.firstPlaceName(["", "—", " Madrid "]), "Madrid");

const attribution = seguir.readAttribution(
  "https://homes-urbanismo.es/proyecto/135-2018-00489?utm_source=google&utm_medium=cpc&q=secreto",
  "https://www.google.com/search?q=plan+parcial",
);
assert.equal(JSON.stringify(attribution.utm), JSON.stringify({ utm_source: "google", utm_medium: "cpc" }));
assert.equal(attribution.referrer, "https://www.google.com/search");
assert.equal(seguir.readAttribution("https://homes-urbanismo.es/proyecto/1", "https://homes-urbanismo.es/explore").referrer, null);

const seen = new Set();
assert.equal(seguir.claimOnce(seen, "visto:cabecera"), true);
assert.equal(seguir.claimOnce(seen, "visto:cabecera"), false);
assert.equal(seguir.claimOnce(seen, "visto:pie"), true);

const { sanitizeAnalyticsBatch } = load("../lib/analytics-validation.ts");
const now = Date.now();
function event(name, props) {
  return {
    id: webcrypto.randomUUID(),
    session: webcrypto.randomUUID(),
    page: webcrypto.randomUUID(),
    name,
    path: "/proyecto/135-2018-00489",
    source: "google",
    at: now,
    props,
  };
}
const batch = sanitizeAnalyticsBatch({
  events: [
    event("seguir_visto", { posicion: "cabecera", email: "ana@ejemplo.es" }),
    event("seguir_clic", { posicion: "barra" }),
    event("seguir_alta", { posicion: "pie", proyecto: "135-2018-00489" }),
    event("seguir_segmento", { valor: "Invierto" }),
  ],
}, now);
assert.equal(batch.length, 4);
assert.equal(batch[0].props.posicion, "cabecera");
assert.equal("email" in batch[0].props, false, "Follow events must not keep an email address");
assert.equal(batch[2].props.proyecto, "135-2018-00489");
assert.equal(batch[3].props.valor, "Invierto");
assert.equal(sanitizeAnalyticsBatch({ events: [event("seguir_alta", { posicion: "lateral" })] }, now)[0].props.posicion, "lateral");
assert.equal(sanitizeAnalyticsBatch({ events: [event("seguir_nuevo", { posicion: "pie" })] }, now), null);

const sql = fs.readFileSync(new URL("../../supabase/migrations/20261127120000_seguir_proyecto.sql", import.meta.url), "utf8");
assert.match(sql, /add column if not exists segmento/i);
assert.match(sql, /on conflict \(email, source, context_key\) do nothing/i);
assert.match(sql, /and segmento is null/i);
assert.doesNotMatch(sql, /delete from public\.homes_launch_waitlist/i);
assert.doesNotMatch(sql, /truncate/i);
assert.doesNotMatch(sql, /drop table/i);
assert.match(sql, /add column if not exists aviso/i);
assert.match(sql, /aviso is null or aviso in \('proyecto', 'zona'\)/);

const activo = seguir.resolveSeguirOferta({
  fase: "Aprobación inicial",
  instrumentos: ["Modificación puntual del Plan General", "Calle de Embajadores"],
  distrito: "Centro",
  municipio: "Madrid",
});
assert.equal(activo.aviso, "proyecto");
assert.equal(seguir.seguirCopy(activo.aviso, activo.lugar).titulo, "Sigue este proyecto");
assert.equal(seguir.seguirCopy(activo.aviso, activo.lugar).barra, "Seguir este proyecto");

const cerrado = seguir.resolveSeguirOferta({
  faseNormalizada: "aprobacion_definitiva",
  instrumentos: ["Plan especial de Latina"],
  distrito: "Latina",
  municipio: "Madrid",
});
assert.equal(cerrado.aviso, "zona");
assert.equal(cerrado.lugar, "Latina");
assert.equal(seguir.seguirCopy(cerrado.aviso, cerrado.lugar).titulo, "Avísame de lo nuevo en Latina");
assert.match(seguir.seguirCopy(cerrado.aviso, cerrado.lugar).legal, /novedades urbanísticas en Latina/);
assert.doesNotMatch(seguir.seguirCopy(cerrado.aviso, cerrado.lugar).texto, /fase/);

const plan = seguir.resolveSeguirOferta({
  fase: "Aprobación definitiva",
  instrumentos: ["Plan General de Ordenación Urbana"],
  distrito: "Centro",
  municipio: "Madrid",
});
assert.equal(plan.aviso, "zona");
assert.equal(plan.lugar, null, "A big city's general plan does not name the city");
assert.equal(seguir.seguirCopy(plan.aviso, plan.lugar).titulo, "Avísame de lo nuevo en este barrio");
assert.match(seguir.seguirCopy(plan.aviso, plan.lugar).legal, /novedades urbanísticas en este barrio/);

const planPueblo = seguir.resolveSeguirOferta({
  fase: "Aprobación definitiva",
  instrumentos: ["Plan General de Ordenación Urbana"],
  distrito: "Centro",
  municipio: "Torrelodones",
});
assert.equal(planPueblo.lugar, "Torrelodones", "A small town's general plan names the town");

const cerradoPueblo = seguir.resolveSeguirOferta({ fase: "Aprobación definitiva", instrumentos: ["Plan parcial"], municipio: "Torrelodones" });
assert.equal(cerradoPueblo.lugar, "Torrelodones");
assert.equal(seguir.isCiudadGrande("València"), true);
assert.equal(seguir.isCiudadGrande("Coruña, A"), true);
assert.equal(seguir.isCiudadGrande("Getafe"), false);

const catalogacion = seguir.resolveSeguirOferta({
  faseNormalizada: "en_tramitacion",
  instrumentos: [
    "Plan General de Ordenación Urbana (PGOU)",
    "Subsanación error plan general ordenación urbana",
    "catalogacion_proteccion",
  ],
  municipio: "Madrid",
});
assert.equal(catalogacion.aviso, "proyecto", "A file in process is not treated as the general plan");

const delimitacion = seguir.resolveSeguirOferta({
  faseNormalizada: "gestion",
  instrumentos: ["Plan General de Ordenación Urbana (PGOU)", "Delimitación Unidad de ejecución"],
  ambito: "APE 3.09 Subestación",
  municipio: "Madrid",
});
assert.equal(delimitacion.aviso, "proyecto", "A development unit inside the general plan is still a project");

const codigo = seguir.resolveSeguirOferta({
  fase: "Aprobación definitiva",
  instrumentos: ["Plan especial"],
  ambito: "APE 08.06 Vereda de Ganapanes",
  municipio: "Madrid",
});
assert.equal(codigo.aviso, "zona");
assert.equal(codigo.lugar, null, "A planning code is not a place name, and a big city is not named");

const archivado = seguir.resolveSeguirOferta({
  fase: "Archivado",
  barrio: "APE 16.11",
  distrito: "Chamberí",
  municipio: "Madrid",
});
assert.equal(archivado.lugar, "Chamberí");
assert.equal(seguir.cleanPlaceLabel("VILLA DE VALLECAS"), "Villa de Vallecas");
assert.equal(seguir.cleanPlaceLabel("VARIOS"), null);
assert.equal(seguir.isExpedienteCerrado({ fase: "En tramitación" }), false);

console.log("Seguir proyecto: attribution, once-per-position, analytics props and additive SQL OK");
