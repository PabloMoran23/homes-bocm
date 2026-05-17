"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Retrasa el montaje de MapContainer hasta el cliente y asigna una key única
 * por ciclo de vida (evita "Map container is being reused" con Strict Mode).
 */
export function useLeafletMount() {
  const [ready, setReady] = useState(false);
  const mapKeyRef = useRef(0);

  useEffect(() => {
    mapKeyRef.current += 1;
    setReady(true);
    return () => setReady(false);
  }, []);

  return { ready, mapKey: `leaflet-${mapKeyRef.current}` };
}
