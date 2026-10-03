"use client";

import { useEffect, useRef, useState } from "react";
import type { CmPortalGeoJson, CmPortalMapMeta, CmPortalProyectoProps } from "@/lib/cm-portal-geo";
import { mapCmPortalQuery } from "@/lib/map-live-urls";
import type { MapBounds } from "@/lib/map-viewport";

type Collection = CmPortalGeoJson<CmPortalProyectoProps>;
type Payload = {
  points?: Collection;
  polygons?: Collection;
  approx?: Collection;
  meta?: CmPortalMapMeta;
};
const EMPTY: Collection = { type: "FeatureCollection", features: [] };
const CACHE_TTL = 900_000;
const CACHE_LIMIT = 16;

type Result = { url: string; token?: number; payload: Payload | null; error: string | null };
const ERROR = "No hemos podido cargar los proyectos de este municipio.";

/** Municipality data survives viewport changes; only polygon requests are cancelled on pan. */
export function usePortalMapData(
  enabled: boolean,
  selection: { slug: string; from: string; to: string; token?: number } | null,
  bounds: MapBounds | null,
) {
  const cache = useRef(new Map<string, { payload: Payload; expires: number }>());
  const [municipality, setMunicipality] = useState<Result | null>(null);
  const [viewport, setViewport] = useState<Result | null>(null);
  // Strings are the effect dependencies: new bounds objects with the same quantized
  // coordinates must not restart a request (or cancel a request already in flight).
  const baseUrl = enabled && selection ? mapCmPortalQuery(selection) : null;
  const selectionToken = selection?.token ?? 0;
  const current = municipality?.url === baseUrl && municipality.token === selectionToken ? municipality : null;
  const full = current?.payload;
  const viewportUrl = baseUrl && full?.meta?.truncated && selection
    ? mapCmPortalQuery({ ...selection, bounds })
    : baseUrl;
  const zone = viewport?.url === viewportUrl ? viewport : null;

  useEffect(() => {
    if (!baseUrl) return;
    const ac = new AbortController();
    const cached = cache.current.get(baseUrl);
    if (cached && cached.expires > Date.now()) {
      setMunicipality({ url: baseUrl, token: selectionToken, payload: cached.payload, error: null });
      return;
    }
    void (async () => {
      try {
        const res = await fetch(baseUrl, { signal: ac.signal });
        if (!res.ok) throw new Error(ERROR);
        const payload: Payload = await res.json();
        if (ac.signal.aborted) return;
        cache.current.delete(baseUrl);
        cache.current.set(baseUrl, { payload, expires: Date.now() + CACHE_TTL });
        if (cache.current.size > CACHE_LIMIT) cache.current.delete(cache.current.keys().next().value!);
        setMunicipality({ url: baseUrl, token: selectionToken, payload, error: null });
      } catch {
        if (!ac.signal.aborted) setMunicipality({ url: baseUrl, token: selectionToken, payload: null, error: ERROR });
      }
    })();
    return () => ac.abort();
  }, [baseUrl, selectionToken]);

  useEffect(() => {
    if (!viewportUrl || viewportUrl === baseUrl) return;
    const ac = new AbortController();
    const cached = cache.current.get(viewportUrl);
    if (cached && cached.expires > Date.now()) {
      setViewport({ url: viewportUrl, payload: cached.payload, error: null });
      return;
    }
    void (async () => {
      try {
        const res = await fetch(viewportUrl, { signal: ac.signal });
        if (!res.ok) throw new Error(ERROR);
        const payload: Payload = await res.json();
        if (ac.signal.aborted) return;
        cache.current.delete(viewportUrl);
        cache.current.set(viewportUrl, { payload, expires: Date.now() + CACHE_TTL });
        if (cache.current.size > CACHE_LIMIT) cache.current.delete(cache.current.keys().next().value!);
        setViewport({ url: viewportUrl, payload, error: null });
      } catch {
        if (!ac.signal.aborted) setViewport({ url: viewportUrl, payload: null, error: ERROR });
      }
    })();
    return () => ac.abort();
  }, [baseUrl, viewportUrl]);

  // Keep the last polygon view while its replacement loads, but never mix municipalities.
  const previousZone = viewport?.url.startsWith(`${baseUrl}&minLng=`) ? viewport.payload : null;
  const view = viewportUrl !== baseUrl ? zone?.payload ?? previousZone : null;
  return {
    points: full?.points ?? null,
    polygons: view?.polygons ?? full?.polygons ?? null,
    approx: full?.approx ?? null,
    meta: full ? {
      ...full.meta,
      ...(view?.meta ? {
        recorteEnVista: true,
        proyectosPoligonos: view.meta.proyectosPoligonos,
        proyectosEnMapa: (full.points ?? EMPTY).features.length + (full.approx ?? EMPTY).features.length + (view.polygons ?? EMPTY).features.length,
        truncated: view.meta.truncated,
        limiteMapa: view.meta.limiteMapa,
      } : {}),
    } as CmPortalMapMeta : null,
    loading: Boolean(baseUrl && !current),
    ready: Boolean(current),
    error: current?.error ?? zone?.error ?? null,
  };
}
