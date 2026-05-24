"use client";

import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import type { PathOptions } from "leaflet";
import { useRouter } from "next/navigation";
import { expedienteGrupoKeyFromVariant } from "@/lib/madrid-expediente";
import {
  featureLayerStyle,
  featurePointStyle,
  featurePopupHtml,
  type FeaturePopupOptions,
  type SectorFeatureCollection,
} from "@/lib/sector-geo";
import { sigmaFichaPath } from "@/lib/sigma-ficha-path";

export function SigmaPolygonsLayer({
  geojson,
  popupOptions,
  visible,
  preview = false,
}: {
  geojson: SectorFeatureCollection | null;
  popupOptions: FeaturePopupOptions | null;
  visible: boolean;
  /** Vista previa (inicio): sin popups ni navegación al hacer clic. */
  preview?: boolean;
}) {
  const map = useMap();
  const router = useRouter();
  const layerRef = useRef<L.GeoJSON | null>(null);
  const routerRef = useRef(router);
  routerRef.current = router;

  useEffect(() => {
    if (!visible || !geojson?.features?.length) {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
      return;
    }

    const layer = L.geoJSON(geojson as GeoJSON.FeatureCollection, {
      style(feature) {
        return featureLayerStyle(feature?.properties) as PathOptions;
      },
      pointToLayer(feature, latlng) {
        return L.circleMarker(latlng, featurePointStyle(feature?.properties) as PathOptions);
      },
      onEachFeature(feature, lyr) {
        if (preview) return;
        const props = feature.properties as Record<string, unknown> | undefined;
        const pop = featurePopupHtml(props, popupOptions ?? undefined);
        lyr.bindPopup(pop, {
          className: "homes-map-popup homes-map-popup-sigma",
          maxWidth: 380,
        });
        lyr.on("click", () => {
          const expKey = expedienteGrupoKeyFromVariant(String(props?.EXP_TX_NUMERO || ""));
          if (expKey) routerRef.current.push(sigmaFichaPath(expKey));
        });
      },
    });

    layer.addTo(map);
    layer.bringToFront();
    layerRef.current = layer;

    return () => {
      map.removeLayer(layer);
      layerRef.current = null;
    };
  }, [map, geojson, popupOptions, visible, preview]);

  return null;
}
