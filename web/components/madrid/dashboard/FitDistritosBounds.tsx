"use client";

import { useEffect } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";

const FIT_OPTS: L.FitBoundsOptions = {
  padding: [14, 14],
  maxZoom: 13,
  animate: false,
};

export function FitDistritosBounds({
  geojson,
}: {
  geojson: GeoJSON.FeatureCollection | null;
}) {
  const map = useMap();

  useEffect(() => {
    if (!geojson?.features?.length) return;

    const layer = L.geoJSON(geojson);
    const bounds = layer.getBounds();
    if (!bounds.isValid()) return;

    const padded = bounds.pad(0.03);

    const apply = () => {
      map.setMaxBounds(padded.pad(0.08));
      map.fitBounds(bounds, FIT_OPTS);
    };

    apply();
    const t1 = window.setTimeout(apply, 80);
    const t2 = window.setTimeout(apply, 280);

    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
      map.setMaxBounds(undefined);
    };
  }, [map, geojson]);

  return null;
}
