"use client";

import { useEffect, useRef, useState } from "react";
import { Map, LngLatBounds, NavigationControl, ScaleControl, AttributionControl, type GeoJSONSource } from "maplibre-gl";
import type { FeatureCollection, Geometry } from "geojson";
import "maplibre-gl/dist/maplibre-gl.css";
import { ensureMaplibreWorker } from "@/lib/maplibre-worker";
import { researchMapStyle } from "@/lib/research-map-style";
import type { SectorFeatureCollection } from "@/lib/sector-geo";

type Point = { lat: number; lng: number };
const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };
const NO_POINTS: Point[] = [];

function fitProject(map: Map, bounds: LngLatBounds) {
  map.fitBounds(bounds, { padding: 38, maxZoom: 15.5, pitch: 45, bearing: -12, duration: 0 });
  map.setZoom(Math.min(map.getZoom() + 0.6, 15.5));
}

export function ResearchTerritoryMap({ geo, points = NO_POINTS, location }: {
  geo: SectorFeatureCollection | null;
  points?: Point[];
  location: string;
}) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<Map | null>(null);
  const boundsRef = useRef<LngLatBounds | null>(null);
  const [loadGeneration, setLoadGeneration] = useState(0);
  const ready = loadGeneration > 0;
  const [flat, setFlat] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!container.current) return;
    ensureMaplibreWorker();
    let map: Map;
    try {
      map = new Map({
        container: container.current, style: researchMapStyle(), center: [-3.7, 40.45], zoom: 9,
        pitch: 45, bearing: -12, maxPitch: 60, renderWorldCopies: false, cooperativeGestures: true, attributionControl: false,
        locale: { "CooperativeGesturesHandler.WindowsHelpText": "Usa Ctrl + rueda para ampliar el mapa", "CooperativeGesturesHandler.MacHelpText": "Usa ⌘ + rueda para ampliar el mapa" },
      });
    } catch {
      queueMicrotask(() => setError(true));
      return;
    }
    mapRef.current = map;
    map.addControl(new NavigationControl({ visualizePitch: true }), "top-right");
    map.addControl(new ScaleControl({ unit: "metric" }), "bottom-left");
    map.addControl(new AttributionControl({ compact: true }), "bottom-right");
    map.on("load", () => {
      const attribution = map.getContainer().querySelector<HTMLDetailsElement>(".maplibregl-ctrl-attrib");
      attribution?.classList.remove("maplibregl-compact-show");
      attribution?.removeAttribute("open");
      const firstLabel = map.getStyle().layers.find(layer => layer.type === "symbol")?.id;
      map.addSource("research-project", { type: "geojson", data: EMPTY });
      map.addLayer({ id: "research-project-fill", type: "fill", source: "research-project", filter: ["==", ["geometry-type"], "Polygon"], paint: { "fill-color": "#b18448", "fill-opacity": 0.12 } }, firstLabel);
      map.addLayer({ id: "research-project-outline", type: "line", source: "research-project", filter: ["!=", ["geometry-type"], "Point"], paint: { "line-color": "#875634", "line-width": 2.5, "line-opacity": 0.95 } }, firstLabel);
      map.addLayer({ id: "research-project-point", type: "circle", source: "research-project", filter: ["==", ["geometry-type"], "Point"], paint: { "circle-radius": 7, "circle-color": "#245b43", "circle-stroke-color": "#fffaf0", "circle-stroke-width": 3 } });
      setLoadGeneration(generation => generation + 1);
    });
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(container.current);
    return () => { observer.disconnect(); mapRef.current = null; map.remove(); };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const source = map?.getSource("research-project") as GeoJSONSource | undefined;
    if (!map || !source) return;
    const data: FeatureCollection = geo?.features.length ? {
      type: "FeatureCollection",
      features: geo.features.filter(feature => feature.geometry && Array.isArray(feature.geometry.coordinates))
        .map(feature => ({ ...feature, properties: feature.properties ?? {}, geometry: feature.geometry as Geometry })),
    } : {
      type: "FeatureCollection",
      features: points.filter(p => Number.isFinite(p.lat) && Number.isFinite(p.lng)).map(p => ({ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: [p.lng, p.lat] } })),
    };
    source.setData(data);
    const bounds = new LngLatBounds();
    const visit = (coordinates: unknown): void => {
      if (!Array.isArray(coordinates)) return;
      if (typeof coordinates[0] === "number" && typeof coordinates[1] === "number") {
        if (Number.isFinite(coordinates[0]) && Number.isFinite(coordinates[1])) bounds.extend([coordinates[0], coordinates[1]]);
      } else coordinates.forEach(visit);
    };
    data.features.forEach(feature => { if (feature.geometry && "coordinates" in feature.geometry) visit(feature.geometry.coordinates); });
    if (bounds.isEmpty()) return;
    // Include neighbouring streets and settlements, rather than crop to the parcel.
    const center = bounds.getCenter();
    const dx = Math.max((bounds.getEast() - bounds.getWest()) * 0.65, 0.004);
    const dy = Math.max((bounds.getNorth() - bounds.getSouth()) * 0.65, 0.003);
    bounds.extend([center.lng - dx, center.lat - dy]);
    bounds.extend([center.lng + dx, center.lat + dy]);
    boundsRef.current = bounds;
    fitProject(map, bounds);
  }, [geo, points, loadGeneration]);

  const hasLocation = Boolean(geo?.features.length || points.length);
  return (
    <div className="research-territory-map" aria-label={`Mapa del proyecto y su entorno: ${location}`}>
      <div ref={container} className="research-map-canvas" />
      <div className="research-map-location"><span aria-hidden="true">◎</span><div><strong>{location}</strong><span>Ámbito y entorno</span></div></div>
      <div className="research-camera-controls">
        <button type="button" disabled={!ready} aria-pressed={!flat} onClick={() => { const next = !flat; setFlat(next); mapRef.current?.easeTo({ pitch: next ? 0 : 45, bearing: next ? 0 : -12, duration: matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 400 }); }}>{flat ? "Vista 3D" : "Vista 2D"}</button>
        <button type="button" disabled={!ready || !hasLocation} onClick={() => { if (boundsRef.current && mapRef.current) { setFlat(false); fitProject(mapRef.current, boundsRef.current); } }}>Centrar ámbito</button>
      </div>
      {error || !hasLocation ? <p className="research-map-message">{error ? "No se ha podido iniciar el mapa." : "Ubicación cartográfica no disponible."}</p> : null}
    </div>
  );
}
