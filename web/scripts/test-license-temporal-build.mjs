import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, readFileSync, existsSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { buildMadridLicenciasWeb } from "./build-madrid-licencias.mjs";
import { buildMadridLicenciasFilterRows } from "./build-madrid-licencias-filter-rows.mjs";
import { buildMadridPresentacion } from "./build-madrid-presentacion.mjs";
import { buildMadridDashboardStats } from "./build-madrid-dashboard-stats.mjs";
const dir = mkdtempSync(join(tmpdir(), "homes-license-temporal-"));
const source = join(dir, "source.jsonl");
const out = dir;
const asOf = "2026-10-14";
const writeSource = rows => writeFileSync(source, rows.map(r => JSON.stringify(r)).join("\n"));
const build = async () => {
  await buildMadridLicenciasWeb({ jsonlPath: source, outDir: out, asOf });
  return buildMadridLicenciasFilterRows({ outDir: out, asOf });
};
try {
  writeSource([
    { fecha_concesin: "14/10/2026", anio_dataset: 2026 },
    { fecha_concesin: "2026-10-14", anio_dataset: 2026 },
    { fecha_concesin: "2025-02", anio_dataset: 2025 },
    { fecha_concesin: "2024", anio_dataset: 2024 },
    { anio_dataset: 8202 },
    { fecha_concesin: "2027-01-01", fecha_de_alta: "2025-01-01" },
    { fecha_concesin: "2025-02-31" },
  ]);
  const first = await build();
  assert.equal(first.totalRows, 3);
  assert.deepEqual(first.rows.map(r => r.m), ["2025-02", "2026-10", "2026-10"]);
  assert.equal(existsSync(join(out, "madrid-licencias-8202.json")), false);
  assert.equal(JSON.parse(readFileSync(join(out, "madrid-license-temporal-quarantine.json"))).length, 3);
  const repeated = await build();
  assert.equal(repeated.temporal.inputDigest, first.temporal.inputDigest);
  assert.deepEqual(repeated.rows, first.rows);
  // A high count can never certify source closure.
  writeSource(Array.from({ length: 401 }, () => ({ fecha_concesin: "2025-02-01" })));
  await build();
  writeFileSync(join(out, "madrid-sigma-filter-rows.json"), JSON.stringify({ totalRows: 0, rows: [], options: {} }));
  let presentation = buildMadridPresentacion({ outDir: out });
  assert.equal(presentation.lastCompleteMonth, null);
  assert.equal(presentation.licencias.coverageStatus, "partial");
  assert.deepEqual(presentation.licencias.comparativa, []);
  assert.equal(presentation.licencias.ritmo[0].status, "partial");
  const stats = buildMadridDashboardStats({ outDir: out });
  assert.equal(stats.licencias.coverageStatus, "partial");
  // Source evidence permits only common closed months; corrections invalidate it.
  writeSource([2023, 2024, 2025].map(y => ({ fecha_concesin: `${y}-02-01` })));
  let filters = await build();
  writeFileSync(join(out, "madrid-period-coverage.json"), JSON.stringify({ periods: Object.fromEntries([2023, 2024, 2025].map(y => [`${y}-02`, { status: "complete", sourceClosed: true, paginationComplete: true, evidence: "source close report", inputDigest: filters.temporal.inputDigest }])) }));
  filters = buildMadridLicenciasFilterRows({ outDir: out, asOf });
  presentation = buildMadridPresentacion({ outDir: out });
  assert.deepEqual(presentation.licencias.comparisonMonths, ["02"]);
  assert.deepEqual(presentation.licencias.comparativa.map(r => r.total), [1, 1, 1]);
  writeSource([{ fecha_concesin: "2026-03-01" }]);
  filters = await build();
  assert.equal(existsSync(join(out, "madrid-licencias-2025.json")), false);
  assert.equal(existsSync(join(out, "madrid-licencias-2025.geojson")), false);
  assert.deepEqual(filters.rows.map(r => r.m), ["2026-03"]);
  assert.equal(filters.periodCoverage["2025-02"].status, "partial");
  assert.deepEqual(buildMadridPresentacion({ outDir: out }).licencias.comparativa, []);
  // Malformed source fails; it does not promote a new filter series.
  const before = readFileSync(join(out, "madrid-licencias-filter-rows.json"), "utf8");
  writeFileSync(join(out, "madrid-licencias-2026.json"), "broken");
  assert.throws(() => buildMadridLicenciasFilterRows({ outDir: out, asOf }));
  assert.equal(readFileSync(join(out, "madrid-licencias-filter-rows.json"), "utf8"), before);
  await build();
  assert.equal(buildMadridPresentacion({ outDir: out }).licencias.total, 1);
  console.log("OK temporal build: repeat, correction, partial API, 401 rows, evidence, stale evidence, fail/recover");
} finally { rmSync(dir, { recursive: true, force: true }); }
