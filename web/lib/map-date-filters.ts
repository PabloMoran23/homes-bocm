import { sigmaActivityMs } from "@/lib/madrid-sigma-filters";
import { parseFechaEs } from "@/lib/ubicacion-resumen";

export type MapDateRange = {
  fromMs: number | null;
  toMs: number | null;
};

export function mapDateRangeFromInputs(from: string, to: string): MapDateRange {
  return {
    fromMs: from ? parseDateInputStartUtc(from) : null,
    toMs: to ? parseDateInputEndUtc(to) : null,
  };
}

/** `input[type=date]` → inicio del día UTC. */
export function parseDateInputStartUtc(yyyyMmDd: string): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(yyyyMmDd.trim());
  if (!m) return null;
  const y = Number(m[1]);
  const mo = Number(m[2]) - 1;
  const d = Number(m[3]);
  if (!Number.isFinite(y) || !Number.isFinite(mo) || !Number.isFinite(d)) return null;
  return Date.UTC(y, mo, d, 0, 0, 0, 0);
}

/** `input[type=date]` → fin del día UTC. */
export function parseDateInputEndUtc(yyyyMmDd: string): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(yyyyMmDd.trim());
  if (!m) return null;
  const y = Number(m[1]);
  const mo = Number(m[2]) - 1;
  const d = Number(m[3]);
  if (!Number.isFinite(y) || !Number.isFinite(mo) || !Number.isFinite(d)) return null;
  return Date.UTC(y, mo, d, 23, 59, 59, 999);
}

export function passesMapDateRange(activityMs: number | null, range: MapDateRange): boolean {
  const { fromMs, toMs } = range;
  if (fromMs == null && toMs == null) return true;
  if (activityMs == null) return false;
  if (fromMs != null && activityMs < fromMs) return false;
  if (toMs != null && activityMs > toMs) return false;
  return true;
}

export function ubicacionActivityMs(properties: {
  ultimaLicenciaFecha?: string | null;
}): number | null {
  const raw = properties.ultimaLicenciaFecha;
  if (!raw || !String(raw).trim()) return null;
  const s = String(raw).trim();
  const d = parseFechaEs(s) ?? ( /^\d{4}-\d{2}-\d{2}$/.test(s) ? new Date(s + "T12:00:00Z") : null);
  return d && !Number.isNaN(d.getTime()) ? d.getTime() : null;
}

export function sigmaFeatureActivityMs(properties: Record<string, unknown>): number | null {
  return sigmaActivityMs(properties);
}
