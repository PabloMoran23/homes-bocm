import type L from "leaflet";

export type MapSpotlightPlacement = "top-left" | "top-right" | "bottom-left" | "bottom-right";

const CARD_W = 236;
const CARD_H = 210;
const BASE_PAD = 36;

/** Coloca la tarjeta en el cuadrante opuesto al centro del polígono. */
export function pickMapSpotlightPlacement(
  x: number,
  y: number,
  width: number,
  height: number,
): MapSpotlightPlacement {
  if (width <= 0 || height <= 0) return "bottom-left";
  const nx = x / width;
  const ny = y / height;
  const vertical = ny > 0.5 ? "top" : "bottom";
  const horizontal = nx > 0.5 ? "left" : "right";
  return `${vertical}-${horizontal}` as MapSpotlightPlacement;
}

export function placementFromLatLng(
  map: L.Map,
  center: [number, number],
): MapSpotlightPlacement {
  const el = map.getContainer();
  const w = el?.clientWidth ?? 400;
  const h = el?.clientHeight ?? 300;
  const pt = map.latLngToContainerPoint([center[0], center[1]]);
  return pickMapSpotlightPlacement(pt.x, pt.y, w, h);
}

/** Reserva espacio en el encuadre para que el polígono no quede bajo la tarjeta. */
export function fitBoundsPaddingForPlacement(placement: MapSpotlightPlacement): {
  top: number;
  right: number;
  bottom: number;
  left: number;
} {
  const edge = 14;
  return {
    top: placement.startsWith("top") ? CARD_H + edge : BASE_PAD,
    right: placement.endsWith("right") ? CARD_W + edge : BASE_PAD,
    bottom: placement.startsWith("bottom") ? CARD_H + edge : BASE_PAD,
    left: placement.endsWith("left") ? CARD_W + edge : BASE_PAD,
  };
}

/** Estima placement tras encuadrar (sin animación) para reservar padding antes del vuelo. */
export function estimatePlacementForBounds(
  map: L.Map,
  bounds: L.LatLngBounds,
  center: [number, number],
): MapSpotlightPlacement {
  const prevCenter = map.getCenter();
  const prevZoom = map.getZoom();
  map.fitBounds(bounds, { padding: [BASE_PAD, BASE_PAD], animate: false });
  const placement = placementFromLatLng(map, center);
  map.setView(prevCenter, prevZoom, { animate: false });
  return placement;
}

export const MAP_SPOTLIGHT_PLACEMENT_CLASS: Record<
  MapSpotlightPlacement,
  { position: string; hidden: string; visible: string }
> = {
  "top-left": {
    position: "top-3 left-3 sm:top-4 sm:left-4",
    hidden: "-translate-x-3 -translate-y-3 opacity-0",
    visible: "translate-x-0 translate-y-0 opacity-100",
  },
  "top-right": {
    position: "top-3 right-3 sm:top-4 sm:right-4",
    hidden: "translate-x-3 -translate-y-3 opacity-0",
    visible: "translate-x-0 translate-y-0 opacity-100",
  },
  "bottom-left": {
    position: "bottom-3 left-3 sm:bottom-4 sm:left-4",
    hidden: "-translate-x-3 translate-y-3 opacity-0",
    visible: "translate-x-0 translate-y-0 opacity-100",
  },
  "bottom-right": {
    position: "bottom-3 right-3 sm:bottom-14 sm:right-4",
    hidden: "translate-x-3 translate-y-3 opacity-0",
    visible: "translate-x-0 translate-y-0 opacity-100",
  },
};
