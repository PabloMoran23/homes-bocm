import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parseLicenseDate, parseMonthKey, licenseTemporal } from "./lib/license-dates.mjs";
import { periodCoverage, commonCompleteMonths } from "./lib/period-coverage.mjs";
const cases = JSON.parse(readFileSync(new URL("../../tests/license-date-cases.json", import.meta.url)));
for (const row of cases) {
  const actual = parseLicenseDate(row.raw, { asOf: "2026-10-14", meaning: row.meaning });
  assert.equal(actual.value, row.value ?? null, String(row.raw));
  assert.equal(actual.precision, row.precision ?? null, String(row.raw));
  assert.equal(actual.reason, row.reason ?? null, String(row.raw));
}
const opts = { asOf: "2026-10-14" };
assert.equal(parseMonthKey("2026-10-14", null, opts), "2026-10");
assert.equal(parseMonthKey("14/10/2026", null, opts), "2026-10");
assert.equal(parseMonthKey("2025", "2025-01-01", opts), null);
assert.equal(parseMonthKey("2027-01-01", "2025-01-01", opts), null);
assert.equal(licenseTemporal({ anioDataset: 8202 }, opts).year, null);
assert.equal(licenseTemporal({ fechaAlta: "2025-01-01", temporal: { fields: { fecha_concesion: { raw: "2027-01-01" } } } }, opts).month, null);
const proof = { status: "complete", sourceClosed: true, paginationComplete: true, inputDigest: "abc", evidence: "source report 42" };
const coverage = periodCoverage(["2025-01", "2026-10"], { periods: { "2025-01": proof, "2026-10": proof } }, { inputDigest: "abc", asOf: "2026-10-14" });
assert.equal(coverage["2025-01"].status, "complete");
assert.equal(coverage["2026-10"].status, "partial");
assert.equal(periodCoverage(["2025-01"], { periods: { "2025-01": proof } }, { inputDigest: "changed", asOf: "2026-10-14" })["2025-01"].status, "partial");
assert.deepEqual(commonCompleteMonths([2024, 2025], coverage), []);
console.log(`OK temporal contracts: ${cases.length} shared fixtures, precision, quarantine, future meaning and closure evidence`);
