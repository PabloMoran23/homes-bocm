#!/usr/bin/env node
/**
 * Comprueba que el árbol local está listo para producción (edición public).
 * Uso: npm run verify:production
 */
import { existsSync, readFileSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { execSync } from "node:child_process";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dataDir = join(root, "public", "data");

const requiredFiles = [
  "madrid-sigma.json",
  "madrid-dashboard-stats.json",
  "madrid-sigma-ambitos-landing.geojson",
  "madrid-licencias-filter-rows.json",
  "madrid-sigma-bocm-projects.json",
  "projects.json",
  "summary.json",
];

let failed = 0;

function ok(msg) {
  console.log(`  ✓ ${msg}`);
}
function fail(msg) {
  console.error(`  ✗ ${msg}`);
  failed += 1;
}

console.log("Homes · verificación producción (edición public)\n");

process.env.NEXT_PUBLIC_EDITION = "public";
process.env.SKIP_BUILD_DATA = "1";

for (const name of requiredFiles) {
  const path = join(dataDir, name);
  if (!existsSync(path)) {
    fail(`Falta ${name}`);
    continue;
  }
  const size = statSync(path).size;
  if (size < 50) {
    fail(`${name} vacío o demasiado pequeño (${size} B)`);
  } else {
    ok(`${name} (${(size / 1e6).toFixed(1)} MB)`);
  }
}

try {
  const stats = JSON.parse(
    readFileSync(join(dataDir, "madrid-dashboard-stats.json"), "utf8"),
  );
  if (!stats.sigma?.total) {
    fail("madrid-dashboard-stats.json sin agregados SIGMA");
  } else {
    ok(
      `Dashboard stats (${stats.generatedAt ?? "?"}): SIGMA ${stats.sigma.total}, licencias ${stats.licencias?.totalRows ?? "n/a"}`,
    );
  }
} catch (e) {
  fail(`madrid-dashboard-stats.json inválido: ${e.message}`);
}

console.log("\nBuild producción (SKIP_BUILD_DATA=1)…");
try {
  execSync("npm run build", {
    cwd: root,
    stdio: "inherit",
    env: { ...process.env, NEXT_PUBLIC_EDITION: "public", SKIP_BUILD_DATA: "1" },
  });
  ok("next build (public)");
} catch {
  fail("next build falló");
}

console.log(failed ? `\n${failed} comprobación(es) fallaron.\n` : "\nListo para desplegar.\n");
process.exit(failed ? 1 : 0);
