#!/usr/bin/env node
/**
 * Download the live web data release from Supabase Storage into
 * web/public/data/ (local dev, and CI before regenerating: several export
 * scripts read the previous files).
 *
 * Skips files whose local bytes already match. No key needed: the bucket is
 * public. Exits 0 with a warning when nothing has been published yet.
 *
 * Usage: node scripts/pull-web-data.mjs [--dir public/data] [--only a.json,b.geojson]
 */
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { fetchLiveManifest, pool, publicUrl, sha256, supabaseUrl } from "./lib/web-data-store.mjs";

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? process.argv[i + 1] : fallback;
}
const dir = resolve(webRoot, arg("dir", "public/data"));
const only = arg("only", "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

const base = supabaseUrl();
const manifest = await fetchLiveManifest(base);
if (!manifest) {
  console.warn("pull-web-data: no release published yet; nothing to download.");
  process.exit(0);
}
mkdirSync(dir, { recursive: true });

const entries = Object.entries(manifest.files).filter(([name]) => !only.length || only.includes(name));
let downloaded = 0;
let bytes = 0;
await pool(entries, 6, async ([name, f]) => {
  const target = join(dir, name);
  if (existsSync(target) && sha256(readFileSync(target)) === f.sha256) return;
  const res = await fetch(publicUrl(base, f.path));
  if (!res.ok) throw new Error(`${name}: HTTP ${res.status}`);
  const body = Buffer.from(await res.arrayBuffer());
  if (sha256(body) !== f.sha256) throw new Error(`${name}: checksum mismatch`);
  writeFileSync(`${target}.tmp`, body);
  renameSync(`${target}.tmp`, target);
  downloaded += 1;
  bytes += body.length;
});
writeFileSync(join(dir, ".release"), `${manifest.version}\n`);
console.log(
  `pull-web-data: release ${manifest.version}, ${entries.length} files, ` +
    `${downloaded} downloaded (${(bytes / 1048576).toFixed(1)} MB).`,
);
