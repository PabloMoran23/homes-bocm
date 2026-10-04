"use client";

import { useEffect, useRef, useState, type ComponentProps } from "react";
import { Map, LngLatBounds, NavigationControl, ScaleControl, Popup, type GeoJSONSource, type MapMouseEvent } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { FeatureCollection, Feature, Geometry } from "geojson";
import type { MadridUnifiedMap } from "@/components/MadridUnifiedMap";
import { homesMasterplanStyle } from "@/lib/map-masterplan-style";
import { ensureMaplibreWorker } from "@/lib/maplibre-worker";
import { attachMasterplanStipple } from "@/lib/map-stipple";
import { HOMES_MAP_MIN_ZOOM, HOMES_MAP_MAX_ZOOM } from "@/lib/map-tiles";
import { featureLayerStyle, featurePointStyle, featurePopupHtml } from "@/lib/sector-geo";
import { expedienteGrupoKeyFromVariant } from "@/lib/madrid-expediente";
import { portalProyectoPopupHtml, type CmPortalProyectoProps } from "@/lib/cm-portal-geo";
import { ubicacionMapPopupHtml } from "@/lib/ubicacion-map-popup";
import { actuacionDesdeMapProps, type UbicacionMapProperties } from "@/lib/ubicacion";
import { clasificarLicenciaMapaDesdeActuacion } from "@/lib/licencia-mapa";
import { LICENCIA_MAPA_CONFIG } from "@/lib/licencia-mapa-config";
import { SIGMA_OBRA_ICON_CONFIG, resolveSigmaObraIconKey } from "@/lib/sigma-classification-icon";
import { sigmaFichaGrupoFromSlug } from "@/lib/sigma-ficha-path";
import { projectIconAnchor, raisedProjectIconSvg, raisedMapIconSvg, approximateProjectIconSvg } from "@/lib/map-raised-project-icon";
import { uncoveredExplorationHints } from "@/lib/map-municipality-placement";

type Props = ComponentProps<typeof MadridUnifiedMap>;
const PITCH = 45;
const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };
const HIT_LAYERS = ["portal-approx-pin","portal-explore-hint","sigma-pin", "portal-polygon-pin", "sigma-fill", "sigma-point", "portal-fill", "portal-point", "licencias-point", "portal-cluster", "licencias-cluster"];

function collection(features: Feature[]): FeatureCollection {
  return { type: "FeatureCollection", features };
}

function dataBounds(data: FeatureCollection): LngLatBounds | null {
  const bounds = new LngLatBounds();
  const visit = (coordinates: unknown): void => {
    if (!Array.isArray(coordinates)) return;
    if (typeof coordinates[0] === "number" && typeof coordinates[1] === "number") {
      if (coordinates.slice(0, 2).every(Number.isFinite)) bounds.extend([coordinates[0], coordinates[1]]);
    } else coordinates.forEach(visit);
  };
  for (const f of data.features) {
    if (f.geometry && "coordinates" in f.geometry) visit(f.geometry.coordinates);
  }
  return bounds.isEmpty() ? null : bounds;
}

