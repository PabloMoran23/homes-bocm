"use client";

import {
  createElementObject,
  createTileLayerComponent,
  withPane,
} from "@react-leaflet/core";
import L from "leaflet";
import "maplibre-gl/dist/maplibre-gl.css";
import "@maplibre/maplibre-gl-leaflet";
import { homesMasterplanStyle } from "@/lib/map-masterplan-style";
import { attachMasterplanStipple } from "@/lib/map-stipple";
import { ensureMaplibreWorker } from "@/lib/maplibre-worker";
import { HOMES_MAP_ATTRIBUTION, HOMES_MAP_MAX_ZOOM, HOMES_MAP_MIN_ZOOM } from "@/lib/map-tiles";

ensureMaplibreWorker();

function scheduleGlResize(gl: { resize: () => void }) {
  const run = () => gl.resize();
  run();
  const t1 = window.setTimeout(run, 80);
  const t2 = window.setTimeout(run, 400);
  return () => {
    window.clearTimeout(t1);
    window.clearTimeout(t2);
  };
}

/**
 * Basemap vectorial tipo plano arquitectónico (OpenFreeMap + estilo propio).
 * Se pinta en el tile pane de Leaflet; polígonos y markers siguen encima.
 */
export const HomesBasemapLayer = createTileLayerComponent(function createHomesBasemap(
  _props,
  context,
) {
  ensureMaplibreWorker();
  const layer = L.maplibreGL({
    style: homesMasterplanStyle(),
    attributionControl: false,
    interactive: false,
    fadeDuration: 0,
    minZoom: HOMES_MAP_MIN_ZOOM,
    maxZoom: HOMES_MAP_MAX_ZOOM,
    ...withPane({}, context),
  });
  layer.getAttribution = () => HOMES_MAP_ATTRIBUTION;

  let cancelResize: (() => void) | undefined;
  layer.once("add", () => {
    const gl = layer.getMaplibreMap();
    if (!gl) return;
    gl.on("error", (ev) => {
      const err = "error" in ev ? ev.error : ev;
      console.warn("[homes-map] MapLibre", err);
    });
    attachMasterplanStipple(gl);
    cancelResize = scheduleGlResize(gl);
  });
  layer.once("remove", () => cancelResize?.());

  return createElementObject(layer, context);
});
