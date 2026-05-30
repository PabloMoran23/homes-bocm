"use client";

import { useEffect, useState } from "react";

/** Leaflet canvas renderer suele ir mejor con muchos polígonos en móvil. */
export function usePreferCanvas(): boolean {
  const [preferCanvas, setPreferCanvas] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 768px)");
    const update = () => setPreferCanvas(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  return preferCanvas;
}
