import type { Feature, Geometry, Position } from "geojson";
import type { ProyectoInfoExtra } from "./proyecto-info-extra";
import type { SigmaVisorFicha, SigmaVisorNtiDoc, SigmaVisorTramite } from "./types";
import type { SigmaExpedienteMetric } from "./sigma-metrics";

export type AreaMilestone = { date: string; label: string; authority: string | null };
export type AreaProject = {
  id: string; group: string; href: string; title: string; summary: string;
  phase: string; phaseDate?: string | null; instrument: string; researched: boolean; scope: "local" | "general";
  distanceM: number; containsPoint: boolean; location: [number, number];
  geometry: Geometry; milestones: AreaMilestone[]; lastMilestone: AreaMilestone | null;
  recent: boolean; sourceUrl: string | null;
};
export type AreaContext = {
  projects: AreaProject[]; total: number; limited: boolean;
  asOf: string; cutoff: string; snapshot: boolean; recentCount: number; containsCount: number;
};
export type AreaProjectDetail = {
  title: string; summary: string; phase: string; group: string; sourceUrl: string | null;
  info: ProyectoInfoExtra | null; tramites: SigmaVisorTramite[];
  visor: SigmaVisorFicha | null; documents: SigmaVisorNtiDoc[];
  documentsTotal: number | null; documentsUrl: string | null;
  metric: SigmaExpedienteMetric | null;
};

