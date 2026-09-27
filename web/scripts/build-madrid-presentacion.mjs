/**
 * Agregado corto para la carta de presentación de Madrid.
 * Lee los filter-rows ya generados y, para barrios, el fichero de licencias de 2025.
 */
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { normalizarActuacionEdificio } from "./lib/actuacion-edificio.mjs";

const OPEN_FASE = new Set([
  "en_tramitacion",
  "aprobacion_inicial",
  "aprobacion_provisional",
  "informacion_publica",
]);

const LABELS = {
  gran_desarrollo_residencial: "Gran desarrollo residencial",
  residencial_o_vivienda: "Vivienda",
  urbanizacion_infraestructuras: "Calles o redes",
  gestion_reparcelacion: "Reparcelación",
  proteccion_catalogo: "Protección de catálogo",
  equipamiento_dotacional: "Equipamiento",
  terciario_comercial_hotelero: "Terciario o comercial",
  plan_especial_uso_actividad: "Uso en edificio existente",
  modificacion_planeamiento_general: "Cambio del plan general",
  ordenacion_parcela_manzana: "Ordenación de parcela o manzana",
  ajuste_administrativo: "Ajuste administrativo",
  planeamiento_otros: "Otro planeamiento",
  modificacion_pgou: "Modificación del PGOU",
  estudio_detalle: "Estudio de detalle",
  plan_parcial: "Plan parcial",
  plan_especial: "Plan especial",
  proyecto_urbanizacion: "Proyecto de urbanización",
  catalogacion_proteccion: "Catalogación / protección",
  otro_instrumento: "Otro instrumento",
  micro_parcela: "Micro parcela",
  parcela: "Parcela",
  manzana_o_ambito_pequeno: "Manzana",
  ambito_medio: "Ámbito medio",
  gran_ambito: "Gran ámbito",
  sin_escala: "Sin escala",
  informacion_publica: "Información pública",
  aprobacion_inicial: "Aprobación inicial",
  aprobacion_provisional: "Aprobación provisional",
  aprobacion_definitiva: "Aprobación definitiva",
  gestion: "Gestión",
  urbanizacion: "Urbanización",
  en_tramitacion: "En tramitación",
  lt500: "< 500 m²",
  "500-2k": "500 – 2.000 m²",
  "2k-10k": "2.000 – 10.000 m²",
  gt10k: "> 10.000 m²",
};

const PROC = {
  "declaracion responsable": "Declaración responsable",
  "licencia urbanistica": "Licencia urbanística",
  "procedimiento ordinario comun": "Procedimiento ordinario",
  "procedimiento ordinario abreviado": "Ordinario abreviado",
  "licencia de funcionamiento": "Licencia de funcionamiento",
  "consultas urbanisticas": "Consultas",
};

const INICIATIVA = {
  privada: "Privada",
  municipal: "Municipal",
  "publica no municipal": "Pública no municipal",
  "definida en plan general": "Definida en el plan general",
};

const DISTRITO_DISPLAY = {
  centro: "Centro",
  chamberi: "Chamberí",
  tetuan: "Tetuán",
  hortaleza: "Hortaleza",
  "ciudad lineal": "Ciudad Lineal",
  salamanca: "Salamanca",
  "moncloa aravaca": "Moncloa-Aravaca",
  carabanchel: "Carabanchel",
  chamartin: "Chamartín",
  "fuencarral el pardo": "Fuencarral-El Pardo",
  retiro: "Retiro",
  "san blas canillejas": "San Blas-Canillejas",
  arganzuela: "Arganzuela",
  "puente de vallecas": "Puente de Vallecas",
  usera: "Usera",
  latina: "Latina",
  "villa de vallecas": "Villa de Vallecas",
  barajas: "Barajas",
  villaverde: "Villaverde",
  vicalvaro: "Vicálvaro",
  moratalaz: "Moratalaz",
};

const DISTRITO_ALIAS = {
  "moncloa aravaca": "moncloa",
  "fuencarral el pardo": "fuencarral",
  "san blas canillejas": "san blas",
};

const MIN_COMPLETE_MONTH = 400;
const COMPARE_YEARS = [2023, 2024, 2025];

function norm(s) {
  return String(s ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function distritoKey(name) {
  const n = norm(name);
  return DISTRITO_ALIAS[n] || n;
}

function labelOf(id) {
  if (!id) return "Sin dato";
  return LABELS[id] || String(id).replace(/_/g, " ");
}

function distritoDisplay(idOrLabel) {
  const n = norm(idOrLabel);
  return DISTRITO_DISPLAY[n] || titleCase(idOrLabel);
}

function isDistrito(id) {
  const n = norm(id);
  if (!n || n === "sin distrito" || n === "varios") return false;
  return /[a-z]/.test(n);
}

function titleCase(s) {
  return String(s)
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .map((w) => (w.length <= 2 ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
}

function bump(map, key, n = 1) {
  if (!key) return;
  map.set(key, (map.get(key) || 0) + n);
}

function sortedCounts(map, nameFn, { limit = 12, skip = () => false } = {}) {
  return [...map.entries()]
    .filter(([id, count]) => count > 0 && !skip(id))
    .sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])))
    .slice(0, limit)
    .map(([id, count]) => ({ name: nameFn(id), count }));
}

