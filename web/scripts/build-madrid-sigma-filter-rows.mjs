/**
 * Filas compactas para filtrar el dashboard SIGMA en cliente.
 */
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

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

function expedienteYear(grupo) {
  const parts = String(grupo || "").split("/");
  if (parts.length >= 2 && /^\d{4}$/.test(parts[1])) return Number(parts[1]);
  return null;
}

function supBucket(m2) {
  if (m2 == null || !(m2 > 0)) return "";
  if (m2 < 500) return "lt500";
  if (m2 < 2000) return "500-2k";
  if (m2 < 10000) return "2k-10k";
  return "gt10k";
}

const SUP_LABELS = {
  lt500: "< 500 m²",
  "500-2k": "500 – 2.000 m²",
  "2k-10k": "2.000 – 10.000 m²",
  gt10k: "> 10.000 m²",
};

function titleCase(s) {
  return String(s)
    .split(/\s+/)
    .map((w) => (w.length <= 2 ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
}

/**
 * @param {{ outDir: string }} opts
 */
export function buildMadridSigmaFilterRows(opts) {
  const { outDir } = opts;
  const sigmaPath = join(outDir, "madrid-sigma.json");
  const slimPath = join(outDir, "madrid-sigma-visor-slim.json");
  const clasPath = join(outDir, "madrid-sigma-clasificacion.json");

  if (!existsSync(sigmaPath)) {
    console.log("Aviso: sin madrid-sigma.json — omitiendo sigma filter-rows");
    return null;
  }

  const sigma = JSON.parse(readFileSync(sigmaPath, "utf-8"));
  const slim = existsSync(slimPath)
    ? JSON.parse(readFileSync(slimPath, "utf-8"))
    : { byGrupoExpediente: {} };
  const clas = existsSync(clasPath)
    ? JSON.parse(readFileSync(clasPath, "utf-8"))
    : { byExpediente: {} };
  const viso = slim.byGrupoExpediente || {};
  const byExp = clas.byExpediente || {};

  const rows = [];
  const axisCounts = {
    categoriaProyecto: new Map(),
    tipoObra: new Map(),
    tipoLegal: new Map(),
    escala: new Map(),
    faseNormalizada: new Map(),
    confianza: new Map(),
    distrito: new Map(),
    iniciativa: new Map(),
    tipoPlaneamiento: new Map(),
    figuraTipo: new Map(),
    sistemaActuacion: new Map(),
    unidadTramitadora: new Map(),
    ambitoOrdenacion: new Map(),
    promotor: new Map(),
    superficie: new Map(),
    faseCatalogo: new Map(),
    layer: new Map(),
    anio: new Map(),
  };

  for (const e of sigma.expedientes || []) {
    const g = String(e.EXP_TX_NUMERO || "").trim();
    if (!g) continue;
    const y = expedienteYear(g);
    const c = byExp[g] || {};
    const v = viso[g];
    const f = v?.visorFicha;

    const row = {
      g,
      y: y || 0,
      cp: c.categoriaProyecto || "",
      to: c.tipoObra || "",
      tl: c.tipoLegal || "",
      es: c.escala || "",
      fn: c.faseNormalizada || "",
      cf: c.confianza || "",
      d: normKey(f?.distrito) || "",
      i: normKey(f?.iniciativa) || "",
      tp: normKey(f?.tipoPlaneamiento) || "",
      fig: normKey(f?.figuraTipo) || "",
      sa: normKey(f?.sistemaActuacion) || "",
      ut: normKey(f?.unidadTramitadora) || "",
      ao: normKey(f?.ambitoOrdenacion) || "",
      pr: normKey(f?.promotor) || "",
      sup: supBucket(f?.superficieAmbitoM2),
      fc: normKey(e.FAS_TX_DENOM) || "",
      ly: normKey(e.sigma_layer_kind || e.source) || "",
      vf: f ? 1 : 0,
      cl: c.categoriaProyecto || c.tipoObra ? 1 : 0,
      geo: e.has_geometry ? 1 : 0,
      tr: v?.tramitacion?.length ? 1 : 0,
    };
    rows.push(row);

    if (row.cp) axisCounts.categoriaProyecto.set(row.cp, (axisCounts.categoriaProyecto.get(row.cp) || 0) + 1);
    if (row.to) axisCounts.tipoObra.set(row.to, (axisCounts.tipoObra.get(row.to) || 0) + 1);
    if (row.tl) axisCounts.tipoLegal.set(row.tl, (axisCounts.tipoLegal.get(row.tl) || 0) + 1);
    if (row.es) axisCounts.escala.set(row.es, (axisCounts.escala.get(row.es) || 0) + 1);
    if (row.fn) axisCounts.faseNormalizada.set(row.fn, (axisCounts.faseNormalizada.get(row.fn) || 0) + 1);
    if (row.cf) axisCounts.confianza.set(row.cf, (axisCounts.confianza.get(row.cf) || 0) + 1);
    if (row.d) axisCounts.distrito.set(row.d, (axisCounts.distrito.get(row.d) || 0) + 1);
    if (row.i) axisCounts.iniciativa.set(row.i, (axisCounts.iniciativa.get(row.i) || 0) + 1);
    if (row.tp) axisCounts.tipoPlaneamiento.set(row.tp, (axisCounts.tipoPlaneamiento.get(row.tp) || 0) + 1);
    if (row.fig) axisCounts.figuraTipo.set(row.fig, (axisCounts.figuraTipo.get(row.fig) || 0) + 1);
    if (row.sa) axisCounts.sistemaActuacion.set(row.sa, (axisCounts.sistemaActuacion.get(row.sa) || 0) + 1);
    if (row.ut) axisCounts.unidadTramitadora.set(row.ut, (axisCounts.unidadTramitadora.get(row.ut) || 0) + 1);
    if (row.ao) axisCounts.ambitoOrdenacion.set(row.ao, (axisCounts.ambitoOrdenacion.get(row.ao) || 0) + 1);
    if (row.pr) axisCounts.promotor.set(row.pr, (axisCounts.promotor.get(row.pr) || 0) + 1);
    if (row.sup) axisCounts.superficie.set(row.sup, (axisCounts.superficie.get(row.sup) || 0) + 1);
    if (row.fc) axisCounts.faseCatalogo.set(row.fc, (axisCounts.faseCatalogo.get(row.fc) || 0) + 1);
    if (row.ly) axisCounts.layer.set(row.ly, (axisCounts.layer.get(row.ly) || 0) + 1);
    if (row.y) axisCounts.anio.set(String(row.y), (axisCounts.anio.get(String(row.y)) || 0) + 1);
  }

  const labelFn = {
    categoriaProyecto: (id) => id.replace(/_/g, " "),
    tipoObra: (id) => id.replace(/_/g, " "),
    tipoLegal: (id) => id.replace(/_/g, " "),
    escala: (id) => id.replace(/_/g, " "),
    faseNormalizada: (id) => id.replace(/_/g, " "),
    confianza: (id) => id,
    distrito: (id) => titleCase(id),
    iniciativa: (id) => titleCase(id),
    tipoPlaneamiento: (id) => titleCase(id),
    figuraTipo: (id) => titleCase(id),
    sistemaActuacion: (id) => titleCase(id),
    unidadTramitadora: (id) => titleCase(id),
    ambitoOrdenacion: (id) => id.toUpperCase(),
    promotor: (id) => id.slice(0, 48),
    superficie: (id) => SUP_LABELS[id] || id,
    faseCatalogo: (id) => titleCase(id),
    layer: (id) => titleCase(id),
    anio: (id) => id,
  };

  const toOptions = (map, key) =>
    [...map.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([id, count]) => ({
        id,
        label: labelFn[key](id),
        count,
      }));

  const payload = {
    generatedAt: new Date().toISOString(),
    totalRows: rows.length,
    options: {
      categoriaProyecto: toOptions(axisCounts.categoriaProyecto, "categoriaProyecto"),
      tipoObra: toOptions(axisCounts.tipoObra, "tipoObra"),
      tipoLegal: toOptions(axisCounts.tipoLegal, "tipoLegal"),
      escala: toOptions(axisCounts.escala, "escala"),
      faseNormalizada: toOptions(axisCounts.faseNormalizada, "faseNormalizada"),
      confianza: toOptions(axisCounts.confianza, "confianza"),
      distritos: toOptions(axisCounts.distrito, "distrito"),
      iniciativas: toOptions(axisCounts.iniciativa, "iniciativa"),
      tipoPlaneamiento: toOptions(axisCounts.tipoPlaneamiento, "tipoPlaneamiento"),
      figuraTipo: toOptions(axisCounts.figuraTipo, "figuraTipo"),
      sistemaActuacion: toOptions(axisCounts.sistemaActuacion, "sistemaActuacion"),
      unidadTramitadora: toOptions(axisCounts.unidadTramitadora, "unidadTramitadora"),
      ambitoOrdenacion: toOptions(axisCounts.ambitoOrdenacion, "ambitoOrdenacion").slice(0, 16),
      promotores: toOptions(axisCounts.promotor, "promotor").slice(0, 24),
      superficie: toOptions(axisCounts.superficie, "superficie"),
      faseCatalogo: toOptions(axisCounts.faseCatalogo, "faseCatalogo"),
      layer: toOptions(axisCounts.layer, "layer"),
      anios: toOptions(axisCounts.anio, "anio"),
    },
    rows,
  };

  const outPath = join(outDir, "madrid-sigma-filter-rows.json");
  writeFileSync(outPath, JSON.stringify(payload));
  const kb = Math.round((readFileSync(outPath).length / 1024) * 10) / 10;
  console.log(`OK: madrid-sigma-filter-rows.json (${rows.length.toLocaleString("es-ES")} filas, ${kb} KB)`);
  return payload;
}
