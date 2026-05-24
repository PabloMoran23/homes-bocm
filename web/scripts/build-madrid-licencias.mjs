/**
 * Exporta licencias urbanísticas (JSONL) → índice + GeoJSON/JSON por año para la web.
 */
import { createReadStream, existsSync, mkdirSync, writeFileSync } from "node:fs";
import { createInterface } from "node:readline";
import { join } from "node:path";
import proj4 from "proj4";
import { normalizarActuacionEdificio } from "./lib/actuacion-edificio.mjs";
import {
  ACTUACION_QUE_LEYENDA,
  labelActuacionQue,
} from "./lib/actuacion-que-config.mjs";

const UTM30 =
  "+proj=utm +zone=30 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs";
const WGS84 = "EPSG:4326";

function utmToWgs84(easting, northing) {
  const [lng, lat] = proj4(UTM30, WGS84, [easting, northing]);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  if (lat < 39.5 || lat > 41.2 || lng < -4.5 || lng > -3) return null;
  return { lat, lng };
}

function parseUtmComponent(raw) {
  if (raw == null || raw === "") return null;
  const n = Number(String(raw).replace(/,/g, "").trim());
  if (!Number.isFinite(n)) return null;
  return n / 100;
}

function isPlaceholderDms(raw) {
  if (raw == null || raw === "") return true;
  const s = String(raw).trim();
  if (s === "0" || s === "0.0") return true;
  return /^0\s*[º°]\s*0\s*['\u2032]?\s*0/i.test(s);
}

function isValidMadrid(lat, lng) {
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return false;
  if (Math.abs(lat) < 1e-6 && Math.abs(lng) < 1e-6) return false;
  return lat >= 39.5 && lat <= 41.2 && lng >= -4.5 && lng <= -3.0;
}

function parseDmsCoord(raw) {
  if (isPlaceholderDms(raw) || typeof raw !== "string") return null;
  const m = raw.trim().match(/([\d.]+)\s*[º°]\s*([\d.]+)\s*['\u2032]?\s*([\d.]*)\s*['\u2033]?\s*([NnSsEeWw])/);
  if (!m) return null;
  const deg = Number(m[1]);
  const min = Number(m[2]);
  const sec = m[3] ? Number(m[3]) : 0;
  if ([deg, min, sec].some((x) => Number.isNaN(x))) return null;
  let v = deg + min / 60 + sec / 3600;
  const hemi = m[4].toUpperCase();
  if (hemi === "S" || hemi === "W") v = -v;
  return v;
}

function resolveCoords(row) {
  const latDms = parseDmsCoord(row.latitud);
  const lngDms = parseDmsCoord(row.longitud);
  if (latDms != null && lngDms != null && isValidMadrid(latDms, lngDms)) {
    return { lat: latDms, lng: lngDms };
  }
  const x = parseUtmComponent(row.coordenadas_x ?? row.coordenada_x);
  const y = parseUtmComponent(row.coordenadas_y ?? row.coordenada_y);
  if (x == null || y == null || x === 0 || y === 0) return null;
  const utm = utmToWgs84(x, y);
  if (utm && isValidMadrid(utm.lat, utm.lng)) return utm;
  return null;
}

function parseYearFromDate(raw) {
  if (!raw || typeof raw !== "string") return null;
  const parts = raw.trim().split(/[/.-]/);
  if (parts.length < 3) return null;
  let y = Number(parts[parts.length - 1]);
  if (y < 100) y += 2000;
  return Number.isFinite(y) && y >= 1990 && y <= 2100 ? y : null;
}

/** Fecha D/M/YYYY o DD/MM/YYYY → `YYYY-MM` (prioriza fecha de concesión). */
function parseMonthKey(concesion, alta) {
  for (const raw of [concesion, alta]) {
    if (!raw || typeof raw !== "string") continue;
    const parts = raw.trim().split(/[/.-]/);
    if (parts.length < 3) continue;
    let d = Number(parts[0]);
    let m = Number(parts[1]);
    let y = Number(parts[2]);
    if (y < 100) y += 2000;
    if (!Number.isFinite(d) || !Number.isFinite(m) || !Number.isFinite(y)) continue;
    if (m < 1 || m > 12 || y < 1990 || y > 2100) continue;
    return `${y}-${String(m).padStart(2, "0")}`;
  }
  return null;
}

function normKey(s) {
  return String(s || "")
    .trim()
    .toLowerCase();
}

import { buildDireccion } from "./direccion.mjs";

function compactRow(row, coords) {
  return {
    anioDataset: row.anio_dataset ?? null,
    fechaAlta: row.fecha_de_alta ?? null,
    fechaConcesion: row.fecha_concesin ?? null,
    procedimiento: row.procedimiento ?? null,
    tipoExpediente: row.tipo_de_expediente ?? null,
    uso: row.uso ?? null,
    distrito: row.descripcin_distrito ?? row.distrito ?? null,
    barrio: row.descripcion_barrio_bdc ?? row.descripcin_barrio ?? null,
    direccion: buildDireccion(row),
    interesado: row.interesado ?? null,
    objeto: row.objeto_de_la_licencia ?? null,
    unidad: row.unidad_responsable ?? null,
    ndpEdificio: row.ndp_edificio ?? null,
    lat: coords?.lat ?? null,
    lng: coords?.lng ?? null,
  };
}

/**
 * @param {{ jsonlPath: string; outDir: string; summaryPath?: string }} opts
 */
export async function buildMadridLicenciasWeb(opts) {
  const { jsonlPath, outDir, minYear } = opts;
  if (!existsSync(jsonlPath)) {
    console.log("Aviso: sin madrid_licencias.jsonl — ejecuta madrid_licencias_download");
    return null;
  }

  mkdirSync(outDir, { recursive: true });

  function topEntries(map, n = 24) {
    return [...map.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, n)
      .map(([name, count]) => ({ name, count }));
  }

  /** @type {Map<number, { features: object[]; rows: object[] }>} */
  const byYear = new Map();
  const byYearCount = {};
  const byUso = new Map();
  const byDistrito = new Map();
  const byProcedimiento = new Map();
  const byTipoExpediente = new Map();
  const byActuacionQue = new Map();
  /** @type {Map<string, { count: number; latSum: number; lngSum: number; n: number }>} */
  const distritoGeo = new Map();
  /** @type {Map<number, Map<string, number>>} */
  const yearUsoMaps = new Map();
  /** @type {Map<number, Map<string, number>>} */
  const yearActuacionMaps = new Map();
  const byMonth = new Map();
  /** @type {Map<string, Map<string, number>>} */
  const monthActuacionMaps = new Map();
  let total = 0;
  let withCoords = 0;

  const rl = createInterface({ input: createReadStream(jsonlPath, "utf-8"), crlfDelay: Infinity });
  for await (const line of rl) {
    if (!line.trim()) continue;
    let row;
    try {
      row = JSON.parse(line);
    } catch {
      continue;
    }
    total += 1;
    const year =
      Number(row.anio_dataset) ||
      parseYearFromDate(row.fecha_concesin) ||
      parseYearFromDate(row.fecha_de_alta) ||
      0;
    if (minYear != null && year > 0 && year < minYear) continue;
    if (!byYear.has(year)) byYear.set(year, { features: [], rows: [] });
    const bucket = byYear.get(year);

    const coords = resolveCoords(row);
    if (coords) withCoords += 1;

    const compact = compactRow(row, coords);
    bucket.rows.push(compact);

    const uso = normKey(compact.uso);
    if (uso) byUso.set(uso, (byUso.get(uso) || 0) + 1);
    const dist = normKey(compact.distrito);
    if (dist) {
      byDistrito.set(dist, (byDistrito.get(dist) || 0) + 1);
      if (coords) {
        let dg = distritoGeo.get(dist);
        if (!dg) {
          dg = { count: 0, latSum: 0, lngSum: 0, n: 0 };
          distritoGeo.set(dist, dg);
        }
        dg.count += 1;
        dg.latSum += coords.lat;
        dg.lngSum += coords.lng;
        dg.n += 1;
      }
    }
    const proc = normKey(compact.procedimiento);
    if (proc) byProcedimiento.set(proc, (byProcedimiento.get(proc) || 0) + 1);
    const tipo = normKey(compact.tipoExpediente);
    if (tipo) byTipoExpediente.set(tipo, (byTipoExpediente.get(tipo) || 0) + 1);
    if (year > 0 && uso) {
      if (!yearUsoMaps.has(year)) yearUsoMaps.set(year, new Map());
      const ym = yearUsoMaps.get(year);
      ym.set(uso, (ym.get(uso) || 0) + 1);
    }
    const actuacionNorm = normalizarActuacionEdificio({
      tipo_expediente: compact.tipoExpediente,
      objeto: compact.objeto,
      uso: compact.uso,
      procedimiento: compact.procedimiento,
    });
    const actuacionCodigo = actuacionNorm.codigo;
    byActuacionQue.set(actuacionCodigo, (byActuacionQue.get(actuacionCodigo) || 0) + 1);
    if (year > 0) {
      if (!yearActuacionMaps.has(year)) yearActuacionMaps.set(year, new Map());
      const ym = yearActuacionMaps.get(year);
      ym.set(actuacionCodigo, (ym.get(actuacionCodigo) || 0) + 1);
    }

    const monthKey = parseMonthKey(row.fecha_concesin, row.fecha_de_alta);
    if (monthKey) {
      byMonth.set(monthKey, (byMonth.get(monthKey) || 0) + 1);
      if (!monthActuacionMaps.has(monthKey)) monthActuacionMaps.set(monthKey, new Map());
      const mm = monthActuacionMaps.get(monthKey);
      mm.set(actuacionCodigo, (mm.get(actuacionCodigo) || 0) + 1);
    }

    if (coords) {
      bucket.features.push({
        type: "Feature",
        geometry: { type: "Point", coordinates: [coords.lng, coords.lat] },
        properties: {
          licencia_urbana: true,
          anio_dataset: compact.anioDataset,
          fecha_concesion: compact.fechaConcesion,
          tipo_expediente: compact.tipoExpediente,
          objeto: compact.objeto,
          uso: compact.uso,
          distrito: compact.distrito,
          direccion: compact.direccion,
          procedimiento: compact.procedimiento,
          actuacion_que: actuacionNorm.codigo,
          actuacion_que_label: actuacionNorm.etiqueta,
        },
      });
    }
  }

  const years = [...byYear.keys()].filter((y) => y > 0).sort((a, b) => b - a);
  const topUsoNames = topEntries(byUso, 8).map((x) => x.name);
  const byYearUso = {};
  for (const y of years) {
    const ym = yearUsoMaps.get(y) || new Map();
    byYearUso[String(y)] = topUsoNames.map((name) => ({
      name,
      count: ym.get(name) || 0,
    }));
  }

  const actuacionQueOrdered = [
    ...ACTUACION_QUE_LEYENDA,
    ...[...byActuacionQue.keys()].filter((c) => !ACTUACION_QUE_LEYENDA.includes(c)),
  ];
  const byYearActuacionQue = years
    .slice()
    .sort((a, b) => a - b)
    .map((y) => {
      const ym = yearActuacionMaps.get(y) || new Map();
      return {
        year: y,
        tipos: actuacionQueOrdered.map((id) => ({
          id,
          label: labelActuacionQue(id),
          count: ym.get(id) || 0,
        })),
      };
    });
  const topDistritoMap = topEntries(byDistrito, 22).map(({ name, count }) => {
    const g = distritoGeo.get(name);
    return {
      name,
      count,
      lat: g?.n ? g.latSum / g.n : null,
      lng: g?.n ? g.lngSum / g.n : null,
      withCoords: g?.count ?? 0,
    };
  });

  const topActuacionQue = actuacionQueOrdered
    .map((id) => ({
      id,
      label: labelActuacionQue(id),
      count: byActuacionQue.get(id) || 0,
    }))
    .filter((x) => x.count > 0)
    .sort((a, b) => b.count - a.count);

  const months = [...byMonth.keys()].sort();
  const seriesByMonth = months.map((month) => ({
    month,
    total: byMonth.get(month) || 0,
  }));
  const seriesByMonthActuacionQue = months.map((month) => {
    const mm = monthActuacionMaps.get(month) || new Map();
    return {
      month,
      tipos: actuacionQueOrdered.map((id) => ({
        id,
        label: labelActuacionQue(id),
        count: mm.get(id) || 0,
      })),
    };
  });

  for (const y of years) {
    const { features, rows } = byYear.get(y);
    byYearCount[String(y)] = rows.length;
    writeFileSync(
      join(outDir, `madrid-licencias-${y}.geojson`),
      JSON.stringify({ type: "FeatureCollection", features }),
    );
    writeFileSync(join(outDir, `madrid-licencias-${y}.json`), JSON.stringify(rows));
    console.log(
      `OK: madrid-licencias-${y} (${rows.length.toLocaleString("es-ES")} filas, ${features.length.toLocaleString("es-ES")} puntos)`,
    );
  }

  const index = {
    generatedAt: new Date().toISOString(),
    source: "datos.madrid.es dataset 300193-0-licencias-urbanisticas",
    totalRows: total,
    withCoords,
    byYear: byYearCount,
    years,
    topUso: topEntries(byUso),
    topDistrito: topEntries(byDistrito),
    topDistritoMap,
    topProcedimiento: topEntries(byProcedimiento),
    topTipoExpediente: topEntries(byTipoExpediente, 20),
    byYearUso,
    byYearActuacionQue,
    topActuacionQue,
    months,
    seriesByMonth,
    seriesByMonthActuacionQue,
  };

  writeFileSync(join(outDir, "madrid-licencias-index.json"), JSON.stringify(index, null, 2));
  console.log(
    `OK: madrid-licencias-index.json (${total.toLocaleString("es-ES")} filas, ${withCoords.toLocaleString("es-ES")} con ubicación)`,
  );
  return index;
}
