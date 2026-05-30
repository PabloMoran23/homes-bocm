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
  shouldShowSigmaFeature,
  type FeaturePopupOptions,
  type SectorFeatureCollection,
} from "@/lib/sector-geo";
import { useMapVisualContext } from "@/components/map/useMapVisualContext";
import { sigmaFichaPath } from "@/lib/sigma-ficha-path";
import type { MapVisualContext } from "@/lib/map-visual-scale";

const HIDDEN_STYLE: PathOptions = {
  opacity: 0,
  fillOpacity: 0,
  weight: 0,
  stroke: false,
};

function applySigmaFeatureStyle(
  map: L.Map,
  subLayer: L.Layer,
  feature: GeoJSON.Feature,
  visual: MapVisualContext,
  preview: boolean,
) {
  const props = feature.properties as Record<string, unknown> | undefined;
  const show = shouldShowSigmaFeature(map, feature, visual, { preview });
  if (!show) {
    if ("setStyle" in subLayer && typeof subLayer.setStyle === "function") {
      subLayer.setStyle(HIDDEN_STYLE);
    }
    return;
  }
  const geom = feature.geometry;
  if (geom?.type === "Point" && "setStyle" in subLayer && typeof subLayer.setStyle === "function") {
    subLayer.setStyle(
      featurePointStyle(props, preview ? null : visual) as PathOptions,
    );
    return;
  }
  if ("setStyle" in subLayer && typeof subLayer.setStyle === "function") {
    subLayer.setStyle(
      featureLayerStyle(props, preview ? null : visual) as PathOptions,
    );
  }
}

export function SigmaPolygonsLayer({
  geojson,
  popupOptions,
  visible,
  preview = false,
  preferCanvas = false,
}: {
  geojson: SectorFeatureCollection | null;
  popupOptions: FeaturePopupOptions | null;
  visible: boolean;
  /** Vista previa (inicio): sin popups ni navegación al hacer clic. */
  preview?: boolean;
  preferCanvas?: boolean;
}) {
  const map = useMap();
  const visual = useMapVisualContext();
  const router = useRouter();
  const layerRef = useRef<L.GeoJSON | null>(null);
  const routerRef = useRef(router);
  routerRef.current = router;

  /** Crea la capa una sola vez al cambiar datos o visibilidad (no en cada pan/zoom). */
  useEffect(() => {
    if (!visible || !geojson?.features?.length) {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
      return;
    }

    const renderer =
      preview && !preferCanvas
        ? L.svg({ padding: 0.5 })
        : preferCanvas
          ? L.canvas({ padding: 0.5 })
          : undefined;

    const layer = L.geoJSON(geojson as GeoJSON.FeatureCollection, {
      ...(renderer ? { renderer } : {}),
      style(feature) {
        return featureLayerStyle(
          feature?.properties,
          preview ? null : visual,
        ) as PathOptions;
      },
      pointToLayer(feature, latlng) {
        return L.circleMarker(
          latlng,
          featurePointStyle(feature?.properties, preview ? null : visual) as PathOptions,
        );
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
  }, [map, geojson, visible, preview, preferCanvas, popupOptions]);

  /** Actualiza visibilidad/estilo in-place al cambiar zoom o tamaño del mapa. */
  useEffect(() => {
    const layer = layerRef.current;
    if (!layer || !visible) return;

    layer.eachLayer((subLayer) => {
      const feature = (
        subLayer as L.Layer & { feature?: GeoJSON.Feature }
      ).feature;
      if (!feature) return;
      applySigmaFeatureStyle(map, subLayer, feature, visual, preview);
    });
  }, [map, visible, preview, visual]);

  return null;
}
