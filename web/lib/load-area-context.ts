import { hasBroadMapExtent } from "./map-project-scope";
import { fetchStaticJson } from "./fetch-static-json";
import { getDirectoryProject, directoryProjectPath } from "./project-directory";
import { sigmaFichaPath } from "./sigma-ficha-path";
import { getSupabaseServer } from "./supabase/server";
import { areaDisplayGeometry, geometryExtentM2, areaDate, areaToday, areaCutoff, areaFeatureGroup, geometryProximity, projectMilestones, type AreaContext, type AreaFeature, type AreaProject } from "./area-context";
import type { SigmaVisorFicha, SigmaVisorTramite } from "./types";

type Collection = { features: AreaFeature[] };
type Visor = { visorFicha?: SigmaVisorFicha; tramitacion?: SigmaVisorTramite[] };
let snapshot: Promise<{ features: AreaFeature[]; visor: Record<string, Visor>; cards: Record<string, { resumen?: string }> }> | null = null;
function loadSnapshot() {
  return snapshot ??= (async () => {
    const [geometry, visor, cards] = await Promise.all([
      fetchStaticJson<Collection>("/data/madrid-sigma-ambitos.geojson"),
      fetchStaticJson<{ byGrupoExpediente: Record<string, Visor> }>("/data/madrid-sigma-visor-slim.json"),
      fetchStaticJson<{ byExpediente: Record<string, { resumen?: string }> }>("/data/madrid-sigma-map-cards.json"),
    ]);
    return { features: geometry?.features || [], visor: visor?.byGrupoExpediente || {}, cards: cards?.byExpediente || {} };
  })();
}
export async function loadAreaContext(lat: number, lng: number, radius: number, months: number): Promise<AreaContext> {
  const today = areaToday(), cutoff = areaCutoff(today, months);
  const dy = radius / 111_000, dx = dy / Math.cos(lat * Math.PI / 180);
  const [local, live] = await Promise.all([
    loadSnapshot(),
    (async () => {
      const supabase = getSupabaseServer();
      if (!supabase) return null;
      const { data, error } = await supabase.rpc("map_sigma_geojson", {
        p_zoom: 16, p_min_lng: lng - dx, p_max_lng: lng + dx,
        p_min_lat: lat - dy, p_max_lat: lat + dy, p_layer: "ambitos", p_limit: 220,
      });
      return !error && Array.isArray(data?.features) ? data as Collection : null;
    })().catch(() => null),
  ]);
  if (!local.features.length && !live) throw new Error("No se pudo cargar el contexto urbanístico");
  // Match complete local polygons first. Live geometries can be simplified or cap large areas.
  const nearby = new Map<string, { feature: AreaFeature; proximity: NonNullable<ReturnType<typeof geometryProximity>> }>();
  for (const feature of [...local.features, ...(live?.features || [])]) {
    const group = areaFeatureGroup(feature);
    if (!group || !feature.geometry) continue;
    const proximity = geometryProximity(feature.geometry, lng, lat);
    if (!proximity || proximity.distanceM > radius) continue;
    const previous = nearby.get(group);
    if (!previous) nearby.set(group, { feature, proximity });
    else if (live?.features.includes(feature)) {
      nearby.set(group, { feature: { ...previous.feature, properties: { ...previous.feature.properties, ...feature.properties } }, proximity: previous.proximity });
    } else if (proximity.distanceM < previous.proximity.distanceM) nearby.set(group, { feature, proximity });
  }
  const projects: AreaProject[] = [];
  for (const [group, { feature, proximity }] of nearby) {
    const properties = feature.properties, visor = local.visor[group];
    const directory = getDirectoryProject(group) || getDirectoryProject(group.replace(/\//g, "-"));
    const phase = String(properties.FAS_TX_DENOM || directory?.status || "Fase no disponible");
    const milestones = projectMilestones(visor?.tramitacion || [], today, { date: areaDate(properties.FEX_DT_APROB), phase });
    const lastMilestone = milestones[0] || null;
    projects.push({
      id: directory?.id || group, group, href: directory ? directoryProjectPath(directory) : sigmaFichaPath(group),
      title: directory?.title || String(properties.EXP_TX_DENOM || group),
      summary: directory?.summary || visor?.visorFicha?.resumenContenido || local.cards[group]?.resumen || "Consulta el expediente para conocer qué se plantea en este ámbito.",
      instrument: visor?.visorFicha?.figuraTipo || String(properties.TFIG_TX_ABREV || "Planeamiento"),
      phase, researched: Boolean(directory?.researched), scope: hasBroadMapExtent(feature.geometry) || (geometryExtentM2(feature.geometry, lat) > 15_000_000 && /cat[aá]logo|normativ|plan general|cines|teatros/i.test(`${properties.EXP_TX_DENOM} ${visor?.visorFicha?.figuraTipo}`)) ? "general" : "local", ...proximity, geometry: areaDisplayGeometry(feature.geometry, { lat, lng, radius }),
      milestones, lastMilestone, recent: Boolean(lastMilestone && lastMilestone.date >= cutoff),
      sourceUrl: typeof properties.ENLACE === "string" ? properties.ENLACE : typeof properties.Enlace === "string" ? properties.Enlace : null,
    });
  }
  projects.sort((a, b) => Number(b.researched) - Number(a.researched) || Number(b.recent) - Number(a.recent) || Number(b.containsPoint) - Number(a.containsPoint) || (b.lastMilestone?.date || "").localeCompare(a.lastMilestone?.date || "") || a.distanceM - b.distanceM);
  return { projects: projects.slice(0, 200), total: projects.length, limited: projects.length > 200, asOf: today, cutoff, snapshot: !live, recentCount: projects.filter(project => project.recent).length, containsCount: projects.filter(project => project.containsPoint).length };
}
