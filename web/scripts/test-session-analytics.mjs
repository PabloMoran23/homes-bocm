import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { webcrypto } from "node:crypto";
import ts from "typescript";

function load(file, globals = {}) {
  const source = ts.transpileModule(fs.readFileSync(new URL(file, import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
  const exports = {};
  vm.runInNewContext(source, { exports, ...globals }, { filename: file });
  return exports;
}
const { sanitizeAnalyticsBatch } = load("../lib/analytics-validation.ts");
const now = Date.now();
const event = { id: webcrypto.randomUUID(), session: webcrypto.randomUUID(), page: webcrypto.randomUUID(), name: "boletin_buscar", path: "/boletin", source: "google", at: now, props: { q: "private address", lat: 40.45, distrito: "Hortaleza", resultados: 0, active_seconds: -5 } };
const clean = sanitizeAnalyticsBatch({ consent: true, events: [event] }, now);
assert.equal(clean[0].props.distrito, "Hortaleza");
assert.equal(clean[0].props.resultados, 0);
assert.equal(clean[0].props.active_seconds, 0);
assert.equal("q" in clean[0].props, false);
assert.equal("lat" in clean[0].props, false);
for (const changed of [{ path: "/boletin?q=secret" }, { path: "/admin/analitica" }, { path: "/ubicacion/123" }, { at: now - 90000000 }, { name: "arbitrary" }, { session: "invalid" }]) {
  assert.equal(sanitizeAnalyticsBatch({ consent: true, events: [{ ...event, ...changed }] }, now), null);
}
assert.equal(sanitizeAnalyticsBatch({ consent: false, events: [event] }), null);
assert.equal(sanitizeAnalyticsBatch({ consent: true, events: Array(21).fill(event) }), null);

function storage() {
  const map = new Map();
  return { getItem: k => map.get(k) || null, setItem: (k,v) => map.set(k,v), removeItem: k => map.delete(k), map };
}
let clock = now;
const batches = [];
const localStorage = storage();
const sessionStorage = storage();
const location = { pathname: "/proyecto/demo", hostname: "homes-urbanismo.es" };
const navigator = { webdriver: false, sendBeacon: () => false };
const a = load("../lib/session-analytics.ts", { process: { env: { NEXT_PUBLIC_SESSION_ANALYTICS: "1" } }, window: new EventTarget(), Event, URL, document: { referrer: "https://www.google.com/search?q=private" }, location, navigator, localStorage, sessionStorage, crypto: webcrypto, Date: class extends Date { static now() { return clock; } }, fetch: async (_url,opts) => { batches.push(JSON.parse(opts.body)); return { status: 204 }; } });
a.startAnalyticsPage(); a.recordSessionEvent("document_click"); await a.flushAnalytics();
assert.equal(batches.length, 0, "No measurement before consent");
assert.equal(sessionStorage.map.size, 0, "No session ID before consent");
a.writeConsent("accepted");
// Child effects can send a fiche event before the global page effect.
a.recordSessionEvent("ficha_proyecto_ver", { id: "demo" });
const firstPage = a.startAnalyticsPage();
await a.flushAnalytics();
assert.equal(batches[0].events.filter(e => e.name === "page_view").length, 1, "No double counting on initial effects");
assert.ok(batches[0].events.every(e => e.source === "google"));
assert.ok(batches[0].events.every(e => !JSON.stringify(e).includes("private")));
const firstSession = batches[0].events[0].session;
location.pathname = "/explore";
a.recordPageEngagement(firstPage, { active_seconds: 20, scroll_percent: 50 });
a.startAnalyticsPage(); a.recordSessionEvent("mapa_buscar", { resultados: 0 }); await a.flushAnalytics();
assert.ok(batches[1].events.every(e => e.session === firstSession), "Navigation stays in same session");
assert.equal(batches[1].events[0].path, "/proyecto/demo", "Previous page engagement belongs to previous route");
clock += 31 * 60 * 1000;
a.recordSessionEvent("mapa_seleccionar", { kind: "proyecto" });
a.recordPageEngagement(firstPage, { active_seconds: 1500 });
await a.flushAnalytics();
assert.notEqual(batches[2].events[0].session, firstSession, "Idle session rotates");
assert.equal(batches[2].events.some(e => e.name === "page_engagement"), false, "Old engagement cannot leak to new session");
a.writeConsent("rejected"); a.recordSessionEvent("document_click"); await a.flushAnalytics();
assert.equal(batches.length, 3, "Revocation stops collection");
assert.equal(sessionStorage.map.size, 0);
a.writeConsent("accepted"); navigator.webdriver = true; a.startAnalyticsPage(); await a.flushAnalytics();
assert.equal(batches.length, 3, "Declared automation is excluded");
assert.equal(a.safeAnalyticsPath("/ubicacion/secret?address=private"), "/ubicacion");
console.log("Session analytics: consent, privacy, deduplication, navigation, expiry and bot checks passed.");
