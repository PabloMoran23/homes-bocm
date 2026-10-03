"use client";

import { useCallback, useEffect, useRef } from "react";
import { useMap, useMapEvents } from "react-leaflet";
import type { MapBounds } from "@/lib/map-viewport";
import { boundsFromLeaflet } from "@/lib/map-viewport";

export function MapBoundsReporter({
  onBoundsChange,
}: {
  onBoundsChange: (bounds: MapBounds) => void;
}) {
  const map = useMap();

  const lastBounds = useRef("");
  const emit = useCallback(() => {
    const bounds = { ...boundsFromLeaflet(map.getBounds()), zoom: map.getZoom() };
    const key = JSON.stringify(bounds);
    if (key === lastBounds.current) return;
    lastBounds.current = key;
    onBoundsChange(bounds);
  }, [map, onBoundsChange]);

  useMapEvents({ moveend: emit, zoomend: emit });

  useEffect(() => {
    map.whenReady(emit);
    return () => { map.off("load", emit); };
  }, [map, emit]);

  return null;
}
