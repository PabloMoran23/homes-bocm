import type { BoletinAreaResult } from "@/lib/boletin-area";

const TTL_MS = 5 * 60 * 1000;
const MAX_ENTRIES = 200;

type CacheEntry = {
  expiresAt: number;
  result: BoletinAreaResult;
};

const cache = new Map<string, CacheEntry>();

function prune(now: number) {
  if (cache.size <= MAX_ENTRIES) return;
  for (const [key, entry] of cache) {
    if (entry.expiresAt <= now) cache.delete(key);
    if (cache.size <= MAX_ENTRIES * 0.8) break;
  }
}

/** Clave estable (~100 m) para reutilizar respuestas calientes en la misma instancia. */
export function boletinAreaCacheKey(input: {
  lat: number;
  lng: number;
  radiusM: number;
  months: number;
  ndp?: string | null;
}) {
  if (input.ndp) {
    return `ndp:${input.ndp.trim()}:${input.radiusM}:${input.months}`;
  }
  const lat = Math.round(input.lat * 1000) / 1000;
  const lng = Math.round(input.lng * 1000) / 1000;
  return `geo:${lat}:${lng}:${input.radiusM}:${input.months}`;
}

export function readBoletinAreaCache(key: string): BoletinAreaResult | null {
  const entry = cache.get(key);
  if (!entry) return null;
  if (entry.expiresAt <= Date.now()) {
    cache.delete(key);
    return null;
  }
  return entry.result;
}

export function writeBoletinAreaCache(key: string, result: BoletinAreaResult) {
  const now = Date.now();
  prune(now);
  cache.set(key, { expiresAt: now + TTL_MS, result });
}

export const BOLETIN_AREA_CACHE_HEADERS = {
  "Cache-Control": "public, s-maxage=300, stale-while-revalidate=600",
} as const;
