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
  color: "#1f4f53",
  weight: 2,
  fillColor: "#1f4f53",
  fillOpacity: 0.28,
};

const INVESTIGADO_PANE = "portalInvestigado";

const INVESTIGADO_STYLE: L.PathOptions = {
  color: "#9a3412",
  weight: 3,
  fillColor: "#ea580c",
  fillOpacity: 0.45,
  pane: INVESTIGADO_PANE,
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

    const polygons = {
      ...geojson,
      features: geojson.features
        .filter((feature) => {
          const type = feature.geometry?.type;
          return type === "Polygon" || type === "MultiPolygon";
        })
        .sort((a, b) => Number(Boolean(a.properties?.investigado)) - Number(Boolean(b.properties?.investigado))),
    };
    if (!polygons.features.length) {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
      return;
    }
    if (!map.getPane(INVESTIGADO_PANE)) {
      const pane = map.createPane(INVESTIGADO_PANE);
      pane.style.zIndex = "450";
    }
    const layer = L.geoJSON(polygons as unknown as GeoJSON.FeatureCollection, {
      style: (feature) =>
        (feature?.properties as CmPortalProyectoProps | undefined)?.investigado
          ? INVESTIGADO_STYLE
          : POLYGON_STYLE,
      onEachFeature(feature, lyr) {
        const p = feature.properties as CmPortalProyectoProps;
        bindMapHoverPopup(lyr, portalProyectoPopupHtml(p), { maxWidth: 300 });
      },
    });
    map.addLayer(layer);
    layer.eachLayer((lyr) => {
      const props = (lyr as L.GeoJSON & { feature?: GeoJSON.Feature }).feature?.properties as
        | CmPortalProyectoProps
        | undefined;
      if (props?.investigado && "bringToFront" in lyr) {
        (lyr as L.Path).bringToFront();
      }
    });
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
