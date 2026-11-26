#!/usr/bin/env node
/**
 * npm prebuild.
 *
 * public/data/ is no longer in git: production reads it from Supabase Storage
 * (lib/web-data.ts). Steps that read or check those files run only when a
 * local copy exists (CI after build-data, or `npm run pull-data`). CI runs
 * them before `npm run publish-data`, so every published release passed them.
 */
import { execSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const run = (cmd, env = process.env) => execSync(cmd, { stdio: "inherit", cwd: webRoot, env });
const hasData = () => existsSync(join(webRoot, "public/data/summary.json"));

const assertData = () => {
  run("node scripts/assert-license-territory.mjs");
  run("node scripts/assert-license-temporal.mjs");
  run("node scripts/assert-map-geo.mjs");
  run("node scripts/assert-statistics-scope.mjs");
};

run("node scripts/test-license-dates.mjs");
run("node scripts/test-statistics-scope.mjs");

if (process.env.SKIP_BUILD_DATA) {
  if (hasData()) {
    run("node scripts/test-statistics-scope-publication.mjs");
    run("node scripts/build-statistics-scope.mjs");
  }
  run("node scripts/copy-maplibre-worker.mjs");
  if (hasData()) {
    assertData();
  } else {
    console.log("prebuild: no local public/data; the site reads the live release from Supabase Storage.");
  }
} else {
  if (hasData()) {
    run("node scripts/test-statistics-scope-publication.mjs");
    run("node scripts/build-statistics-scope.mjs");
  }
  run("node scripts/copy-maplibre-worker.mjs");
  const env = { ...process.env };
  if (env.NEXT_PUBLIC_EDITION === "public" && !env.BUILD_DATA_SCOPE) env.BUILD_DATA_SCOPE = "madrid-public";
  run("npm run build-data", env);
  run("node scripts/assert-license-temporal.mjs");
  run("node scripts/assert-map-geo.mjs");
  run("node scripts/assert-statistics-scope.mjs");
}
