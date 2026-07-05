"use client";

import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import type { PathOptions } from "leaflet";
import {
  featureLayerStyle,
  featurePointStyle,
  featurePopupHtml,
  shouldShowSigmaFeature,
  type FeaturePopupOptions,
  type SectorFeatureCollection,
} from "@/lib/sector-geo";
import { expedienteGrupoKeyFromVariant } from "@/lib/madrid-expediente";
import { useMapVisualContext } from "@/components/map/useMapVisualContext";
import { bindMapHoverPopup } from "@/lib/map-hover-popup";
import type { MapVisualContext } from "@/lib/map-visual-scale";

const HIDDEN_STYLE: PathOptions = {
  opacity: 0,
  fillOpacity: 0,
  weight: 0,
  stroke: false,
};

function expedienteFromProps(props: Record<string, unknown> | undefined): string {
  return expedienteGrupoKeyFromVariant(String(props?.EXP_TX_NUMERO || ""));
}

function applySigmaFeatureStyle(
  map: L.Map,
  subLayer: L.Layer,
  feature: GeoJSON.Feature,
  visual: MapVisualContext,
  preview: boolean,
  selectedExpediente: string | null,
) {
  const props = feature.properties as Record<string, unknown> | undefined;
  const show = shouldShowSigmaFeature(map, feature, visual, { preview });
  if (!show) {
    if ("setStyle" in subLayer && typeof subLayer.setStyle === "function") {
      subLayer.setStyle(HIDDEN_STYLE);
    }
    return;
  }
  const selected = Boolean(
    selectedExpediente && expedienteFromProps(props) === selectedExpediente,
  );
  const geom = feature.geometry;
  const base =
    geom?.type === "Point"
      ? (featurePointStyle(props, preview ? null : visual) as PathOptions)
      : (featureLayerStyle(props, preview ? null : visual) as PathOptions);

  const style: PathOptions = selected
    ? {
        ...base,
        weight: Math.max(3, (Number(base.weight) || 2) + 2),
        fillOpacity: Math.min(0.58, (Number(base.fillOpacity) || 0.28) * 1.35),
        opacity: Math.min(1, (Number(base.opacity) || 0.9) + 0.05),
      }
    : base;

  if ("setStyle" in subLayer && typeof subLayer.setStyle === "function") {
    subLayer.setStyle(style);
  }
}

export function SigmaPolygonsLayer({
  geojson,
  popupOptions,
  visible,
  preview = false,
  preferCanvas = false,
  cardSelection = false,
  selectedExpediente = null,
  onSelectExpediente,
}: {
  geojson: SectorFeatureCollection | null;
  popupOptions: FeaturePopupOptions | null;
  visible: boolean;
  /** Vista previa (inicio): sin popups ni navegación al hacer clic. */
  preview?: boolean;
  preferCanvas?: boolean;
  /** Explorar: tarjeta React en lugar de popup HTML. */
  cardSelection?: boolean;
  selectedExpediente?: string | null;
  onSelectExpediente?: (expedienteGrupo: string) => void;
}) {
  const map = useMap();
  const visual = useMapVisualContext();
  const layerRef = useRef<L.GeoJSON | null>(null);
  const onSelectRef = useRef(onSelectExpediente);
  onSelectRef.current = onSelectExpediente;

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

        if (cardSelection) {
          lyr.on("click", (e: L.LeafletMouseEvent) => {
            L.DomEvent.stopPropagation(e);
            const grupo = expedienteFromProps(props);
            if (grupo) onSelectRef.current?.(grupo);
          });
          return;
        }

        const pop = featurePopupHtml(props, popupOptions ?? undefined);
        bindMapHoverPopup(lyr, pop, {
          className: "homes-map-popup homes-map-popup-sigma",
          maxWidth: 380,
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
  }, [map, geojson, visible, preview, preferCanvas, popupOptions, cardSelection, visual]);

  /** Actualiza visibilidad/estilo in-place al cambiar zoom o tamaño del mapa. */
  useEffect(() => {
    const layer = layerRef.current;
    if (!layer || !visible) return;

    layer.eachLayer((subLayer) => {
      const feature = (
        subLayer as L.Layer & { feature?: GeoJSON.Feature }
      ).feature;
      if (!feature) return;
      applySigmaFeatureStyle(
        map,
        subLayer,
        feature,
        visual,
        preview,
        selectedExpediente,
      );
    });
  }, [map, visible, preview, visual, selectedExpediente]);

  return null;
}
