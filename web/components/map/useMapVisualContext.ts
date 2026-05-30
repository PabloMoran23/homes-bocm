"use client";

import { useEffect, useState } from "react";
import { useMap } from "react-leaflet";
import { readMapVisualContext, type MapVisualContext } from "@/lib/map-visual-scale";

/** Reacciona a zoom, movimiento y tamaño del contenedor del mapa. */
export function useMapVisualContext(): MapVisualContext {
  const map = useMap();
  const [ctx, setCtx] = useState<MapVisualContext>(() => readMapVisualContext(map));

  useEffect(() => {
    const update = () => setCtx(readMapVisualContext(map));
    update();
    map.on("zoomend", update);
    map.on("moveend", update);
    map.on("resize", update);
    const el = map.getContainer();
    let ro: ResizeObserver | null = null;
    if (el && typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(update);
      ro.observe(el);
    }
    return () => {
      map.off("zoomend", update);
      map.off("moveend", update);
      map.off("resize", update);
      ro?.disconnect();
    };
  }, [map]);

  return ctx;
}
