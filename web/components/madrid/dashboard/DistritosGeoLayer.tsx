"use client";

import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import type { PathOptions } from "leaflet";
import { fmtChart } from "@/lib/dashboard-chart-theme";
import {
  distritoFillColor,
  distritoStrokeColor,
  type MadridDistritoGeoProperties,
} from "@/lib/distrito-choropleth";
import { formatDistritoLabel } from "@/lib/madrid-distrito";

export function DistritosGeoLayer({
  geojson,
  countByKey,
  quantileBreaks,
  valueLabel,
}: {
  geojson: GeoJSON.FeatureCollection;
  countByKey: Map<string, number>;
  quantileBreaks: number[];
  valueLabel: string;
}) {
  const map = useMap();
  const layerRef = useRef<L.GeoJSON | null>(null);

  useEffect(() => {
    if (!geojson?.features?.length) return;

    const layer = L.geoJSON(geojson, {
      style(feature) {
        const props = feature?.properties as MadridDistritoGeoProperties | undefined;
        const key = props?.distrito_key ?? "";
        const count = countByKey.get(key) ?? 0;
        return {
          color: distritoStrokeColor(count, quantileBreaks),
          weight: count > 0 ? 2 : 1,
          fillColor: distritoFillColor(count, quantileBreaks),
          fillOpacity: 0.88,
        } as PathOptions;
      },
      onEachFeature(feature, lyr) {
        const props = feature.properties as MadridDistritoGeoProperties;
        const key = props?.distrito_key ?? "";
        const count = countByKey.get(key) ?? 0;
        const label = formatDistritoLabel(props?.nombre ?? key);
        lyr.bindTooltip(
          `<span class="font-medium">${label}</span><br/><span class="tabular-nums">${fmtChart(count)} ${valueLabel}</span>`,
          { sticky: true, opacity: 0.95 },
        );
        lyr.bindPopup(
          `<p class="font-semibold text-slate-900">${label}</p><p class="mt-1 text-sm tabular-nums text-slate-600">${fmtChart(count)} ${valueLabel}</p>`,
        );
      },
    });

    layer.addTo(map);
    layerRef.current = layer;

    return () => {
      map.removeLayer(layer);
      layerRef.current = null;
    };
  }, [map, geojson, countByKey, quantileBreaks, valueLabel]);

  return null;
}
