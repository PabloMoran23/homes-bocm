import { hasBroadMapExtent } from "./map-project-scope";
import { getProjectDirectory, municipalityProjects, municipalityPath, directoryProjectPath, getDirectoryProject } from "./project-directory";
import { areaToday, areaDate, areaCutoff, geometryProximity, areaDisplayGeometry } from "./area-context";
import { areaDistanceM, resolveAreaMunicipality, municipalityNameKey, municipalityReference, areaCatalogueText, hasReliableAreaGeometry, isNationalAreaCard, type NationalAreaProject, type NationalAreaResult } from "./national-area";
import { getSupabaseServer } from "./supabase/server";
import type { CmPortalGeoJson, CmPortalProyectoProps, CmMunicipioOption } from "./cm-portal-geo";

type MapPayload = { points?: CmPortalGeoJson<CmPortalProyectoProps>; polygons?: CmPortalGeoJson<CmPortalProyectoProps>; approx?: CmPortalGeoJson<CmPortalProyectoProps> };
let municipalityIndex: Promise<CmMunicipioOption[]> | null = null;
async function liveMunicipalities() {
  if (!municipalityIndex) municipalityIndex = (async () => {
    const db = getSupabaseServer(); if (!db) return [];
    const { data, error } = await db.rpc("map_cm_municipios");
    if (error) { municipalityIndex = null; return []; }
    return (data?.municipios || []) as CmMunicipioOption[];
  })().catch(() => { municipalityIndex = null; return []; });
  return municipalityIndex;
}
export async function loadNationalArea(lat: number, lng: number, name: string, label: string, radiusM: number, months: number): Promise<NationalAreaResult> {
  const directory = getProjectDirectory(), asOf = areaToday(), cutoff = areaCutoff(asOf, months);
  const index = await liveMunicipalities();
  const liveOptions = index.flatMap(m => {
    const center = municipalityReference(m);
    return m.n > 0 && center ? [{ slug:m.slug, name:m.nombre, province:"", center }] : [];
  });
  const municipality = resolveAreaMunicipality(directory.municipalities, name, lat, lng) || resolveAreaMunicipality(liveOptions, name, lat, lng);
  const municipalityHref = municipality ? municipality.province ? municipalityPath(municipality) : `/explore?municipio=${encodeURIComponent(municipality.slug)}` : "";
  const result: NationalAreaResult = { center: { lat, lng, label }, municipality: municipality ? { name: municipality.name, href: municipalityHref } : null, scope: "uncovered", radiusM, months, asOf, nearby: [], recent: [], history: [], total: 0, liveUnavailable: false, catalogueDate: directory.generatedAt, alternatives: [] };
  if (!municipality) {
    result.alternatives = directory.municipalities.filter(m => areaDistanceM(m.center, [lng,lat]) <= 60000).sort((a,b) => areaDistanceM(a.center,[lng,lat])-areaDistanceM(b.center,[lng,lat])).slice(0,3).map(m => ({ name:m.name, href:municipalityPath(m) }));
    return result;
  }
  const records = new Map<string, NationalAreaProject>();
  for (const p of municipalityProjects(municipality).filter(p => isNationalAreaCard(p.title))) records.set(p.id, { id:p.id, href:directoryProjectPath(p), title:p.title, summary:p.summary, phase:p.status, researched:p.researched, date:null });
  const keys = new Set([municipality.name, ...municipality.name.split("/"), name].map(municipalityNameKey));
  const slugs = liveOptions.filter(m => [m.name, ...m.name.split("/")].some(part => keys.has(municipalityNameKey(part))) && areaDistanceM(m.center, [lng,lat]) < 80000).map(m => m.slug);
  if (!slugs.length) slugs.push(municipality.slug);
  // A separate recent query avoids losing new records to the map's centre-based limit.
  const db = getSupabaseServer();
  const dy = radiusM / 111000, dx = dy / Math.cos(lat * Math.PI / 180);
  const queries = [{ from:null, bbox:false }, { from:cutoff, bbox:false }, { from:null, bbox:true }];
  const responses = await Promise.all(slugs.slice(0,3).flatMap(slug => queries.map(query => (async () => {
    if (!db) return null;
    const { data, error } = await db.rpc("map_cm_portal_view_100", { p_slug:slug, p_from:query.from, p_to:query.from ? asOf : null, p_min_lng:query.bbox ? lng-dx : null, p_min_lat:query.bbox ? lat-dy : null, p_max_lng:query.bbox ? lng+dx : null, p_max_lat:query.bbox ? lat+dy : null });
    return error ? null : data as MapPayload;
  })().catch(() => null))));
  result.liveUnavailable = !responses.some(Boolean);
  const catalogueRecords = new Map(records);
  // Current public RPCs apply the active entity policy. Do not reinsert excluded
  // historical directory entries when a live query succeeded.
  if (!result.liveUnavailable) records.clear();
  for (const payload of responses) {
    for (const feature of [...(payload?.points?.features || []), ...(payload?.polygons?.features || []), ...(payload?.approx?.features || [])]) {
      const p = feature.properties; if (!p?.id || !isNationalAreaCard(p.nombrePopular || p.titulo || "")) continue;
      const canonical = getDirectoryProject(p.id), id = canonical?.id || p.id, previous = records.get(id) || catalogueRecords.get(id);
      const date = areaDate(p.fecha), geometry = feature.geometry;
      const item: NationalAreaProject = { id, href:canonical ? directoryProjectPath(canonical) : `/proyecto/${encodeURIComponent(id)}`, title:areaCatalogueText(p.nombrePopular || canonical?.title || p.titulo), summary:areaCatalogueText(p.resumen && !/^Instrumento: [^.]+\.$/i.test(p.resumen) ? p.resumen : previous?.summary || ""), phase:p.fase || previous?.phase || "", researched:Boolean(p.investigado || previous?.researched), date:date && date <= asOf ? date : previous?.date || null };
      if (hasReliableAreaGeometry(p, geometry) && !hasBroadMapExtent(geometry)) {
        const proximity = geometryProximity(geometry!, lng, lat);
        if (proximity && proximity.distanceM <= radiusM) Object.assign(item, { distanceM:proximity.distanceM, containsPoint:proximity.containsPoint, geometry:areaDisplayGeometry(geometry!, { lat,lng,radius:radiusM }) });
      }
      if (previous?.geometry && !item.geometry && !hasBroadMapExtent(geometry)) Object.assign(item, { geometry:previous.geometry, distanceM:previous.distanceM, containsPoint:previous.containsPoint });
      records.set(id,item);
    }
  }
  const all = [...records.values()].sort((a,b) => (b.date || "").localeCompare(a.date || "") || Number(b.researched)-Number(a.researched) || Number(Boolean(b.summary))-Number(Boolean(a.summary)) || a.title.localeCompare(b.title,"es"));
  result.total = all.length;
  result.nearby = all.filter(p => p.geometry).sort((a,b) => (a.distanceM || 0)-(b.distanceM || 0)).slice(0,12);
  result.recent = all.filter(p => p.date && p.date >= cutoff).slice(0,12);
  const recentIds = new Set(result.recent.map(p => p.id));
  result.history = all.filter(p => !recentIds.has(p.id) && !p.geometry).slice(0,12);
  result.scope = result.nearby.length ? "nearby" : "municipal";
  return result;
}
