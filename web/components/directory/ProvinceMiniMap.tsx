"use client";

import { useEffect, useRef, useState } from "react";
import { homesMasterplanStyle } from "@/lib/map-masterplan-style";
import styles from "./ProvinceAtlas.module.css";

// Render previews in sequence and release WebGL immediately after each snapshot.
// A page of provinces must not keep dozens of map instances alive.
let renderQueue = Promise.resolve();
export default function ProvinceMiniMap({
  centers,
}: {
  centers: [number, number][];
}) {
  const host = useRef<HTMLDivElement>(null);
  const [snapshot, setSnapshot] = useState<string>();
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let disposed = false;
    let cancel: (() => void) | undefined;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        observer.disconnect();
        renderQueue = renderQueue
          .then(async () => {
            if (disposed || !host.current) return;
            const ml = await import("maplibre-gl");
            if (disposed || !host.current) return;
            ml.setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");
            await new Promise<void>((resolve) => {
              const map = new ml.Map({
                container: host.current!,
                style: homesMasterplanStyle(),
                center: centers[0],
                zoom: 9,
                interactive: false,
                attributionControl: false,
                canvasContextAttributes: { preserveDrawingBuffer: true },
                fadeDuration: 0,
              });
              let finished = false;
              const finish = (success: boolean) => {
                if (finished) return;
                finished = true;
                clearTimeout(timer);
                if (!disposed) {
                  if (success) {
                    try {
                      setSnapshot(map.getCanvas().toDataURL("image/png"));
                    } catch {
                      setFailed(true);
                    }
                  } else setFailed(true);
                }
                map.remove();
                resolve();
              };
              const timer = setTimeout(() => finish(false), 12000);
              cancel = () => finish(false);
              if (centers.length > 1) {
                const bounds = new ml.LngLatBounds();
                centers.forEach((center) => bounds.extend(center));
                map.fitBounds(bounds, { padding: 16, maxZoom: 9, duration: 0 });
              }
              map.once("load", () => {
                map.addSource("municipalities", {
                  type: "geojson",
                  data: {
                    type: "FeatureCollection",
                    features: centers.map((center) => ({
                      type: "Feature",
                      properties: {},
                      geometry: { type: "Point", coordinates: center },
                    })),
                  },
                });
                map.addLayer({
                  id: "municipalities",
                  type: "circle",
                  source: "municipalities",
                  paint: {
                    "circle-radius": 3,
                    "circle-color": "#1f4f53",
                    "circle-stroke-width": 1,
                    "circle-stroke-color": "#faf7ef",
                  },
                });
                map.once("idle", () => finish(true));
              });
            });
          })
          .catch(() => {
            if (!disposed) setFailed(true);
          });
      },
      { rootMargin: "200px" },
    );
    if (host.current) observer.observe(host.current);
    return () => {
      disposed = true;
      observer.disconnect();
      cancel?.();
    };
  }, [centers]);
  return (
    <div className={styles.miniMap} aria-hidden="true">
      <div ref={host} className={styles.mapHost} />
      {/* Browser-generated cartographic preview, not a remotely optimized image. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {snapshot && <img src={snapshot} alt="" />}
      {!snapshot && (
        <span className={styles.mapState}>
          {failed ? "Mapa no disponible" : "Cargando mapa…"}
        </span>
      )}
    </div>
  );
}
