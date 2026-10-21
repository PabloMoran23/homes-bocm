import type { StyleSpecification } from "maplibre-gl";
import { homesMasterplanStyle } from "./map-masterplan-style";

/** The Homes basemap, with geographic context kept legible around a project. */
export function researchMapStyle(): StyleSpecification {
  const style = homesMasterplanStyle();
  for (const layer of style.layers) {
    if (layer.id === "place-neighbourhood" && layer.type === "symbol") {
      layer.minzoom = 11;
      delete layer.maxzoom;
      layer.paint = { ...layer.paint, "text-opacity": 1, "text-color": "#40584a", "text-halo-width": 1.8 };
    }
  }
  style.layers.push(
    {
      id: "research-street-names", type: "symbol", source: "openmaptiles", "source-layer": "transportation_name", minzoom: 12,
      layout: {
        "symbol-placement": "line", "symbol-spacing": 180,
        "text-field": ["coalesce", ["get", "name:es"], ["get", "name"], ["get", "ref"]],
        "text-font": ["Noto Sans Regular"], "text-size": ["interpolate", ["linear"], ["zoom"], 12, 10, 16, 12],
        "text-max-angle": 30, "text-padding": 3,
      },
      paint: { "text-color": "#4b574c", "text-halo-color": "#faf7ef", "text-halo-width": 1.8 },
    },
    {
      id: "research-local-places", type: "symbol", source: "openmaptiles", "source-layer": "poi", minzoom: 14,
      filter: ["match", ["get", "class"], ["park", "school", "college", "hospital", "cemetery", "town_hall", "stadium"], true, false],
      layout: {
        "text-field": ["coalesce", ["get", "name:es"], ["get", "name"]], "text-font": ["Noto Sans Regular"],
        "text-size": 10, "text-max-width": 10, "text-padding": 8,
      },
      paint: { "text-color": "#526746", "text-halo-color": "#faf7ef", "text-halo-width": 1.5 },
    },
    {
      id: "research-town-names", type: "symbol", source: "openmaptiles", "source-layer": "place", minzoom: 7,
      filter: ["match", ["get", "class"], ["city", "town", "village", "hamlet"], true, false],
      layout: {
        "text-field": ["coalesce", ["get", "name:es"], ["get", "name"]], "text-font": ["Noto Sans Bold"],
        "text-size": ["interpolate", ["linear"], ["zoom"], 7, 12, 14, 16], "text-padding": 12,
      },
      paint: { "text-color": "#254c3b", "text-halo-color": "#faf7ef", "text-halo-width": 2 },
    },
  );
  return style;
}
