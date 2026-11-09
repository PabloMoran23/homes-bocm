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

  // The Leaflet adapter schedules an untracked resize frame. Route navigation can
  // remove the layer before that frame runs, leaving its internal map null.
  const transitionLayer = layer as unknown as { _map?: L.Map; _transitionEnd: () => void; _resizeContainer: () => void; _zoomEnd: () => void };
  let resizeFrame: number | null = null;
  transitionLayer._transitionEnd = () => {
    if (resizeFrame != null) L.Util.cancelAnimFrame(resizeFrame);
    resizeFrame = L.Util.requestAnimFrame(() => {
      resizeFrame = null;
      const map = transitionLayer._map, gl = layer.getMaplibreMap();
      if (!map || !gl) return;
      const zoom = map.getZoom(), center = map.getCenter();
      const offset = map.latLngToContainerPoint(map.getBounds().getNorthWest());
      transitionLayer._resizeContainer();
      L.DomUtil.setTransform(gl.getCanvas(), offset, 1);
      gl.once("moveend", () => { if (transitionLayer._map && layer.getMaplibreMap() === gl) transitionLayer._zoomEnd(); });
      gl.jumpTo({ center:[center.lng,center.lat], zoom:zoom - 1 });
    });
  };


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
  layer.once("remove", () => {
    cancelResize?.();
    if (resizeFrame != null) L.Util.cancelAnimFrame(resizeFrame);
    resizeFrame = null;
  });

  return createElementObject(layer, context);
});
