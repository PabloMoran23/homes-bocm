import type { Project } from "./types";
import type { SectorFeatureCollection } from "./sector-geo";

/** Claves para enlazar con sector-geometries.geojson (incluye legacy sin boletin_source_id). */
export function collectProjectSectorKeys(p: Pick<Project, "sectorKey" | "sectorGeoKey">): string[] {
  const keys: string[] = [];
  if (p.sectorGeoKey) keys.push(p.sectorGeoKey);
  if (p.sectorKey && !keys.includes(p.sectorKey)) keys.push(p.sectorKey);
  return keys;
}

export function filterSectorGeoJson(
  fc: SectorFeatureCollection | null,
  sectorKeys: Set<string>,
): SectorFeatureCollection {
  if (!fc?.features?.length || sectorKeys.size === 0) {
    return { type: "FeatureCollection", features: [] };
  }
  return {
    type: "FeatureCollection",
    features: fc.features.filter((f) => {
      const sk = f.properties?.stable_key;
      return sk && sectorKeys.has(sk);
    }),
  };
}

export function filterSectorGeoJsonForProjects(
  fc: SectorFeatureCollection | null,
  projects: Pick<Project, "sectorKey" | "sectorGeoKey">[],
): SectorFeatureCollection {
  const keys = new Set<string>();
  for (const p of projects) {
    for (const k of collectProjectSectorKeys(p)) keys.add(k);
  }
  return filterSectorGeoJson(fc, keys);
}
