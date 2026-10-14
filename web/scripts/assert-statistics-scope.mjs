import { readFileSync } from "node:fs";
import { assertStatisticsScope } from "../lib/statistics-scope.mjs";
// Optional absolute URL supports the same check after publication, without agents.
const url = process.argv[2];
let summary;
if (url) {
  const response = await fetch(url, { signal: AbortSignal.timeout(15000), cache: "no-store" });
  if (!response.ok) throw new Error(`statistics-scope: HTTP ${response.status}`);
  summary = await response.json();
} else {
  summary = JSON.parse(readFileSync(new URL("../public/data/summary.json", import.meta.url), "utf8"));
}
assertStatisticsScope(summary);
console.log(`statistics-scope OK: ${summary.buildScope}, ${summary.total} anuncios`);
