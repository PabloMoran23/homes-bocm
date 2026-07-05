"use client";

import { useEffect } from "react";
import { useMap } from "react-leaflet";

/** Cierra la selección al pulsar el mapa fuera de un polígono. */
export function MapSelectionClearLayer({ onClear }: { onClear: () => void }) {
  const map = useMap();

  useEffect(() => {
    const handler = () => onClear();
    map.on("click", handler);
    return () => {
      map.off("click", handler);
    };
  }, [map, onClear]);

  return null;
}
