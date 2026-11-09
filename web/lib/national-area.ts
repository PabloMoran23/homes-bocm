import type { Geometry } from "geojson";
import type { CmMunicipioOption } from "./cm-portal-geo";
import type { DirectoryMunicipality } from "./project-directory";

export type NationalAreaProject = { id: string; href: string; title: string; summary: string; phase: string; date: string | null; researched: boolean; distanceM?: number; containsPoint?: boolean; geometry?: Geometry };
export type NationalAreaResult = {
  center: { lat: number; lng: number; label: string }; municipality: { name: string; href: string } | null;
  scope: "nearby" | "municipal" | "uncovered"; radiusM: number; months: number; asOf: string;
  nearby: NationalAreaProject[]; recent: NationalAreaProject[]; history: NationalAreaProject[];
  total: number; liveUnavailable: boolean; catalogueDate: string; alternatives: { name: string; href: string }[];
};
export function municipalityNameKey(name: string) {
  return name.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}
export function areaDistanceM(a: [number, number], b: [number, number]) {
  const rad = Math.PI / 180, dy = (b[1] - a[1]) * rad, dx = (b[0] - a[0]) * rad;
  const v = Math.sin(dy/2)**2 + Math.cos(a[1]*rad)*Math.cos(b[1]*rad)*Math.sin(dx/2)**2;
  return 6371000 * 2 * Math.asin(Math.min(1, Math.sqrt(v)));
}
/** Exact municipality name (including bilingual variants), never nearest-town inference. */
export function resolveAreaMunicipality(rows: DirectoryMunicipality[], name: string, lat: number, lng: number) {
  const keys = new Set([name, ...name.split("/")].map(municipalityNameKey));
  const matches = rows.filter(row => [row.name, ...row.name.split("/")].some(part => keys.has(municipalityNameKey(part))));
  const nearby = matches.filter(row => areaDistanceM(row.center, [lng, lat]) < 80000).sort((a,b) => areaDistanceM(a.center,[lng,lat])-areaDistanceM(b.center,[lng,lat]));
  // Homonymous neighbouring municipalities require a more precise identifier.
  return nearby.length === 1 ? nearby[0] : null;
}
export function hasReliableAreaGeometry(properties: { approx?: boolean; coordSource?: string }, geometry?: Geometry | null) {
  return Boolean(geometry && !properties.approx && properties.coordSource && !/municip|jitter|aprox|approx|fallback|unknown/i.test(properties.coordSource));
}

/** File attachments stay in the full ficha, rather than becoming project cards. */
export function isNationalAreaCard(title: string) {
  return Boolean(title.trim()) && !/\.(?:pdf|docx?|xlsx?|zip)(?:\s|$)/i.test(title);
}

/** Geographic reference for municipality matching only, never a project position. */
export function municipalityReference(m: CmMunicipioOption): [number, number] | null {
  if (typeof m.centerLng === "number" && typeof m.centerLat === "number" && Number.isFinite(m.centerLng) && Number.isFinite(m.centerLat)) return [m.centerLng, m.centerLat];
  const bounds = [m.west, m.south, m.east, m.north];
  if (!bounds.every(value => typeof value === "number" && Number.isFinite(value)) || m.west! >= m.east! || m.south! >= m.north!) return null;
  return [(m.west! + m.east!) / 2, (m.south! + m.north!) / 2];
}

export function areaCatalogueText(text: string) {
  return text.replace(/<[^>]*>/g, " ").replace(/&nbsp;|&#160;/gi, " ").replace(/&amp;/gi, "&").replace(/&quot;/gi, '\"').replace(/&#39;|&apos;/gi, "'").replace(/\s+/g, " ").trim();
}
