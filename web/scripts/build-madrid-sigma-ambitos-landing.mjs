/**
 * GeoJSON ligero para el mapa de inicio (vista previa, sin interacción).
 * Recorta ámbitos enormes, simplifica geometría y deja solo props de estilo.
 */
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const outDir = join(__dirname, "..", "public", "data");
const sourcePath = join(outDir, "madrid-sigma-ambitos.geojson");
const landingPath = join(outDir, "madrid-sigma-ambitos-landing.geojson");

const MAX_BBOX_KM2 = 15;
/** ~15 m en Madrid; miniatura portada (SVG) sin “escalones” tan marcados. */
const SIMPLIFY_TOLERANCE = 0.00015;

function accumulateBounds(coords, depth, b) {
  if (!coords || depth > 14) return;
  if (
    Array.isArray(coords) &&
    coords.length >= 2 &&
    typeof coords[0] === "number" &&
    typeof coords[1] === "number"
  ) {
    const lng = coords[0];
    const lat = coords[1];
    b.minLat = Math.min(b.minLat, lat);
    b.maxLat = Math.max(b.maxLat, lat);
    b.minLng = Math.min(b.minLng, lng);
    b.maxLng = Math.max(b.maxLng, lng);
    return;
  }
  if (Array.isArray(coords)) {
    for (const c of coords) accumulateBounds(c, depth + 1, b);
  }
}

function approximateBBoxAreaKm2(geometry) {
  if (!geometry?.type || !geometry.coordinates) return null;
  const t = geometry.type;
  if (t !== "Polygon" && t !== "MultiPolygon") return null;
  const b = { minLat: 90, maxLat: -90, minLng: 180, maxLng: -180 };
  accumulateBounds(geometry.coordinates, 0, b);
  if (b.minLat >= b.maxLat || b.minLng >= b.maxLng) return null;
  const latSpan = b.maxLat - b.minLat;
  const lngSpan = b.maxLng - b.minLng;
  const avgLatRad = ((b.minLat + b.maxLat) / 2) * (Math.PI / 180);
  return latSpan * 111 * lngSpan * 111 * Math.cos(avgLatRad);
}

function sqDist(a, b) {
  const dx = a[0] - b[0];
  const dy = a[1] - b[1];
  return dx * dx + dy * dy;
}

function perpDist(p, a, b) {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  if (!dx && !dy) return Math.sqrt(sqDist(p, a));
  const t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy);
  return Math.sqrt(sqDist(p, [a[0] + t * dx, a[1] + t * dy]));
}

function douglasPeucker(points, tolerance, start = 0, end = points.length - 1, out = new Set()) {
  if (end <= start + 1) {
    out.add(start);
    out.add(end);
    return out;
  }
  let maxD = 0;
  let idx = start;
  for (let i = start + 1; i < end; i += 1) {
    const d = perpDist(points[i], points[start], points[end]);
    if (d > maxD) {
      maxD = d;
      idx = i;
    }
  }
  if (maxD > tolerance) {
    douglasPeucker(points, tolerance, start, idx, out);
    douglasPeucker(points, tolerance, idx, end, out);
  } else {
    out.add(start);
    out.add(end);
  }
  return out;
}

function simplifyRing(ring, tolerance) {
  if (!Array.isArray(ring) || ring.length <= 4) return ring;
  const keep = douglasPeucker(ring, tolerance);
  return [...keep].sort((a, b) => a - b).map((i) => ring[i]);
}

function simplifyCoords(coords, type, tolerance) {
  if (type === "Polygon") return coords.map((ring) => simplifyRing(ring, tolerance));
  if (type === "MultiPolygon") {
    return coords.map((poly) => poly.map((ring) => simplifyRing(ring, tolerance)));
  }
  return coords;
}

function main() {
  if (!existsSync(sourcePath)) {
    console.log("Aviso: sin madrid-sigma-ambitos.geojson — omitiendo landing map");
    return;
  }

  const raw = JSON.parse(readFileSync(sourcePath, "utf-8"));
  const features = [];
  let excluded = 0;

  for (const f of raw.features || []) {
    const km2 = approximateBBoxAreaKm2(f.geometry);
    if (km2 != null && km2 > MAX_BBOX_KM2) {
      excluded += 1;
      continue;
    }
    const kind = f.properties?.sigma_layer_kind;
    if (!f.geometry?.type) continue;
    features.push({
      type: "Feature",
      properties: kind ? { sigma_layer_kind: kind } : {},
      geometry: {
        type: f.geometry.type,
        coordinates: simplifyCoords(f.geometry.coordinates, f.geometry.type, SIMPLIFY_TOLERANCE),
      },
    });
  }

  const payload = { type: "FeatureCollection", features };
  writeFileSync(landingPath, JSON.stringify(payload));
  const kb = Math.round(Buffer.byteLength(JSON.stringify(payload), "utf-8") / 1024);
  console.log(
    `OK: madrid-sigma-ambitos-landing.geojson (${features.length} ámbitos, ${kb} KB, ${excluded} excluidos por tamaño)`,
  );
}

main();
