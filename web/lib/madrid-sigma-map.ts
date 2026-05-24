import { useEffect, useMemo, useState } from "react";
import type { SectorFeatureCollection } from "@/lib/sector-geo";
import {
  filterSigmaMapFeaturesByBBox,
  SIGMA_MAP_DEFAULT_MAX_BBOX_KM2,
} from "@/lib/sigma-map-geometry";

export const SIGMA_AMBITOS_MAP_URL = "/data/madrid-sigma-ambitos.geojson";
export const SIGMA_AMBITOS_LANDING_URL = "/data/madrid-sigma-ambitos-landing.geojson";

/** Mismo recorte que Explorar (capa «ámbitos», sin polígonos enormes). */
export function filterSigmaAmbitosForMap(fc: SectorFeatureCollection): SectorFeatureCollection {
  return filterSigmaMapFeaturesByBBox(fc, SIGMA_MAP_DEFAULT_MAX_BBOX_KM2).visible;
}

function useSigmaAmbitosMapGeoFromUrl(url: string, prefiltered: boolean) {
  const [raw, setRaw] = useState<SectorFeatureCollection | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(url);
        if (!res.ok) throw new Error(String(res.status));
        if (!cancelled) {
          setRaw((await res.json()) as SectorFeatureCollection);
          setReady(true);
        }
      } catch {
        if (!cancelled) {
          setErr(
            "Faltan datos SIGMA de Madrid. Ejecuta: npm run build-data en la carpeta web/.",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [url]);

  const geo = useMemo(
    () => (raw ? (prefiltered ? raw : filterSigmaAmbitosForMap(raw)) : null),
    [raw, prefiltered],
  );

  return { geo, err, ready, loading: !ready && !err };
}

export function useSigmaAmbitosMapGeo() {
  return useSigmaAmbitosMapGeoFromUrl(SIGMA_AMBITOS_MAP_URL, false);
}

/** Vista previa de inicio: GeoJSON simplificado (~1,5 MB vs ~23 MB). */
export function useSigmaAmbitosLandingGeo(enabled = true) {
  const state = useSigmaAmbitosMapGeoFromUrl(SIGMA_AMBITOS_LANDING_URL, true);
  if (!enabled) {
    return { geo: null, err: null, ready: false, loading: false };
  }
  return state;
}
