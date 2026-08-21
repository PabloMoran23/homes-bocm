"use client";

import { useEffect, useMemo, useRef } from "react";
import { useMap } from "react-leaflet";
import type { Feature } from "geojson";
import { HomesFocusMask } from "@/components/map/homes-focus-mask-layer";
import { focusKeyForFeatures, polygonFeaturesOf } from "@/lib/map-focus-mask";

export function ProjectFocusMaskLayer({
  features,
  active = true,
  fadeMs = 420,
}: {
  features?: Feature[] | null;
  active?: boolean;
  fadeMs?: number;
}) {
  const map = useMap();
  const layerRef = useRef<HomesFocusMask | null>(null);
  const polygons = useMemo(() => polygonFeaturesOf(features), [features]);
  const polygonsRef = useRef(polygons);
  polygonsRef.current = polygons;
  const key = active && polygons.length > 0 ? focusKeyForFeatures(polygons) : "";

  useEffect(() => {
    const layer = new HomesFocusMask();
    layer.addTo(map);
    layerRef.current = layer;
    return () => {
      map.removeLayer(layer);
      layerRef.current = null;
    };
  }, [map]);

  useEffect(() => {
    const layer = layerRef.current;
    if (!layer) return;
    if (key) {
      layer.setFeatures(polygonsRef.current);
      layer.animateProgress(1, fadeMs);
    } else {
      layer.animateProgress(0, fadeMs);
    }
  }, [key, fadeMs]);

  return null;
}
