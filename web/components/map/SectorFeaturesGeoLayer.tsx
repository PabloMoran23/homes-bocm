"use client";

import { useMemo } from "react";
import { GeoJSON } from "react-leaflet";
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
import { useMapVisualContext } from "@/components/map/useMapVisualContext";
import { useMap } from "react-leaflet";

export function SectorFeaturesGeoLayer({
  geojson,
  popupOptions,
  layerKey,
}: {
  geojson: SectorFeatureCollection;
  popupOptions?: FeaturePopupOptions | null;
  layerKey: string;
}) {
  const map = useMap();
  const visual = useMapVisualContext();

  const filtered = useMemo(() => {
    const features = geojson.features.filter((f) =>
      shouldShowSigmaFeature(map, f as GeoJSON.Feature, visual),
    );
    return { type: "FeatureCollection" as const, features };
  }, [geojson, map, visual.zoom, visual.containerWidth, visual.containerHeight]);

  const dataKey = `${layerKey}-z${visual.zoom}-w${visual.containerWidth}`;

  return (
    <GeoJSON
      key={dataKey}
      data={filtered as never}
      style={(feature) => {
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
        layer.bindPopup(pop, {
          className: isSigmaFeature(props)
            ? "homes-map-popup homes-map-popup-sigma"
            : "homes-map-popup",
          maxWidth: isSigmaFeature(props) ? 360 : 320,
        });
      }}
    />
  );
}
