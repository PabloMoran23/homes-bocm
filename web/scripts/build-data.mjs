/**
 * Genera public/data/projects.json, summary.json y admin-coverage.json desde:
 * - history_parsed_incremental.csv (BOCM / Madrid)
 * - ccaa_history_parsed_incremental.csv (resto CCAA)
 * - índices history_index*.jsonl (huecos índice → parseo)
 * - municipios_coords_cache.json, sector_geometry_map.geojson
 */
import { createHash } from "node:crypto";
import { execSync, spawnSync } from "node:child_process";
import {
  readFileSync,
  mkdirSync,
  writeFileSync,
  existsSync,
  copyFileSync,
  readdirSync,
  unlinkSync,
} from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "csv-parse/sync";
import { buildMadridLicenciasWeb } from "./build-madrid-licencias.mjs";
import { buildMadridDashboardStats } from "./build-madrid-dashboard-stats.mjs";
import {
  sanitizeSigmaExpedienteMetric,
  sanitizeMetricsByExpediente,
  viviendasCoherentesConSuperficie,
} from "../lib/vivienda-plausible.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const webRoot = join(__dirname, "..");
const pocRoot = join(webRoot, "..");
const homesRoot = join(pocRoot, "..");
const bocmCsv = join(pocRoot, "output/history_parsed_incremental.csv");
const ccaaCsv = join(pocRoot, "output/ccaa_history_parsed_incremental.csv");
const coordsPath = join(pocRoot, "output/municipios_coords_cache.json");
const sectorGeoPath = join(pocRoot, "output/sector_geometry_map.geojson");
const madridAytoMatchPath = join(pocRoot, "output/madrid_ayto_bocm_match.json");
const madridAytoLinksPath = join(pocRoot, "output/madrid_ayto_bocm_links.jsonl");
const madridAytoIpGeoPath = join(pocRoot, "output/madrid_ayto_expedientes_ip.geojson");
const madridAytoAdGeoPath = join(pocRoot, "output/madrid_ayto_expedientes_ad.geojson");
const madridAytoGestionGeoPath = join(pocRoot, "output/madrid_ayto_expedientes_gestion.geojson");
const madridAytoUrbanGeoPath = join(pocRoot, "output/madrid_ayto_expedientes_urbanizacion.geojson");
const madridSigmaIndexPath = join(pocRoot, "output/madrid_ayto_expedientes_index.json");
const madridLicenciasJsonlPath = join(pocRoot, "output/madrid_licencias.jsonl");
const madridVisoExpedientesPath = join(pocRoot, "output/madrid_viso_expedientes.json");
const madridSigmaExpMetricsPath = join(pocRoot, "output/madrid_sigma_expediente_metrics.json");
const outDir = join(webRoot, "public/data");

/** `madrid-public`: solo Madrid capital en projects + licencias recientes (deploy MVP). */
const buildScope = process.env.BUILD_DATA_SCOPE || "full";
const isMadridPublicBuild = buildScope === "madrid-public";
const LICENCIAS_MIN_YEAR_PUBLIC = 2022;

if (isMadridPublicBuild) {
  console.log(
    `BUILD_DATA_SCOPE=madrid-public (proyectos Madrid capital; licencias desde ${LICENCIAS_MIN_YEAR_PUBLIC})`,
  );
}

const TERRITORIO_BY_SOURCE = {
  bocm: { id: "comunidad-madrid", label: "Comunidad de Madrid" },
  boja: { id: "andalucia", label: "Andalucía" },
  dogv: { id: "comunitat-valenciana", label: "Comunitat Valenciana" },
  bocyl: { id: "castilla-leon", label: "Castilla y León" },
  docm: { id: "castilla-mancha", label: "Castilla-La Mancha" },
  boc_canarias: { id: "canarias", label: "Canarias" },
  bopa: { id: "asturias", label: "Principado de Asturias" },
  boc_cantabria: { id: "cantabria", label: "Cantabria" },
  boib: { id: "illes-balears", label: "Illes Balears" },
  dog: { id: "galicia", label: "Galicia" },
  bopv: { id: "euskadi", label: "Euskadi" },
  borm: { id: "murcia", label: "Región de Murcia" },
  dogc: { id: "catalunya", label: "Catalunya" },
};

/** Índice PDF por fuente (líneas en jsonl). */
const INDEX_BY_SOURCE = {
  bocm: join(pocRoot, "output/history_index.jsonl"),
  boja: join(homesRoot, "ccaa-boletines/output/history_index_boja_vivienda.jsonl"),
  dogv: join(homesRoot, "ccaa-boletines/output/history_index_dogv_vivienda.jsonl"),
  bocyl: join(homesRoot, "ccaa-boletines/output/history_index_bocyl_vivienda.jsonl"),
  docm: join(homesRoot, "ccaa-boletines/output/history_index_docm_vivienda.jsonl"),
  boc_canarias: join(homesRoot, "ccaa-boletines/output/history_index_boc_canarias_vivienda.jsonl"),
  bopa: join(homesRoot, "ccaa-boletines/output/history_index_bopa_vivienda.jsonl"),
  boc_cantabria: join(homesRoot, "ccaa-boletines/output/history_index_boc_cantabria_vivienda.jsonl"),
  boib: join(homesRoot, "ccaa-boletines/output/history_index_boib_all.jsonl"),
  dog: join(homesRoot, "ccaa-boletines/output/history_index_dog_all.jsonl"),
  bopv: join(homesRoot, "ccaa-boletines/output/history_index_bopv_all.jsonl"),
  borm: join(homesRoot, "ccaa-boletines/output/history_index_borm_all.jsonl"),
  dogc: join(homesRoot, "poc-dogc/output/history_index_vivienda.jsonl"),
};

