"use client";

import { useEffect } from "react";
import { useMap } from "react-leaflet";

/** Leaflet necesita invalidateSize cuando el contenedor obtiene altura real. */
export function MapSizeFix() {
  const map = useMap();
  useEffect(() => {
    const fit = () => map.invalidateSize({ animate: false });
    fit();
    const t1 = window.setTimeout(fit, 80);
    const t2 = window.setTimeout(fit, 400);
    const parent = map.getContainer().parentElement;
    let ro: ResizeObserver | null = null;
    if (parent && typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(() => fit());
      ro.observe(parent);
    }
    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
      ro?.disconnect();
    };
  }, [map]);
  return null;
}
