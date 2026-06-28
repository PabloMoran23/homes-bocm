"use client";

import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import {
  portalProyectoPopupHtml,
  type CmPortalGeoJson,
  type CmPortalProyectoProps,
} from "@/lib/cm-portal-geo";
import { bindMapHoverPopup } from "@/lib/map-hover-popup";

const POLYGON_STYLE: L.PathOptions = {
  color: "#6d28d9",
  weight: 1.5,
  fillColor: "#8b5cf6",
  fillOpacity: 0.22,
};

export function PortalProyectosPolygonLayer({
  geojson,
  visible,
}: {
  geojson: CmPortalGeoJson<CmPortalProyectoProps> | null;
  visible: boolean;
}) {
  const map = useMap();
  const layerRef = useRef<L.GeoJSON | null>(null);

  useEffect(() => {
    if (!visible || !geojson?.features?.length) {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
      return;
    }

    const layer = L.geoJSON(geojson as unknown as GeoJSON.FeatureCollection, {
      style: POLYGON_STYLE,
      onEachFeature(feature, lyr) {
        const p = feature.properties as CmPortalProyectoProps;
        bindMapHoverPopup(lyr, portalProyectoPopupHtml(p), { maxWidth: 300 });
      },
    });
    map.addLayer(layer);
    layerRef.current = layer;

    return () => {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
    };
  }, [geojson, map, visible]);

  return null;
}