function yearBucket() {
  return {
    nuevaPlanta: 0,
    reforma: 0,
    demolicion: 0,
    primeraOcupacion: 0,
    localAVivienda: 0,
    aperturas: 0,
    reformasMenores: 0,
    obraVivienda: 0,
    obraLocal: 0,
    total: 0,
  };
}

function addActuacion(bucket, row) {
  bucket.total += 1;
  if (row.a === "local_actividad") bucket.aperturas += 1;
  if (row.a === "vivienda_obra_menor") bucket.reformasMenores += 1;
  if (row.a === "vivienda_obra") bucket.obraVivienda += 1;
  if (row.a === "local_obra") bucket.obraLocal += 1;
  if (row.a === "edificio_obra_grande") bucket.nuevaPlanta += 1;
  if (row.a === "edificio_reforma_conservacion") bucket.reforma += 1;
  if (row.a === "edificio_demolicion") bucket.demolicion += 1;
  if (row.a === "edificio_primera_ocupacion") bucket.primeraOcupacion += 1;
  if (row.a === "local_a_vivienda") bucket.localAVivienda += 1;
}

/**
 * @param {{ outDir: string }} opts
 */
export function buildMadridPresentacion(opts) {
  const { outDir } = opts;
  const licPath = join(outDir, "madrid-licencias-filter-rows.json");
  const sigPath = join(outDir, "madrid-sigma-filter-rows.json");
  if (!existsSync(licPath) || !existsSync(sigPath)) {
    console.log("Aviso: sin filter-rows — omitiendo presentación Madrid");
    return null;
  }

  const lic = JSON.parse(readFileSync(licPath, "utf-8"));
  const sig = JSON.parse(readFileSync(sigPath, "utf-8"));

  const monthCounts = new Map();
  const yearCounts = new Map();
  const byYear = new Map();
  const proc = new Map();
  const distritoAll = new Map();
  const distritoRecent = new Map();
  const distritoLabels = new Map();
  let sinDistrito = 0;

  for (const opt of lic.options?.distritos ?? []) {
    if (opt.id && opt.id !== "_sin_distrito") distritoLabels.set(opt.id, opt.label);
  }

  for (const row of lic.rows) {
    const month = row.m || "";
    const year = Number(month.slice(0, 4));
    if (!month || !Number.isFinite(year)) continue;
    bump(monthCounts, month);
    if (year >= 2023 && year <= 2026) bump(yearCounts, year);

    if (!isDistrito(row.d)) sinDistrito += 1;
    else {
      bump(distritoAll, row.d);
      distritoLabels.set(row.d, distritoDisplay(row.d));
    }

    if (PROC[row.p]) bump(proc, row.p);

    if (!COMPARE_YEARS.includes(year)) continue;
    if (!byYear.has(year)) byYear.set(year, yearBucket());
    addActuacion(byYear.get(year), row);
    if (isDistrito(row.d)) bump(distritoRecent, row.d);
  }

  const completeMonths = [...monthCounts.entries()]
    .filter(([month, count]) => month >= "2023-01" && month <= "2026-12" && count >= MIN_COMPLETE_MONTH)
    .map(([month]) => month)
    .sort();
  const lastCompleteMonth = completeMonths.at(-1) || "2025-12";

  const ytdBucket = yearBucket();
  byYear.set(2026, ytdBucket);
  for (const row of lic.rows) {
    const month = row.m || "";
    if (!month.startsWith("2026") || month > lastCompleteMonth) continue;
    addActuacion(ytdBucket, row);
    if (isDistrito(row.d)) bump(distritoRecent, row.d);
  }

  const ritmo = [];
  for (const [month, count] of [...monthCounts.entries()].sort((a, b) => a[0].localeCompare(b[0]))) {
    if (month >= "2025-01" && month <= lastCompleteMonth) ritmo.push({ month, total: count });
  }

  const comparativa = COMPARE_YEARS.map((year) => {
    const b = byYear.get(year) || yearBucket();
    return {
      year,
      aperturas: b.aperturas,
      reformasMenores: b.reformasMenores,
      obraVivienda: b.obraVivienda,
      obraLocal: b.obraLocal,
      nuevaPlanta: b.nuevaPlanta,
      reforma: b.reforma,
      demolicion: b.demolicion,
      primeraOcupacion: b.primeraOcupacion,
      localAVivienda: b.localAVivienda,
      total: b.total,
    };
  });

  const barriosLocal = new Map();
  const barriosReforma = new Map();
  const lic2025 = join(outDir, "madrid-licencias-2025.json");
  if (existsSync(lic2025)) {
    const batch = JSON.parse(readFileSync(lic2025, "utf-8"));
    for (const r of batch) {
      const barrio = titleCase(r.barrio || "");
      if (!barrio) continue;
      const act = normalizarActuacionEdificio({
        tipo_expediente: r.tipoExpediente,
        objeto: r.objeto,
        uso: r.uso,
        procedimiento: r.procedimiento,
      });
      if (act.codigo === "local_actividad") bump(barriosLocal, barrio);
      if (act.codigo === "vivienda_obra_menor" || act.codigo === "vivienda_obra") {
        bump(barriosReforma, barrio);
      }
    }
  }

  const fase = new Map();
  const abiertosTipo = new Map();
  const escala = new Map();
  const instrumento = new Map();
  const iniciativa = new Map();
  const superficie = new Map();
  const promotor = new Map();
  const planesDistrito = new Map();
  const planesDistritoLabel = new Map();
  const incoados = new Map();
  let abiertos = 0;
  let abiertosGranAmbito = 0;
  let conGeometria = 0;
  let iniciativaConDato = 0;
  let superficieConDato = 0;

  const sigDistritoLabel = new Map(
    (sig.options?.distritos ?? []).map((o) => [o.id, o.label]),
  );
  const sigIniciativaLabel = new Map(
    (sig.options?.iniciativas ?? []).map((o) => [o.id, o.label]),
  );
  const sigPromotorLabel = new Map(
    (sig.options?.promotores ?? []).map((o) => [o.id, o.label]),
  );

  for (const row of sig.rows) {
    if (row.geo) conGeometria += 1;
    if (row.fn) bump(fase, row.fn);
    if (row.es) bump(escala, row.es);
    if (row.tl) bump(instrumento, row.tl);
    if (row.y >= 2016 && row.y <= 2026) bump(incoados, row.y);
    if (row.i && row.i !== "-") {
      iniciativaConDato += 1;
      bump(iniciativa, row.i);
    }
    if (row.sup) {
      superficieConDato += 1;
      bump(superficie, row.sup);
    }
    if (row.pr && row.pr !== "-") bump(promotor, row.pr);
    if (row.d && norm(row.d) !== "varios") {
      const key = distritoKey(sigDistritoLabel.get(row.d) || row.d);
      bump(planesDistrito, key);
      planesDistritoLabel.set(key, distritoDisplay(sigDistritoLabel.get(row.d) || row.d));
    }
    if (OPEN_FASE.has(row.fn)) {
      abiertos += 1;
      if (row.cp) bump(abiertosTipo, row.cp);
      if (row.es === "gran_ambito") abiertosGranAmbito += 1;
    }
  }

  const cruce = [];
  const seen = new Set();
  for (const [id, licenciasCount] of distritoRecent) {
    const key = distritoKey(distritoLabels.get(id) || id);
    if (seen.has(key)) continue;
    seen.add(key);
    cruce.push({
      name: distritoDisplay(id),
      licencias: licenciasCount,
      planes: planesDistrito.get(key) || 0,
    });
  }
  cruce.sort((a, b) => b.licencias - a.licencias);

  const ytd = byYear.get(2026) || yearBucket();
  const y2025 = comparativa.find((r) => r.year === 2025);

  const payload = {
    generatedAt: new Date().toISOString(),
    lastCompleteMonth,
    licencias: {
      total: lic.totalRows,
      sinDistrito,
      hastaMes: ytd.total,
      comparativa,
      ritmo,
      procedimiento: sortedCounts(proc, (id) => PROC[id] || id, { limit: 6 }),
      porDistrito: sortedCounts(distritoAll, (id) => distritoDisplay(id), { limit: 21 }),
      barriosLocal2025: sortedCounts(barriosLocal, (name) => name, { limit: 8 }),
      barriosReforma2025: sortedCounts(barriosReforma, (name) => name, { limit: 8 }),
      cambiosLocal2025: y2025?.aperturas ?? 0,
      reformasMenores2025: y2025?.reformasMenores ?? 0,
    },
    planes: {
      total: sig.totalRows,
      conGeometria,
      abiertos,
      abiertosGranAmbito,
      iniciativaConDato,
      superficieConDato,
      porFase: sortedCounts(fase, labelOf, { limit: 8 }),
      abiertosPorTipo: sortedCounts(abiertosTipo, labelOf, { limit: 8 }),
      incoados: [...incoados.entries()]
        .sort((a, b) => a[0] - b[0])
        .map(([year, count]) => ({ year, count })),
      porEscala: sortedCounts(escala, labelOf, { limit: 6 }),
      porInstrumento: sortedCounts(instrumento, labelOf, { limit: 8 }),
      iniciativa: sortedCounts(iniciativa, (id) => INICIATIVA[id] || titleCase(id), { limit: 5 }),
      superficie: ["lt500", "500-2k", "2k-10k", "gt10k"]
        .filter((id) => superficie.has(id))
        .map((id) => ({ name: labelOf(id), count: superficie.get(id) })),
      promotores: sortedCounts(
        promotor,
        (id) => {
          const raw = sigPromotorLabel.get(id) || id;
          return raw.length > 42 ? `${raw.slice(0, 41)}…` : raw;
        },
        { limit: 8 },
      ),
    },
    cruce,
  };

  writeFileSync(join(outDir, "madrid-presentacion.json"), JSON.stringify(payload));
  console.log(
    `OK: madrid-presentacion.json (${payload.licencias.total} licencias, ${payload.planes.total} planes, hasta ${lastCompleteMonth})`,
  );
  return payload;
}
