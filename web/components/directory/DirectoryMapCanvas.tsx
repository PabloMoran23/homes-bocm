"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import "maplibre-gl/dist/maplibre-gl.css";
import { homesMasterplanStyle } from "@/lib/map-masterplan-style";
import type { DirectoryMapProps } from "./DirectoryMap";
import styles from "./Directory.module.css";

export default function DirectoryMapCanvas({
  points,
  label,
  local,
}: DirectoryMapProps) {
  const element = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const router = useRouter();

  useEffect(() => {
    let disposed = false;
    let map: import("maplibre-gl").Map | undefined;
    let resize: ResizeObserver | undefined;
    const timeout = window.setTimeout(
      () => setState((s) => (s === "loading" ? "error" : s)),
      15000,
    );
    async function create() {
      try {
        const ml = await import("maplibre-gl");
        if (disposed || !element.current || !points.length) return;
        ml.setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");
        map = new ml.Map({
          container: element.current,
          style: homesMasterplanStyle(),
          center: points[0].center,
          zoom: local ? 12 : 5,
          attributionControl: { compact: true },
          scrollZoom: false,
          cooperativeGestures: true,
          dragRotate: false,
          pitchWithRotate: false,
        });
        map.touchZoomRotate.disableRotation();
        map.addControl(
          new ml.NavigationControl({ showCompass: false }),
          "top-right",
        );
        if (!local && points.length > 1) {
          const bounds = new ml.LngLatBounds();
          points.forEach((p) => bounds.extend(p.center));
          map.fitBounds(bounds, {
            padding: { top: 65, bottom: 65, left: 40, right: 40 },
            maxZoom: 10,
            duration: 0,
          });
        }
        map.on("load", () => {
          if (disposed || !map) return;
          map.addSource("directory-places", {
            type: "geojson",
            data: {
              type: "FeatureCollection",
              features: points.map((p) => ({
                type: "Feature",
                geometry: { type: "Point", coordinates: p.center },
                properties: { name: p.name, href: p.href ?? "" },
              })),
            },
          });
          map.addLayer({
            id: "directory-halos",
            type: "circle",
            source: "directory-places",
            paint: {
              "circle-radius": local ? 24 : 9,
              "circle-color": "#1f4f53",
              "circle-opacity": 0.1,
            },
          });
          map.addLayer({
            id: "directory-points",
            type: "circle",
            source: "directory-places",
            paint: {
              "circle-radius": local ? 7 : 4,
              "circle-color": "#1f4f53",
              "circle-stroke-width": 2,
              "circle-stroke-color": "#fffaf0",
            },
          });
          map.addLayer({
            id: "directory-labels",
            type: "symbol",
            source: "directory-places",
            minzoom: local ? 0 : 7,
            layout: {
              "text-field": ["get", "name"],
              "text-font": ["Noto Sans Regular"],
              "text-size": 12,
              "text-anchor": "top",
              "text-offset": [0, 1.2],
            },
            paint: {
              "text-color": "#1f4f53",
              "text-halo-color": "#faf7ef",
              "text-halo-width": 2,
            },
          });
          if (!local) {
            map.on("mouseenter", "directory-points", () => {
              if (map) map.getCanvas().style.cursor = "pointer";
            });
            map.on("mouseleave", "directory-points", () => {
              if (map) map.getCanvas().style.cursor = "";
            });
            map.on("click", "directory-points", (event) => {
              const href = event.features?.[0]?.properties?.href;
              if (typeof href === "string" && href.startsWith("/proyectos/"))
                router.push(href);
            });
          }
          window.clearTimeout(timeout);
          setState("ready");
        });
        resize = new ResizeObserver(() => map?.resize());
        resize.observe(element.current);
      } catch {
        if (!disposed) setState("error");
      }
    }
    void create();
    return () => {
      disposed = true;
      window.clearTimeout(timeout);
      resize?.disconnect();
      map?.remove();
    };
  }, [points, local, router]);

  return (
    <>
      <div
        ref={element}
        className={styles.mapCanvas}
        role="region"
        aria-label={`Mapa: ${label}`}
      />
      {state !== "ready" ? (
        <div className={styles.mapLoading} role="status">
          {state === "error"
            ? "El mapa no está disponible. Puedes continuar con el listado."
            : "Cargando cartografía…"}
        </div>
      ) : null}
    </>
  );
}
