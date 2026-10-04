"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { CmPortalGeoJson, CmPortalMapMeta, CmPortalProyectoProps, CmPortalHintProps } from "@/lib/cm-portal-geo";
import { mapCmPortalQuery } from "@/lib/map-live-urls";
import type { MapBounds } from "@/lib/map-viewport";
import { portalSeenInView, portalZoomLevel, rememberPortalProjects, type PortalSeen } from "@/lib/map-portal-continuity";

type Collection = CmPortalGeoJson<CmPortalProyectoProps>;
type Payload = { points?: Collection; polygons?: Collection; approx?: Collection; hints?: CmPortalGeoJson<CmPortalHintProps>; meta?: CmPortalMapMeta };
const CACHE_TTL = 900_000;
const CACHE_LIMIT = 32;
const SEEN_LEVELS = 8;
type Result = { url: string; scope: string; token: number; payload: Payload | null; error: string | null };
const ERROR = "No hemos podido cargar los proyectos de esta zona.";

/** Initial framing and later movement always use the same bounded viewport query. */
export function usePortalMapData(enabled: boolean, selection: { slug: string; from: string; to: string; token?: number } | null, bounds: MapBounds | null) {
  const cache = useRef(new Map<string, { payload: Payload; expires: number }>());
  const [result, setResult] = useState<Result | null>(null);
  const [seen, setSeen] = useState<Record<string, PortalSeen>>({});
  const token = selection?.token ?? 0;
  const settled = bounds && (bounds.cameraToken == null ? bounds.interaction == null : bounds.cameraToken === token + 1);
  const scope = enabled && selection ? `${selection.slug}:${selection.from}:${selection.to}:${portalZoomLevel(bounds?.zoom)}` : null;
  const url = scope && settled && selection && bounds ? mapCmPortalQuery({ ...selection, bounds }) : null;
  const matching = result?.url === url && result?.token === token ? result : null;
  const previous = result?.scope === scope && result.token === token ? result : null;

  useEffect(() => {
    if (!url || !scope) return;
    const ac = new AbortController();
    const accept = (payload: Payload) => {
      setSeen(previousSeen => {
        const now = Date.now();
        const valid = Object.entries(previousSeen).filter(([, value]) => now - value.updatedAt < CACHE_TTL && value !== previousSeen[scope]);
        return { ...Object.fromEntries(valid.slice(-(SEEN_LEVELS - 1))), [scope]: rememberPortalProjects(previousSeen[scope] && now - previousSeen[scope].updatedAt < CACHE_TTL ? previousSeen[scope] : undefined, payload, now) };
      });
      setResult({ url, scope, token, payload, error: null });
    };
    const cached = cache.current.get(url);
    if (cached && cached.expires > Date.now()) {
      accept(cached.payload);
      return;
    }
    void (async () => {
      try {
        const res = await fetch(url, { signal: ac.signal });
        if (!res.ok) throw new Error(ERROR);
        const payload: Payload = await res.json();
        if (ac.signal.aborted) return;
        cache.current.delete(url);
        cache.current.set(url, { payload, expires: Date.now() + CACHE_TTL });
        if (cache.current.size > CACHE_LIMIT) cache.current.delete(cache.current.keys().next().value!);
        accept(payload);
      } catch {
        if (!ac.signal.aborted) setResult({ url, scope, token, payload: null, error: ERROR });
      }
    })();
    return () => ac.abort();
  }, [url, scope, token]);

  const visible = useMemo(() => portalSeenInView(scope ? seen[scope] : undefined, settled ? bounds : null), [seen, scope, settled, bounds]);
  const active = matching?.payload ?? previous?.payload;
  return {
    ...visible,
    approx: scope && settled ? seen[scope]?.approx ?? active?.approx ?? null : null,
    hints: matching?.payload?.hints ?? null,
    meta: active?.meta ?? null,
    loading: Boolean(enabled && selection && !matching),
    ready: Boolean(active || visible.points),
    error: matching?.error ?? null,
  };
}
