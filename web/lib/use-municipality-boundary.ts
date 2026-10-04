"use client";
import { useEffect, useState } from "react";
import type { MunicipalityGeometry } from "@/lib/map-municipality-placement";
const cache = new Map<string, MunicipalityGeometry>();
export function useMunicipalityBoundary(selection: { nombre: string; initialFrame: { west: number; east: number; south: number; north: number } } | null, enabled: boolean) {
  const frame = selection?.initialFrame;
  const lng = frame ? (frame.west + frame.east) / 2 : 0;
  const lat = frame ? (frame.south + frame.north) / 2 : 0;
  const url = selection && enabled ? `/api/dominio/map-municipio-boundary?${new URLSearchParams({ name: selection.nombre, lng: lng.toFixed(5), lat: lat.toFixed(5) })}` : null;
  const [result, setResult] = useState<{ url: string; geometry: MunicipalityGeometry | null } | null>(null);
  useEffect(() => {
    if (!url) return;
    const abort = new AbortController();
    void (async () => {
      const cached = cache.get(url);
      if (cached) { setResult({ url, geometry: cached }); return; }
      try {
        const response = await fetch(url, { signal: abort.signal });
        if (!response.ok) throw new Error("Boundary unavailable");
        const body = await response.json() as { geometry: MunicipalityGeometry };
        if (abort.signal.aborted) return;
        cache.set(url, body.geometry);
        if (cache.size > 20) cache.delete(cache.keys().next().value!);
        setResult({ url, geometry: body.geometry });
      } catch { if (!abort.signal.aborted) setResult({ url, geometry: null }); }
    })();
    return () => abort.abort();
  }, [url]);
  return result?.url === url ? result.geometry : null;
}