/** Native camera: the basemap and every feature share the same perspective. */
export function PerspectiveMapCanvas(props: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<Map | null>(null);
  const latest = useRef(props);
  useEffect(() => { latest.current = props; }, [props]);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const initialFitDone = useRef(false);
  const frameToken = useRef<number | null>(null);
  const interaction = useRef(0);

  useEffect(() => {
    if (!container.current) return;
    ensureMaplibreWorker();
    const initial = latest.current;
    let map: Map;
    try {
      map = new Map({
        container: container.current,
        style: homesMasterplanStyle(),
        center: initial.mapScope === "cm" ? [-3.65, 40.45] : [-3.703, 40.42],
        zoom: initial.mapScope === "cm" ? 8 : initial.initialView === "explore" ? 11 : 10,
        pitch: PITCH,
        minPitch: PITCH,
        maxPitch: PITCH,
        minZoom: HOMES_MAP_MIN_ZOOM,
        maxZoom: HOMES_MAP_MAX_ZOOM,
        attributionControl: false,
        dragRotate: false,
        touchPitch: false,
        renderWorldCopies: false,
      });
    } catch {
      queueMicrotask(() => setError("No se ha podido iniciar el mapa. Prueba a recargar la página."));
      return;
    }
    mapRef.current = map;
    map.touchZoomRotate.disableRotation();
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new ScaleControl({ unit: "metric" }), "bottom-left");
    attachMasterplanStipple(map);
    const hoverPopup = new Popup({ closeButton: false, closeOnClick: false, maxWidth: "380px", className: "homes-map-popup" });
    let pinnedPopup: Popup | null = null;
    let hoverKey = "";

    const htmlFor = (feature: Feature, layer: string): string => {
      if (layer === "portal-explore-hint") return '<div class="text-xs font-medium text-slate-700">Acércate para explorar esta zona</div>';
      if (layer.startsWith("sigma")) return featurePopupHtml(feature.properties ?? undefined, latest.current.sigmaPopupOptions ?? undefined);
      if (layer.startsWith("licencias")) return ubicacionMapPopupHtml(feature.properties as UbicacionMapProperties);
      return portalProyectoPopupHtml(feature.properties as CmPortalProyectoProps);
    };
    const hits = (event: MapMouseEvent) => map.queryRenderedFeatures(event.point, { layers: HIT_LAYERS.filter(id => !!map.getLayer(id)) });
    const click = async (event: MapMouseEvent) => {
      const feature = hits(event)[0];
      hoverPopup.remove();
      pinnedPopup?.remove();
      if (!feature) {
        if (latest.current.sigmaCardSelection) latest.current.onSelectSigmaExpediente?.(null);
        latest.current.onSelectPortalProject?.(null);
        latest.current.onSelectLicense?.(null);
        return;
      }
      const layer = feature.layer.id;
      if (layer === "portal-explore-hint" && feature.geometry.type === "Point") {
        interaction.current += 1;
        map.easeTo({ center: feature.geometry.coordinates as [number, number], zoom: Math.min(map.getZoom() + 2, 18), duration: 500 });
      } else if (layer.endsWith("cluster") && feature.geometry.type === "Point") {
        const source = map.getSource(feature.source) as GeoJSONSource;
        const zoom = await source.getClusterExpansionZoom(Number(feature.properties.cluster_id));
        if (mapRef.current !== map) return;
        interaction.current += 1;
        map.easeTo({ center: feature.geometry.coordinates as [number, number], zoom, duration: 450 });
      } else if (layer === "licencias-point" && latest.current.onSelectLicense) {
        latest.current.onSelectLicense(feature.properties as UbicacionMapProperties);
      } else if ((layer === "portal-point" || layer === "portal-polygon-pin" || layer === "portal-approx-pin") && latest.current.onSelectPortalProject) {
        latest.current.onSelectPortalProject(feature.properties as CmPortalProyectoProps);
      } else if (layer === "portal-fill" && latest.current.onSelectPortalProject) {
        return;
      } else if (layer.startsWith("sigma") && latest.current.sigmaCardSelection) {
        if (layer !== "sigma-pin") return;
        const key = expedienteGrupoKeyFromVariant(String(feature.properties.EXP_TX_NUMERO || ""));
        if (key) latest.current.onSelectSigmaExpediente?.(key);
      } else {
        pinnedPopup = new Popup({ maxWidth: "380px", className: "homes-map-popup" })
          .setLngLat(event.lngLat).setHTML(htmlFor(feature, layer)).addTo(map);
      }
    };
    const hover = (event: MapMouseEvent) => {
      const feature = hits(event)[0];
      map.getCanvas().style.cursor = feature ? "pointer" : "";
      if (!feature || feature.layer.id.endsWith("cluster") || (feature.layer.id.startsWith("sigma") && latest.current.sigmaCardSelection) || (feature.layer.id.startsWith("portal") && feature.layer.id !== "portal-explore-hint" && latest.current.onSelectPortalProject) || (feature.layer.id.startsWith("licencias") && latest.current.onSelectLicense)) {
        hoverPopup.remove();
        hoverKey = "";
        return;
      }
      const key = `${feature.layer.id}:${feature.geometry.type === "Point" ? feature.geometry.coordinates.join(",") : feature.id}`;
      if (key !== hoverKey) {
        hoverKey = key;
        hoverPopup.setLngLat(event.lngLat).setHTML(htmlFor(feature, feature.layer.id)).addTo(map);
      }
    };
    const report = () => {
      const b = map.getBounds();
      const dx = (b.getEast() - b.getWest()) * 0.08;
      const dy = (b.getNorth() - b.getSouth()) * 0.08;
      latest.current.onBoundsChange?.({ west: b.getWest() - dx, east: b.getEast() + dx, south: b.getSouth() - dy, north: b.getNorth() + dy, zoom: map.getZoom() + 1, cameraToken: frameToken.current, interaction: interaction.current });
    };
    map.once("load", () => {
      for (const key of Object.keys(SIGMA_OBRA_ICON_CONFIG) as Array<keyof typeof SIGMA_OBRA_ICON_CONFIG>) {
        const image = new Image();
        image.onload = () => {
          if (mapRef.current === map && !map.hasImage(`project-${key}`)) map.addImage(`project-${key}`, image, { pixelRatio: 2 });
        };
        image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(raisedProjectIconSvg(key))}`;
        const approximateImage = new Image();
        approximateImage.onload = () => { if (mapRef.current === map && !map.hasImage(`approx-${key}`)) map.addImage(`approx-${key}`, approximateImage, { pixelRatio: 2 }); };
        approximateImage.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(approximateProjectIconSvg(key))}`;
      }
      for (const [key, config] of Object.entries(LICENCIA_MAPA_CONFIG)) {
        const image = new Image();
        image.onload = () => { if (mapRef.current === map && !map.hasImage(`license-${key}`)) map.addImage(`license-${key}`, image, { pixelRatio: 2 }); };
        image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(raisedMapIconSvg(config))}`;
      }
      for (const id of ["sigma", "portal-polygons"]) {
        map.addSource(id, { type: "geojson", data: EMPTY });
        const prefix = id === "sigma" ? "sigma" : "portal";
        map.addLayer({ id: `${prefix}-fill`, type: "fill", source: id, filter: ["==", ["geometry-type"], "Polygon"], paint: { "fill-color": ["get", "_fill"], "fill-opacity": ["get", "_opacity"] } });
        map.addLayer({ id: `${prefix}-line`, type: "line", source: id, filter: ["!=", ["geometry-type"], "Point"], paint: { "line-color": ["get", "_color"], "line-width": ["get", "_weight"] } });
      }
      map.addLayer({ id: "sigma-point", type: "circle", source: "sigma", filter: ["==", ["geometry-type"], "Point"], paint: { "circle-radius": ["get", "_radius"], "circle-color": ["get", "_fill"], "circle-stroke-color": ["get", "_color"], "circle-stroke-width": 1.5 } });
      for (const id of ["licencias", "portal"]) {
        map.addSource(id, { type: "geojson", data: EMPTY, cluster: true, clusterRadius: 48, clusterMaxZoom: window.innerWidth < 768 ? 12 : id === "portal" ? 14 : 15 });
        map.addLayer({ id: `${id}-cluster`, type: "circle", source: id, filter: ["has", "point_count"], paint: { "circle-radius": ["step", ["get", "point_count"], 17, 100, 22, 1000, 27], "circle-color": "#1f4f53", "circle-stroke-width": 3, "circle-stroke-color": "#f7f3eb" } });
        map.addLayer({ id: `${id}-count`, type: "symbol", source: id, filter: ["has", "point_count"], layout: { "text-field": ["get", "point_count_abbreviated"], "text-font": ["Noto Sans Regular"], "text-size": 12 }, paint: { "text-color": "#fff" } });
        map.addLayer({ id: `${id}-point`, type: "circle", source: id, filter: ["!", ["has", "point_count"]], paint: { "circle-radius": ["case", ["get", "_highlight"], 10, 7], "circle-color": ["get", "_fill"], "circle-stroke-color": "#fff", "circle-stroke-width": 2 } });
      }
      for (const id of ["sigma-pins", "portal-polygon-pins"]) {
        map.addSource(id, { type: "geojson", data: EMPTY });
        map.addLayer({ id: id === "sigma-pins" ? "sigma-pin" : "portal-polygon-pin", type: "symbol", source: id,
          layout: { "icon-image": ["get", "_icon"], "icon-anchor": "bottom", "icon-offset": [0, 6], "icon-size": ["case", ["get", "_highlight"], 1.15, 1], "icon-pitch-alignment": "viewport", "icon-rotation-alignment": "viewport", "icon-allow-overlap": true },
        });
      }
      // Project points use the same upright badges as polygon projects.
      map.removeLayer("portal-point");
      map.addLayer({ id: "portal-point", type: "symbol", source: "portal", filter: ["!", ["has", "point_count"]],
        layout: { "icon-image": ["get", "_icon"], "icon-anchor": "bottom", "icon-offset": [0, 6], "icon-pitch-alignment": "viewport", "icon-rotation-alignment": "viewport", "icon-allow-overlap": true },
      });
      map.removeLayer("licencias-point");
      map.addLayer({ id: "licencias-point", type: "symbol", source: "licencias", filter: ["!", ["has", "point_count"]],
        layout: { "icon-image": ["get", "_icon"], "icon-anchor": "bottom", "icon-offset": [0, 6], "icon-size": ["case", ["get", "_highlight"], 1.15, 1], "icon-pitch-alignment": "viewport", "icon-rotation-alignment": "viewport", "icon-allow-overlap": true },
      });
      map.setLayoutProperty("sigma-point", "visibility", "none");
      map.addSource("portal-hints", { type: "geojson", data: EMPTY });
      map.addLayer({ id: "portal-explore-hint", type: "circle", source: "portal-hints", maxzoom: 16.5,
        paint: { "circle-radius": 4.5, "circle-color": "#d84a3e", "circle-stroke-color": "#fff", "circle-stroke-width": 1.5, "circle-opacity": .95 },
      });
      map.addLayer({ id: "portal-explore-label", type: "symbol", source: "portal-hints", maxzoom: 14,
        layout: { "text-field": "Explorar zona", "text-font": ["Noto Sans Regular"], "text-size": 10, "text-offset": [0,1], "text-anchor": "top" },
        paint: { "text-color": "#9b352d", "text-halo-color": "#fff", "text-halo-width": 2 },
      });
      map.addSource("portal-approx", { type: "geojson", data: EMPTY });
      map.addLayer({ id: "portal-approx-pin", type: "symbol", source: "portal-approx",
        layout: { "icon-image": ["get", "_icon"], "icon-anchor": "bottom", "icon-offset": [0,6], "icon-size": ["case", ["get", "_highlight"], 1.15, 1], "icon-pitch-alignment": "viewport", "icon-rotation-alignment": "viewport", "icon-allow-overlap": true },
        paint: { "icon-opacity": .9 },
      });
      map.addSource("municipality-boundary", { type: "geojson", data: EMPTY });
      map.addLayer({ id: "municipality-boundary", type: "line", source: "municipality-boundary", paint: { "line-color": "#4a7578", "line-width": 1, "line-opacity": .45, "line-dasharray": [3,3] } });
      setReady(true);
      report();
    });
    map.on("click", click);
    map.on("mousemove", hover);
    map.on("movestart", (event) => {
      if (event.originalEvent) interaction.current += 1;
      hoverPopup.remove(); hoverKey = "";
    });
    map.on("moveend", report);
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      hoverPopup.remove();
      pinnedPopup?.remove();
      mapRef.current = null;
      map.remove();
      initialFitDone.current = false;
      frameToken.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const visibleProjects = [...(props.portalGeojson?.features ?? []), ...(props.portalPolygonGeojson?.features ?? []), ...(props.portalApproxGeojson?.features ?? [])];
    const b = map.getBounds();
    const hintBounds = { west: b.getWest(), east: b.getEast(), south: b.getSouth(), north: b.getNorth() };
    const hints = props.showPortal && props.showExplorationHints && map.getZoom() < 16.5
      ? uncoveredExplorationHints(hintBounds, visibleProjects, props.municipalityBoundary ?? null) : EMPTY;
    (map.getSource("portal-hints") as GeoJSONSource).setData(hints as FeatureCollection);
    (map.getSource("municipality-boundary") as GeoJSONSource).setData(props.municipalityBoundary ? collection([{ type: "Feature", geometry: props.municipalityBoundary, properties: {} }]) : EMPTY);
    const iconForProject = (id: string, fallback?: Pick<CmPortalProyectoProps, "tipoObra" | "categoriaProyecto">) => {
      const group = expedienteGrupoKeyFromVariant(/^\d+-\d+-\d+$/.test(id) ? sigmaFichaGrupoFromSlug(id) : id);
      return resolveSigmaObraIconKey(props.sigmaClassificationIndex?.[group] ?? (fallback ? { tipoObra: fallback.tipoObra ?? null, categoriaProyecto: fallback.categoriaProyecto ?? null } : undefined));
    };
    const visual = { zoom: map.getZoom() + 1, containerWidth: map.getContainer().clientWidth, containerHeight: map.getContainer().clientHeight };
    const sigma = collection((props.showSigma !== false ? props.sigmaGeojson?.features ?? [] : []).filter(f => f.geometry).map((f, id) => {
      const style = f.geometry?.type === "Point" ? featurePointStyle(f.properties, visual) : featureLayerStyle(f.properties, visual);
      const selected = !!props.selectedSigmaExpediente && expedienteGrupoKeyFromVariant(String(f.properties?.EXP_TX_NUMERO || "")) === props.selectedSigmaExpediente;
      return { type: "Feature", id, geometry: f.geometry as Geometry, properties: { ...f.properties, _color: style.color, _fill: style.fillColor, _opacity: selected ? 0.5 : style.fillOpacity ?? 0.28, _weight: Number(style.weight ?? 2) + (selected ? 2 : 0), _radius: Number(style.radius ?? 5) + (selected ? 2 : 0) } };
    }));
    const polygons = collection((props.showPortal ? props.portalPolygonGeojson?.features ?? [] : []).filter(f => f.geometry.type === "Polygon" || f.geometry.type === "MultiPolygon").map((f, id) => ({ ...f, id, geometry: f.geometry as Geometry, properties: { ...f.properties, _color: f.properties.investigado ? "#9a3412" : "#1f4f53", _fill: f.properties.investigado ? "#ea580c" : "#1f4f53", _opacity: f.properties.investigado ? 0.45 : 0.28, _weight: f.properties.investigado ? 3 : 2 } })));
    const licencias = collection((props.showUbicaciones !== false ? props.ubicacionesGeojson?.features ?? [] : []).map((f, id) => ({ ...f, id, properties: { ...f.properties, _fill: LICENCIA_MAPA_CONFIG[clasificarLicenciaMapaDesdeActuacion(actuacionDesdeMapProps(f.properties))].bg, _icon: `license-${clasificarLicenciaMapaDesdeActuacion(actuacionDesdeMapProps(f.properties))}`, _highlight: f.properties.ndp === props.highlightNdp || f.properties.ndp === props.selectedLicenseNdp } })) as Feature[]);
    const portal = collection((props.showPortal ? props.portalGeojson?.features ?? [] : []).filter(f => f.geometry.type === "Point" && f.properties.coordSource !== "municipio_centroid_jitter").map((f, id) => ({ ...f, id, geometry: f.geometry as Geometry, properties: { ...f.properties, _fill: "#7c3aed", _highlight: f.properties.id === props.selectedPortalProjectId, _icon: `project-${iconForProject(f.properties.id, f.properties)}` } })));
    const approximate = collection((props.showPortal ? props.portalApproxGeojson?.features ?? [] : []).map((f, id) => ({ ...f, id, geometry: f.geometry as Geometry, properties: { ...f.properties, _icon: `approx-${iconForProject(f.properties.id, f.properties)}`, _highlight: f.properties.id === props.selectedPortalProjectId } })));
    (map.getSource("portal-approx") as GeoJSONSource).setData(approximate);
    for (const [id, data] of [["sigma", sigma], ["portal-polygons", polygons], ["licencias", licencias], ["portal", portal]] as const) (map.getSource(id) as GeoJSONSource).setData(data);

    const pins = (data: FeatureCollection, sigmaPins: boolean): FeatureCollection => {
      const groups = new Set<string>();
      return collection(data.features.flatMap(feature => {
        const p = feature.properties ?? {};
        const group = sigmaPins ? expedienteGrupoKeyFromVariant(String(p.EXP_TX_NUMERO || "")) : String(p.id || "");
        if (group && groups.has(group)) return [];
        const anchor = projectIconAnchor(feature.geometry);
        if (!anchor) return [];
        if (group) groups.add(group);
        const icon = iconForProject(group, p);
        return [{ ...feature, geometry: { type: "Point" as const, coordinates: anchor }, properties: { ...p, _icon: `project-${icon}`, _highlight: sigmaPins ? !!props.selectedSigmaExpediente && group === props.selectedSigmaExpediente : group === props.selectedPortalProjectId } }];
      }));
    };
    (map.getSource("sigma-pins") as GeoJSONSource).setData(pins(sigma, true));
    (map.getSource("portal-polygon-pins") as GeoJSONSource).setData(pins(polygons, false));

    if (!initialFitDone.current && !props.focusFrame) {
      // Leaflet's zoom is one level above the native 512px vector tile camera.
      if (props.fitToData !== false) {
        const bounds = dataBounds(collection([...sigma.features, ...polygons.features, ...licencias.features, ...portal.features]));
        if (bounds) {
          map.fitBounds(bounds, { padding: 48, maxZoom: 13, duration: 0 });
          initialFitDone.current = true;
        }
      } else {
        if (props.mapScope === "cm") map.fitBounds([[-4.85, 39.85], [-3.15, 41.15]], { padding: 24, maxZoom: 8, duration: 0 });
        initialFitDone.current = true;
      }
    }
  }, [ready, props.showExplorationHints, props.municipalityBoundary, props.portalApproxGeojson, props.portalHints, props.sigmaClassificationIndex, props.sigmaGeojson, props.portalGeojson, props.portalPolygonGeojson, props.ubicacionesGeojson, props.showSigma, props.showPortal, props.showUbicaciones, props.highlightNdp, props.selectedSigmaExpediente, props.selectedPortalProjectId, props.selectedLicenseNdp, props.fitToData, props.mapScope, props.focusFrame]);

  useEffect(() => {
    const map = mapRef.current;
    const frame = props.focusFrame;
    if (!map || !ready || !frame || frameToken.current === frame.token) return;
    if (![frame.west, frame.south, frame.east, frame.north].every(Number.isFinite)) return;
    frameToken.current = frame.token;
    interaction.current = 0;
    initialFitDone.current = true;
    let { west, south, east, north } = frame;
    if (!frame.tight) {
      if (east - west < 0.012) { const mid = (east + west) / 2; west = mid - 0.01; east = mid + 0.01; }
      if (north - south < 0.008) { const mid = (north + south) / 2; south = mid - 0.006; north = mid + 0.006; }
    }
    if (frame.zoom != null) map.easeTo({ center: [(west + east) / 2, (south + north) / 2], zoom: frame.zoom, duration: 700 });
    else map.fitBounds([[west, south], [east, north]], { padding: frame.padding ?? 56, maxZoom: frame.maxZoom ?? (frame.tight ? 17 : 16), duration: 700 });
  }, [ready, props.focusFrame]);


  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !props.highlightNdp) return;
    const feature = props.ubicacionesGeojson?.features.find(f => f.properties.ndp === props.highlightNdp);
    if (feature) map.flyTo({ center: feature.geometry.coordinates, zoom: 16, duration: 550 });
  }, [ready, props.highlightNdp, props.ubicacionesGeojson]);

  return <div className="homes-perspective-map relative h-full w-full"><div ref={container} className="h-full w-full" />{error ? <p role="alert" className="absolute inset-0 flex items-center justify-center bg-[#f3eee4] p-6 text-sm">{error}</p> : null}</div>;
}
