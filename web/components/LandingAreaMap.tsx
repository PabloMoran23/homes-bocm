"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import "maplibre-gl/dist/maplibre-gl.css";
import { homesMasterplanStyle } from "@/lib/map-masterplan-style";
import { ensureMaplibreWorker } from "@/lib/maplibre-worker";

function area(radius: number): GeoJSON.Feature<GeoJSON.Polygon> {
  const center = [-3.7074, 40.4154];
  const coordinates = Array.from({ length: 65 }, (_, i) => {
    const angle = i / 64 * Math.PI * 2;
    return [center[0] + Math.cos(angle) * radius / (111320 * Math.cos(center[1] * Math.PI / 180)), center[1] + Math.sin(angle) * radius / 111320];
  });
  return { type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [coordinates] } };
}
export function LandingAreaMap() {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<import("maplibre-gl").Map | null>(null);
  const [radius, setRadius] = useState(500);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let disposed = false;
    let resize: ResizeObserver | undefined;
    const visibility = new IntersectionObserver(entries => {
      if (!entries.some(entry => entry.isIntersecting)) return;
      visibility.disconnect();
      void import("maplibre-gl").then(({ Map, Marker }) => {
        if (disposed || !container.current) return;
        ensureMaplibreWorker();
        const map = new Map({ container: container.current, style: homesMasterplanStyle(), center: [-3.7074, 40.4154], zoom: 14.4, interactive: false, attributionControl: false });
        mapRef.current = map;
        map.on("load", () => {
          map.addSource("area", { type: "geojson", data: area(500) });
          map.addLayer({ id: "area-fill", type: "fill", source: "area", paint: { "fill-color": "#1f4f53", "fill-opacity": .12 } });
          map.addLayer({ id: "area-line", type: "line", source: "area", paint: { "line-color": "#1f4f53", "line-width": 2, "line-dasharray": [3, 2] } });
          new Marker({ color: "#1f4f53" }).setLngLat([-3.7074, 40.4154]).addTo(map);
          setReady(true);
        });
        resize = new ResizeObserver(() => map.resize()); resize.observe(container.current);
      }).catch(() => { if (!disposed) setFailed(true); });
    }, { rootMargin: "200px" });
    if (container.current) visibility.observe(container.current);
    return () => { disposed = true; visibility.disconnect(); resize?.disconnect(); mapRef.current?.remove(); mapRef.current = null; };
  }, []);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    (map.getSource("area") as import("maplibre-gl").GeoJSONSource)?.setData(area(radius));
    map.jumpTo({ zoom: radius === 300 ? 15 : radius === 500 ? 14.4 : 13.7 });
  }, [radius, ready]);
  return <div className="landing-area-map">
    <div className="absolute inset-0" aria-hidden="true"><div ref={container} className="h-full w-full" /></div>
    {!ready && <p className="absolute left-5 top-24 text-sm text-slate-600" role="status">{failed ? "Mapa no disponible. Puedes abrir la consulta." : "Cargando cartografía…"}</p>}
    <div className="landing-area-toolbar"><span>Vista de consulta · Madrid</span><div role="group" aria-label="Radio de consulta">{[300, 500, 1000].map(value => <button type="button" key={value} aria-pressed={radius === value} onClick={() => setRadius(value)}>{value === 1000 ? "1 km" : `${value} m`}</button>)}</div></div>
    <Link className="landing-area-location" href="/boletin?q=Calle%20Mayor%2012%2C%20Madrid"><span><small>Dirección de ejemplo</small><strong>Calle Mayor, 12</strong><span>Consultar actividad alrededor</span></span><b aria-hidden>↗</b></Link>
    <span className="landing-area-attribution">© OpenStreetMap · © OpenMapTiles</span>
  </div>;
}
