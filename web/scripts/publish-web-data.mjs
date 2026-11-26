#!/usr/bin/env node
/**
 * Publish web/public/data/* to Supabase Storage (bucket `web-data`).
 *
 * - Uploads only files whose bytes changed (content-addressed objects).
 * - Files missing locally keep their current published version, so a partial
 *   export (e.g. only sitemap-projects.json) is a valid publish.
 * - Switches the live release by rewriting manifest.json last: readers see
 *   either the old release or the new one, never a mix.
 * - Prunes objects no longer referenced by the last --keep releases.
 *
 * Env: SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_SECRET_KEY), and SUPABASE_URL /
 * NEXT_PUBLIC_SUPABASE_URL / SUPABASE_DB_URL to locate the project.
 *
 * Usage: node scripts/publish-web-data.mjs [--dir public/data] [--dry-run]
 *          [--keep 5] [--source label] [--release-out path.json]
 */
import { existsSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  MANIFEST_CACHE_SECONDS,
  MANIFEST_PATH,
  OBJECT_CACHE_SECONDS,
  contentTypeFor,
  fetchLiveManifest,
  isPublishedName,
  listPrefix,
  objectPathFor,
  pool,
  removePaths,
  sha256,
  supabaseUrl,
  uploadObject,
} from "./lib/web-data-store.mjs";

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? process.argv[i + 1] : fallback;
}
const dryRun = process.argv.includes("--dry-run");
const dir = resolve(webRoot, arg("dir", "public/data"));
const keep = Math.max(2, Number(arg("keep", "5")));
const source = arg("source", process.env.GITHUB_WORKFLOW ? "ci" : "local");
const releaseOut = arg("release-out", "");

const key = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_SECRET_KEY || "";
if (!key && !dryRun) {
  console.error("publish-web-data: SUPABASE_SERVICE_ROLE_KEY is required (or use --dry-run).");
  process.exit(1);
}
const base = supabaseUrl();

if (!existsSync(dir)) {
  console.error(`publish-web-data: ${dir} does not exist.`);
  process.exit(1);
}

const local = readdirSync(dir)
  .filter((name) => isPublishedName(name) && statSync(join(dir, name)).isFile())
  .sort()
  .map((name) => {
    const body = readFileSync(join(dir, name));
    if (body.length === 0) throw new Error(`${name} is empty; refusing to publish it.`);
    // A truncated export must fail here, not in the browser.
    JSON.parse(body.toString("utf8"));
    const hash = sha256(body);
    return { name, body, hash, bytes: body.length, path: objectPathFor(hash, name) };
  });

const live = await fetchLiveManifest(base);
const previous = live?.files ?? {};

const files = { ...previous };
const changed = [];
for (const f of local) {
  if (previous[f.name]?.sha256 !== f.hash) changed.push(f);
  files[f.name] = { path: f.path, sha256: f.hash, bytes: f.bytes, contentType: contentTypeFor(f.name) };
}
const sortedFiles = Object.fromEntries(Object.keys(files).sort().map((k) => [k, files[k]]));
const totalBytes = Object.values(sortedFiles).reduce((s, f) => s + f.bytes, 0);
const uploadBytes = changed.reduce((s, f) => s + f.bytes, 0);

console.log(
  `publish-web-data: ${local.length} local files, ${changed.length} changed ` +
    `(${(uploadBytes / 1048576).toFixed(1)} MB), release total ${(totalBytes / 1048576).toFixed(1)} MB` +
    (live ? `, live ${live.version}` : ", nothing published yet"),
);
for (const f of changed) console.log(`  ~ ${f.name} (${(f.bytes / 1048576).toFixed(2)} MB)`);

if (changed.length === 0) {
  console.log("publish-web-data: no changes; live release kept.");
  process.exit(0);
}

const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z");
const fingerprint = sha256(Buffer.from(JSON.stringify(sortedFiles))).slice(0, 10);
const version = `${stamp}-${fingerprint}`;
const manifest = {
  version,
  publishedAt: new Date().toISOString(),
  previousVersion: live?.version ?? null,
  source,
  gitSha: process.env.GITHUB_SHA || null,
  runId: process.env.GITHUB_RUN_ID || null,
  files: sortedFiles,
};

if (dryRun) {
  console.log(`publish-web-data: dry run, would publish ${version}.`);
  process.exit(0);
}

await pool(changed, 4, async (f) => {
  const r = await uploadObject(base, key, f.path, f.body, {
    contentType: contentTypeFor(f.name),
    cacheSeconds: OBJECT_CACHE_SECONDS,
    upsert: false,
  });
  console.log(`  ${r === "exists" ? "=" : "+"} ${f.path} ← ${f.name}`);
});

const manifestBody = Buffer.from(JSON.stringify(manifest, null, 2));
await uploadObject(base, key, `manifests/${version}.json`, manifestBody, {
  contentType: "application/json",
  cacheSeconds: 31536000,
  upsert: false,
});
// Last write: this is the switch to the new release.
await uploadObject(base, key, MANIFEST_PATH, manifestBody, {
  contentType: "application/json",
  cacheSeconds: MANIFEST_CACHE_SECONDS,
  upsert: true,
});
console.log(`publish-web-data: live release is now ${version}.`);

if (releaseOut) {
  writeFileSync(
    releaseOut,
    JSON.stringify({
      version,
      source,
      git_sha: manifest.gitSha,
      run_id: manifest.runId,
      file_count: Object.keys(sortedFiles).length,
      changed_files: changed.map((f) => f.name),
      total_bytes: totalBytes,
      uploaded_bytes: uploadBytes,
    }),
  );
}

// Prune: keep every object referenced by the newest `keep` manifests.
try {
  const manifestPaths = (await listPrefix(base, key, "manifests")).sort();
  const kept = manifestPaths.slice(-keep);
  const referenced = new Set();
  for (const p of kept) {
    const res = await fetch(`${base}/storage/v1/object/public/web-data/${p}`);
    if (!res.ok) throw new Error(`read ${p}: HTTP ${res.status}`);
    for (const f of Object.values((await res.json()).files ?? {})) referenced.add(f.path);
  }
  for (const f of Object.values(sortedFiles)) referenced.add(f.path);
  const stale = (await listPrefix(base, key, "objects")).filter((p) => !referenced.has(p));
  const oldManifests = manifestPaths.slice(0, -keep);
  if (stale.length || oldManifests.length) {
    await removePaths(base, key, [...stale, ...oldManifests]);
    console.log(`publish-web-data: pruned ${stale.length} objects, ${oldManifests.length} manifests.`);
  }
} catch (err) {
  // The release is already live; pruning retries on the next publish.
  console.warn(`publish-web-data: prune skipped: ${err.message}`);
}
