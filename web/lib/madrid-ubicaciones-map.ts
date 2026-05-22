import { useEffect, useState } from "react";
import type { UbicacionMapProperties } from "@/lib/ubicacion";

export type UbicacionesMapGeoJson = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: UbicacionMapProperties;
  }>;
};

export const UBICACIONES_MAP_URL = "/data/ubicaciones-map.geojson";

/** Mismo recorte que en Explorar (Madrid capital y entorno). */
export function filterUbicacionesMadridCapital(geo: UbicacionesMapGeoJson): UbicacionesMapGeoJson {
  const features = geo.features.filter((f) => {
    const [lng, lat] = f.geometry.coordinates;
    return lat >= 39.5 && lat <= 41.2 && lng >= -4.5 && lng <= -3.0;
  });
  return { ...geo, features };
}

export function useUbicacionesMapGeo() {
  const [geo, setGeo] = useState<UbicacionesMapGeoJson | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(UBICACIONES_MAP_URL);
        if (!res.ok) throw new Error(String(res.status));
        if (!cancelled) {
          setGeo((await res.json()) as UbicacionesMapGeoJson);
          setReady(true);
        }
      } catch {
        if (!cancelled) {
          setErr(
            "Faltan datos de Madrid. Ejecuta: npm run build-data (y db/ingest_madrid_ubicacion.py si aplica).",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return { geo, err, ready, loading: !ready && !err };
}
