/**
 * Descarga límites oficiales de distritos (Ayuntamiento de Madrid) y genera
 * public/data/madrid-distritos.geojson (WGS84, simplificado).
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const TOPO_URL =
  "https://geoportal.madrid.es/fsdescargas/IDEAM_WBGEOPORTAL/LIMITES_ADMINISTRATIVOS/Distritos/TopoJSON/Distritos.json";

/** @param {string} name */
export function normDistritoKey(name) {
  return String(name ?? "")
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/-/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * @param {import('topojson-specification').Topology} topology
 * @param {number} i
 */
function decodeArc(topology, i) {
  const arcs = topology.arcs[i < 0 ? ~i : i];
  const t = topology.transform;
  let x = 0;
  let y = 0;
  /** @type {[number, number][]} */
  const coords = [];
  for (const point of arcs) {
    x += point[0];
    y += point[1];
    if (t) {
      coords.push([
        roundCoord(x * t.scale[0] + t.translate[0]),
        roundCoord(y * t.scale[1] + t.translate[1]),
      ]);
    } else {
      coords.push([x, y]);
    }
  }
  if (i < 0) coords.reverse();
  return coords;
}

/** @param {number} n */
function roundCoord(n) {
  return Math.round(n * 1e5) / 1e5;
}

/**
 * @param {import('topojson-specification').Topology} topology
 * @param {number[]} arcIndices
 */
function decodeRing(topology, arcIndices) {
  /** @type {[number, number][]} */
  let coords = [];
  for (const i of arcIndices) {
    const arc = decodeArc(topology, i);
    if (coords.length) {
      const last = coords[coords.length - 1];
      const first = arc[0];
      if (last[0] === first[0] && last[1] === first[1]) arc.shift();
    }
    coords = coords.concat(arc);
  }
  return coords;
}

/**
 * @param {import('topojson-specification').Topology} topology
 * @param {{ type: string; arcs?: number[][]; properties?: Record<string, unknown> }} geom
 */
function decodeGeometry(topology, geom) {
  if (geom.type === "Polygon") {
    return { type: "Polygon", coordinates: geom.arcs.map((ring) => decodeRing(topology, ring)) };
  }
  if (geom.type === "MultiPolygon") {
    return {
      type: "MultiPolygon",
      coordinates: geom.arcs.map((poly) => poly.map((ring) => decodeRing(topology, ring))),
    };
  }
  return null;
}

/**
 * @param {import('topojson-specification').Topology} topology
 * @param {{ type: string; geometries?: { type: string; arcs?: number[][]; properties?: Record<string, unknown> }[] }} object
 */
function topoToFeatureCollection(topology, object) {
  if (object.type !== "GeometryCollection" || !object.geometries?.length) {
    throw new Error("Formato TopoJSON de distritos inesperado");
  }
  return {
    type: "FeatureCollection",
    features: object.geometries.map((g) => {
      const geometry = decodeGeometry(topology, g);
      const props = g.properties || {};
      const nombre = String(props.NOMBRE || props.DISTRI_MAY || "").trim();
      return {
        type: "Feature",
        properties: {
          cod_dis: props.COD_DIS_TX ?? props.COD_DIS ?? null,
          nombre,
          distrito_key: normDistritoKey(nombre || props.DISTRI_MAY),
        },
        geometry,
      };
    }),
  };
}

async function fetchTopoJson() {
  const res = await fetch(TOPO_URL, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`Descarga distritos: HTTP ${res.status}`);
  return res.json();
}

/**
 * @param {{ outDir: string; cachePath?: string }} opts
 */
export async function buildMadridDistritos(opts) {
  const { outDir, cachePath } = opts;
  const cache = cachePath ?? join(outDir, ".cache-madrid-distritos-topo.json");
  mkdirSync(dirname(cache), { recursive: true });
  mkdirSync(outDir, { recursive: true });

  let topology;
  if (existsSync(cache)) {
    topology = JSON.parse(readFileSync(cache, "utf-8"));
  } else {
    topology = await fetchTopoJson();
    writeFileSync(cache, JSON.stringify(topology));
  }

  const object = topology.objects?.Distritos;
  if (!object) throw new Error("TopoJSON sin objeto Distritos");

  const fc = topoToFeatureCollection(topology, object);
  const outPath = join(outDir, "madrid-distritos.geojson");
  writeFileSync(outPath, JSON.stringify(fc));

  const kb = Math.round((readFileSync(outPath).length / 1024) * 10) / 10;
  console.log(
    `OK: madrid-distritos.geojson (${fc.features.length} distritos, ${kb} KB)`,
  );
  return fc;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const outDir = process.argv[2] || join(__dirname, "../public/data");
  buildMadridDistritos({ outDir }).catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
