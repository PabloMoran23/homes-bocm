import {
  CM_PORTAL_PROYECTOS_POLIGONOS_URL,
  CM_PORTAL_PROYECTOS_URL,
  type CmPortalGeoJson,
  type CmPortalProyectoProps,
} from "@/lib/cm-portal-geo";
import { ensureProject } from "@/lib/ensure-project";
import { fetchStaticJson } from "@/lib/fetch-static-json";
import type { Project } from "@/lib/types";

type PortalRow = Partial<Project> & Pick<Project, "id">;

type PortalIndexFile = {
  generatedAt?: string;
  items?: PortalRow[];
};

let indexPromise: Promise<Map<string, Project>> | null = null;

function centroidFromGeometry(geometry: GeoJSON.Geometry | null | undefined): [number, number] | null {
  if (!geometry) return null;
  let ring: number[][] | null = null;
  if (geometry.type === "Polygon") {
    ring = geometry.coordinates[0] ?? null;
  } else if (geometry.type === "MultiPolygon") {
    ring = geometry.coordinates[0]?.[0] ?? null;
  } else if (geometry.type === "Point") {
    const [lng, lat] = geometry.coordinates;
    return typeof lng === "number" && typeof lat === "number" ? [lng, lat] : null;
  }
  if (!ring?.length) return null;
  let lngSum = 0;
  let latSum = 0;
  for (const [lng, lat] of ring) {
    lngSum += lng;
    latSum += lat;
  }
  return [lngSum / ring.length, latSum / ring.length];
}

function projectFromPortalProps(
  p: CmPortalProyectoProps,
  coords: [number, number] | null,
): Project {
  const [lng, lat] = coords ?? [];
  return ensureProject({
    id: p.id,
    sourceId: "ayuntamiento-portal",
    sourceLabel: p.municipio ? `Portal · ${p.municipio}` : "Portal municipal",
    territorioId: p.sectorKey || "comunidad-madrid",
    territorioLabel: p.municipio || "Comunidad de Madrid",
    title: p.titulo || p.id,
    municipio: p.municipio || "",
    tipoInstrumento: p.tipo || "",
    bocmDate: p.fecha || "",
    resumen: p.titulo || "",
    sigmaEnlace: p.url || null,
    sectorKey: p.sectorKey || null,
    coordSource: p.coordSource || null,
    sigmaCatalogSource: p.catalogSource || "ayuntamiento-portal",
    lat: lat ?? null,
    lng: lng ?? null,
  });
}

function ingestGeojson(
  map: Map<string, Project>,
  fc: CmPortalGeoJson<CmPortalProyectoProps> | null,
) {
  for (const feature of fc?.features ?? []) {
    const p = feature.properties;
    if (!p?.id || map.has(p.id)) continue;
    const coords =
      feature.geometry.type === "Point"
        ? (feature.geometry.coordinates as [number, number])
        : centroidFromGeometry(feature.geometry);
    map.set(p.id, projectFromPortalProps(p, coords));
  }
}

async function loadPortalIndexFromGeojson(): Promise<Map<string, Project>> {
  const map = new Map<string, Project>();
  const [points, polygons] = await Promise.all([
    fetchStaticJson<CmPortalGeoJson<CmPortalProyectoProps>>(CM_PORTAL_PROYECTOS_URL),
    fetchStaticJson<CmPortalGeoJson<CmPortalProyectoProps>>(CM_PORTAL_PROYECTOS_POLIGONOS_URL),
  ]);
  ingestGeojson(map, polygons);
  ingestGeojson(map, points);
  return map;
}

async function loadPortalIndex(): Promise<Map<string, Project>> {
  if (!indexPromise) {
    indexPromise = (async () => {
      const fromFile = await fetchStaticJson<PortalIndexFile>("/data/cm-portal-proyectos-index.json");
      if (fromFile?.items?.length) {
        const map = new Map<string, Project>();
        for (const row of fromFile.items) {
          if (!row.id) continue;
          map.set(row.id, ensureProject(row));
        }
        return map;
      }
      return loadPortalIndexFromGeojson();
    })();
  }
  return indexPromise;
}

export async function loadCmPortalProjectById(id: string): Promise<Project | null> {
  const key = decodeURIComponent(id).trim();
  if (!key) return null;
  const map = await loadPortalIndex();
  return map.get(key) ?? null;
}
