import { areaDate, areaCutoff } from "./area-context";
import { normalizarActuacionEdificio } from "./actuacion-edificio";

export type MonthlyLicenseSummary = {
  from: string; to: string; periodMonths: number; maxMonths: number; expanded: boolean;
  latestDate: string | null; total: number; categories: { label: string; count: number }[];
};
export type LicenseFeature = { geometry?: { coordinates?: number[] }; properties: Record<string, unknown> };
export const AREA_LICENSE_TARGET = 20;
const labels: Record<string, string> = { vivienda_obra: "Obras en viviendas", vivienda_obra_menor: "Obras menores en viviendas", local_obra: "Obras en locales", local_actividad: "Aperturas o cambios de actividad en locales", local_a_vivienda: "Locales convertidos en viviendas", edificio_obra_grande: "Edificios nuevos o ampliaciones", edificio_reforma_conservacion: "Reformas y conservación de edificios", edificio_demolicion: "Demoliciones", obra_exterior: "Obras en patios o exteriores", edificio_primera_ocupacion: "Primeras ocupaciones", vivienda_uso: "Cambios de uso en viviendas", consulta: "Consultas urbanísticas", tramite_generico: "Otros trámites", otro: "Otros trámites" };
/** Shared rolling window for every category; never older than the search filter. */
export function summarizeMonthlyLicenses(features: LicenseFeature[], lat: number, lng: number, radius: number, today: string, maxMonths = 12): MonthlyLicenseSummary {
  const limit = Math.max(1, Math.min(120, Math.floor(maxMonths)));
  const cutoff = areaCutoff(today, limit);
  let latestDate: string | null = null;
  const nearby: { date:string; label:string }[] = [];
  for (const feature of features) {
    const date = areaDate(String(feature.properties.fecha_concesion || ""));
    if (!date || date > today) continue;
    if (!latestDate || date > latestDate) latestDate = date;
    if (date < cutoff) continue;
    const coords = feature.geometry?.coordinates;
    if (!coords || coords.length !== 2 || !coords.every(Number.isFinite)) continue;
    const dy = (coords[1] - lat) * Math.PI / 180, dx = (coords[0] - lng) * Math.PI / 180;
    const a = Math.sin(dy / 2) ** 2 + Math.cos(lat * Math.PI / 180) * Math.cos(coords[1] * Math.PI / 180) * Math.sin(dx / 2) ** 2;
    if (6371000 * 2 * Math.asin(Math.min(1, Math.sqrt(a))) > radius) continue;
    const p = feature.properties, code = String(p.actuacion_que || normalizarActuacionEdificio(p).codigo);
    nearby.push({ date, label: labels[code] || "Otros trámites" });
  }
  const windows = [...new Set([1,3,6,12,24,36,limit].filter(months => months <= limit))].sort((a,b) => a-b);
  let periodMonths = limit, selected = nearby;
  for (const months of windows) {
    const from = areaCutoff(today, months);
    const rows = nearby.filter(row => row.date >= from);
    periodMonths = months; selected = rows;
    if (rows.length >= AREA_LICENSE_TARGET) break;
  }
  const counts = new Map<string,number>();
  for (const row of selected) counts.set(row.label,(counts.get(row.label) || 0)+1);
  return { from:areaCutoff(today,periodMonths), to:today, periodMonths, maxMonths:limit, expanded:periodMonths > 1, latestDate, total:selected.length, categories:[...counts].map(([label,count]) => ({label,count})).sort((a,b) => b.count-a.count) };
}
