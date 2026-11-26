/**
 * Supabase Storage layout for the web data files (web/public/data/*).
 *
 *   objects/<sha256>.<ext>     content-addressed, never rewritten
 *   manifests/<version>.json   one per release, immutable
 *   manifest.json              pointer to the live release
 *
 * Shared by publish-web-data.mjs (CI, service key) and pull-web-data.mjs
 * (anyone, public bucket). Plain fetch against the Storage REST API.
 */
import { createHash } from "node:crypto";

export const BUCKET = "web-data";
export const MANIFEST_PATH = "manifest.json";
/**
 * Objects are immutable, but browsers reach them through the stable
 * /data/<name> URL (middleware rewrite), and the upstream Cache-Control is
 * what they get. Keep it short so a new release is seen within minutes;
 * revalidating an unchanged object is a cheap 304.
 */
export const OBJECT_CACHE_SECONDS = 300;
export const MANIFEST_CACHE_SECONDS = 60;

/**
 * Files the web serves from /data/*. Same set that used to be committed to
 * git; files outside this list stay local (dev-only outputs of build-data).
 */
const ALLOWED_NAMES = new Set([
  "cm-portal-licencias.geojson",
  "cm-portal-proyectos-poligonos.geojson",
  "cm-portal-proyectos.geojson",
  "landing-map-spotlight.geojson",
  "landing-map-spotlight.json",
  "madrid-dashboard-stats.json",
  "madrid-distritos.geojson",
  "madrid-filter-temporal-quarantine.json",
  "madrid-licencias-filter-rows.json",
  "madrid-licencias-index.json",
  "madrid-licencias-territory-report.json",
  "madrid-license-temporal-quarantine.json",
  "madrid-presentacion.json",
  "madrid-sigma-ad.geojson",
  "madrid-sigma-ambitos-landing.geojson",
  "madrid-sigma-ambitos.geojson",
  "madrid-sigma-bocm-projects.json",
  "madrid-sigma-clasificacion.json",
  "madrid-sigma-filter-rows.json",
  "madrid-sigma-gestion.geojson",
  "madrid-sigma-ip.geojson",
  "madrid-sigma-map-cards.json",
  "madrid-sigma-metrics.json",
  "madrid-sigma-programas.json",
  "madrid-sigma-urbanizacion.geojson",
  "madrid-sigma-visor-slim.json",
  "madrid-sigma.json",
  "projects.json",
  "sector-geometries.geojson",
  "sitemap-projects.json",
  "summary.json",
  "ubicaciones-map.geojson",
  "ubicaciones-search.json",
]);
const ALLOWED_PATTERNS = [/^madrid-licencias-20\d\d\.(geo)?json$/];

export function isPublishedName(name) {
  return ALLOWED_NAMES.has(name) || ALLOWED_PATTERNS.some((re) => re.test(name));
}

export function contentTypeFor(name) {
  return name.endsWith(".geojson") ? "application/geo+json" : "application/json";
}

export function sha256(buf) {
  return createHash("sha256").update(buf).digest("hex");
}

export function objectPathFor(hash, name) {
  const ext = name.endsWith(".geojson") ? "geojson" : "json";
  return `objects/${hash}.${ext}`;
}

/** https://<ref>.supabase.co from env, or derived from the pooler DB URL user. */
export function supabaseUrl(env = process.env) {
  const explicit = env.SUPABASE_URL || env.NEXT_PUBLIC_SUPABASE_URL;
  if (explicit) return explicit.replace(/\/$/, "");
  const db = env.SUPABASE_DB_URL || env.DATABASE_URL;
  if (db) {
    try {
      const user = decodeURIComponent(new URL(db).username);
      const m = /^postgres\.([a-z0-9]{20})$/.exec(user);
      if (m) return `https://${m[1]}.supabase.co`;
      const host = /^db\.([a-z0-9]{20})\.supabase\.co$/.exec(new URL(db).hostname);
      if (host) return `https://${host[1]}.supabase.co`;
    } catch {
      /* fall through */
    }
  }
  throw new Error(
    "Supabase URL unknown: set SUPABASE_URL (or NEXT_PUBLIC_SUPABASE_URL, or SUPABASE_DB_URL with a pooler user).",
  );
}

export function publicUrl(base, path) {
  return `${base}/storage/v1/object/public/${BUCKET}/${path}`;
}

/** Live manifest, or null when nothing has been published yet. */
export async function fetchLiveManifest(base) {
  const res = await fetch(`${publicUrl(base, MANIFEST_PATH)}?t=${Date.now()}`, {
    headers: { "cache-control": "no-cache" },
  });
  if (res.status === 400 || res.status === 404) return null;
  if (!res.ok) throw new Error(`manifest: HTTP ${res.status}`);
  return res.json();
}

function authHeaders(key) {
  const h = { apikey: key };
  // Legacy service_role keys are JWTs; new sb_secret_ keys go in apikey only.
  if (key.startsWith("eyJ")) h.authorization = `Bearer ${key}`;
  return h;
}

export async function uploadObject(base, key, path, body, { contentType, cacheSeconds, upsert }) {
  const res = await fetch(`${base}/storage/v1/object/${BUCKET}/${path}`, {
    method: "POST",
    headers: {
      ...authHeaders(key),
      "content-type": contentType,
      "cache-control": `max-age=${cacheSeconds}`,
      "x-upsert": upsert ? "true" : "false",
    },
    body,
  });
  if (res.ok) return "uploaded";
  const text = await res.text();
  // Content-addressed: an existing object already has these bytes.
  if (!upsert && (res.status === 409 || /already exists|Duplicate/i.test(text))) return "exists";
  throw new Error(`upload ${path}: HTTP ${res.status} ${text.slice(0, 300)}`);
}

export async function listPrefix(base, key, prefix) {
  const out = [];
  for (let offset = 0; ; offset += 1000) {
    const res = await fetch(`${base}/storage/v1/object/list/${BUCKET}`, {
      method: "POST",
      headers: { ...authHeaders(key), "content-type": "application/json" },
      body: JSON.stringify({ prefix, limit: 1000, offset, sortBy: { column: "name", order: "asc" } }),
    });
    if (!res.ok) throw new Error(`list ${prefix}: HTTP ${res.status} ${(await res.text()).slice(0, 300)}`);
    const page = await res.json();
    out.push(...page.filter((o) => o.id).map((o) => `${prefix}/${o.name}`));
    if (page.length < 1000) return out;
  }
}

export async function removePaths(base, key, paths) {
  for (let i = 0; i < paths.length; i += 100) {
    const res = await fetch(`${base}/storage/v1/object/${BUCKET}`, {
      method: "DELETE",
      headers: { ...authHeaders(key), "content-type": "application/json" },
      body: JSON.stringify({ prefixes: paths.slice(i, i + 100) }),
    });
    if (!res.ok) throw new Error(`delete: HTTP ${res.status} ${(await res.text()).slice(0, 300)}`);
  }
}

/** Run async tasks with a fixed concurrency. */
export async function pool(items, size, fn) {
  const results = new Array(items.length);
  let next = 0;
  async function worker() {
    while (next < items.length) {
      const i = next++;
      results[i] = await fn(items[i], i);
    }
  }
  await Promise.all(Array.from({ length: Math.min(size, items.length) }, worker));
  return results;
}
