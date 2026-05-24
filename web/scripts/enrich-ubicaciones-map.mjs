/**
 * Añade actuacionQue / actuacionQueLabel al geojson de ubicaciones
 * (requiere ultimaLicenciaObjeto, Uso, Procedimiento en properties).
 *
 *   node scripts/enrich-ubicaciones-map.mjs
 */
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { normalizarActuacionEdificio } from "./lib/actuacion-edificio.mjs";

const geoPath = join(process.cwd(), "public/data/ubicaciones-map.geojson");
const geo = JSON.parse(readFileSync(geoPath, "utf8"));

for (const f of geo.features) {
  const p = f.properties;
  const norm = normalizarActuacionEdificio({
    tipo_expediente: p.ultimaLicenciaTipo,
    objeto: p.ultimaLicenciaObjeto,
    uso: p.ultimaLicenciaUso,
    procedimiento: p.ultimaLicenciaProcedimiento,
  });
  p.actuacionQue = norm.codigo;
  p.actuacionQueLabel = norm.etiqueta;
}

writeFileSync(geoPath, JSON.stringify(geo));
console.log(`Enriched ${geo.features.length} features → ${geoPath}`);
