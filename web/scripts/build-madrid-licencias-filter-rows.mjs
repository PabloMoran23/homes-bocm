/**
 * Filas compactas para filtrar el dashboard de licencias en cliente.
 */
import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { createHash } from "node:crypto";
import { licenseTemporal, DATE_RULE_VERSION } from "./lib/license-dates.mjs";
import { periodCoverage } from "./lib/period-coverage.mjs";
import { normalizarActuacionEdificio } from "./lib/actuacion-edificio.mjs";
import { labelActuacionQue } from "./lib/actuacion-que-config.mjs";

function normKey(s) {
  return String(s ?? "")
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/-/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function normDistritoKey(name) {
  return normKey(name).replace(/-/g, " ");
}

function titleCase(s) {
  return String(s)
    .split(/\s+/)
    .map((w) => (w.length <= 2 ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
}

/**
 * @param {{ outDir: string }} opts
 */
export function buildMadridLicenciasFilterRows(opts) {
  const { outDir } = opts;
  const rows = [];
  const quarantine = [];
  const inputHash = createHash("sha256").update(DATE_RULE_VERSION);
  const asOf = opts.asOf || new Date().toISOString().slice(0, 10);
  const distritoCounts = new Map();
  const actuacionCounts = new Map();
  const procedimientoCounts = new Map();
  const usoCounts = new Map();

  const files = readdirSync(outDir)
    .map((name) => {
      const m = /^madrid-licencias-(\d{4})\.json$/.exec(name);
      return m ? { year: Number(m[1]), path: join(outDir, name) } : null;
    })
    .filter(Boolean)
    .sort((a, b) => a.year - b.year);

  if (!files.length) {
    console.log("Aviso: sin madrid-licencias-YYYY.json — omitiendo filter-rows");
    return null;
  }

  for (const { path } of files) {
    const content = readFileSync(path, "utf-8");
    inputHash.update(content);
    const batch = JSON.parse(content);
    for (const r of batch) {
      const temporal = licenseTemporal(r, { asOf });
      if (temporal.quarantine.length) quarantine.push({ id: r.id ?? null, fields: temporal.quarantine });
      const month = temporal.month;
      if (!month) continue;

      const act = normalizarActuacionEdificio({
        tipo_expediente: r.tipoExpediente,
        objeto: r.objeto,
        uso: r.uso,
        procedimiento: r.procedimiento,
      });
      const dKey = normDistritoKey(r.distrito) || "_sin_distrito";
      const aKey = act.codigo;
      const pKey = normKey(r.procedimiento) || "_sin_procedimiento";
      const uKey = normKey(r.uso) || "_sin_uso";

      rows.push({ m: month, d: dKey, a: aKey, p: pKey, u: uKey });

      distritoCounts.set(dKey, (distritoCounts.get(dKey) || 0) + 1);
      actuacionCounts.set(aKey, (actuacionCounts.get(aKey) || 0) + 1);
      procedimientoCounts.set(pKey, (procedimientoCounts.get(pKey) || 0) + 1);
      usoCounts.set(uKey, (usoCounts.get(uKey) || 0) + 1);
    }
  }

  const toOptions = (map, labelFn) =>
    [...map.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([id, count]) => ({
        id,
        label: labelFn(id),
        count,
      }));

  const inputDigest = inputHash.digest("hex");
  const coveragePath = join(outDir, "madrid-period-coverage.json");
  const evidence = existsSync(coveragePath) ? JSON.parse(readFileSync(coveragePath, "utf-8")) : {};
  const coverage = periodCoverage(rows.map(r => r.m), evidence, { inputDigest, asOf });
  const payload = {
    temporal: { ruleVersion: DATE_RULE_VERSION, inputDigest, asOf, quarantineCount: quarantine.length, rebuild: "full" },
    periodCoverage: coverage,
    generatedAt: new Date().toISOString(),
    totalRows: rows.length,
    options: {
      distritos: toOptions(distritoCounts, (id) =>
        id === "_sin_distrito" ? "Sin distrito" : titleCase(id.replace(/-/g, " ")),
      ),
      actuaciones: toOptions(actuacionCounts, (id) => labelActuacionQue(id)),
      procedimientos: toOptions(procedimientoCounts, (id) =>
        id === "_sin_procedimiento"
          ? "Sin procedimiento"
          : titleCase(id),
      ).slice(0, 16),
      usos: toOptions(usoCounts, (id) =>
        id === "_sin_uso" ? "Sin uso indicado" : titleCase(id),
      ).slice(0, 12),
    },
    rows,
  };

  const outPath = join(outDir, "madrid-licencias-filter-rows.json");
  writeFileSync(outPath, JSON.stringify(payload));
  writeFileSync(join(outDir, "madrid-filter-temporal-quarantine.json"), JSON.stringify(quarantine));
  const kb = Math.round((readFileSync(outPath).length / 1024) * 10) / 10;
  console.log(`OK: madrid-licencias-filter-rows.json (${rows.length.toLocaleString("es-ES")} filas, ${kb} KB)`);
  return payload;
}
