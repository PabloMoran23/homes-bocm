import L from "leaflet";
import type { GeoJSON } from "geojson";

/** Contexto visual del mapa (zoom + tamaño del contenedor). */
export type MapVisualContext = {
  zoom: number;
  containerWidth: number;
  containerHeight: number;
};

export function readMapContainerSize(map: L.Map): { width: number; height: number } {
  const el = map.getContainer();
  return {
    width: el?.clientWidth ?? 400,
    height: el?.clientHeight ?? 300,
  };
}

export function readMapVisualContext(map: L.Map): MapVisualContext {
  const { width, height } = readMapContainerSize(map);
  return {
    zoom: map.getZoom(),
    containerWidth: width,
    containerHeight: height,
  };
}

/** Panel estrecho o bajo (móvil): un poco más de zoom permitido. */
function smallMapBoost(width: number, height: number): number {
  if (width < 400 || height < 260) return 0.15;
  if (width < 640) return 0.10;
  return 0;
}

/**
 * Techo de zoom según tamaño del panel (ajuste sutil).
 * En pantalla pequeña permite +0,5 / +1 nivel respecto al base.
 */
export function capZoomForContainer(
  baseMaxZoom: number,
  width: number,
  height = 400,
  minZoom = 10,
): number {
  const cap = baseMaxZoom + smallMapBoost(width, height);
  return Math.max(minZoom, Math.min(19, Math.round(cap)));
}

/** Zoom fijo inicial (portada / explorar): mismo criterio sutil. */
export function fixedZoomForContainer(
  baseZoom: number,
  width: number,
  height = 400,
): number {
  return capZoomForContainer(baseZoom, width, height, 9);
}

/** Encuadre fitBounds: en panel pequeño un poco más cerrado (= algo más de zoom). */
export function boundsScaleForContainer(
  baseScale: number,
  width: number,
  height = 400,
): number {
  let s = baseScale;
  if (width < 400 || height < 260) s *= 0.97;
  else if (width < 640) s *= 0.99;
  return s;
}

/** Multiplicador de grosor: pantallas estrechas y zoom alto → trazo un poco más fino. */
export function mapStrokeScale(ctx: MapVisualContext): number {
  let s = 1;
  if (ctx.containerWidth < 480) s *= 0.9;
  else if (ctx.containerWidth < 768) s *= 0.95;
  else if (ctx.containerWidth < 1024) s *= 0.98;
  if (ctx.zoom >= 17) s *= 0.96;
  if (ctx.zoom >= 18) s *= 0.93;
  return Math.max(0.72, s);
}

export function scaledWeight(base: number, ctx: MapVisualContext): number {
  return Math.max(0.5, Math.round(base * mapStrokeScale(ctx) * 10) / 10);
}

export function scaledRadius(base: number, ctx: MapVisualContext): number {
  return Math.max(3, Math.round(base * mapStrokeScale(ctx)));
}

/** Área mínima en px² del bbox para ocultar polígonos SIGMA diminutos. */
export function minSigmaPixelArea(
  ctx: MapVisualContext,
  opts?: { preview?: boolean },
): number {
  if (opts?.preview) {
    if (ctx.containerWidth < 400) return 12;
    if (ctx.containerWidth < 640) return 8;
    return 5;
  }
  if (ctx.zoom < 16) return 0;
  if (ctx.zoom < 17) return 24;
  if (ctx.zoom < 18) return 40;
  return 52;
}

function metersPerPixel(map: L.Map, lat: number): number {
  const c = map.getCenter();
  const a = map.latLngToContainerPoint(L.latLng(lat, c.lng));
  const b = map.latLngToContainerPoint(L.latLng(lat, c.lng + 0.001));
  const px = Math.max(1, Math.abs(b.x - a.x));
  const meters = 111320 * Math.cos((lat * Math.PI) / 180) * 0.001;
  return meters / px;
}

/** Aproximación del área del bbox de la geometría en píxeles de pantalla. */
export function geometryPixelBBoxArea(
  map: L.Map,
  geometry: GeoJSON.Geometry | null | undefined,
): number {
  if (!geometry) return Infinity;
  try {
    const layer = L.geoJSON({
      type: "Feature",
      geometry,
      properties: {},
    } as GeoJSON.Feature);
    const bounds = layer.getBounds();
    if (!bounds.isValid()) return 0;
    const center = bounds.getCenter();
    const mpp = metersPerPixel(map, center.lat);
    const latM = Math.abs(bounds.getNorth() - bounds.getSouth()) * 111320;
    const lngM =
      Math.abs(bounds.getEast() - bounds.getWest()) *
      111320 *
      Math.cos((center.lat * Math.PI) / 180);
    return (latM * lngM) / (mpp * mpp);
  } catch {
    return Infinity;
  }
}

export function scalePathStyle(
  style: Record<string, unknown>,
  visual: MapVisualContext | null | undefined,
): Record<string, unknown> {
  if (!visual) return style;
  const out = { ...style };
  if (typeof out.weight === "number") {
    out.weight = scaledWeight(out.weight, visual);
  }
  if (typeof out.radius === "number") {
    out.radius = scaledRadius(out.radius, visual);
  }
  return out;
}