/** Only complete, valid calendar dates. Never synthesize dates from an expediente's year. */
export function areaDate(raw: unknown): string | null {
  if (typeof raw === "number") {
    const date = new Date(raw);
    return Number.isFinite(date.getTime()) && raw > 0 ? date.toISOString().slice(0, 10) : null;
  }
  if (typeof raw !== "string") return null;
  let value = raw.trim();
  const es = value.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (es) value = `${es[3]}-${es[2].padStart(2, "0")}-${es[1].padStart(2, "0")}`;
  if (!/^\d{4}-\d{2}-\d{2}(?:T.*)?$/.test(value)) return null;
  const iso = value.slice(0, 10), date = new Date(`${iso}T12:00:00Z`);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === iso ? iso : null;
}
export function areaToday(): string {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Madrid", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
  return ["year", "month", "day"].map(type => parts.find(part => part.type === type)!.value).join("-");
}
export function areaCutoff(today: string, months: number): string {
  const date = new Date(`${today}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() - months * 30);
  return date.toISOString().slice(0, 10);
}
export function projectMilestones(rows: SigmaVisorTramite[], asOf: string, fallback?: { date: unknown; phase: string }): AreaMilestone[] {
  const events = rows.flatMap(row => {
    const date = areaDate(row.fecha);
    return date && date <= asOf && row.tramite ? [{ date, label: row.tramite, authority: row.organo }] : [];
  });
  const fallbackDate = areaDate(fallback?.date);
  const comparable = (value: string) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
  const equivalent = fallbackDate && events.some(event => comparable(event.label) === comparable(fallback?.phase || "")
    && Math.abs(Date.parse(event.date) - Date.parse(fallbackDate)) <= 3 * 86400_000);
  if (fallbackDate && fallbackDate <= asOf && !equivalent) events.push({ date: fallbackDate, label: fallback?.phase || "Trámite registrado", authority: null });
  return [...new Map(events.map(event => [`${event.date}:${event.label}`, event])).values()].sort((a, b) => b.date.localeCompare(a.date));
}

function inRing(point: Position, ring: Position[]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const a = ring[i], b = ring[j];
    if ((a[1] > point[1]) !== (b[1] > point[1]) && point[0] < (b[0] - a[0]) * (point[1] - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
  }
  return inside;
}
/** Distance to the actual polygon, including holes; never to its centroid. */
export function geometryProximity(geometry: Geometry, lng: number, lat: number): { distanceM: number; containsPoint: boolean; location: [number, number] } | null {
  const sx = 111_320 * Math.cos(lat * Math.PI / 180), sy = 111_320;
  const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.type === "MultiPolygon" ? geometry.coordinates : [];
  for (const rings of polygons) {
    if (rings[0] && inRing([lng, lat], rings[0]) && !rings.slice(1).some(ring => inRing([lng, lat], ring))) {
      return { distanceM: 0, containsPoint: true, location: [lng, lat] };
    }
  }
  let best = Infinity, location: [number, number] = [lng, lat];
  const consider = (a: Position, b = a) => {
    const ax = (a[0] - lng) * sx, ay = (a[1] - lat) * sy;
    const dx = (b[0] - a[0]) * sx, dy = (b[1] - a[1]) * sy;
    const t = dx || dy ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / (dx * dx + dy * dy))) : 0;
    const distance = Math.hypot(ax + t * dx, ay + t * dy);
    if (distance < best) { best = distance; location = [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]; }
  };
  if (geometry.type === "Point") consider(geometry.coordinates);
  for (const rings of polygons) for (const ring of rings) for (let i = 1; i < ring.length; i++) consider(ring[i - 1], ring[i]);
  return Number.isFinite(best) ? { distanceM: Math.round(best), containsPoint: best < .01, location } : null;
}
export type AreaFeature = Feature<Geometry, Record<string, unknown>>;
export function areaFeatureGroup(feature: AreaFeature): string | null {
  const raw = feature.properties?.EXP_TX_NUMERO;
  if (typeof raw !== "string" || !raw.trim()) return null;
  const parts = raw.trim().split("/");
  return parts.length === 3 && /^\d+$/.test(parts[2]) ? `${parts[0]}/${parts[1]}/${parts[2].padStart(5, "0")}` : raw.trim();
}
export function areaPhaseHint(phase: string, recent: boolean): string {
  const normalized = phase.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  if (/definitiva/.test(normalized)) return "Aprobación registrada; la ejecución de las obras requiere confirmación independiente.";
  if (/inicial|provisional|informacion publica|tramitacion/.test(normalized)) return recent
    ? "Hay un movimiento de tramitación dentro del periodo consultado."
    : "Es la última fase registrada; no hay hitos documentados en el periodo consultado.";
  return "Consulta el expediente y sus fuentes para conocer el alcance de la actuación.";
}

/** Approximate surface only to distinguish city-wide context from local scopes. */
export function geometrySurfaceM2(geometry: Geometry, lat: number): number {
  const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.type === "MultiPolygon" ? geometry.coordinates : [];
  const area = (ring: Position[]) => Math.abs(ring.reduce((sum, point, i) => {
    const next = ring[(i + 1) % ring.length];
    return sum + point[0] * next[1] - next[0] * point[1];
  }, 0)) / 2;
  return polygons.reduce((sum, rings) => sum + (rings[0] ? area(rings[0]) - rings.slice(1).reduce((holes, ring) => holes + area(ring), 0) : 0), 0) * 111_320 ** 2 * Math.cos(lat * Math.PI / 180);
}
/** Simplify large outlines for display, after proximity has used the full polygon. */
export function areaDisplayGeometry(geometry: Geometry, window?: { lat: number; lng: number; radius: number }): Geometry {
  const simplifyRing = (ring: Position[]): Position[] => {
    if (ring.length < 250) return ring;
    const keep = new Set([0, ring.length - 1]), stack = [[0, ring.length - 1]];
    const tolerance2 = .00008 ** 2;
    while (stack.length) {
      const [start, end] = stack.pop()!;
      const a = ring[start], b = ring[end], dx = b[0] - a[0], dy = b[1] - a[1];
      let maximum = tolerance2, index = -1;
      for (let i = start + 1; i < end; i++) {
        const point = ring[i];
        const t = dx || dy ? Math.max(0, Math.min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / (dx * dx + dy * dy))) : 0;
        const d2 = (point[0] - a[0] - t * dx) ** 2 + (point[1] - a[1] - t * dy) ** 2;
        if (d2 > maximum) { maximum = d2; index = i; }
      }
      if (index >= 0) { keep.add(index); stack.push([start, index], [index, end]); }
    }
    const result = [...keep].sort((a, b) => a - b).map(i => ring[i]);
    return result.length >= 4 ? result : ring;
  };
  if (geometry.type === "Polygon") return { ...geometry, coordinates: geometry.coordinates.map(simplifyRing) };
  if (geometry.type === "MultiPolygon") {
    const relevant = window ? geometry.coordinates.filter(rings => {
      const proximity = geometryProximity({ type: "Polygon", coordinates: rings }, window.lng, window.lat);
      return proximity && proximity.distanceM <= window.radius;
    }) : geometry.coordinates;
    return { ...geometry, coordinates: relevant.map(rings => rings.map(simplifyRing)) };
  }
  return geometry;
}

export function geometryExtentM2(geometry: Geometry, lat: number): number {
  const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.type === "MultiPolygon" ? geometry.coordinates : [];
  let west = Infinity, east = -Infinity, south = Infinity, north = -Infinity;
  for (const rings of polygons) for (const ring of rings) for (const point of ring) {
    west = Math.min(west, point[0]); east = Math.max(east, point[0]); south = Math.min(south, point[1]); north = Math.max(north, point[1]);
  }
  return Number.isFinite(west) ? (east - west) * (north - south) * 111_320 ** 2 * Math.cos(lat * Math.PI / 180) : 0;
}

/** Research chronology uses dates written in the event, never the source publication date. */
export function researchMilestones(info: ProyectoInfoExtra | null, asOf: string): AreaMilestone[] {
  if (!info) return [];
  const monthNames = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
  const datePattern = /\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}\/\d{1,2}\/\d{4}\b|\b\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+de\s+\d{4}\b/gi;
  const events: AreaMilestone[] = [];
  for (const row of info.datos.filter(dato => dato.bloque === "cronologia")) {
    const matches = [...row.valor.matchAll(datePattern)];
    for (const [i, match] of matches.entries()) {
      const written = match[0].match(/^(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})$/i);
      const date = written ? areaDate(`${written[3]}-${String(monthNames.indexOf(written[2].toLowerCase()) + 1).padStart(2, "0")}-${written[1].padStart(2, "0")}`) : areaDate(match[0]);
      if (!date || date > asOf) continue;
      if (i === 0) events.push({ date, label: row.etiqueta, authority: row.fuenteNombre });
      else {
        const previous = matches[i - 1];
        const preceding = row.valor.slice((previous.index || 0) + previous[0].length, match.index);
        if (/BOCM|bolet[ií]n/i.test(preceding) && /public|anuncio/i.test(preceding)) events.push({ date, label: "Publicación en BOCM", authority: row.fuenteNombre });
      }
    }
  }
  return [...new Map(events.map(event => [`${event.date}:${event.label}`, event])).values()].sort((a, b) => b.date.localeCompare(a.date));
}

const approvalKind = (label: string) => /aprobaci[oó]n\s+(definitiva|provisional|inicial)/i.exec(label)?.[1].toLowerCase() || null;
export function enrichAreaProject(project: AreaProject, detail: AreaProjectDetail, asOf: string, cutoff: string): AreaProject {
  const research = researchMilestones(detail.info, asOf);
  const documentedPhases = new Set(research.map(event => approvalKind(event.label)).filter(Boolean));
  const recorded = [...project.milestones, ...projectMilestones(detail.tramites, asOf)]
    .filter(event => !documentedPhases.has(approvalKind(event.label)));
  const milestones = [...new Map([...recorded, ...research].map(event => [`${event.date}:${event.label}`, event])).values()].sort((a, b) => b.date.localeCompare(a.date));
  const latestApproval = milestones.find(event => approvalKind(event.label));
  return {
    ...project, title: detail.info?.datos.find(dato => dato.clave === "nombre_publico")?.valor || project.title, summary: detail.summary || project.summary,
    phase: latestApproval ? `Aprobación ${approvalKind(latestApproval.label)}` : detail.phase || project.phase,
    phaseDate: latestApproval?.date || project.phaseDate,
    researched: Boolean(detail.info) || project.researched,
    milestones, lastMilestone: milestones[0] || null, recent: Boolean(milestones[0] && milestones[0].date >= cutoff),
  };
}
