/** Contract shared by the data build and every runtime summary read. */
export function createStatisticsScope(summary) {
  if (!["full", "madrid-public"].includes(summary.buildScope)) throw new Error("statistics-scope: unknown buildScope");
  const manifest = {
    version: 1,
    buildScope: summary.buildScope,
    geography: summary.buildScope === "full" ? "España" : "Comunidad de Madrid",
    coverage: "partial",
    sources: summary.bySource.map((r) => r.name),
    territories: summary.byTerritorio.filter((r) => r.count > 0).map((r) => r.name),
    period: { ...summary.dateRange },
    checkedAt: summary.generatedAt,
    denominator: { population: "all-published-announcements", count: summary.total },
    limitations: "Cobertura parcial de las fuentes y territorios enumerados; no representa todos los anuncios ni permite comparar cobertura homogénea entre comunidades.",
  };
  assertStatisticsScope({ ...summary, statisticsScope: manifest });
  return manifest;
}

export function assertStatisticsScope(summary) {
  const m = summary?.statisticsScope;
  const fail = (reason) => { throw new Error(`statistics-scope: ${reason}`); };
  if (!m || m.version !== 1 || !["full", "madrid-public"].includes(summary.buildScope) || m.buildScope !== summary.buildScope) fail("missing or incompatible manifest");
  if (m.geography !== (summary.buildScope === "full" ? "España" : "Comunidad de Madrid") || m.coverage !== "partial" || typeof m.limitations !== "string" || !m.limitations.trim()) fail("unproven geography or coverage");
  if (!Number.isInteger(summary.total) || summary.total < 0 || m.denominator?.population !== "all-published-announcements" || m.denominator.count !== summary.total) fail("denominator mismatch");
  if (m.checkedAt !== summary.generatedAt || !Number.isFinite(Date.parse(m.checkedAt))) fail("invalid check date");
  if (!summary.dateRange || m.period?.min !== summary.dateRange.min || m.period?.max !== summary.dateRange.max) fail("period mismatch");
  for (const key of ["byYear", "byTerritorio", "bySource"]) {
    const rows = summary[key];
    if (!Array.isArray(rows) || rows.some((r) => !r || !Number.isInteger(r.count) || r.count < 0 || typeof (key === "byYear" ? r.year : r.name) !== "string") || rows.reduce((n, r) => n + r.count, 0) !== summary.total) fail(`${key} denominator mismatch`);
    const names = rows.map((r) => key === "byYear" ? r.year : r.name);
    if (new Set(names).size !== names.length) fail(`${key} duplicated group`);
  }
  for (const key of ["byTipo", "byMunicipio"]) {
    const rows = summary[key];
    if (!Array.isArray(rows) || rows.some((r) => !r || typeof r.name !== "string" || !Number.isInteger(r.count) || r.count < 0) || rows.reduce((n, r) => n + r.count, 0) > summary.total) fail(`${key} exceeds denominator`);
  }
  const same = (a, b) => Array.isArray(a) && JSON.stringify([...a].sort()) === JSON.stringify([...b].sort());
  if (!same(m.sources, summary.bySource.map((r) => r.name)) || !same(m.territories, summary.byTerritorio.filter((r) => r.count > 0).map((r) => r.name))) fail("source or territory mismatch");
  const years = summary.byYear.map((r) => r.year).sort();
  if (years.some((y) => !/^\d{4}$/.test(y)) || m.period.min !== (years[0] ?? null) || m.period.max !== (years.at(-1) ?? null)) fail("year range mismatch");
  return m;
}

export function nationalStatisticsScope(summary) {
  try {
    const manifest = assertStatisticsScope(summary);
    return manifest.buildScope === "full" ? { ...manifest, title: `${manifest.geography} · cobertura parcial` } : null;
  } catch { return null; }
}
