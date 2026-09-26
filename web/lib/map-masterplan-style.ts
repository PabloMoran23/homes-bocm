import type { FilterSpecification, StyleSpecification } from "maplibre-gl";
import { MASTERPLAN as C } from "@/lib/map-masterplan-palette";

const OMT = "openmaptiles";

function roadFilter(...classes: string[]): FilterSpecification {
  return [
    "all",
    ["!=", ["get", "brunnel"], "tunnel"],
    ["match", ["get", "class"], classes, true, false],
  ] as FilterSpecification;
}

/**
 * Estilo MapLibre (schema OpenMapTiles / teselas OpenFreeMap).
 * Pensado para leerse como plano de urbanismo, no como mapa de calles.
 */
export function homesMasterplanStyle(): StyleSpecification {
  return {
    version: 8,
    name: "homes-masterplan",
    sources: {
      openmaptiles: {
        type: "vector",
        url: "https://tiles.openfreemap.org/planet",
      },
    },
    glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
    layers: [
      {
        id: "background",
        type: "background",
        paint: { "background-color": C.paper },
      },
      {
        id: "landuse-residential",
        type: "fill",
        source: OMT,
        "source-layer": "landuse",
        filter: ["==", ["get", "class"], "residential"],
        paint: {
          "fill-color": C.paperUrban,
          "fill-opacity": ["interpolate", ["linear"], ["zoom"], 8, 0.55, 14, 0.2],
        },
      },
      {
        id: "landuse-industrial",
        type: "fill",
        source: OMT,
        "source-layer": "landuse",
        filter: ["match", ["get", "class"], ["industrial", "commercial", "retail"], true, false],
        paint: { "fill-color": "#e6ddd0", "fill-opacity": 0.45 },
      },
      {
        id: "landcover-farmland",
        type: "fill",
        source: OMT,
        "source-layer": "landcover",
        filter: ["==", ["get", "class"], "farm"],
        paint: { "fill-color": C.farmland, "fill-opacity": 0.55 },
      },
      {
        id: "landcover-sand",
        type: "fill",
        source: OMT,
        "source-layer": "landcover",
        filter: ["==", ["get", "class"], "sand"],
        paint: { "fill-color": C.sand, "fill-opacity": 0.5 },
      },
      {
        id: "landcover-grass",
        type: "fill",
        source: OMT,
        "source-layer": "landcover",
        filter: ["==", ["get", "class"], "grass"],
        paint: { "fill-color": C.grass, "fill-opacity": 0.7 },
      },
      {
        id: "park",
        type: "fill",
        source: OMT,
        "source-layer": "park",
        paint: { "fill-color": C.park, "fill-opacity": 0.82 },
      },
      {
        id: "landcover-wood",
        type: "fill",
        source: OMT,
        "source-layer": "landcover",
        filter: ["==", ["get", "class"], "wood"],
        paint: { "fill-color": C.wood, "fill-opacity": 0.72 },
      },
      {
        id: "landuse-cemetery",
        type: "fill",
        source: OMT,
        "source-layer": "landuse",
        filter: ["==", ["get", "class"], "cemetery"],
        paint: { "fill-color": "#cfd9b4", "fill-opacity": 0.75 },
      },
      {
        id: "landuse-pitch",
        type: "fill",
        source: OMT,
        "source-layer": "landuse",
        filter: ["match", ["get", "class"], ["pitch", "track", "stadium"], true, false],
        paint: { "fill-color": C.pitch, "fill-opacity": 0.85 },
      },
      {
        id: "landuse-hospital",
        type: "fill",
        source: OMT,
        "source-layer": "landuse",
        filter: ["==", ["get", "class"], "hospital"],
        paint: { "fill-color": C.accentOchre, "fill-opacity": 0.72 },
      },
      {
        id: "landuse-school",
        type: "fill",
        source: OMT,
        "source-layer": "landuse",
        filter: ["==", ["get", "class"], "school"],
        paint: { "fill-color": C.accentRose, "fill-opacity": 0.55 },
      },
      {
        id: "water",
        type: "fill",
        source: OMT,
        "source-layer": "water",
        filter: ["!=", ["get", "brunnel"], "tunnel"],
        paint: { "fill-color": C.water },
      },
      {
        id: "waterway",
        type: "line",
        source: OMT,
        "source-layer": "waterway",
        filter: ["!=", ["get", "brunnel"], "tunnel"],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": C.waterway,
          "line-width": ["interpolate", ["exponential", 1.3], ["zoom"], 8, 0.6, 14, 2.2, 18, 8],
        },
      },
      {
        id: "aeroway",
        type: "fill",
        source: OMT,
        "source-layer": "aeroway",
        minzoom: 11,
        filter: ["match", ["geometry-type"], ["Polygon", "MultiPolygon"], true, false],
        paint: { "fill-color": "#e4dccf", "fill-opacity": 0.8 },
      },
      {
        id: "rail",
        type: "line",
        source: OMT,
        "source-layer": "transportation",
        filter: [
          "all",
          ["!=", ["get", "brunnel"], "tunnel"],
          ["match", ["get", "class"], ["rail", "transit"], true, false],
        ],
        paint: {
          "line-color": C.rail,
          "line-width": ["interpolate", ["linear"], ["zoom"], 12, 0.4, 16, 1.2],
        },
      },
      {
        id: "road-path",
        type: "line",
        source: OMT,
        "source-layer": "transportation",
        minzoom: 14,
        filter: roadFilter("path", "pedestrian"),
        paint: {
          "line-color": C.path,
          "line-dasharray": [1, 0.8],
          "line-width": ["interpolate", ["exponential", 1.2], ["zoom"], 14, 0.6, 18, 3],
        },
      },
      {
        id: "road-minor-casing",
        type: "line",
        source: OMT,
        "source-layer": "transportation",
        minzoom: 13,
        filter: roadFilter("minor", "service", "track"),
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": C.roadMinorCasing,
          "line-width": ["interpolate", ["exponential", 1.2], ["zoom"], 13, 1.2, 16, 6, 20, 16],
        },
      },
      {
        id: "road-minor",
        type: "line",
        source: OMT,
        "source-layer": "transportation",
        minzoom: 13,
        filter: roadFilter("minor", "service", "track"),
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": C.roadMinor,
          "line-width": ["interpolate", ["exponential", 1.2], ["zoom"], 13, 0.8, 16, 4.2, 20, 12],
        },
      },
      {
        id: "road-mid-casing",
        type: "line",
        source: OMT,
        "source-layer": "transportation",
        filter: roadFilter("secondary", "tertiary"),
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": C.roadMidCasing,
          "line-width": ["interpolate", ["exponential", 1.2], ["zoom"], 8, 1.2, 12, 3, 16, 10, 20, 22],
        },
      },
      {
        id: "road-mid",
        type: "line",
        source: OMT,
        "source-layer": "transportation",
        filter: roadFilter("secondary", "tertiary"),
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": C.roadMid,
          "line-width": ["interpolate", ["exponential", 1.2], ["zoom"], 8, 0.6, 12, 1.8, 16, 7, 20, 16],
        },
      },
      {
        id: "road-major-casing",
        type: "line",
        source: OMT,
        "source-layer": "transportation",
        filter: roadFilter("motorway", "trunk", "primary"),
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": C.roadMajorCasing,
          "line-width": ["interpolate", ["exponential", 1.2], ["zoom"], 6, 1, 10, 2.4, 14, 8, 20, 26],
        },
      },
      {
        id: "road-major",
        type: "line",
        source: OMT,
        "source-layer": "transportation",
        filter: roadFilter("motorway", "trunk", "primary"),
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": C.roadMajor,
          "line-width": ["interpolate", ["exponential", 1.2], ["zoom"], 6, 0.5, 10, 1.5, 14, 5.5, 20, 18],
        },
      },
      {
        id: "building",
        type: "fill",
        source: OMT,
        "source-layer": "building",
        minzoom: 12,
        paint: {
          "fill-color": C.building,
          "fill-opacity": ["interpolate", ["linear"], ["zoom"], 12, 0.35, 14, 1],
          "fill-outline-color": C.buildingLine,
        },
      },
      {
        id: "boundary",
        type: "line",
        source: OMT,
        "source-layer": "boundary",
        minzoom: 7,
        filter: ["all", ["==", ["get", "admin_level"], 4], ["!=", ["get", "maritime"], 1]],
        paint: {
          "line-color": C.boundary,
          "line-dasharray": [2, 2],
          "line-width": 0.8,
          "line-opacity": 0.45,
        },
      },
      {
        id: "water-label",
        type: "symbol",
        source: OMT,
        "source-layer": "waterway",
        minzoom: 13,
        filter: ["match", ["geometry-type"], ["LineString", "MultiLineString"], true, false],
        layout: {
          "symbol-placement": "line",
          "text-field": ["coalesce", ["get", "name:es"], ["get", "name"]],
          "text-font": ["Noto Sans Italic"],
          "text-size": 12,
          "text-letter-spacing": 0.12,
        },
        paint: {
          "text-color": "#d7ecec",
          "text-halo-color": C.water,
          "text-halo-width": 1,
        },
      },
      {
        id: "place-neighbourhood",
        type: "symbol",
        source: OMT,
        "source-layer": "place",
        minzoom: 13,
        maxzoom: 16,
        filter: ["match", ["get", "class"], ["suburb", "neighbourhood", "quarter"], true, false],
        layout: {
          "text-field": ["coalesce", ["get", "name:es"], ["get", "name"]],
          "text-font": ["Noto Sans Regular"],
          "text-size": ["interpolate", ["linear"], ["zoom"], 13, 10, 15, 12],
          "text-transform": "uppercase",
          "text-letter-spacing": 0.08,
          "text-max-width": 8,
        },
        paint: {
          "text-color": C.label,
          "text-halo-color": C.labelHalo,
          "text-halo-width": 1.2,
          "text-opacity": 0.7,
        },
      },
    ],
  };
}
