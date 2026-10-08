"use client";

import { useEffect, useRef } from "react";
import "maplibre-gl/dist/maplibre-gl.css";
import { homesMasterplanStyle } from "@/lib/map-masterplan-style";
import { ensureMaplibreWorker } from "@/lib/maplibre-worker";

export function LandingMapBackground() {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let disposed = false;
    let map: import("maplibre-gl").Map | undefined;
    let observer: ResizeObserver | undefined;
    void import("maplibre-gl").then(({ Map }) => {
      if (disposed || !container.current) return;
      ensureMaplibreWorker();
      map = new Map({ container: container.current, style: homesMasterplanStyle(), center: [-3.695, 40.425], zoom: 12, interactive: false, attributionControl: false, fadeDuration: 0 });
      observer = new ResizeObserver(() => map?.resize());
      observer.observe(container.current);
    });
    return () => { disposed = true; observer?.disconnect(); map?.remove(); };
  }, []);
  return <div ref={container} className="h-full w-full" />;
}