function normText(s) {
  return (s || "")
    .normalize("NFC")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

function stableSectorKey({ boletinSourceId, municipio, nombreSector, municipioProvincia }) {
  const parts = [
    normText(boletinSourceId),
    normText(municipio),
    normText(nombreSector),
    normText(municipioProvincia),
  ];
  return createHash("sha256").update(parts.join("||"), "utf8").digest("hex");
}

/** Clave legacy (sector_geometry.sqlite sin boletin_source_id en el hash). */
function legacySectorKey({ municipio, nombreSector, municipioProvincia }) {
  return stableSectorKey({
    boletinSourceId: "",
    municipio,
    nombreSector,
    municipioProvincia,
  });
}

function normExpediente(num) {
  return String(num || "")
    .trim()
    .replace(/\s+/g, "");
}

function expVariants(num) {
  const n = normExpediente(num);
  if (!n) return [];
  const out = new Set([n]);
  const parts = n.split("/");
  if (parts.length === 3 && /^\d+$/.test(parts[2])) {
    out.add(`${parts[0]}/${parts[1]}/${parts[2].padStart(5, "0")}`);
    out.add(`${parts[0]}/${parts[1]}/${parts[2].padStart(4, "0")}`);
    if (parts[2].startsWith("0")) {
      out.add(`${parts[0]}/${parts[1]}/${parts[2].replace(/^0+/, "") || "0"}`);
    }
  }
  return [...out];
}

function expedienteGrupoKeyFromVariant(raw) {
  const n = normExpediente(String(raw || ""));
  const parts = n.split("/");
  if (parts.length === 3 && /^\d+$/.test(parts[2]))
    return `${parts[0]}/${parts[1]}/${parts[2].padStart(5, "0")}`;
  return n;
}

/** Métricas PDF→expediente para fichas y mapa (compacto). */
function buildMadridSigmaMetricsWeb() {
  const metricsDb = join(pocRoot, "db/poc_local.sqlite");
  const metricsPy = join(pocRoot, "db/export_sigma_metrics_web.py");
  if (existsSync(metricsPy) && existsSync(metricsDb)) {
    try {
      const r = spawnSync("python3", [metricsPy, metricsDb, join(outDir, "madrid-sigma-metrics.json")], {
        cwd: pocRoot,
        encoding: "utf-8",
      });
      if (r.status === 0) {
        const metricsPath = join(outDir, "madrid-sigma-metrics.json");
        const payload = JSON.parse(readFileSync(metricsPath, "utf-8"));
        payload.byExpediente = sanitizeMetricsByExpediente(payload.byExpediente);
        writeFileSync(metricsPath, JSON.stringify(payload));
        console.log((r.stdout || "").trim() || "OK: madrid-sigma-metrics.json (SQLite)");
        return null;
      }
      console.warn("Métricas SQLite:", r.stderr?.slice(0, 200) || r.stdout?.slice(0, 200));
    } catch (err) {
      console.warn("Métricas SQLite:", err?.message || err);
    }
  }
  if (!existsSync(madridSigmaExpMetricsPath)) {
    console.log("Aviso: sin métricas SIGMA para web");
    return null;
  }
  const raw = JSON.parse(readFileSync(madridSigmaExpMetricsPath, "utf-8"));
  const byExpediente = {};
  for (const [grupo, row] of Object.entries(raw.expedientes || {})) {
    if (!row || typeof row !== "object") continue;
    const m = row.metrics || {};
    const hechos = Array.isArray(m.hechos) ? m.hechos : [];
    byExpediente[grupo] = sanitizeSigmaExpedienteMetric({
      num_viviendas_max: m.num_viviendas_max ?? null,
      sup_total_m2: m.sup_total_m2 ?? null,
      sup_edificable_m2: m.sup_edificable_m2 ?? null,
      tipo_vivienda: m.tipo_vivienda ?? null,
      genera_vivienda_nueva: m.genera_vivienda_nueva ?? null,
      familia_expediente: m.familia_expediente ?? null,
      pdfs_procesados:
        typeof m.pdfs_procesados === "number"
          ? m.pdfs_procesados
          : Array.isArray(m.fuentes_pdf)
            ? m.fuentes_pdf.length
            : null,
      doc_role_principal: m.doc_role_principal ?? null,
      hechos: hechos.slice(0, 6).map((h) => ({
        metric: h.metric ?? h.metrica ?? null,
        value: h.value ?? h.valor ?? null,
        confianza: h.confianza ?? null,
        doc_role: h.doc_role ?? null,
        pdf_name: h.pdf_name ?? null,
      })),
    });
  }
  const payload = {
    generatedAt: raw.generatedAt || new Date().toISOString(),
    count: Object.keys(byExpediente).length,
    byExpediente,
  };
  writeFileSync(join(outDir, "madrid-sigma-metrics.json"), JSON.stringify(payload));
  console.log(`OK: madrid-sigma-metrics.json (${payload.count} expedientes con métricas)`);
  return payload;
}

function sigmaSlugFromGrupo(grupo) {
  return expedienteGrupoKeyFromVariant(grupo).replace(/\//g, "-");
}

function shortDenom(text, max = 58) {
  const s = String(text || "")
    .trim()
    .replace(/\s+/g, " ");
  if (!s) return "Expediente urbanístico";
  return s.length <= max ? s : `${s.slice(0, max - 1)}…`;
}

function yearFromExpedienteNum(num) {
  const parts = String(num || "").split("/");
  if (parts.length < 2) return null;
  const y = Number(parts[1]);
  return Number.isFinite(y) && y >= 1990 && y <= 2100 ? y : null;
}

function dateLabelForExpediente(num) {
  const y = yearFromExpedienteNum(num);
  if (!y) return "Madrid";
  if (y >= 2024) return "Reciente";
  if (y >= 2020) return String(y);
  return String(y);
}

function tagForSpotlight(metric, catalog) {
  const g = metric?.genera_vivienda_nueva;
  if (g === "si") return "Vivienda nueva";
  if (g === "probable_si") return "Gran escala";
  const fam = metric?.familia_expediente || "";
  if (fam.includes("plan_parcial")) return "Plan parcial";
  if (fam.includes("modificacion_pgou")) return "Plan General";
  if (fam.includes("estudio_detalle")) return "Estudio de detalle";
  const fig = String(catalog?.FIG_TX_ETIQ || catalog?.TFIG_TX_ABREV || "");
  if (/PE|plan especial/i.test(fig)) return "Plan especial";
  return "Planeamiento";
}

function titleForSpotlight(denom, n) {
  const d = shortDenom(denom, 52);
  if (n >= 400) return `Hasta ${n.toLocaleString("es-ES")} viviendas: ${d}`;
  if (n >= 80) return `${d} — ${n.toLocaleString("es-ES")} viviendas previstas`;
  return d;
}

function dekForSpotlight(catalog, metric, n) {
  const bits = [];
  if (catalog?.FAS_TX_DENOM) bits.push(String(catalog.FAS_TX_DENOM));
  if (metric?.sup_total_m2 != null && metric.sup_total_m2 > 0) {
    bits.push(`${Math.round(metric.sup_total_m2).toLocaleString("es-ES")} m² de ámbito`);
  }
  const tv = metric?.tipo_vivienda ? String(metric.tipo_vivienda).replace(/\s+/g, " ").trim() : "";
  if (tv) bits.push(tv.slice(0, 48));
  bits.push(
    n >= 1000
      ? "Cifra extraída de la documentación del expediente (revisar en ficha)"
      : "Ver ámbito y tramitación en la ficha",
  );
  return bits.join(" · ");
}

function scoreSpotlight(metric, catalog) {
  const sanitized = sanitizeSigmaExpedienteMetric(metric);
  const n = Number(sanitized?.num_viviendas_max) || 0;
  if (n <= 0) return 0;
  const sup = sanitized?.sup_total_m2;
  const edif = sanitized?.sup_edificable_m2;
  if (!viviendasCoherentesConSuperficie(n, sup, edif)) return 0;

  let score = n;
  const g = sanitized?.genera_vivienda_nueva;
  if (g === "si") score *= 1.35;
  else if (g === "probable_si") score *= 1.15;
  else if (g === "stock_existente_o_rehabilitacion") score *= 0.55;
  else if (g === "no") score *= 0.1;

  // Descartar extracciones dudosas (rehabilitación con cifras desproporcionadas)
  if (n > 12_000 && g === "stock_existente_o_rehabilitacion") score *= 0.15;
  if (n > 8_000 && g !== "si" && g !== "probable_si") score *= 0.4;

  const y = yearFromExpedienteNum(catalog?.EXP_TX_NUMERO);
  if (y && y >= 2022) score *= 1.12;
  else if (y && y >= 2019) score *= 1.05;

  if (String(catalog?.FAS_TX_DENOM || "").toLowerCase().includes("definitiva")) score *= 1.08;

  return score;
}

/** Titulares landing desde mayores programas edificatorios (métricas SIGMA). */
function buildLandingNewsSpotlight() {
  const metricsPath = join(outDir, "madrid-sigma-metrics.json");
  const sigmaPath = join(outDir, "madrid-sigma.json");
  if (!existsSync(metricsPath) || !existsSync(sigmaPath)) {
    console.log("Aviso: sin datos para landing-news.json");
    return;
  }

  const metrics = JSON.parse(readFileSync(metricsPath, "utf-8"));
  const sigma = JSON.parse(readFileSync(sigmaPath, "utf-8"));
  const catalogByGrupo = new Map();
  for (const e of sigma.expedientes || []) {
    const g = expedienteGrupoKeyFromVariant(e.EXP_TX_NUMERO || "");
    if (g) catalogByGrupo.set(g, e);
  }

  const candidates = [];
  for (const [grupo, metric] of Object.entries(metrics.byExpediente || {})) {
    const sanitized = sanitizeSigmaExpedienteMetric(metric);
    const n = Number(sanitized?.num_viviendas_max);
    if (!Number.isFinite(n) || n < 50) continue;
    const catalog = catalogByGrupo.get(grupo) || catalogByGrupo.get(expedienteGrupoKeyFromVariant(grupo));
    const score = scoreSpotlight(sanitized, catalog);
    if (score < 40) continue;
    const denom = catalog?.EXP_TX_DENOM || grupo;
    candidates.push({
      id: `sigma-${sigmaSlugFromGrupo(grupo)}`,
      href: `/sigma/${encodeURIComponent(sigmaSlugFromGrupo(grupo))}`,
      tag: tagForSpotlight(sanitized, catalog),
      dateLabel: dateLabelForExpediente(catalog?.EXP_TX_NUMERO || grupo),
      title: titleForSpotlight(denom, n),
      dek: dekForSpotlight(catalog, sanitized, n),
      score,
      numViviendas: n,
      expedienteGrupo: grupo,
    });
  }

  candidates.sort((a, b) => b.score - a.score);
  const top = candidates.slice(0, 4);
  if (!top.length) {
    console.log("Aviso: landing-news.json sin candidatos (umbral viviendas)");
    return;
  }

  const items = top.map((item, i) => ({
    id: item.id,
    href: item.href,
    tag: item.tag,
    dateLabel: item.dateLabel,
    title: item.title,
    dek: item.dek,
    featured: i === 0,
    numViviendas: item.numViviendas,
    expedienteGrupo: item.expedienteGrupo,
  }));

  const payload = {
    generatedAt: new Date().toISOString(),
    source: "madrid-sigma-metrics + madrid-sigma.json",
    criteria:
      "Mayor num_viviendas_max coherente con m² de ámbito/edificabilidad (Madrid, métricas PDF)",
    items,
  };
  writeFileSync(join(outDir, "landing-news.json"), JSON.stringify(payload, null, 2));
  console.log(
    `OK: landing-news.json (${items.length} titulares, destacado: ${items[0].numViviendas?.toLocaleString("es-ES")} viv.)`,
  );
}

/** Mapa SIGMA (grupo-expediente) ↔ fichas BOCM del portal para popups en /madrid/sigma. */
function buildMadridSigmaBocmProjectsByExpediente(projects) {
  const byExp = new Map();
  for (const p of projects) {
    if (normText(p.municipio) !== "madrid") continue;
    const exp = p.sigmaExpediente;
    if (!exp || !String(exp).includes("/")) continue;
    const g = expedienteGrupoKeyFromVariant(String(exp));
    if (!byExp.has(g)) byExp.set(g, []);
    byExp.get(g).push({
      id: p.id,
      title: String(p.title || "").slice(0, 220),
      bocmDate: String(p.bocmDate || ""),
      artNum: String(p.artNum || ""),
      esRelevante: p.esRelevante ?? null,
    });
  }
  const out = {};
  for (const [g, rows] of byExp) {
    rows.sort((a, b) => String(b.bocmDate).localeCompare(String(a.bocmDate)));
    const seen = new Set();
    const uniq = [];
    for (const r of rows) {
      if (seen.has(r.id)) continue;
      seen.add(r.id);
      uniq.push(r);
    }
    out[g] = uniq.slice(0, 25);
  }
  return out;
}

function expedientesFromBocmRow(row) {
  const found = new Set();

  function addSlash(s) {
    const n = normExpediente(s);
    if (!n || !n.includes("/")) return;
    for (const v of expVariants(n)) found.add(v);
  }

  const pe = String(row.procedimiento_expediente || "").trim();
  if (pe) {
    if (pe.includes("/")) addSlash(pe);
    else {
      const m = pe.match(/\b(\d{1,4})-(\d{4})-(\d{1,8})\b/);
      if (m) addSlash(`${m[1]}/${m[2]}/${m[3]}`);
    }
  }

  const blob = [
    row.procedimiento_expediente,
    row.title,
    row.resumen,
    row.nombre_sector,
    row.organo_aprobador,
  ]
    .filter(Boolean)
    .join(" ");

  for (const m of blob.matchAll(/\b(\d{1,4}\/\d{4}\/\d{1,8})\b/g)) addSlash(m[1]);
  for (const m of blob.matchAll(/\b(\d{1,4})-(\d{4})-(\d{1,8})\b/g)) addSlash(`${m[1]}/${m[2]}/${m[3]}`);
  return found;
}

/** project id coherente con buildProject(...) */
function bocmRowProjectId(row) {
  const parsed = rowToProject(row, { defaultSourceId: "bocm" });
  return `${parsed.sourceId}-${parsed.pubDate}-${parsed.artNum}-${parsed.fp || parsed.sectorKey.slice(0, 12) || "na"}`;
}

function formatArcgisMsToDate(ms) {
  const n = Number(ms);
  if (ms === null || ms === "" || Number.isNaN(n)) return null;
  try {
    return new Date(n).toISOString().slice(0, 10);
  } catch {
    return null;
  }
}

/** Mapa grupo-expediente (5 dígitos último tramo) → menciones BO BOCM Madrid capital. */
function buildMadridBoletinMentionsByExpediente(rows) {
  const map = new Map();

  for (const row of rows) {
    if (normText(row.municipio) !== "madrid") continue;
    const sid = (row.boletin_source_id || "bocm").trim().toLowerCase();
    if (sid !== "bocm") continue;
    const exps = expedientesFromBocmRow(row);
    if (!exps.size) continue;
    const groups = new Set([...exps].map((e) => expedienteGrupoKeyFromVariant(e)));

    const meta = {
      projectId: bocmRowProjectId(row),
      bocmDate: row.bocm_date || row.date_pub || row.fecha || "",
      artNum: String(row.art_num || row.id || ""),
      title: (row.title || "").slice(0, 220),
      estadoTramitacion: (row.estado_tramitacion || "").trim() || null,
      tipoInstrumento: (row.tipo_instrumento || "").trim() || null,
      esRelevante: parseRelevante(row),
      pdfUrl: (row.pdf_url || "").trim() || null,
    };
    for (const g of groups) {
      if (!map.has(g)) map.set(g, []);
      map.get(g).push(meta);
    }
  }

  return map;
}

function loadMadridSigmaIndexBundle(indexPath) {
  if (!existsSync(indexPath)) return { generatedAt: null, byVariant: new Map() };
  const raw = JSON.parse(readFileSync(indexPath, "utf-8"));
  const byVariant = new Map();

  for (const row of raw.expedientes || []) {
    const num = row.EXP_TX_NUMERO;
    if (!num && num !== 0) continue;

    const vars = expVariants(String(num));
    for (const v of vars) {
      if (!byVariant.has(v)) byVariant.set(v, row);
    }
  }

  return { generatedAt: raw.generatedAt ?? null, byVariant };
}

function sigmaIndexLookup(bundle, expedienteSigma) {
  if (!bundle?.byVariant?.size || !expedienteSigma) return null;

  const vars = expVariants(String(expedienteSigma));

  for (const v of vars) {
    const hit = bundle.byVariant.get(v);
    if (hit) return hit;
  }
  return null;
}

/** Enriquece snapshot SIGMA desde índice + línea temporal BOCM mismo nº expediente. */
function enrichProjectSigmaBoletines(project, sigmaBundle, mencionesPorExpKey) {
  if (!project.sigmaExpediente) return;

  const snap = sigmaIndexLookup(sigmaBundle, project.sigmaExpediente);
  if (snap) {
    project.sigmaCatalogSyncedAt = sigmaBundle.generatedAt ?? null;
    project.sigmaFiguraCodigo =
      snap.FIG_TX_ETIQ != null && String(snap.FIG_TX_ETIQ).trim() !== ""
        ? String(snap.FIG_TX_ETIQ).trim()
        : null;
    project.sigmaTipoFigura =
      snap.TFIG_TX_ABREV != null && String(snap.TFIG_TX_ABREV).trim() !== ""
        ? String(snap.TFIG_TX_ABREV).trim()
        : null;
    project.sigmaOrganoTramitador =
      snap.ORG_TX_DESC != null && String(snap.ORG_TX_DESC).trim() !== ""
        ? String(snap.ORG_TX_DESC).trim()
        : null;
    project.sigmaCatalogSource =
      typeof snap.source === "string" && snap.source ? snap.source : null;
    project.sigmaSigmaLayerKind =
      snap.sigma_layer_kind != null && String(snap.sigma_layer_kind).trim() !== ""
        ? String(snap.sigma_layer_kind)
        : null;
    project.sigmaHasGeometrySigma = snap.has_geometry === true;

    const oid = snap.EXP_ID;

    project.sigmaObjectId =
      oid != null && String(oid).trim() !== "" && !Number.isNaN(Number(oid))
        ? Number(oid)
        : null;

    project.sigmaFechaAprobacion = formatArcgisMsToDate(snap.FEX_DT_APROB);
    project.sigmaInfopublicaInicio = formatArcgisMsToDate(snap.FEX_DT_INFOPUB_INI);
    project.sigmaInfopublicaFin = formatArcgisMsToDate(snap.FEX_DT_INFOPUB_FIN);

    if (snap.EXP_TX_DENOM && String(snap.EXP_TX_DENOM).trim())
      project.sigmaDenominacion = String(snap.EXP_TX_DENOM).trim();

    if (snap.FAS_TX_DENOM && String(snap.FAS_TX_DENOM).trim())
      project.sigmaFase = String(snap.FAS_TX_DENOM).trim();

    if (snap.Enlace && String(snap.Enlace).trim()) project.sigmaEnlace = String(snap.Enlace).trim();
  }

  const grupo = expedienteGrupoKeyFromVariant(project.sigmaExpediente);
  const lista = mencionesPorExpKey.get(grupo);

  if (lista && lista.length) {
    project.sigmaBoletinMismaExpediente = lista
      .map((entry) => ({
        ...entry,
        mismoAnuncioQueEstaVista: entry.projectId === project.id,
      }))
      .sort((a, b) => String(b.bocmDate || "").localeCompare(String(a.bocmDate || "")));
  }
}

function loadMadridVisoBundle(path) {
  if (!existsSync(path)) return { generatedAt: null, byGrupo: new Map() };
  const raw = JSON.parse(readFileSync(path, "utf-8"));
  const byGrupo = new Map();
  for (const [k, v] of Object.entries(raw.byGrupoExpediente || {})) {
    byGrupo.set(k, v);
  }
  return { generatedAt: raw.generatedAt ?? null, byGrupo };
}

/** Enriquece desde `madrid_viso_fetch` (tramitación HTML + PDFs NTI cuando existen). */
function enrichProjectSigmaVisor(project, visoBundle) {
  if (!project.sigmaExpediente || !visoBundle?.byGrupo?.size) return;
  const g = expedienteGrupoKeyFromVariant(project.sigmaExpediente);
  const v = visoBundle.byGrupo.get(g);
  if (!v || v.sinDatosVisor) return;

  const tram = Array.isArray(v.tramitacion) ? v.tramitacion : [];
  const docUrls = Array.isArray(v.documentacionUrls) ? v.documentacionUrls : [];
  const nti = v.ntiArbol && typeof v.ntiArbol === "object" ? v.ntiArbol : null;
  const hasNti = nti != null && typeof nti.documentosTotal === "number";

  if (!tram.length && !docUrls.length && !hasNti) return;

  project.sigmaVisorFetchedAt = visoBundle.generatedAt ?? null;
  if (v.visorUrlUsada && String(v.visorUrlUsada).trim())
    project.sigmaVisorUrl = String(v.visorUrlUsada).trim();
  if (tram.length) project.sigmaVisorTramitacion = tram;
  if (docUrls.length) project.sigmaVisorDocumentacionUrls = docUrls;
  if (v.ntiListadoUrl && String(v.ntiListadoUrl).trim())
    project.sigmaVisorNtiListadoUrl = String(v.ntiListadoUrl).trim();
  if (hasNti) {
    project.sigmaVisorNtiDocumentosTotal = nti.documentosTotal;
    const ntiDocs =
      Array.isArray(nti.documentos) && nti.documentos.length
        ? nti.documentos
        : Array.isArray(nti.documentosMuestra)
          ? nti.documentosMuestra
          : [];
    if (ntiDocs.length)
      project.sigmaVisorNtiDocumentosMuestra = ntiDocs.slice(0, 40);
  }
  if (v.visorCabecera && typeof v.visorCabecera === "object")
    project.sigmaVisorCabecera = v.visorCabecera;
}

function parseRelevante(row) {
  const v = String(row.es_relevante ?? "")
    .trim()
    .toLowerCase();
  if (v === "true" || v === "1" || v === "yes") return true;
  if (v === "false" || v === "0" || v === "no") return false;
  return null;
}

function territorioForSource(sourceId) {
  const sid = (sourceId || "bocm").trim().toLowerCase();
  return (
    TERRITORIO_BY_SOURCE[sid] || {
      id: sid.replace(/[^a-z0-9]+/g, "-"),
      label: sid.toUpperCase(),
    }
  );
}

function countJsonlLines(path) {
  if (!existsSync(path)) return null;
  const raw = readFileSync(path, "utf-8");
  if (!raw.trim()) return 0;
  return raw.split("\n").filter((l) => l.trim()).length;
}

function centroidFromGeometry(geom) {
  if (!geom || !geom.coordinates) return null;
  const pts = [];
  const walk = (c, depth) => {
    if (depth > 4) return;
    if (typeof c[0] === "number" && typeof c[1] === "number") {
      pts.push([c[0], c[1]]);
      return;
    }
    for (const x of c) walk(x, depth + 1);
  };
  walk(geom.coordinates, 0);
  if (!pts.length) return null;
  const lon = pts.reduce((a, p) => a + p[0], 0) / pts.length;
  const lat = pts.reduce((a, p) => a + p[1], 0) / pts.length;
  return [lat, lon];
}

/** Primer registro gana (claves estables en sector_geometry). */
function registerCentroid(byKey, key, entry) {
  if (!key || byKey.has(key)) return;
  byKey.set(key, entry);
}

/** Registra centroide por nº expediente SIGMA; `overwrite` permite que IP sustituya AD. */
function putSigmaCentroid(byExp, key, entry, overwrite) {
  if (!key) return;
  if (!overwrite && byExp.has(key)) return;
  byExp.set(key, entry);
}

function loadSectorCentroids() {
  const byKey = new Map();
  const byMunicipio = new Map();
  if (!existsSync(sectorGeoPath)) {
    console.warn("Sin sector_geometry_map.geojson — ejecuta: python3 -m sector_geometry.export_map_geojson");
    return { byKey, byMunicipio };
  }
  const fc = JSON.parse(readFileSync(sectorGeoPath, "utf-8"));
  for (const f of fc.features || []) {
    const p = f.properties || {};
    const sk = p.stable_key;
    const c = centroidFromGeometry(f.geometry);
    if (!c) continue;
    const entry = { lat: c[0], lng: c[1], resolverId: p.resolver_id || null };
    registerCentroid(byKey, sk, entry);
    const legacyFromProps = legacySectorKey({
      municipio: p.municipio,
      nombreSector: p.sector,
      municipioProvincia: p.provincia_linea,
    });
    registerCentroid(byKey, legacyFromProps, entry);
    const m = normText(p.municipio);
    if (m && !byMunicipio.has(m)) byMunicipio.set(m, entry);
  }
  return { byKey, byMunicipio };
}

function loadMadridSigmaCentroids() {
  const byExp = new Map();

  function ingestSigmaGeo(path, geoSource, overwrite) {
    if (!existsSync(path)) return;
    try {
      const fc = JSON.parse(readFileSync(path, "utf-8"));
      for (const f of fc.features || []) {
        const props = f.properties || {};
        const num = props.EXP_TX_NUMERO;
        const c = centroidFromGeometry(f.geometry);
        if (num == null || num === "" || !c) continue;
        const entry = { lat: c[0], lng: c[1], sigmaGeoSource: geoSource };
        for (const v of expVariants(String(num))) putSigmaCentroid(byExp, v, entry, overwrite);
      }
    } catch {
      /* omitir archivo corrupto */
    }
  }

  /* Primero catálogo AD (~3k); luego IP (pocos), que sustituye si el expediente está en ambos. */
  ingestSigmaGeo(madridAytoAdGeoPath, "ad", false);
  ingestSigmaGeo(madridAytoGestionGeoPath, "gestion", false);
  ingestSigmaGeo(madridAytoUrbanGeoPath, "urbanizacion", false);
  ingestSigmaGeo(madridAytoIpGeoPath, "ip", true);

  return byExp;
}

function rowToProject(row, { defaultSourceId }) {
  const sourceId = (row.boletin_source_id || defaultSourceId || "bocm").trim().toLowerCase();
  const terr = territorioForSource(sourceId);
  const municipio = (row.municipio || "").trim();
  const nombreSector = (row.nombre_sector || "").trim();
  const municipioProvincia = (row.municipio_provincia || "").trim();
  const fp = (row.proyecto_fingerprint || "").trim();
  const pubDate = row.bocm_date || row.date_pub || row.fecha || "";
  const artNum = row.art_num || row.id || "";

  const sectorKey = stableSectorKey({
    boletinSourceId: sourceId,
    municipio,
    nombreSector,
    municipioProvincia,
  });
  const sectorGeoKey = legacySectorKey({ municipio, nombreSector, municipioProvincia });

  return {
    sourceId,
    territorioId: terr.id,
    territorioLabel: terr.label,
    pubDate,
    artNum,
    fp,
    municipio,
    nombreSector,
    municipioProvincia,
    sectorKey,
    sectorGeoKey,
    esRelevante: parseRelevante(row),
    parseError: (row.error || "").trim() || null,
    row,
  };
}

function lookupSectorCentroid(parsed, sectorCentroids) {
  const keys = [parsed.sectorKey, parsed.sectorGeoKey].filter(Boolean);
  for (const k of keys) {
    const hit = sectorCentroids.byKey.get(k);
    if (hit) return hit;
  }
  return null;
}

function resolveCoords(parsed, coordsCache, sectorCentroids, madridSigmaCentroids, sigmaLink) {
  const { municipio } = parsed;

  if (sigmaLink?.sigma_expediente && madridSigmaCentroids?.size) {
    for (const v of expVariants(sigmaLink.sigma_expediente)) {
      const sigma = madridSigmaCentroids.get(v);
      if (sigma) {
        const srcByGeo = {
          ip: "sigma_madrid_ip",
          ad: "sigma_madrid_ad",
          gestion: "sigma_madrid_gestion",
          urbanizacion: "sigma_madrid_urbanizacion",
        };
        const src = srcByGeo[sigma.sigmaGeoSource] || "sigma_madrid_ad";
        return { lat: sigma.lat, lng: sigma.lng, coordSource: src };
      }
    }
  }

  const fromSector = lookupSectorCentroid(parsed, sectorCentroids);
  if (fromSector) {
    return { lat: fromSector.lat, lng: fromSector.lng, coordSource: "sector_geometry" };
  }

  const m = normText(municipio);
  if (m) {
    const fb = sectorCentroids.byMunicipio.get(m);
    if (fb) return { lat: fb.lat, lng: fb.lng, coordSource: "sector_geometry_municipio" };
  }

  if (municipio && coordsCache[municipio]) {
    const c = coordsCache[municipio];
    return { lat: c[0], lng: c[1], coordSource: "municipio_cache" };
  }

  return { lat: null, lng: null, coordSource: null };
}

function buildProject(parsed, coordsCache, sectorCentroids, madridAytoLinks, madridSigmaCentroids) {
  const {
    row,
    sourceId,
    territorioId,
    territorioLabel,
    pubDate,
    artNum,
    fp,
    municipio,
    nombreSector,
    sectorKey,
    sectorGeoKey,
    esRelevante,
    parseError,
  } = parsed;
  const projectId = `${sourceId}-${pubDate}-${artNum}-${fp || sectorKey.slice(0, 12) || "na"}`;
  const sigmaLink = madridAytoLinks?.get(projectId);
  const { lat, lng, coordSource } = resolveCoords(
    parsed,
    coordsCache,
    sectorCentroids,
    madridSigmaCentroids,
    sigmaLink,
  );

  return {
    id: projectId,
    sourceId,
    sourceLabel: territorioLabel,
    territorioId,
    territorioLabel,
    bocmDate: pubDate,
    artNum: String(artNum),
    title: row.title || "",
    pdfUrl: row.pdf_url || null,
    municipio,
    tipoInstrumento: row.tipo_instrumento || "",
    nombreSector,
    estadoTramitacion: row.estado_tramitacion || "",
    fechaAcuerdo: row.fecha_acuerdo || null,
    organo: row.organo_aprobador || "",
    promotor: (row.promotor_o_propietario || "").trim() || null,
    numViviendas:
      row.num_viviendas_max !== undefined &&
      row.num_viviendas_max !== "" &&
      !Number.isNaN(Number(row.num_viviendas_max))
        ? Number(row.num_viviendas_max)
        : null,
    supTotalM2:
      row.sup_total_m2 !== undefined && row.sup_total_m2 !== "" && !Number.isNaN(Number(row.sup_total_m2))
        ? Number(row.sup_total_m2)
        : null,
    supEdificableM2:
      row.sup_edificable_m2 !== undefined &&
      row.sup_edificable_m2 !== "" &&
      !Number.isNaN(Number(row.sup_edificable_m2))
        ? Number(row.sup_edificable_m2)
        : null,
    tipoVivienda: (row.tipo_vivienda || "").trim() || null,
    resumen: row.resumen || "",
    municipioProvincia: row.municipio_provincia || "",
    categoriasTematicas: row.categorias_tematicas || null,
    economicoResumen: row.economico_resumen || null,
    procedimientoExpediente: row.procedimiento_expediente || null,
    procedimientoTipo: (row.procedimiento_tipo || "").trim() || null,
    importeTotalEur:
      row.importe_total_eur_estimado !== undefined &&
      row.importe_total_eur_estimado !== "" &&
      !Number.isNaN(Number(row.importe_total_eur_estimado))
        ? Number(row.importe_total_eur_estimado)
        : null,
    requiereSegundaPasada:
      row.requiere_segunda_pasada === true ||
      row.requiere_segunda_pasada === "True" ||
      row.requiere_segunda_pasada === "true",
    charsTextoTotal:
      row.chars_texto_total !== undefined && row.chars_texto_total !== ""
        ? Number(row.chars_texto_total)
        : null,
    esRelevante,
    parseError,
    sectorKey,
    sectorGeoKey: parsed.sectorGeoKey,
    coordSource,
    lat,
    lng,
    sigmaMatchType: sigmaLink?.match_type ?? null,
    sigmaMatchScore: sigmaLink?.match_score ?? null,
    sigmaExpediente: sigmaLink?.sigma_expediente ?? null,
    sigmaDenominacion: sigmaLink?.sigma_denominacion ?? null,
    sigmaFase: sigmaLink?.sigma_fase ?? null,
    sigmaEnlace: sigmaLink?.sigma_enlace ?? null,
    sigmaEnIp: sigmaLink?.sigma_en_ip === true,
  };
}

function parseCsv(path) {
  if (!existsSync(path)) return [];
  const raw = readFileSync(path, "utf-8");
  return parse(raw, { columns: true, skip_empty_lines: true, relax_column_count: true });
}

function ingestRows(rows, defaultSourceId, projects, seenIds, statsBySource, madridAytoLinks, madridSigmaCentroids) {
  for (const row of rows) {
    const parsed = rowToProject(row, { defaultSourceId });
    const p = buildProject(parsed, coords, sectorCentroids, madridAytoLinks, madridSigmaCentroids);
    if (seenIds.has(p.id)) continue;
    seenIds.add(p.id);
    projects.push(p);

    const sid = p.sourceId;
    if (!statsBySource.has(sid)) {
      const terr = territorioForSource(sid);
      statsBySource.set(sid, {
        sourceId: sid,
        territorioId: terr.id,
        territorioLabel: terr.label,
        csvRows: 0,
        relevant: 0,
        notRelevant: 0,
        relevanceUnknown: 0,
        withMunicipio: 0,
        withSector: 0,
        withCoords: 0,
        parseErrors: 0,
      });
    }
    const st = statsBySource.get(sid);
    st.csvRows += 1;
    if (p.esRelevante === true) st.relevant += 1;
    else if (p.esRelevante === false) st.notRelevant += 1;
    else st.relevanceUnknown += 1;
    if (p.municipio) st.withMunicipio += 1;
    if (p.municipio && p.nombreSector) st.withSector += 1;
    if (p.lat != null && p.lng != null) st.withCoords += 1;
    if (p.parseError) st.parseErrors += 1;
  }
}

function buildAdminCoverage(statsBySource, projects) {
  const sources = [];
  let indexTotal = 0;
  let csvTotal = 0;
  let relevantTotal = 0;
  let gapTotal = 0;

  const allSourceIds = new Set([
    ...Object.keys(INDEX_BY_SOURCE),
    ...statsBySource.keys(),
  ]);

  for (const sid of [...allSourceIds].sort()) {
    const st = statsBySource.get(sid) || {
      sourceId: sid,
      territorioId: territorioForSource(sid).id,
      territorioLabel: territorioForSource(sid).label,
      csvRows: 0,
      relevant: 0,
      notRelevant: 0,
      relevanceUnknown: 0,
      withMunicipio: 0,
      withSector: 0,
      withCoords: 0,
      parseErrors: 0,
    };
    const indexPath = INDEX_BY_SOURCE[sid];
    const indexPdfCount = indexPath ? countJsonlLines(indexPath) : null;
    const indexGap =
      indexPdfCount != null && indexPdfCount > st.csvRows ? indexPdfCount - st.csvRows : null;
    const parseCoveragePct =
      indexPdfCount != null && indexPdfCount > 0
        ? Math.round((st.csvRows / indexPdfCount) * 1000) / 10
        : null;

    if (indexPdfCount != null) indexTotal += indexPdfCount;
    csvTotal += st.csvRows;
    relevantTotal += st.relevant;
    if (indexGap != null) gapTotal += indexGap;

    sources.push({
      ...st,
      indexPdfCount,
      indexGap,
      parseCoveragePct,
      inWeb: st.csvRows,
      relevantPct:
        st.csvRows > 0 ? Math.round((st.relevant / st.csvRows) * 1000) / 10 : null,
      sectorPct:
        st.relevant > 0 ? Math.round((st.withSector / st.relevant) * 1000) / 10 : null,
      coordsPct:
        st.csvRows > 0 ? Math.round((st.withCoords / st.csvRows) * 1000) / 10 : null,
    });
  }

  sources.sort((a, b) => (b.indexPdfCount ?? b.csvRows) - (a.indexPdfCount ?? a.csvRows));

  const gaps = [];
  for (const s of sources) {
    if (s.indexGap != null && s.indexGap > 500) {
      gaps.push({
        priority: s.parseCoveragePct != null && s.parseCoveragePct < 15 ? "high" : "medium",
        sourceId: s.sourceId,
        territorioLabel: s.territorioLabel,
        label: `Parseo pendiente (${s.territorioLabel})`,
        detail: `${s.indexGap.toLocaleString("es-ES")} PDFs en índice sin fila en CSV (${s.parseCoveragePct ?? "?"}% parseado).`,
      });
    }
    if (s.csvRows > 50 && s.relevantPct != null && s.relevantPct < 25) {
      gaps.push({
        priority: "medium",
        sourceId: s.sourceId,
        territorioLabel: s.territorioLabel,
        label: `Baja relevancia (${s.territorioLabel})`,
        detail: `Solo ${s.relevantPct}% marcados relevantes; el índice «vivienda» incluye mucho fuera de planeamiento.`,
      });
    }
    if (s.relevant > 100 && s.sectorPct != null && s.sectorPct < 20) {
      gaps.push({
        priority: "medium",
        sourceId: s.sourceId,
        territorioLabel: s.territorioLabel,
        label: `Poco sector/municipio (${s.territorioLabel})`,
        detail: `${s.sectorPct}% de relevantes con municipio+sector; revisar prompt LLM o filtros.`,
      });
    }
    if (s.relevant > 50 && s.coordsPct != null && s.coordsPct < 15) {
      gaps.push({
        priority: "low",
        sourceId: s.sourceId,
        territorioLabel: s.territorioLabel,
        label: `Geocodificación débil (${s.territorioLabel})`,
        detail: `${s.coordsPct}% con coordenadas en web; faltan resolvers GIS o caché municipal.`,
      });
    }
    if (s.parseErrors > 20) {
      gaps.push({
        priority: "high",
        sourceId: s.sourceId,
        territorioLabel: s.territorioLabel,
        label: `Errores de parseo (${s.territorioLabel})`,
        detail: `${s.parseErrors.toLocaleString("es-ES")} filas con campo error en CSV.`,
      });
    }
  }

  gaps.sort((a, b) => {
    const rank = { high: 0, medium: 1, low: 2 };
    return rank[a.priority] - rank[b.priority];
  });

  const withCoords = projects.filter((p) => p.lat != null && p.lng != null).length;

  return {
    generatedAt: new Date().toISOString(),
    totals: {
      indexPdfCount: indexTotal,
      csvRows: csvTotal,
      inWeb: projects.length,
      relevant: relevantTotal,
      notRelevant: projects.filter((p) => p.esRelevante === false).length,
      relevanceUnknown: projects.filter((p) => p.esRelevante == null).length,
      withCoords,
      indexGap: gapTotal,
    },
    sources,
    gaps: gaps.slice(0, 40),
    madridCapital: buildMadridCapitalBlock(projects, loadMadridAytoMatch()),
  };
}

function countMadridAytoResolverMatches() {
  if (!existsSync(sectorGeoPath)) return 0;
  try {
    const fc = JSON.parse(readFileSync(sectorGeoPath, "utf-8"));
    return (fc.features || []).filter(
      (f) => f?.properties?.resolver_id === "madrid_ayto_pgoum_ambito",
    ).length;
  } catch {
    return 0;
  }
}

function loadMadridAytoMatch() {
  if (!existsSync(madridAytoMatchPath)) return null;
  try {
    return JSON.parse(readFileSync(madridAytoMatchPath, "utf-8"));
  } catch {
    return null;
  }
}

/** bocm_id → enlace SIGMA (solo Madrid capital con match). */
function loadMadridAytoLinksByBocmId() {
  const map = new Map();
  if (!existsSync(madridAytoLinksPath)) return map;
  const raw = readFileSync(madridAytoLinksPath, "utf-8");
  for (const line of raw.split("\n")) {
    const t = line.trim();
    if (!t) continue;
    try {
      const o = JSON.parse(t);
      if (o.bocm_id) map.set(o.bocm_id, o);
    } catch {
      /* skip */
    }
  }
  return map;
}

/** Solo municipio «Madrid» (capital); no confundir con toda la CM en BOCM. */
function buildMadridCapitalBlock(projects, madridMatch) {
  const madrid = projects.filter((p) => normText(p.municipio) === "madrid");
  const relevant = madrid.filter((p) => p.esRelevante === true);
  const withSector = relevant.filter((p) => p.nombreSector);
  const withCoords = madrid.filter((p) => p.lat != null && p.lng != null);
  const sigmaCoordSources = new Set([
    "sigma_madrid_ip",
    "sigma_madrid_ad",
    "sigma_madrid_gestion",
    "sigma_madrid_urbanizacion",
  ]);
  const withSigmaPrecise = madrid.filter((p) => sigmaCoordSources.has(p.coordSource));
  const withSigmaIp = madrid.filter((p) => p.coordSource === "sigma_madrid_ip");
  const withSigmaAd = madrid.filter((p) => p.coordSource === "sigma_madrid_ad");
  const madridMatchedSigma = madrid.filter((p) => p.sigmaExpediente);
  const matchedWithSigmaPrecise = madridMatchedSigma.filter((p) =>
    sigmaCoordSources.has(p.coordSource),
  );
  const aytoResolver = countMadridAytoResolverMatches();

  const block = {
    note: "Filas con municipio=Madrid (capital). El territorio BOCM abarca toda la Comunidad.",
    bocmFilasWeb: madrid.length,
    bocmRelevantes: relevant.length,
    bocmConSector: withSector.length,
    bocmConCoords: withCoords.length,
    bocmCoordsDesdeSigmaPoligono: withSigmaPrecise.length,
    bocmCoordsSigmaPoligonoIp: withSigmaIp.length,
    bocmCoordsSigmaPoligonoAd: withSigmaAd.length,
    bocmConMatchSigmaConUbicPoligono: matchedWithSigmaPrecise.length,
    bocmConMatchSigmaTotal: madridMatchedSigma.length,
    bocmResolverAytoPgoum: aytoResolver,
    sigmaSyncAt: madridMatch?.generatedAt ?? null,
    sigmaExpedientesIp: madridMatch?.sigma?.expedientes_ip_total ?? null,
    sigmaSinBocm: madridMatch?.sigma?.expedientes_ip_sin_bocm ?? null,
    bocmMatchSigma: madridMatch?.bocm_madrid_ciudad?.match_total ?? null,
    bocmMatchPctRelevantes: madridMatch?.bocm_madrid_ciudad?.pct_match_relevantes ?? null,
    samplesSigmaSinBocm: madridMatch?.sigma?.samples_sin_bocm?.slice(0, 5) ?? [],
    samplesBocmSinMatch: madridMatch?.bocm_madrid_ciudad?.samples_sin_match?.slice(0, 5) ?? [],
  };

  if (madridMatch == null) {
    block.syncHint =
      "Ejecuta: python3 -m sector_geometry.madrid_ayto_sync (desde poc-bocm/) y vuelve a npm run build-data";
  }
  return block;
}

const coords = existsSync(coordsPath) ? JSON.parse(readFileSync(coordsPath, "utf-8")) : {};
const sectorCentroids = loadSectorCentroids();
const madridSigmaCentroids = loadMadridSigmaCentroids();
console.log(
  `SIGMA centroides indexados (variantes de n.º expediente; IP sobrescribe AD si ambos existen): ${madridSigmaCentroids.size.toLocaleString("es-ES")}`,
);
const madridAytoLinks = loadMadridAytoLinksByBocmId();

const projects = [];
const seenIds = new Set();
const statsBySource = new Map();

ingestRows(parseCsv(bocmCsv), "bocm", projects, seenIds, statsBySource, madridAytoLinks, madridSigmaCentroids);
if (!isMadridPublicBuild && existsSync(ccaaCsv)) {
  ingestRows(parseCsv(ccaaCsv), "", projects, seenIds, statsBySource, madridAytoLinks, madridSigmaCentroids);
} else if (!isMadridPublicBuild) {
  console.log("Aviso: sin ccaa_history_parsed_incremental.csv");
}

projects.sort((a, b) => {
  if (a.bocmDate !== b.bocmDate) return b.bocmDate.localeCompare(a.bocmDate);
  return a.artNum.localeCompare(b.artNum);
});

const madridSigmaIndexBundle = loadMadridSigmaIndexBundle(madridSigmaIndexPath);
const madridVisoBundle = loadMadridVisoBundle(madridVisoExpedientesPath);
const madridMencionesExp = buildMadridBoletinMentionsByExpediente(parseCsv(bocmCsv));
for (const p of projects) enrichProjectSigmaBoletines(p, madridSigmaIndexBundle, madridMencionesExp);
for (const p of projects) enrichProjectSigmaVisor(p, madridVisoBundle);

const ntiExportScript = join(pocRoot, "db/export_nti_for_web.py");
if (existsSync(ntiExportScript)) {
  try {
    const ntiOut = execSync(`python3 "${ntiExportScript}"`, { cwd: pocRoot, encoding: "utf-8" });
    console.log("sigma-nti-linked:", ntiOut.trim());
  } catch (err) {
    console.warn("sigma-nti-linked export omitido:", err?.message || err);
  }
}

const madridVisorTramitacionProyectos = projects.filter(
  (p) => (p.sigmaVisorTramitacion?.length ?? 0) > 0,
).length;

const exportProjects = isMadridPublicBuild
  ? projects.filter((p) => normText(p.municipio) === "madrid")
  : projects;

if (isMadridPublicBuild) {
  console.log(
    `Export web: ${exportProjects.length.toLocaleString("es-ES")} proyectos Madrid capital (de ${projects.length.toLocaleString("es-ES")} filas BOCM ingestadas)`,
  );
}

const adminCoverage = isMadridPublicBuild
  ? null
  : buildAdminCoverage(statsBySource, projects);

const byMunicipio = new Map();
const byTipo = new Map();
const byYear = new Map();
const byTerritorio = new Map();
const byTerritorioRelevant = new Map();
const bySource = new Map();
let dateMin = "9999";
let dateMax = "0000";
let withCoords = 0;
let totalRelevant = 0;
let totalNotRelevant = 0;
let totalRelevanceUnknown = 0;
let coordSigmaIp = 0;
let coordSigmaAd = 0;

for (const p of exportProjects) {
  if (p.lat != null && p.lng != null) withCoords += 1;
  if (p.coordSource === "sigma_madrid_ip") coordSigmaIp += 1;
  if (p.coordSource === "sigma_madrid_ad") coordSigmaAd += 1;
  if (p.coordSource === "sigma_madrid_gestion" || p.coordSource === "sigma_madrid_urbanizacion") {
    coordSigmaAd += 1;
  }
  if (p.esRelevante === true) totalRelevant += 1;
  else if (p.esRelevante === false) totalNotRelevant += 1;
  else totalRelevanceUnknown += 1;

  if (p.municipio) byMunicipio.set(p.municipio, (byMunicipio.get(p.municipio) || 0) + 1);
  const t = p.tipoInstrumento || "Sin clasificar";
  byTipo.set(t, (byTipo.get(t) || 0) + 1);
  const y = p.bocmDate.slice(0, 4);
  if (y && y.length === 4) {
    byYear.set(y, (byYear.get(y) || 0) + 1);
    if (y < dateMin) dateMin = y;
    if (y > dateMax) dateMax = y;
  }
  byTerritorio.set(p.territorioLabel, (byTerritorio.get(p.territorioLabel) || 0) + 1);
  if (p.esRelevante === true) {
    byTerritorioRelevant.set(
      p.territorioLabel,
      (byTerritorioRelevant.get(p.territorioLabel) || 0) + 1,
    );
  }
  bySource.set(p.sourceId, (bySource.get(p.sourceId) || 0) + 1);
}

const sortEntries = (m) =>
  [...m.entries()].sort((a, b) => b[1] - a[1]).map(([name, count]) => ({ name, count }));

const summary = {
  generatedAt: new Date().toISOString(),
  total: exportProjects.length,
  buildScope: isMadridPublicBuild ? "madrid-public" : "full",
  totalRelevant,
  totalNotRelevant,
  totalRelevanceUnknown,
  withCoords,
  coordsDesdeSigmaPolygon: {
    ip: coordSigmaIp,
    ad: coordSigmaAd,
    total: coordSigmaIp + coordSigmaAd,
  },
  dateRange: {
    min: dateMin === "9999" ? null : dateMin,
    max: dateMax === "0000" ? null : dateMax,
  },
  byMunicipio: sortEntries(byMunicipio).slice(0, 50),
  byTipo: sortEntries(byTipo).slice(0, 30),
  byYear: [...byYear.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([year, count]) => ({ year, count })),
  byTerritorio: sortEntries(byTerritorio),
  byTerritorioRelevant: sortEntries(byTerritorioRelevant),
  bySource: sortEntries(bySource),
  portal: {
    name: "Homes · Urbanismo",
    tagline: "Proyectos urbanísticos en tu zona",
  },
};

const madridSigmaBocmByExp = buildMadridSigmaBocmProjectsByExpediente(exportProjects);

mkdirSync(outDir, { recursive: true });
writeFileSync(join(outDir, "projects.json"), JSON.stringify(exportProjects));
writeFileSync(join(outDir, "summary.json"), JSON.stringify(summary, null, 2));
if (adminCoverage) {
  writeFileSync(join(outDir, "admin-coverage.json"), JSON.stringify(adminCoverage, null, 2));
}
writeFileSync(
  join(outDir, "madrid-sigma-bocm-projects.json"),
  JSON.stringify({
    generatedAt: summary.generatedAt,
    expedienteKeys: Object.keys(madridSigmaBocmByExp).length,
    byExpediente: madridSigmaBocmByExp,
  }),
);
console.log(
  `OK: madrid-sigma-bocm-projects.json (${Object.keys(madridSigmaBocmByExp).length} expedientes con ficha BOCM)`,
);

if (existsSync(madridSigmaIndexPath)) {
  copyFileSync(madridSigmaIndexPath, join(outDir, "madrid-sigma.json"));
  console.log("OK: madrid-sigma.json copiado");
}
if (existsSync(madridVisoExpedientesPath)) {
  const visoRaw = JSON.parse(readFileSync(madridVisoExpedientesPath, "utf-8"));
  const byG = visoRaw.byGrupoExpediente || {};
  const slim = {};
  for (const [grupo, rec] of Object.entries(byG)) {
    if (!rec || typeof rec !== "object") continue;
    const nti = rec.ntiArbol || {};
    const docs = nti.documentos || nti.documentosMuestra || [];
    slim[grupo] = {
      expedienteGrupo: grupo,
      sinDatosVisor: rec.sinDatosVisor,
      visorUrlUsada: rec.visorUrlUsada,
      visorCabecera: rec.visorCabecera,
      visorFicha: rec.visorFicha,
      tramitacion: rec.tramitacion,
      documentacionUrls: rec.documentacionUrls,
      ntiListadoUrl: rec.ntiListadoUrl,
      ntiDocumentosTotal:
        typeof nti.documentosTotal === "number" ? nti.documentosTotal : null,
      ntiDocumentosMuestra: Array.isArray(docs) ? docs.slice(0, 15) : [],
    };
  }
  const slimPath = join(outDir, "madrid-sigma-visor-slim.json");
  writeFileSync(
    slimPath,
    JSON.stringify(
      {
        generatedAt: visoRaw.generatedAt,
        conVisorFicha: visoRaw.conVisorFicha,
        byGrupoExpediente: slim,
      },
      null,
      0,
    ),
  );
  console.log(
    `OK: madrid-sigma-visor-slim.json (${Object.keys(slim).length} expedientes, sin árboles NTI completos)`,
  );
}

const sigmaClasificacionExport = join(pocRoot, "db", "export_sigma_clasificacion_web.py");
if (existsSync(sigmaClasificacionExport)) {
  try {
    const r = spawnSync("python3", [sigmaClasificacionExport, join(outDir, "madrid-sigma-clasificacion.json")], {
      cwd: pocRoot,
      encoding: "utf-8",
    });
    if (r.status === 0) {
      console.log((r.stdout || "").trim() || "OK: madrid-sigma-clasificacion.json");
    } else {
      console.warn("SIGMA clasificación web:", r.stderr?.slice(0, 200) || r.stdout?.slice(0, 200));
    }
  } catch (err) {
    console.warn("SIGMA clasificación web:", err?.message || err);
  }
}
if (existsSync(madridAytoIpGeoPath)) {
  copyFileSync(madridAytoIpGeoPath, join(outDir, "madrid-sigma-ip.geojson"));
  console.log("OK: madrid-sigma-ip.geojson copiado");
}
if (existsSync(madridAytoAdGeoPath)) {
  copyFileSync(madridAytoAdGeoPath, join(outDir, "madrid-sigma-ad.geojson"));
  console.log("OK: madrid-sigma-ad.geojson copiado");
} else {
  console.log("Aviso: sin output/madrid_ayto_expedientes_ad.geojson (mapa AD no disponible hasta sync)");
}
if (existsSync(madridAytoGestionGeoPath)) {
  copyFileSync(madridAytoGestionGeoPath, join(outDir, "madrid-sigma-gestion.geojson"));
  console.log("OK: madrid-sigma-gestion.geojson copiado");
}
if (existsSync(madridAytoUrbanGeoPath)) {
  copyFileSync(madridAytoUrbanGeoPath, join(outDir, "madrid-sigma-urbanizacion.geojson"));
  console.log("OK: madrid-sigma-urbanizacion.geojson copiado");
}

buildMadridSigmaMetricsWeb();
buildLandingNewsSpotlight();

try {
  await buildMadridLicenciasWeb({
    jsonlPath: madridLicenciasJsonlPath,
    outDir,
    minYear: isMadridPublicBuild ? LICENCIAS_MIN_YEAR_PUBLIC : undefined,
  });
  if (isMadridPublicBuild) {
    for (const name of readdirSync(outDir)) {
      const m = /^madrid-licencias-(\d{4})\.(json|geojson)$/.exec(name);
      if (m && Number(m[1]) < LICENCIAS_MIN_YEAR_PUBLIC) {
        unlinkSync(join(outDir, name));
        console.log(`OK: eliminado ${name} (fuera de alcance público)`);
      }
    }
  }
} catch (err) {
  console.warn("Licencias urbanísticas (web):", err?.message || err);
}

try {
  buildMadridDashboardStats({ outDir });
} catch (err) {
  console.warn("Dashboard Madrid (stats):", err?.message || err);
}

const ubicacionesExport = join(pocRoot, "db", "export_ubicaciones_web.py");
const ubicacionesDb = join(pocRoot, "db", "poc_local.sqlite");
if (existsSync(ubicacionesExport) && existsSync(ubicacionesDb)) {
  try {
    const r = spawnSync("python3", [ubicacionesExport, ubicacionesDb], {
      cwd: pocRoot,
      encoding: "utf-8",
    });
    if (r.status === 0) {
      console.log("OK: ubicaciones-map.geojson + search (SQLite v2)");
    } else {
      console.warn("Ubicaciones web:", r.stderr?.slice(0, 200) || r.stdout?.slice(0, 200));
    }
  } catch (err) {
    console.warn("Ubicaciones web:", err?.message || err);
  }
} else {
  console.log(
    "Aviso: sin poc_local.sqlite — ejecuta db/migrate_sqlite.py y db/ingest_madrid_ubicacion.py",
  );
}

const sigmaAmbitosExport = join(pocRoot, "db", "export_sigma_ambito_web.py");
if (existsSync(sigmaAmbitosExport) && existsSync(ubicacionesDb)) {
  try {
    const r = spawnSync("python3", [sigmaAmbitosExport, ubicacionesDb], {
      cwd: pocRoot,
      encoding: "utf-8",
    });
    if (r.status === 0) {
      console.log((r.stdout || "").trim() || "OK: madrid-sigma-ambitos.geojson (SQLite)");
    } else {
      console.warn("SIGMA ámbitos web:", r.stderr?.slice(0, 200) || r.stdout?.slice(0, 200));
    }
  } catch (err) {
    console.warn("SIGMA ámbitos web:", err?.message || err);
  }
}

const sigmaAmbitosPath = join(outDir, "madrid-sigma-ambitos.geojson");
const landingScript = join(webRoot, "scripts", "build-madrid-sigma-ambitos-landing.mjs");
if (existsSync(sigmaAmbitosPath) && existsSync(landingScript)) {
  try {
    const lr = spawnSync("node", [landingScript], { cwd: webRoot, encoding: "utf-8" });
    if (lr.status === 0) console.log((lr.stdout || "").trim());
    else console.warn("SIGMA landing map:", lr.stderr?.slice(0, 200) || lr.stdout?.slice(0, 200));
  } catch (err) {
    console.warn("SIGMA landing map:", err?.message || err);
  }
}

if (existsSync(sectorGeoPath)) {
  copyFileSync(sectorGeoPath, join(outDir, "sector-geometries.geojson"));
  console.log("OK: sector-geometries.geojson copiado");
} else {
  writeFileSync(
    join(outDir, "sector-geometries.geojson"),
    JSON.stringify({ type: "FeatureCollection", features: [] }),
  );
}

console.log(
  `OK: ${exportProjects.length} projects (${totalRelevant} relevantes, ${withCoords} con coords; ` +
    `Madrid visor tramitación ${madridVisorTramitacionProyectos}) → public/data/`,
);
const mc = adminCoverage?.madridCapital;
if (mc?.bocmCoordsDesdeSigmaPoligono != null) {
  console.log(
    `    Madrid · ubicación desde polígono SIGMA: ${mc.bocmCoordsDesdeSigmaPoligono} (` +
      `${mc.bocmCoordsSigmaPoligonoIp ?? 0} IP, ${mc.bocmCoordsSigmaPoligonoAd ?? 0} AD); ` +
      `match expediente + polígono: ${mc.bocmConMatchSigmaConUbicPoligono ?? "—"} / ${mc.bocmConMatchSigmaTotal ?? "—"} con SIGMA`,
  );
}
console.log(
  `    Global · coordsDesdeSigmaPolygon (todos los territorios): ip=${coordSigmaIp}, ad=${coordSigmaAd}, total=${coordSigmaIp + coordSigmaAd}`,
);
if (adminCoverage) {
  console.log(
    `OK: admin-coverage.json (${adminCoverage.sources.length} fuentes, ${adminCoverage.gaps.length} alertas)`,
  );
}
