"use client";

import { useEffect, useRef } from "react";
import { useMap, useMapEvents } from "react-leaflet";
import type { MapBounds } from "@/lib/map-viewport";
import { boundsFromLeaflet } from "@/lib/map-viewport";

export function MapBoundsReporter({
  onBoundsChange,
}: {
  onBoundsChange: (bounds: MapBounds) => void;
}) {
  const map = useMap();
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const emit = () => {
    onBoundsChange(boundsFromLeaflet(map.getBounds()));
  };

  useMapEvents({
    moveend: () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(emit, 80);
    },
    zoomend: () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(emit, 80);
    },
  });

  useEffect(() => {
    const onReady = () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(emit, 120);
    };
    map.whenReady(onReady);
    const t = window.setTimeout(onReady, 450);
    return () => {
      window.clearTimeout(t);
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [map, onBoundsChange]);

  return null;
}
