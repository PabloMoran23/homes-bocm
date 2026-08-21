"use client";

import { useMemo } from "react";
import { GeoJSON, useMap } from "react-leaflet";
import L from "leaflet";
import type { PathOptions } from "leaflet";
import {
  clasificarLicenciaMapa,
  createLicenciaDivIcon,
} from "@/lib/licencia-mapa";
import {
  featureLayerStyle,
  featurePointStyle,
  featurePopupHtml,
  isLicenciaFeature,
  isSigmaFeature,
  shouldShowSigmaFeature,
  type FeaturePopupOptions,
  type SectorFeatureCollection,
  type SectorFeatureProperties,
} from "@/lib/sector-geo";
import { bindMapHoverPopup } from "@/lib/map-hover-popup";
import { useMapVisualContext } from "@/components/map/useMapVisualContext";

const FOCUS_HITAREA: PathOptions = {
  stroke: false,
  fill: true,
  fillOpacity: 0.01,
  fillColor: "#ffffff",
  opacity: 0,
  weight: 0,
};

export function SectorFeaturesGeoLayer({
  geojson,
  popupOptions,
  layerKey,
  appearance = "default",
}: {
  geojson: SectorFeatureCollection;
  popupOptions?: FeaturePopupOptions | null;
  layerKey: string;
  /** `focus`: el velo pinta el borde; esta capa solo sirve de hit-area. */
  appearance?: "default" | "focus";
}) {
  const map = useMap();
  const visual = useMapVisualContext();

  const filtered = useMemo(() => {
    const features = geojson.features.filter((f) =>
      shouldShowSigmaFeature(map, f as GeoJSON.Feature, visual),
    );
    return { type: "FeatureCollection" as const, features };
  }, [geojson, map, visual.zoom, visual.containerWidth, visual.containerHeight]);

  const dataKey = `${layerKey}-${appearance}-z${visual.zoom}-w${visual.containerWidth}`;

  return (
    <GeoJSON
      key={dataKey}
      data={filtered as never}
      style={(feature) => {
        if (appearance === "focus") return FOCUS_HITAREA;
        const props = feature?.properties as SectorFeatureProperties | undefined;
        return featureLayerStyle(props, visual) as PathOptions;
      }}
      pointToLayer={(feature, latlng) => {
        const props = feature?.properties as SectorFeatureProperties | undefined;
        if (isLicenciaFeature(props)) {
          const cat = clasificarLicenciaMapa(props?.tipo_expediente);
          return L.marker(latlng, { icon: createLicenciaDivIcon(cat, false) });
        }
        return L.circleMarker(latlng, featurePointStyle(props, visual) as PathOptions);
      }}
      onEachFeature={(feature, layer) => {
        const props = feature.properties as SectorFeatureProperties | undefined;
        const pop = featurePopupHtml(props, popupOptions ?? undefined);
        bindMapHoverPopup(layer, pop, {
          className: isSigmaFeature(props)
            ? "homes-map-popup homes-map-popup-sigma"
            : "homes-map-popup",
          maxWidth: isSigmaFeature(props) ? 360 : 320,
        });
      }}
    />
  );
}
