/**
 * Agrega estadísticas Madrid (licencias + SIGMA) → public/data/madrid-dashboard-stats.json
 */
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { sanitizeSigmaExpedienteMetric } from "../lib/vivienda-plausible.mjs";

function topEntries(map, n = 20) {
  return [...map.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([name, count]) => ({ name, count }));
}

function inc(map, key, delta = 1) {
  const k = String(key ?? "")
    .trim()
    .toLowerCase();
  if (!k) return;
  map.set(k, (map.get(k) || 0) + delta);
}

function expedienteYear(grupo) {
  const parts = String(grupo || "").split("/");
  if (parts.length >= 2 && /^\d{4}$/.test(parts[1])) return Number(parts[1]);
  return null;
}

function titleCase(s) {
  return String(s)
    .split(/\s+/)
    .map((w) => (w.length <= 2 ? w : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
}

/**
 * @param {{ outDir: string }} opts
 */
export function buildMadridDashboardStats(opts) {
  const { outDir } = opts;
  const licPath = join(outDir, "madrid-licencias-index.json");
  const sigmaPath = join(outDir, "madrid-sigma.json");
  const slimPath = join(outDir, "madrid-sigma-visor-slim.json");
  const metricsPath = join(outDir, "madrid-sigma-metrics.json");

  /** @type {import('./build-madrid-dashboard-stats.mjs').MadridDashboardStats['licencias']} */
  let licencias = null;
  if (existsSync(licPath)) {
    const idx = JSON.parse(readFileSync(licPath, "utf-8"));
    const years = (idx.years || []).slice().sort((a, b) => a - b);
    const seriesByYear = years.map((y) => ({
      year: y,
      total: idx.byYear?.[String(y)] ?? 0,
      uso: (idx.byYearUso?.[String(y)] || []).map((x) => ({
        name: x.name,
        count: x.count,
      })),
    }));
    licencias = {
      generatedAt: idx.generatedAt,
      totalRows: idx.totalRows,
      withCoords: idx.withCoords,
      years,
      seriesByYear,
      seriesByYearMapaTipo: idx.byYearMapaTipo || [],
      seriesByMonth: idx.seriesByMonth || [],
      seriesByMonthMapaTipo: idx.seriesByMonthMapaTipo || [],
      months: idx.months || [],
      topMapaTipo: idx.topMapaTipo || [],
      topUso: idx.topUso || [],
      topDistrito: idx.topDistrito || [],
      topDistritoMap: idx.topDistritoMap || [],
      topProcedimiento: idx.topProcedimiento || [],
      topTipoExpediente: idx.topTipoExpediente || [],
    };
  }

  const byYear = new Map();
  const byFase = new Map();
  const byFiguraTipo = new Map();
  const byTfig = new Map();
  const byTipoPlan = new Map();
  const byPromotor = new Map();
  const byDistrito = new Map();
  const byIniciativa = new Map();
  const byTramite = new Map();
  const byLayer = new Map();
  const byOrgano = new Map();
  const supBuckets = new Map([
    ["< 500 m²", 0],
    ["500 – 2.000 m²", 0],
    ["2.000 – 10.000 m²", 0],
    ["> 10.000 m²", 0],
  ]);
  let totalSigma = 0;
  let conVisorFicha = 0;
  let conGeometry = 0;
  let conTramitacion = 0;
  let conMetricas = 0;
  let viviendasTotal = 0;
  let viviendasExpedientes = 0;

  if (existsSync(sigmaPath)) {
    const sigma = JSON.parse(readFileSync(sigmaPath, "utf-8"));
    const slim = existsSync(slimPath)
      ? JSON.parse(readFileSync(slimPath, "utf-8"))
      : { byGrupoExpediente: {} };
    const viso = slim.byGrupoExpediente || {};

    for (const e of sigma.expedientes || []) {
      const grupo = String(e.EXP_TX_NUMERO || "").trim();
      if (!grupo) continue;
      totalSigma += 1;
      const y = expedienteYear(grupo);
      if (y) inc(byYear, String(y));

      inc(byFase, e.FAS_TX_DENOM);
      inc(byTfig, e.TFIG_TX_ABREV);
      inc(byLayer, e.sigma_layer_kind || e.source);
      inc(byOrgano, e.ORG_TX_DESC);

      if (e.has_geometry) conGeometry += 1;

      const v = viso[grupo];
      if (v?.tramitacion?.length) conTramitacion += 1;
      const f = v?.visorFicha;
      if (f) {
        conVisorFicha += 1;
        inc(byTipoPlan, f.tipoPlaneamiento);
        inc(byDistrito, f.distrito);
        inc(byIniciativa, f.iniciativa);
        if (f.promotor) inc(byPromotor, f.promotor);
        if (f.figuraTipo) inc(byFiguraTipo, f.figuraTipo);
        const m2 = f.superficieAmbitoM2;
        if (m2 != null && m2 > 0) {
          if (m2 < 500) supBuckets.set("< 500 m²", supBuckets.get("< 500 m²") + 1);
          else if (m2 < 2000) supBuckets.set("500 – 2.000 m²", supBuckets.get("500 – 2.000 m²") + 1);
          else if (m2 < 10000)
            supBuckets.set("2.000 – 10.000 m²", supBuckets.get("2.000 – 10.000 m²") + 1);
          else supBuckets.set("> 10.000 m²", supBuckets.get("> 10.000 m²") + 1);
        }
      }
      if (v?.tramitacion) {
        for (const t of v.tramitacion) {
          if (t?.tramite) inc(byTramite, t.tramite);
        }
      }
    }
  }

  const topViviendas = [];
  if (existsSync(metricsPath)) {
    const met = JSON.parse(readFileSync(metricsPath, "utf-8"));
    const byExp = met.byExpediente || {};
    for (const [grupo, raw] of Object.entries(byExp)) {
      if (!raw || typeof raw !== "object") continue;
      const m = sanitizeSigmaExpedienteMetric(raw);
      conMetricas += 1;
      const v = m.num_viviendas_max;
      if (v != null && v > 0) {
        viviendasExpedientes += 1;
        viviendasTotal += v;
        topViviendas.push({ grupo, viviendas: v, sup: m.sup_total_m2 });
      }
    }
    topViviendas.sort((a, b) => b.viviendas - a.viviendas);
  }

  const sigmaYears = topEntries(byYear, 30).map(({ name, count }) => ({
    year: Number(name),
    count,
  }));

  const distritoCentroids = {};
  if (licencias?.topDistritoMap) {
    for (const d of licencias.topDistritoMap) {
      if (d.lat != null && d.lng != null) {
        const k = String(d.name).trim().toLowerCase().replace(/-/g, " ");
        distritoCentroids[k] = { lat: d.lat, lng: d.lng, label: d.name };
      }
    }
  }

  const stats = {
    generatedAt: new Date().toISOString(),
    distritoCentroids,
    licencias,
    sigma: {
      total: totalSigma,
      conVisorFicha,
      conTramitacion,
      conGeometry,
      conMetricasPdf: conMetricas,
      viviendasEnMetricas: viviendasTotal,
      expedientesConViviendas: viviendasExpedientes,
      seriesByYear: sigmaYears,
      byFase: topEntries(byFase, 12).map((x) => ({ ...x, name: titleCase(x.name) })),
      byFiguraTipo: topEntries(byFiguraTipo, 14).map((x) => ({ ...x, name: titleCase(x.name) })),
      byTipoFiguraAbrev: topEntries(byTfig, 12).map((x) => ({ ...x, name: x.name.toUpperCase() })),
      byTipoPlaneamiento: topEntries(byTipoPlan, 10).map((x) => ({
        ...x,
        name: titleCase(x.name),
      })),
      byPromotor: topEntries(byPromotor, 20).map((x) => ({ ...x, name: x.name })),
      byDistrito: topEntries(byDistrito, 22).map((x) => ({ ...x, name: titleCase(x.name) })),
      byIniciativa: topEntries(byIniciativa, 6).map((x) => ({ ...x, name: titleCase(x.name) })),
      byTramite: topEntries(byTramite, 14).map((x) => ({ ...x, name: titleCase(x.name) })),
      byLayer: topEntries(byLayer, 8).map((x) => ({ ...x, name: titleCase(x.name) })),
      byOrgano: topEntries(byOrgano, 12).map((x) => ({ ...x, name: titleCase(x.name) })),
      superficieBuckets: [...supBuckets.entries()].map(([name, count]) => ({ name, count })),
      topViviendas: topViviendas.slice(0, 12).map((x) => ({
        expedienteGrupo: x.grupo,
        viviendas: x.viviendas,
        supM2: x.sup,
      })),
    },
  };

  const outPath = join(outDir, "madrid-dashboard-stats.json");
  writeFileSync(outPath, JSON.stringify(stats));
  console.log(
    `OK: madrid-dashboard-stats.json (sigma ${totalSigma}, ficha visor ${conVisorFicha}, licencias ${licencias?.totalRows ?? 0})`,
  );
  return stats;
}
